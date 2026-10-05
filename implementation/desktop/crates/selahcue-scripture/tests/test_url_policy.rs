//! Which URLs the download path may request (feature `installed`).
//!
//! The rule is HTTPS only, for the first request and for every redirect hop. Plain http to a
//! loopback address exists for tests alone, behind a constructor whose name says so. Each refusal
//! below names the specific refusal it must reach, so a generic "refused" cannot satisfy two
//! different cases.
#![cfg(feature = "installed")]
#![allow(clippy::unwrap_used)]

use selahcue_scripture::url_policy::{resolve_redirect, UrlPolicy, UrlRefusal};

fn product() -> UrlPolicy {
    UrlPolicy::https_only()
}

fn loopback_tests() -> UrlPolicy {
    UrlPolicy::allow_loopback_http_for_tests()
}

#[test]
fn https_is_allowed_by_both_policies() {
    for p in [product(), loopback_tests()] {
        assert_eq!(p.check("https://example.org/bsb.tsv.gz"), Ok(()));
        assert_eq!(p.check("HTTPS://Example.org:8443/a/b?c=d#e"), Ok(()));
        assert_eq!(p.check("https://[2001:db8::1]/x"), Ok(()));
    }
}

#[test]
fn plain_http_is_refused_by_the_product_policy_even_on_loopback() {
    for url in [
        "http://example.org/a",
        "http://127.0.0.1:9000/a",
        "http://[::1]:9000/a",
        "http://localhost/a",
    ] {
        assert!(
            matches!(product().check(url), Err(UrlRefusal::NotHttps { .. })),
            "{url} must be refused as not https"
        );
    }
}

#[test]
fn the_test_policy_allows_http_to_a_loopback_address_and_nothing_else() {
    let p = loopback_tests();
    assert_eq!(p.check("http://127.0.0.1:9000/a"), Ok(()));
    assert_eq!(p.check("http://127.0.0.1/a"), Ok(()));
    assert_eq!(p.check("http://[::1]:9000/a"), Ok(()));
    // The positive control for the refusals below: the same shape, but a real host.
    for url in [
        "http://example.org/a",
        "http://127.0.0.1.example.org/a",
        "http://localhost.example.org/a",
        "http://10.0.0.1/a",
        "http://0.0.0.0/a",
    ] {
        assert!(
            matches!(p.check(url), Err(UrlRefusal::NotHttps { .. })),
            "{url} is not loopback and must be refused even by the test policy"
        );
    }
}

#[test]
fn other_schemes_are_refused_by_both_policies() {
    for p in [product(), loopback_tests()] {
        for url in [
            "ftp://example.org/a",
            "file:///etc/passwd",
            "ws://127.0.0.1/a",
            "javascript:alert(1)//",
            "gopher://example.org/",
        ] {
            let got = p.check(url);
            assert!(
                matches!(
                    got,
                    Err(UrlRefusal::NotHttps { .. }) | Err(UrlRefusal::Malformed)
                ),
                "{url} must be refused, got {got:?}"
            );
        }
    }
}

#[test]
fn credentials_in_the_url_are_refused() {
    for p in [product(), loopback_tests()] {
        assert_eq!(
            p.check("https://user:pw@example.org/a"),
            Err(UrlRefusal::Credentials)
        );
        assert_eq!(
            p.check("https://example.org@evil.example/a"),
            Err(UrlRefusal::Credentials)
        );
    }
}

#[test]
fn a_malformed_url_is_refused_not_guessed_at() {
    for url in [
        "",
        "example.org/a",
        "https://",
        "https:///a",
        "https://exa mple.org/a",
        "https://example.org/a\nHost: evil",
        "https://example.org/\u{0}",
    ] {
        assert_eq!(
            product().check(url),
            Err(UrlRefusal::Malformed),
            "{url:?} must be malformed"
        );
    }
}

#[test]
fn redirect_locations_resolve_against_the_current_url() {
    let base = "https://cdn.example.org/translations/bsb.tsv.gz";
    assert_eq!(
        resolve_redirect(base, "https://other.example.org/x").as_deref(),
        Some("https://other.example.org/x")
    );
    assert_eq!(
        resolve_redirect(base, "/moved/bsb.tsv.gz").as_deref(),
        Some("https://cdn.example.org/moved/bsb.tsv.gz")
    );
    assert_eq!(
        resolve_redirect(base, "//mirror.example.org/bsb.tsv.gz").as_deref(),
        Some("https://mirror.example.org/bsb.tsv.gz")
    );
    // A downgrade stays visible so the policy can refuse it.
    assert_eq!(
        resolve_redirect(base, "http://cdn.example.org/bsb.tsv.gz").as_deref(),
        Some("http://cdn.example.org/bsb.tsv.gz")
    );
    // Relative-path and empty locations are not followed.
    assert_eq!(resolve_redirect(base, "bsb.tsv.gz"), None);
    assert_eq!(resolve_redirect(base, ""), None);
    assert_eq!(resolve_redirect("not a url", "/x"), None);
}

#[test]
fn a_redirect_from_https_to_http_is_refused_by_the_policy() {
    let base = "https://cdn.example.org/bsb.tsv.gz";
    let next = resolve_redirect(base, "http://cdn.example.org/bsb.tsv.gz").unwrap();
    assert!(matches!(
        product().check(&next),
        Err(UrlRefusal::NotHttps { .. })
    ));
    // ...and so is one from a loopback test server to a real http host.
    let next = resolve_redirect("http://127.0.0.1:1/a", "http://example.org/a").unwrap();
    assert!(matches!(
        loopback_tests().check(&next),
        Err(UrlRefusal::NotHttps { .. })
    ));
}
