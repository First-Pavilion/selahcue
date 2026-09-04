/**
 * The email mirror, checked against the SERVER's verdict rather than against itself.
 *
 * `tests/fixtures/email-mirror.json` is the single definition. It carries one row per
 * address with a `serverAccepts` column, and it has exactly two consumers:
 *
 *   - this file, which asserts `emailPolicy` agrees with that column on every row;
 *   - `scripts/service_text_reference.py`, which RE-DERIVES the column by calling the
 *     pinned Django's own `validate_email`, EXITS NON-ZERO rather than skipping when
 *     Django is absent or is the wrong version, and drives a generated corpus of several
 *     thousand addresses through BOTH runtimes to look for a divergence nobody named.
 *
 * WHY THAT SECOND CONSUMER IS WORDED SO CAREFULLY. The previous version of it did not ask
 * Django — it fell back to a transcription of the same regex the client had, the same wrong
 * rule typed twice, and that fallback is what actually ran. It agreed with itself and
 * printed OK while two verdicts in this file were wrong: `a@b.12` and `a@b.-xy` were
 * recorded as server-ACCEPTED, and Django 6.1 rejects both. The transcription was Django
 * <= 5.1's; 5.2 rebuilt `EmailValidator.domain_regex` on `DomainNameValidator`.
 *
 * A check that compares against another system must query that system, not a copy of it.
 * That is the rule this file and that script now both obey.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import { readFileSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import {
  CASE_FOLDED_LOCAL_LETTERS,
  EMAIL_INVALID,
  EMAIL_REQUIRED,
  MAX_EMAIL_LENGTH,
  normalizeEmail,
  serverWouldAcceptEmail,
  validateEmail,
} from '../src/lib/auth/emailPolicy.ts'

interface MirrorCase {
  address: string
  serverAccepts: boolean
  note: string
  divergence?: string[]
}

const CASES: MirrorCase[] = JSON.parse(
  readFileSync(new URL('./fixtures/email-mirror.json', import.meta.url), 'utf8'),
).cases

/** The domain as the server splits it out — the LAST at-sign, per `value.rsplit("@", 1)`. */
function domainOf(address: string): string {
  const normalized = normalizeEmail(address)
  return normalized.slice(normalized.lastIndexOf('@') + 1)
}

/**
 * The shape families a domain can belong to.
 *
 * These are the units the lockout control below reasons in. The IDN family is the one this
 * PR actually broke, but naming only that one would leave the next family to be discovered
 * by a customer, so every family the mirror supports has to carry its own evidence.
 */
type DomainClass = 'allowlist' | 'ip-literal' | 'punycode' | 'idn' | 'ascii'

function domainClass(address: string): DomainClass {
  const domain = domainOf(address)
  if (domain === 'localhost') return 'allowlist'
  if (domain.startsWith('[')) return 'ip-literal'
  if (domain.split('.').some((label) => label.startsWith('xn--'))) return 'punycode'
  if (/[^\u0000-\u007f]/u.test(domain)) return 'idn'
  return 'ascii'
}

const DOMAIN_CLASSES: DomainClass[] = ['allowlist', 'ip-literal', 'punycode', 'idn', 'ascii']

