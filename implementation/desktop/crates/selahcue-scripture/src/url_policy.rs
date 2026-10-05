//! Which URLs the download path may request (feature `installed`).
//!
//! One rule, applied to the first request and to every redirect hop: HTTPS only. A translation is
//! pinned by SHA-256, so a hostile network could not change the bytes anyway, but a request that
//! starts or ends on plain http still leaks which translation the user is fetching and invites a
//! downgrade, so it is never made.
//!
//! Plain http to a loopback address exists for the crate's own tests (a one-shot local server is
//! the only way to exercise a download without the network). It is not a setting: it needs
//! [`UrlPolicy::allow_loopback_http_for_tests`], whose name is the warning, and that constructor is
//! compiled only when debug assertions are on (tests and dev builds), so a release binary cannot
//! build one: the type's only constructor there is [`UrlPolicy::https_only`]. Even the test policy
//! refuses http to any host that is not literally `127.0.0.1` or `[::1]`, so a test cannot be
//! redirected off the machine.
//!
//! The checks here are on text, before any socket is opened, so a refused URL costs no request.

/// What a URL may look like before the client is allowed to request it. The default is the
/// product policy, [`UrlPolicy::https_only`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct UrlPolicy {
    allow_loopback_http: bool,
}

/// Why a URL was refused. Each variant is a distinct reason so a caller (and a test) can tell
/// "not https" from "garbage".
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum UrlRefusal {
    /// The scheme is not `https` (or, under the test policy, `http` to a loopback address).
    NotHttps { scheme: String },
    /// Not a URL this code is willing to parse: empty, no scheme, no host, whitespace or a control
    /// character.
    Malformed,
    /// The authority carries `user:password@` (or any `@`): never followed, since the text before
    /// the `@` is not the host the reader thinks it is.
    Credentials,
}

impl std::fmt::Display for UrlRefusal {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            UrlRefusal::NotHttps { scheme } => {
                write!(f, "only https URLs are allowed (got '{scheme}')")
            }
            UrlRefusal::Malformed => write!(f, "the URL is not well formed"),
            UrlRefusal::Credentials => write!(f, "a URL with credentials in it is not allowed"),
        }
    }
}

impl std::error::Error for UrlRefusal {}

impl UrlPolicy {
    /// The product policy: `https` and nothing else.
    pub const fn https_only() -> UrlPolicy {
        UrlPolicy {
            allow_loopback_http: false,
        }
    }

    /// **Tests only.** Also allows plain `http` to `127.0.0.1` or `[::1]`, so a test can serve a
    /// download from a local socket. Product code must use [`UrlPolicy::https_only`]. Exists only
    /// when debug assertions are on: a release build has no way to make this policy.
    #[cfg(debug_assertions)]
    #[doc(hidden)]
    pub const fn allow_loopback_http_for_tests() -> UrlPolicy {
        UrlPolicy {
            allow_loopback_http: true,
        }
    }

    /// Whether this policy lets plain http to a loopback address through.
    #[doc(hidden)]
    pub const fn allows_loopback_http(self) -> bool {
        self.allow_loopback_http
    }

    /// `Ok(())` when `url` may be requested under this policy.
    pub fn check(&self, url: &str) -> Result<(), UrlRefusal> {
        if url.is_empty() || url.chars().any(|c| c.is_control() || c.is_whitespace()) {
            return Err(UrlRefusal::Malformed);
        }
        let (scheme, rest) = split_scheme(url).ok_or(UrlRefusal::Malformed)?;
        let authority = authority_of(rest);
        if authority.is_empty() {
            return Err(UrlRefusal::Malformed);
        }
        if authority.contains('@') {
            return Err(UrlRefusal::Credentials);
        }
        let host = host_of(authority).ok_or(UrlRefusal::Malformed)?;
        if host.is_empty() {
            return Err(UrlRefusal::Malformed);
        }
        let scheme = scheme.to_ascii_lowercase();
        match scheme.as_str() {
            "https" => Ok(()),
            "http" if self.allow_loopback_http && is_loopback(host) => Ok(()),
            _ => Err(UrlRefusal::NotHttps { scheme }),
        }
    }
}

