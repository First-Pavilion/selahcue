"""Prefer the existing HTTPS Ubuntu archive on the standard hosted EC2 image."""

from contextlib import contextmanager
import errno
import os
import re
import secrets
import selectors
import stat
import subprocess
import sys
import time
from typing import NamedTuple


EC2 = b"http://us-east-2.ec2.archive.ubuntu.com/ubuntu/\tpriority:1\n"
PUBLIC = b"https://archive.ubuntu.com/ubuntu/\tpriority:2\n"
SECURITY = b"https://security.ubuntu.com/ubuntu/\tpriority:3\n"
AZURE = b"http://azure.archive.ubuntu.com/ubuntu/\tpriority:1\n"
ORIGINAL = EC2 + PUBLIC + SECURITY
PREFERRED = EC2.replace(b":1\n", b":2\n") + PUBLIC.replace(b":2\n", b":1\n") + SECURITY
SOURCE = "ubuntu.sources"
MIRROR = "apt-mirrors.txt"
MIRROR_SOURCE = b"mirror+file:/etc/apt/apt-mirrors.txt"
EXPECTED_PATHS = {
    b"directory": ("Dir/d", b"/"),
    b"etc": ("Dir::Etc/d", b"/etc/apt/"),
    b"sourcelist": ("Dir::Etc::sourcelist/f", b"/etc/apt/sources.list"),
    b"sourceparts": ("Dir::Etc::sourceparts/d", b"/etc/apt/sources.list.d/"),
}


class Skip(Exception):
    """The runner can use its original configuration."""


class GuardFailure(Exception):
    """An operational failure prevents safe completion of the setup."""


def stock_paths(output):
    """Accept only requested assignments for the expected effective APT paths."""
    if not output.endswith(b"\n"):
        return False
    seen = set()
    for line in output[:-1].split(b"\n"):
        match = re.fullmatch(rb"([a-z]+)='([^'\x00]*)'", line)
        if match is None:
            return False
        name, value = match.groups()
        if name in seen:
            return False
        seen.add(name)
        if name == b"rootdir":
            if value not in (b"", b"/"):
                return False
        elif name not in EXPECTED_PATHS or value != EXPECTED_PATHS[name][1]:
            return False
    return EXPECTED_PATHS.keys() <= seen


def query_paths():
    if "APT_CONFIG" in os.environ:
        return False
    # APT applies Binary::<argv[0]> before querying. Use the package consumer's
    # namespace, while executing only the read-only apt-config program.
    query = ["apt-get", "shell", "rootdir", "RootDir"]
    for name, (key, _) in EXPECTED_PATHS.items():
        query.extend((name.decode("ascii"), key))

    deadline = time.monotonic() + 2
    output = bytearray()
    with subprocess.Popen(query, executable="/usr/bin/apt-config", shell=False,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        try:
            with selectors.DefaultSelector() as ready:
                ready.register(process.stdout, selectors.EVENT_READ)
                while time.monotonic() < deadline and ready.select(deadline - time.monotonic()):
                    chunk = os.read(process.stdout.fileno(), min(1024, 8193 - len(output)))
                    if not chunk:
                        break
                    if len(output) + len(chunk) > 8192:
                        raise GuardFailure("configuration query exceeded its output bound")
                    output.extend(chunk)
                else:
                    raise GuardFailure("configuration query timed out")
            if process.wait(timeout=max(0, deadline - time.monotonic())) != 0:
                raise GuardFailure("configuration query failed")
        finally:
            if process.poll() is None:
                process.kill()
    return stock_paths(bytes(output))


def active_reference(contents):
    """Recognize an enabled binary Deb822 stanza with the exact mirror URI."""
    if re.search(rb"[\x00-\x08\x0b-\x1f\x7f]", contents):
        raise Skip("unsupported_sources")
    stanzas = []
    fields = {}
    for line in contents.split(b"\n"):
        if not line:
            if fields:
                stanzas.append(fields)
                fields = {}
            continue
        if line.startswith(b"#"):
            continue
        # Folded fields and duplicate keys are outside the known runner layout.
        name, separator, value = line.partition(b":")
        key = name.lower()
        if not separator or not re.fullmatch(rb"[a-z][a-z0-9-]*", key) or key in fields:
            raise Skip("unsupported_sources")
        fields[key] = value.split()
    if fields:
        stanzas.append(fields)

    active = False
    for fields in stanzas:
        types = fields.get(b"types", [])
        uris = fields.get(b"uris", [])
        suites = fields.get(b"suites", [])
        enabled = fields.get(b"enabled", [b"yes"])
        if (not types or set(types) - {b"deb", b"deb-src"} or len(uris) != 1 or not suites
                or (any(not suite.endswith(b"/") for suite in suites) and not fields.get(b"components"))
                or enabled not in ([b"yes"], [b"no"])):
            raise Skip("unsupported_sources")
        if b"deb" in types and uris == [MIRROR_SOURCE] and enabled == [b"yes"]:
            active = True
    return active


@contextmanager
def open_checked(path, flags, parent=None):
    try:
        fd = os.open(path, flags | os.O_NOFOLLOW, dir_fd=parent)
    except FileNotFoundError as error:
        raise Skip("missing") from error
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            raise Skip("unsafe_layout") from error
        raise
    try:
        yield fd
    finally:
        os.close(fd)


def safe_owner_mode(info, owner):
    return info.st_uid == owner and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)


@contextmanager
def directory(path, owner, parent=None):
    with open_checked(path, os.O_RDONLY | os.O_DIRECTORY, parent) as fd:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or not safe_owner_mode(info, owner):
            raise Skip("unsafe_layout")
        yield fd, (info.st_dev, info.st_ino)