describe('the client agrees with the server on every fixture', () => {
  test('the fixture set is real and covers both verdicts', () => {
    // The premise, pinned so the sweep below cannot go vacuous by the file emptying or
    // by every row landing on one verdict — a sweep of fifty accepts would pass just as
    // well for `return true`.
    const accepted = CASES.filter((row) => row.serverAccepts)
    const rejected = CASES.filter((row) => !row.serverAccepts)
    assert.ok(accepted.length >= 15, `only ${accepted.length} accepted fixtures`)
    assert.ok(rejected.length >= 15, `only ${rejected.length} rejected fixtures`)

    // And the four Cody measured against real Django are present BY VALUE, so deleting
    // them to make this file pass is a visible edit rather than a quiet one.
    for (const address of ['a@b.c', 'a@b..com', 'a@-b.com', 'a@b-.com']) {
      const row = CASES.find((candidate) => candidate.address === address)
      assert.ok(row, `${address} is missing from the fixture set`)
      assert.equal(row.serverAccepts, false, `${address} must be recorded as server-rejected`)
    }

    // The two the FIRST version of this file got wrong, pinned by value with the corrected
    // verdict. These are the rows a re-transcription of the pre-5.2 pattern would flip back.
    for (const address of ['a@b.12', 'a@b.-xy']) {
      const row = CASES.find((candidate) => candidate.address === address)
      assert.ok(row, `${address} is missing from the fixture set`)
      assert.equal(
        row.serverAccepts,
        false,
        `${address} is REJECTED by Django 6.1. Recording it as accepted is the exact defect ` +
          'this fixture shipped with — the pre-5.2 domain pattern transcribed and labelled 6.1.',
      )
    }
  })

  test('serverWouldAcceptEmail matches serverAccepts on every row', () => {
    const disagreements: string[] = []
    for (const row of CASES) {
      if (serverWouldAcceptEmail(row.address) !== row.serverAccepts) {
        disagreements.push(
          `${JSON.stringify(row.address)} — server ${row.serverAccepts ? 'accepts' : 'rejects'}, ` +
            `client ${row.serverAccepts ? 'rejects' : 'accepts'} (${row.note})`,
        )
      }
    }
    assert.deepEqual(disagreements, [], `the mirror has drifted:\n  ${disagreements.join('\n  ')}`)
  })

  test('validateEmail reports the same verdict, with a message the user can act on', () => {
    for (const row of CASES) {
      const message = validateEmail(row.address)
      if (row.serverAccepts) {
        assert.equal(message, '', `${JSON.stringify(row.address)} must be submittable`)
      } else {
        assert.ok(message !== '', `${JSON.stringify(row.address)} must not be submittable`)
        assert.ok(
          message === EMAIL_REQUIRED || message === EMAIL_INVALID,
          `unexpected message for ${JSON.stringify(row.address)}: ${message}`,
        )
      }
    }
  })

  test('an empty or whitespace-only address asks for one rather than calling it invalid', () => {
    assert.equal(validateEmail(''), EMAIL_REQUIRED)
    assert.equal(validateEmail('   '), EMAIL_REQUIRED)
    // The service-strip set, not the JS one: the server sees these as empty too.
    assert.equal(validateEmail('\u001c\u001c'), EMAIL_REQUIRED)
  })
})

/**
 * THE LOCKOUT CONTROL — the half the first mirror had no equivalent of.
 *
 * The two ways to get a mirror wrong are not symmetrical in how they hurt. Being LOOSER
 * than the server sends a doomed request and misattributes the rejection; being STRICTER
 * refuses the address before any request happens, and because `validateEmail` gates
 * sign-in, signup, forgot-password AND resend, a stricter-than-server rule closes every
 * auth surface to whoever it refuses. There is no error message to misread, no retry that
 * helps and no server log that shows it.
 *
 * That is not hypothetical here. The first mirror rejected every internationalised domain —
 * `a@münchen.de`, `a@éxample.com`, `a@b.cé` — all of which Django 6.1 accepts, and all of
 * which the `/\S+@\S+\.\S+/` it replaced also accepted. The regression was invisible to a
 * fixture set that contained no IDN row.
 *
 * So the control is written on the CLASS rather than the instance, in two halves that have
 * to hold together: every domain family the mirror supports must carry a server-accepted
 * row, AND the client must accept every one of them. Deleting the rows to make the second
 * half pass fails the first.
 */