/// The absolute URL a redirect `location` names when it is received on a response from `base`,
/// or `None` when it is not one this code follows (empty, or a relative path such as `bsb.tsv.gz`).
/// Absolute URLs, scheme-relative (`//host/path`) and root-relative (`/path`) locations resolve;
/// the result is then run through [`UrlPolicy::check`] like any other URL, so a downgrade to http
/// is refused there and not silently followed.
pub fn resolve_redirect(base: &str, location: &str) -> Option<String> {
    let location = location.trim();
    if location.is_empty() {
        return None;
    }
    let (base_scheme, base_rest) = split_scheme(base)?;
    let authority = authority_of(base_rest);
    if authority.is_empty() {
        return None;
    }
    if let Some(after) = location.strip_prefix("//") {
        return Some(format!("{base_scheme}://{after}"));
    }
    if location.starts_with('/') {
        return Some(format!("{base_scheme}://{authority}{location}"));
    }
    // An absolute URL carries its own scheme; a relative path does not.
    split_scheme(location).map(|_| location.to_string())
}

/// `(scheme, everything after "://")`, or `None` when there is no well-formed scheme.
fn split_scheme(url: &str) -> Option<(&str, &str)> {
    let (scheme, rest) = url.split_once("://")?;
    let mut chars = scheme.chars();
    let first = chars.next()?;
    let valid = first.is_ascii_alphabetic()
        && chars.all(|c| c.is_ascii_alphanumeric() || matches!(c, '+' | '-' | '.'));
    valid.then_some((scheme, rest))
}

/// The authority part: everything up to the first `/`, `?` or `#`.
fn authority_of(rest: &str) -> &str {
    let end = rest.find(['/', '?', '#']).unwrap_or(rest.len());
    &rest[..end]
}

/// The host of an authority, without the port. An IPv6 literal keeps its brackets.
fn host_of(authority: &str) -> Option<&str> {
    if let Some(inner) = authority.strip_prefix('[') {
        let close = inner.find(']')?;
        // `[::1]` plus an optional `:port`; anything else after the bracket is garbage.
        let after = &inner[close + 1..];
        if !(after.is_empty() || after.starts_with(':')) {
            return None;
        }
        return Some(&authority[..close + 2]);
    }
    Some(authority.split(':').next().unwrap_or(authority))
}

/// Literally `127.0.0.1` or `[::1]`. A name such as `localhost` is not trusted: it resolves
/// through the hosts file and the resolver, which a test has no business depending on.
fn is_loopback(host: &str) -> bool {
    matches!(host, "127.0.0.1" | "[::1]")
}

/// `text` with the query string, the fragment and any `user:password@` taken out of every URL in it.
///
/// A signed or tokenised URL (a CDN redirect to `...?token=SECRET`) must never reach an error
/// message: errors travel to the operator UI, to `bible://phase` events, to logs and to bug
/// reports. Any whitespace-separated word containing `://` is cut at its first `?` or `#`, its
/// credentials (the text before an `@` in the authority) are replaced by `REDACTED`, the punctuation
/// that followed the URL (a trailing `:` or `.`) is kept, and everything else is left as it was.
pub fn redact_urls(text: &str) -> String {
    const TAIL: &[char] = &[':', ';', ',', '.', ')', ']', '}', '\'', '"'];
    let mut out = String::with_capacity(text.len());
    for piece in text.split_inclusive(char::is_whitespace) {
        let word_len = piece.trim_end_matches(char::is_whitespace).len();
        let (word, space) = piece.split_at(word_len);
        if word.contains("://") {
            let core_len = word.trim_end_matches(TAIL).len();
            let (core, tail) = word.split_at(core_len);
            let cut = core.find(['?', '#']).unwrap_or(core.len());
            out.push_str(&without_credentials(&core[..cut]));
            out.push_str(tail);
        } else {
            out.push_str(word);
        }
        out.push_str(space);
    }
    out
}

/// `word` with the `user:password@` part of the first URL authority in it replaced by `REDACTED@`.
fn without_credentials(word: &str) -> String {
    let Some(start) = word.find("://").map(|i| i + 3) else {
        return word.to_string();
    };
    let authority_len = word[start..].find('/').unwrap_or(word.len() - start);
    let authority = &word[start..start + authority_len];
    match authority.rfind('@') {
        Some(at) => format!("{}REDACTED@{}", &word[..start], &word[start + at + 1..]),
        None => word.to_string(),
    }
}