def identity(info):
    return info.st_dev, info.st_ino


def file_attributes(info):
    return info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)


def fingerprint(info):
    # Reads may update atime. Changes to the inode, bytes or other metadata are relevant.
    return (identity(info), info.st_mode, info.st_uid, info.st_gid, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class Observation(NamedTuple):
    data: bytes
    info: os.stat_result

    def unchanged(self, other):
        return self.data == other.data and fingerprint(self.info) == fingerprint(other.info)


def file_observation(parent, name, owner, list_attributes, limit):
    try:
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError as error:
        raise Skip("missing") from error

    def safe(info):
        return (stat.S_ISREG(info.st_mode) and safe_owner_mode(info, owner)
                and (name != MIRROR or info.st_nlink == 1))

    if not safe(before):
        raise Skip("unsafe_layout")
    if before.st_size > limit:
        raise Skip("unsupported_sources" if name == SOURCE else "unknown_mirror")
    with open_checked(name, os.O_RDONLY | os.O_NONBLOCK, parent) as fd:
        info = os.fstat(fd)
        if not safe(info) or fingerprint(before) != fingerprint(info):
            raise GuardFailure("file changed during inspection")
        if list_attributes(fd):
            raise Skip("unsupported_metadata")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit or fingerprint(os.fstat(fd)) != fingerprint(info):
            raise GuardFailure("file changed during inspection")
        return Observation(data, info)


@contextmanager
def observations(root, owner, list_attributes):
    with (directory(root, owner) as (root_fd, root_id),
          directory("etc", owner, root_fd) as (etc_fd, etc_id),
          directory("apt", owner, etc_fd) as (apt_fd, apt_id),
          directory("sources.list.d", owner, apt_fd) as (sources_fd, sources_id)):
        source = file_observation(sources_fd, SOURCE, owner, list_attributes, 64 * 1024)
        mirror = file_observation(apt_fd, MIRROR, owner, list_attributes, 1024)
        yield apt_fd, (root_id, etc_id, apt_id, sources_id), source, mirror


def publish(root, owner, list_attributes, effective_paths, apt_fd, dirs, source, mirror):
    name = ".operator-apt-mirror-" + secrets.token_hex(16)
    temp_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                      0o600, dir_fd=apt_fd)
    staged = True
    temp_id = None
    try:
        temp_id = identity(os.fstat(temp_fd))
        if os.write(temp_fd, PREFERRED) != len(PREFERRED):
            raise GuardFailure("incomplete write")
        uid, gid, mode = file_attributes(mirror.info)
        os.fchown(temp_fd, uid, gid)
        os.fchmod(temp_fd, mode)
        os.fsync(temp_fd)
        expected = os.fstat(temp_fd)
        if list_attributes(temp_fd) or file_attributes(expected) != (uid, gid, mode):
            raise GuardFailure("unsupported staging metadata")

        # Rechecks can detect drift. Rename is atomic for readers, not a compare-and-swap
        # against root. The hosted setup assumes no concurrent privileged APT reconfiguration.
        if not effective_paths():
            raise GuardFailure("effective paths changed")
        with observations(root, owner, list_attributes) as (_, current_dirs, current_source, current_mirror):
            if (current_dirs != dirs or not current_source.unchanged(source)
                    or not current_mirror.unchanged(mirror)
                    or fingerprint(os.stat(name, dir_fd=apt_fd, follow_symlinks=False)) != fingerprint(expected)):
                raise GuardFailure("APT files changed before publication")
        os.replace(name, MIRROR, src_dir_fd=apt_fd, dst_dir_fd=apt_fd)
        staged = False

        with observations(root, owner, list_attributes) as (_, final_dirs, final_source, final):
            info = final.info
            if (final_dirs != dirs or not final_source.unchanged(source)
                    or final.data != PREFERRED or identity(info) != temp_id
                    or file_attributes(info) != (uid, gid, mode)):
                raise GuardFailure("APT mirror readback failed")
    except Skip as error:
        raise GuardFailure("APT configuration changed during publication") from error
    finally:
        try:
            if staged:
                info = os.stat(name, dir_fd=apt_fd, follow_symlinks=False)
                if temp_id is None or identity(info) == temp_id:
                    os.unlink(name, dir_fd=apt_fd)
        except FileNotFoundError:
            pass
        finally:
            os.close(temp_fd)


def configure(root, owner, list_attributes, effective_paths):
    if not effective_paths():
        return "unsupported_configuration"
    try:
        with observations(root, owner, list_attributes) as (apt_fd, dirs, source, mirror):
            if not active_reference(source.data):
                return "inactive_sources"
            if mirror.data == PREFERRED:
                return "already_preferred"
            if mirror.data == AZURE + PUBLIC + SECURITY:
                return "azure"
            if mirror.data != ORIGINAL:
                return "unknown_mirror"
            publish(root, owner, list_attributes, effective_paths, apt_fd, dirs, source, mirror)
    except Skip as skip:
        return str(skip)
    return "promoted"


def report(root, owner, list_attributes, effective_paths):
    try:
        decision = configure(root, owner, list_attributes, effective_paths)
    except (GuardFailure, OSError, subprocess.SubprocessError):
        print("operator APT mirror: failed", file=sys.stderr)
        return 1
    print(f"operator APT mirror: {decision}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 1 or os.geteuid() != 0:
        sys.exit("operator APT mirror: invalid invocation")
    sys.exit(report("/", 0, os.listxattr, query_paths))