describe('the client is never stricter than the server', () => {
  test('every domain family has a server-accepted row to be checked against', () => {
    for (const family of DOMAIN_CLASSES) {
      const rows = CASES.filter((row) => row.serverAccepts && domainClass(row.address) === family)
      assert.ok(
        rows.length > 0,
        `no server-ACCEPTED fixture row has a ${family} domain. Without one, this file ` +
          'cannot notice the client refusing that whole family — which is how the IDN ' +
          'lockout shipped.',
      )
    }
  })

  test('no address the server accepts is refused by the client', () => {
    const lockedOut = CASES.filter(
      (row) => row.serverAccepts && !serverWouldAcceptEmail(row.address),
    )
    assert.deepEqual(
      lockedOut.map((row) => `${row.address} [${domainClass(row.address)}] — ${row.note}`),
      [],
      'the client refuses an address the server accepts. Every one of these is a customer ' +
        'who cannot sign in, sign up, reset a password or request a new link, with no ' +
        'message that explains why.',
    )
  })

  test('the case-folded local letters Django accepts are accepted in all three forms', () => {
    // THE SECOND LOCKOUT, and the one the IDN fix does not reach. `ul` widened the DOMAIN
    // classes; nothing widened the LOCAL ones — but `user_regex` carries `re.IGNORECASE`,
    // and Python's IGNORECASE is full case folding, so the ASCII letter classes contain
    // code points nobody wrote in them. Two survive `.lower()` and reach the regex.
    //
    // The premise is pinned BY VALUE first. Consuming the constant in a loop and nothing
    // else would make emptying the constant a PASS — the loop would simply not run, the
    // classes would narrow, and `bılgi@example.com` would be refused with a green suite.
    assert.equal(
      CASE_FOLDED_LOCAL_LETTERS,
      'ıſ',
      'the case-folded set changed. It is not a style choice — it was swept exhaustively ' +
        'over all 0x110000 code points against the installed Django 6.1.1 user_regex, and ' +
        'narrowing it locks the affected people out of every auth surface. Re-measure ' +
        'against the pinned Django before changing this.',
    )
    assert.ok(CASE_FOLDED_LOCAL_LETTERS.length > 0)

    // All three of Django's local-part classes span the ASCII letters, so all three gain
    // them. One form per class, so removing the constant from any single class fails here
    // and names which one.
    for (const ch of CASE_FOLDED_LOCAL_LETTERS) {
      const point = `U+${ch.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0')}`
      assert.equal(
        serverWouldAcceptEmail(`${ch}mith@example.com`),
        true,
        `${point} in a dot-atom local part is accepted by Django 6.1 and must be submittable`,
      )
      assert.equal(
        serverWouldAcceptEmail(`"${ch}"@example.com`),
        true,
        `${point} inside a quoted local part is accepted by Django 6.1`,
      )
      assert.equal(
        serverWouldAcceptEmail(`"\\${ch}"@example.com`),
        true,
        `${point} backslash-escaped inside a quoted local part is accepted by Django 6.1`,
      )
      // And it survives normalisation unchanged — which is WHY it has to be in the class.
      assert.equal(normalizeEmail(ch), ch, `${point} must be lowercase already`)
    }

    // NEGATIVE CONTROLS. Without these, "add every code point the fold pulls in" would
    // look identical to the correct answer. U+0130 also matches `user_regex`, but
    // normalisation turns it into `i` + U+0307, which the class does not contain.
    assert.equal(serverWouldAcceptEmail('İ@example.com'), false, 'U+0130 lowercases away')
    // U+212A likewise matches, and lowercases to a plain `k` — accepted, but by the
    // ordinary ASCII class, not by anything added here.
    assert.equal(serverWouldAcceptEmail('K@example.com'), true)
    assert.equal(normalizeEmail('K@example.com'), 'k@example.com')
    // And an ordinary non-ASCII letter is still refused: `ul` is a DOMAIN range. If this
    // ever passes, the fix has widened the local part far beyond what the fold does.
    assert.equal(serverWouldAcceptEmail('josé@example.com'), false)
  })

  test('the IDN family is checked by value, not only by classification', () => {
    // POSITIVE VALUES FIRST. The class sweep above is driven by the fixture file, so a
    // future edit that dropped the IDN rows would be caught by the coverage half — but
    // only as a missing-row message. These three are the addresses actually observed to
    // be locked out, named here so the regression itself is unmistakable.
    for (const address of ['a@münchen.de', 'a@éxample.com', 'a@b.cé']) {
      assert.equal(
        serverWouldAcceptEmail(address),
        true,
        `${address} is accepted by Django 6.1 and must be submittable. Rejecting it is the ` +
          'IDN lockout this PR introduced and the review caught.',
      )
      assert.equal(validateEmail(address), '')
    }
  })
})

