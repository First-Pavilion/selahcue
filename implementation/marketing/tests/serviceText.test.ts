/**
 * The client/server whitespace mirror, tested over the WHOLE DOMAIN rather than a sample.
 *
 * WHY NOT FIXTURES. `signupPolicy.test.ts` used to assert "collapseWhitespace matches the
 * service transform" with fixtures made of `\n`, `\t` and spaces — every one of them drawn
 * from the region where JavaScript and Python already agree. It pinned the claim without
 * testing it, and the claim was false: five characters Python strips and JavaScript does
 * not, and one the other way. A sample cannot find a divergence it does not sample.
 *
 * So the sweep below classifies EVERY code point in 0x0000..0x10FFFF and compares the
 * result against `PYTHON_WHITESPACE`, which is CPython's own answer. There is nowhere left
 * for a divergence to hide.
 *
 * `PYTHON_WHITESPACE` is re-derivable in one line, and `scripts/service_text_reference.py`
 * re-derives it and fails if this file's copy has drifted:
 *
 *   python3 -c "print([cp for cp in range(0x110000) if chr(cp).strip() == ''])"
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'
import {
  PYTHON_WHITESPACE,
  SERVICE_WHITESPACE_CLASS,
  isServiceWhitespace,
  serviceCollapse,
  serviceStrip,
} from '../src/lib/auth/serviceText.ts'

const PYTHON = new Set(PYTHON_WHITESPACE)

describe('the whitespace mirror agrees with Python on every code point', () => {
  test('all 1,114,112 code points classify identically', () => {
    // The premise, pinned so a future edit that empties the class cannot turn this sweep
    // vacuous: an empty class would classify NOTHING as whitespace and the sweep would
    // then be asserting that Python's set is empty, which it would notice — but an
    // over-broad class (`[\s\S]`) would classify everything and fail the same way. Both
    // directions are covered because both sides of the comparison are asserted below.
    assert.ok(SERVICE_WHITESPACE_CLASS.length > 0, 'the shared class is empty')
    assert.equal(PYTHON.size, 29, 'the pinned Python set changed size — re-derive it')

    const mismatched: string[] = []
    for (let codePoint = 0; codePoint <= 0x10ffff; codePoint += 1) {
      // Lone surrogates are not characters and cannot appear in a well-formed string.
      if (codePoint >= 0xd800 && codePoint <= 0xdfff) continue
      const character = String.fromCodePoint(codePoint)
      if (isServiceWhitespace(character) !== PYTHON.has(codePoint)) {
        mismatched.push(`U+${codePoint.toString(16).toUpperCase().padStart(4, '0')}`)
      }
    }

    assert.deepEqual(mismatched, [], `these code points disagree with Python: ${mismatched}`)
  })

  test('the sweep is not vacuous — it fails for JS `trim` on both divergence sets', () => {
    // POSITIVE CONTROL, and the reason this file exists. If the sweep above could pass
    // for the OLD implementation (JavaScript's own `trim`), it would be proving nothing.
    // These are the exact characters the old mirror got wrong, in both directions.
    const pythonOnly = ['\u001c', '\u001d', '\u001e', '\u001f', '\u0085']
    for (const character of pythonOnly) {
      assert.equal(character.trim(), character, 'premise: JS does not strip this')
      assert.ok(isServiceWhitespace(character), 'but the service mirror must')
    }

    // U+FEFF runs the other way: JS strips it, Python keeps it.
    assert.equal('\ufeff'.trim(), '', 'premise: JS strips U+FEFF')
    assert.ok(!isServiceWhitespace('\ufeff'), 'the service mirror must NOT strip U+FEFF')
  })
})

describe('the transforms themselves', () => {
  test('serviceCollapse reproduces `" ".join(value.strip().split())`', () => {
    // The benign cases the old fixtures covered — kept, because a mirror that broke these
    // would be a regression even though they are not where the divergence lives.
    assert.equal(serviceCollapse('  Grace   Community  '), 'Grace Community')
    assert.equal(serviceCollapse('\n\tGrace\n\n Community\t'), 'Grace Community')
    assert.equal(serviceCollapse('   '), '')
    assert.equal(serviceCollapse(''), '')

    // And the cases that were wrong. Three information separators are an EMPTY org name
    // to the server, so they must be an empty one here.
    assert.equal(serviceCollapse('\u001c\u001c\u001c'), '')
    assert.equal(serviceCollapse('\u0085'), '')
    assert.equal(serviceCollapse('Grace\u001cCommunity'), 'Grace Community')

    // U+FEFF is NOT whitespace to Python, so it must survive here — collapsing it would
    // mean the client validated a different string than the server stores.
    assert.equal(serviceCollapse('Grace\ufeffCommunity'), 'Grace\ufeffCommunity')
    assert.equal(serviceCollapse('\ufeff'), '\ufeff')
  })

  test('serviceStrip reproduces `value.strip()`', () => {
    assert.equal(serviceStrip('  hello  '), 'hello')
    assert.equal(serviceStrip('\u001c\u001chello\u0085'), 'hello')
    assert.equal(serviceStrip('\u001c'.repeat(12)), '', 'an all-separator password is empty to Python')
    assert.equal(serviceStrip('\ufeffhello\ufeff'), '\ufeffhello\ufeff', 'U+FEFF is not stripped')
  })
})
