"""Synthetic file controls, not actual Tauri build/package proof."""
import json
import os
import logging
import traceback
from unittest.mock import patch
import pilot_installer_scan as core
import contextlib
import io
import tempfile
from pathlib import Path
import unittest
try:
 import pilot_asset_provenance as assets
except ImportError:
 assets = None

class AssetTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(assets, 'asset policy missing')
  self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
  self.root = Path(self.temp.name)
  (self.root / 'settings.js').write_text('Help: OPENAI_API_KEY; no credential value')
  self.inventory = {'settings.js': assets.file_digest(self.root / 'settings.js')[1]}
 def test_public_help_label_passes_asset_policy(self):
  snapshot = assets.capture_assets(self.root, self.inventory)
  assets.verify_unchanged(snapshot)
 def test_actual_key_in_asset_fails(self):
  secret = b'synthetic-actual-key-canary-874ab'
  (self.root / 'settings.js').write_bytes(secret)
  self.inventory['settings.js'] = assets.file_digest(self.root / 'settings.js')[1]
  with self.assertRaisesRegex(assets.PolicyError, 'asset-known-secret'):
   assets.capture_assets(self.root, self.inventory, known_secrets=(secret,))
 def test_extra_changed_and_symlink_assets_fail(self):
  snapshot = assets.capture_assets(self.root, self.inventory)
  (self.root / 'extra.js').write_text('extra')
  with self.assertRaises(assets.PolicyError): assets.verify_unchanged(snapshot)
  (self.root / 'extra.js').unlink(); (self.root / 'settings.js').write_text('changed')
  with self.assertRaises(assets.PolicyError): assets.verify_unchanged(snapshot)
 def test_fresh_codegen_directory_rejects_stale_cache(self):
  output = self.root / 'out'; output.mkdir(); (output / 'old.br').write_bytes(b'stale')
  with self.assertRaisesRegex(assets.PolicyError, 'asset-output-not-fresh'):
   assets.begin_codegen(output)
 def test_generated_inventory_and_emitted_packaged_hash_chain(self):
  source = self.root / 'source'; source.mkdir()
  (self.root / 'settings.js').rename(source / 'settings.js')
  inputs = assets.capture_assets(source, self.inventory)
  output = self.root / 'fresh'; output.mkdir(); token = assets.begin_codegen(output)
  (output / 'asset.br').write_bytes(b'explicit-synthetic-encoded-output')
  generated = {'asset.br': assets.file_digest(output / 'asset.br')[1]}
  op = self.root / 'operator'; op.write_bytes(b'synthetic-emitted-native')
  digest = assets.file_digest(op)[1]
  result = assets.finish_codegen(inputs, token, generated, emitted_operator=op,
                                 emitted_sha256=digest, packaged_sha256=digest)
  self.assertEqual(result.coverage, 'synthetic-helper-chain-only')
  with self.assertRaisesRegex(assets.PolicyError, 'asset-operator-binding'):
   assets.finish_codegen(inputs, token, generated, emitted_operator=op,
                         emitted_sha256=digest, packaged_sha256='0'*64)

 def test_config_toolchain_codegen_hash_inputs_and_features_are_pinned(self):
  root = self.root / 'contract'; root.mkdir()
  for name in ('Cargo.lock','rust-toolchain.toml','embedded_assets.rs','assets.rs'):
   (root / name).write_bytes(b'explicit-synthetic-reviewed-input')
  (root / 'tauri.conf.json').write_text('{"build":{"frontendDist":"dist"}}')
  pins = {p.name: assets.file_digest(p)[1] for p in root.iterdir()}
  assets.verify_build_contract(root, pins, config_path='tauri.conf.json', frontend_dist='dist', codegen_features=('compression',))
  for features, dist in [((), 'dist'), (('compression',), 'other')]:
   with self.assertRaises(assets.PolicyError):
    assets.verify_build_contract(root, pins, config_path='tauri.conf.json', frontend_dist=dist, codegen_features=features)
 def test_cargo_emitted_output_binding_and_debug_rejection(self):
  op = self.root / 'emitted'; op.write_bytes(b'synthetic-native-output')
  digest = assets.file_digest(op)[1]; log = self.root / 'cargo.json'
  row = {'reason':'compiler-artifact','target':{'name':'selahcue-operator'},'executable':str(op),'profile':{'debug_assertions':False}}
  log.write_text(json.dumps(row)); assets.verify_cargo_output(log, op, digest)
  row['profile']['debug_assertions'] = True; log.write_text(json.dumps(row))
  with self.assertRaisesRegex(assets.PolicyError,'asset-cargo-binding'): assets.verify_cargo_output(log, op, digest)
 def test_symlink_source_and_extra_generated_output_are_rejected(self):
  (self.root / 'settings.js').unlink(); (self.root / 'settings.js').symlink_to(self.root / 'missing')
  with self.assertRaises(assets.PolicyError): assets.capture_assets(self.root, self.inventory)
 def test_secret_bytes_and_fragments_never_appear_in_errors_or_repr(self):
  secret = b'synthetic-private-asset-canary-9823'
  (self.root / 'settings.js').write_bytes(secret)
  self.inventory['settings.js'] = assets.file_digest(self.root / 'settings.js')[1]
  output = io.StringIO()
  with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
   try: assets.capture_assets(self.root, self.inventory, known_secrets=(secret,))
   except assets.PolicyError as error: output.write(str(error))
  for index in range(len(secret)-7): self.assertNotIn(secret[index:index+8].decode(),output.getvalue())

 def test_full_traceback_and_logger_suppress_private_filesystem_context(self):
  target = self.root / 'regular'; target.write_bytes(bytes(1000000))
  private_path = 'synthetic-private-path-canary-2764'
  original = Path.open
  def denied(path, *args, **kwargs):
   if path == target: raise PermissionError(private_path)
   return original(path, *args, **kwargs)
  for call in (lambda: core.scan_component(target), lambda: assets.scan_asset(target)):
   output = io.StringIO(); logger = logging.Logger('isolated-p04-test')
   logger.addHandler(logging.StreamHandler(output))
   with patch.object(Path, 'open', denied):
    try: call()
    except assets.PolicyError as error:
     output.write(''.join(traceback.format_exception(type(error),error,error.__traceback__)))
     logger.exception('public refusal')
   text = output.getvalue(); self.assertIn('component-unreadable',text)
   for index in range(len(private_path)-7): self.assertNotIn(private_path[index:index+8],text)
 def test_known_secret_inventory_size_does_not_add_target_read_passes(self):
  target = self.root / 'read-target'; target.write_bytes(b'clean synthetic public asset')
  original = Path.open
  for call in (lambda values: core.scan_resource(target,known_secrets=values),
               lambda values: assets.scan_asset(target,values)):
   counts = []
   for count in (0,16):
    opened = []
    def counted(path,*args,**kwargs):
     if path == target: opened.append(1)
     return original(path,*args,**kwargs)
    values = tuple(('synthetic-known-inventory-%04d'%i).encode() for i in range(count))
    with patch.object(Path,'open',counted): call(values)
    counts.append(len(opened))
   self.assertEqual(counts[0],counts[1])

 def assert_private_refusal(self,call,private):
  output = io.StringIO(); logger = logging.Logger('p04-final-boundary')
  logger.addHandler(logging.StreamHandler(output))
  try: call()
  except Exception as error:
   self.assertIsInstance(error,assets.PolicyError)
   output.write(''.join(traceback.format_exception(type(error),error,error.__traceback__)))
   logger.exception('public filesystem refusal')
  else: self.fail('expected fixed policy refusal')
  for index in range(len(private)-7): self.assertNotIn(private[index:index+8],output.getvalue())
 def test_metadata_and_source_resolution_boundaries_redact_full_diagnostics(self):
  target = self.root / 'target'; target.write_bytes(bytes(1000000))
  private = 'private-fs-canary-742db986'
  for method, call in [('is_symlink',lambda: core.scan_component(target)),
                       ('is_file',lambda: core.scan_component(target)),
                       ('is_symlink',lambda: core.verify_inventory(self.root,self.inventory)),
                       ('is_dir',lambda: core.verify_inventory(self.root,self.inventory))]:
   with self.subTest(method=method):
    with patch.object(Path,method,side_effect=PermissionError(private)):
     self.assert_private_refusal(call,private)
  for error in (PermissionError(private),RuntimeError(private)):
   for call in (lambda: core.scan_component(target),lambda: assets.scan_asset(target)):
    with patch.object(Path,'resolve',side_effect=error): self.assert_private_refusal(call,private)
 def test_actual_own_locked_directory_refuses_without_private_context(self):
  if hasattr(os,'geteuid') and os.geteuid()==0: self.skipTest('root bypasses permission fixture')
  private = 'private-locked-dir-canary-7ab9'
  locked = self.root / private; locked.mkdir(); target = locked / 'target'
  target.write_bytes(bytes(1000000)); locked.chmod(0)
  try: self.assert_private_refusal(lambda:core.scan_component(target),private)
  finally: locked.chmod(0o700)

 def test_actual_source_resolve_symlink_loop_has_fixed_diagnostics(self):
  private = 'private-resolve-loop-canary-6ed2'
  loop = self.root / private; loop.symlink_to(loop.name)
  self.assert_private_refusal(lambda:core.source_root(str(loop / 'module.py')),private)
 def test_boundary_does_not_hide_programming_runtime_errors(self):
  target = self.root / 'regular'; target.write_bytes(bytes(1000000))
  with patch.object(Path,'is_file',side_effect=RuntimeError('programming-error-control')):
   with self.assertRaisesRegex(RuntimeError,'programming-error-control'): core.scan_component(target)

if __name__ == '__main__': unittest.main()