/**
 * The rules that are easy to state and easy to get subtly wrong, each pinned on an input
 * where a plausible wrong implementation gives a DIFFERENT answer.
 *
 * Every address here is outside the agreeing region for the specific mistake it names. A
 * row both the right and the wrong implementation reject proves nothing about either.
 */
describe('the boundaries the server draws', () => {
  test('the domain is split on the LAST at-sign', () => {
    // Quinn: the module has always claimed this and nothing tested it, because the fixture
    // row that could have came from the region where both splits agree.
    //
    // Django does `value.rsplit("@", 1)`. Splitting on the FIRST at-sign instead gives
    // user `"a` and domain `b"@example.com`, and rejects — so this row discriminates.
    assert.equal(serverWouldAcceptEmail('"a@b"@example.com'), true)
    // The companion, which BOTH splits reject: an unquoted at-sign is not in the dot-atom
    // class. Present so "accepts anything with two at-signs" is not what the row above
    // rewards.
    assert.equal(serverWouldAcceptEmail('a@b@c.com'), false)
  })

  test('320 characters is the cap, and it is applied to the NORMALISED address', () => {
    const at320 = `${'a'.repeat(308)}@example.com`
    const at321 = `${'a'.repeat(309)}@example.com`
    assert.equal(at320.length, MAX_EMAIL_LENGTH)
    assert.equal(at321.length, MAX_EMAIL_LENGTH + 1)
    assert.equal(serverWouldAcceptEmail(at320), true, '320 characters is inside the cap')
    assert.equal(serverWouldAcceptEmail(at321), false, '321 characters is refused by length')
    // Applied AFTER stripping, because that is the string the server measures: padding an
    // over-long address with spaces must not change the verdict, and padding a legal one
    // to 321 raw characters must not make it fail.
    assert.equal(serverWouldAcceptEmail(`   ${at320}   `), true)
    assert.equal(serverWouldAcceptEmail(`   ${at321}   `), false)
  })

  test('an IP literal is validated as an address, not just matched as a shape', () => {
    // The old rule checked `[hex, colons and dots]` and stopped. Django then parses it.
    assert.equal(serverWouldAcceptEmail('user@[192.168.1.1]'), true)
    assert.equal(serverWouldAcceptEmail('user@[999.999.999.999]'), false, 'octets over 255')
    assert.equal(serverWouldAcceptEmail('user@[1.2.3]'), false, 'three octets is not an address')
    assert.equal(serverWouldAcceptEmail('user@[01.2.3.4]'), false, 'a leading zero raises')
    assert.equal(serverWouldAcceptEmail('user@[::1]'), true)
    assert.equal(serverWouldAcceptEmail('user@[1::2::3]'), false, 'two compressions is ambiguous')
    // Django refuses an IPv6 literal over 39 characters BEFORE parsing it, so the pair
    // either side of that boundary is the only way to see the rule.
    assert.equal(serverWouldAcceptEmail('user@[0000:0000:0000:0000:0000:0000:0000:0001]'), true)
    assert.equal(serverWouldAcceptEmail('user@[00000:0000:0000:0000:0000:0000:0000:0001]'), false)
  })

  test('the TLD class has no digits and no leading hyphen', () => {
    // The two rows the first fixture got backwards, plus the punycode escape hatch that is
    // the ONLY way a digit reaches a TLD.
    assert.equal(serverWouldAcceptEmail('a@b.12'), false)
    assert.equal(serverWouldAcceptEmail('a@b.c0m'), false)
    assert.equal(serverWouldAcceptEmail('a@b.-xy'), false)
    assert.equal(serverWouldAcceptEmail('a@b.xn--p1ai'), true)
    // And `tld_no_fqdn_re`, not `tld_re`: an address may not carry the trailing dot a
    // fully qualified domain name may.
    assert.equal(serverWouldAcceptEmail('a@b.com.'), false)
  })
})

describe('normalisation matches `_normalize_email`', () => {
  test('the address is stripped and lowercased the way the server does it', () => {
    assert.equal(normalizeEmail('  Pastor@YourChurch.ORG  '), 'pastor@yourchurch.org')
    // U+001C is whitespace to Python and not to JavaScript. Stripping it here is what
    // stops the client validating a different string than the server stores.
    assert.equal(normalizeEmail('\u001cpastor@yourchurch.org\u001c'), 'pastor@yourchurch.org')
    // U+FEFF runs the other way and must survive, which makes this address invalid on
    // BOTH sides rather than valid on one.
    assert.equal(normalizeEmail('\ufeffpastor@yourchurch.org'), '\ufeffpastor@yourchurch.org')
    assert.equal(serverWouldAcceptEmail('\ufeffpastor@yourchurch.org'), false)
  })
})

describe('the rule the module must never acquire', () => {
  test('nothing here can tell a registered address from an unregistered one', () => {
    // Two addresses of identical shape, one of which is the fixture used throughout the
    // suite as "registered". The verdict must depend on shape alone.
    assert.equal(validateEmail('pastor@yourchurch.org'), '')
    assert.equal(validateEmail('nobody-has-this-address@nowhere.test'), '')
  })
})

/**
 * The reference script is the other consumer, and its independence is the property that
 * failed last time. These assertions are about that script's SOURCE, because the script
 * itself only runs where Django is installed and this file has to hold everywhere.
 */
describe('the reference script cannot quietly become a copy again', () => {
  const REFERENCE = readFileSync(
    new URL('../scripts/service_text_reference.py', import.meta.url),
    'utf8',
  )

  test('the pre-5.2 rule is a discriminator, never an authority', () => {
    // It is kept deliberately — the escape check needs something to disagree with — so it
    // cannot simply be banned by name. What must stay true is that it is CONSULTED in
    // exactly one place. The failure being prevented is the original one: a verdict
    // computed from a transcription and then reported as the server's answer.
    const callSites = REFERENCE.split('\n').filter(
      (line) => line.includes('pre_5_2_verdict(') && !line.trimStart().startsWith('def '),
    )
    assert.equal(
      callSites.length,
      1,
      'expected `pre_5_2_verdict` to be called from exactly one place — the escape check. ' +
        `Found ${callSites.length} call sites:\n  ${callSites.join('\n  ')}\n` +
        'If it has been wired into a validation path, the script is agreeing with a copy again.',
    )

    // And the fallback that caused the defect is gone rather than renamed: no branch may
    // answer "is this valid" without Django.
    assert.ok(
      !/def\s+transcribed_is_valid/.test(REFERENCE),
      'the transcribed fallback validator is back. A copy of the client rule agrees with ' +
        'the client by construction and turns "unverified" into "verified".',
    )
  })

  test('it refuses to certify against a Django that is not the pinned one', () => {
    // Root cause #1 was a wrong-version transcription. The script now reads the pin out of
    // the API's pyproject and checks the installed version against it; asserted here so
    // deleting that check is a failing test.
    assert.ok(
      REFERENCE.includes('def check_django_matches_the_pin'),
      'the version gate is gone — a column derived from Django 5.1 looks exactly like one ' +
        'derived from 6.1, and that is how two verdicts shipped wrong',
    )
  })

  test('it exits NON-ZERO when Django is missing, without being asked to', () => {
    // THIS IS RUN, NOT READ. Every other assertion in this block is about the script's
    // source, because the script only does its real work where Django is installed. This
    // one is about its EXIT CODE, because that is the property that failed: the previous
    // version printed a twenty-line banner saying nothing had been verified and then
    // exited 0, so `npm run test:mirrors` reported success to a developer who had checked
    // nothing about the email rule. A loud skip and a pass are the same thing to a gate.
    //
    // Django is hidden deterministically rather than hoped absent: `sys.modules['django']
    // = None` makes `import django` raise on any machine, including one where the real
    // package is installed. Otherwise this test would assert one thing on CI and the
    // opposite on a developer's laptop.
    const HIDE_DJANGO =
      "import sys, runpy; sys.modules['django'] = None; " +
      "sys.argv = ['service_text_reference.py']; " +
      "runpy.run_path('scripts/service_text_reference.py', run_name='__main__')"

    const run = (extraEnv: Record<string, string>) =>
      spawnSync('python3', ['-c', HIDE_DJANGO], {
        cwd: new URL('..', import.meta.url).pathname,
        encoding: 'utf8',
        env: { ...process.env, ...extraEnv },
      })

    const bare = run({ SELAHCUE_MIRRORS_ALLOW_SKIP: '', SELAHCUE_MIRRORS_REQUIRE: '' })
    assert.equal(
      bare.error,
      undefined,
      `could not run the reference script at all: ${bare.error?.message}`,
    )
    assert.notEqual(
      bare.status,
      0,
      'the reference script exited 0 with no Django installed. It verified NOTHING about ' +
        'the email mirror and reported success — which is exactly how two wrong verdicts ' +
        `shipped. Output:\n${bare.stdout}${bare.stderr}`,
    )

    // POSITIVE CONTROL. Without it, "exited non-zero" is indistinguishable from the script
    // being broken, missing, or unable to find its own fixtures — all of which also exit
    // non-zero and none of which are the property under test.
    const optedOut = run({ SELAHCUE_MIRRORS_ALLOW_SKIP: '1', SELAHCUE_MIRRORS_REQUIRE: '' })
    assert.equal(
      optedOut.status,
      0,
      'with the opt-out set, the whitespace half alone must still run and pass. It did ' +
        `not, so the failure above may not be the fail-closed default at all:\n${optedOut.stdout}${optedOut.stderr}`,
    )
    assert.match(
      optedOut.stdout,
      /THE EMAIL MIRROR WAS NOT CHECKED AT ALL/,
      'the opt-out path must still say, in its summary line, that the email mirror is ' +
        'unverified — a green run that reads as a full pass is the defect, not the exit code',
    )

    // And the override outranks the opt-out, so a stray variable on a runner cannot
    // downgrade CI's gate back to a skip.
    const overridden = run({ SELAHCUE_MIRRORS_ALLOW_SKIP: '1', SELAHCUE_MIRRORS_REQUIRE: '1' })
    assert.notEqual(
      overridden.status,
      0,
      'SELAHCUE_MIRRORS_REQUIRE=1 must beat SELAHCUE_MIRRORS_ALLOW_SKIP=1',
    )
  })

  test('every divergence class the review found still has a named home', () => {
    // The classes are declared in the script and enforced there against the fixture. Named
    // here as well so that quietly deleting one from the script is visible from the side
    // that consumes the fixture.
    for (const name of [
      'digit-in-tld',
      'leading-hyphen-tld',
      'length-cap',
      'ip-literal-semantics',
      'ipv6-tagged-branch',
      'idn-domain',
      'case-fold-residual',
    ]) {
      assert.ok(
        REFERENCE.includes(`"${name}"`),
        `the divergence class ${name} is no longer declared in the reference script`,
      )
      assert.ok(
        CASES.some((row) => row.divergence?.includes(name)),
        `no fixture row is tagged with the divergence class ${name}`,
      )
    }
  })
})
