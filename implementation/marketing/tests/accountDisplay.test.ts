/**
 * The pure display rules for the Account page (ClickUp 17tnw2bhkd2): dates in UTC, an exclusive
 * plan end shown as its last day, and quota seconds shown as whole minutes rounded down.
 */
import assert from 'node:assert/strict'
import test, { describe } from 'node:test'

import {
  deviceLabel,
  formatAccountDate,
  formatPlanEnd,
  countLeftLine,
  minutesLeftLine,
  minutesUsed,
  quotaUnavailable,
  wholeMinutes,
} from '../src/lib/accountDisplay.ts'

describe('dates', () => {
  test('a timestamp is shown as day, month name and year in UTC', () => {
    assert.equal(formatAccountDate('2027-05-05T00:00:00+00:00'), '5 May 2027')
    assert.equal(formatAccountDate('2026-12-09T10:00:00+00:00'), '9 Dec 2026')
  })

  test('UTC wins over the offset the timestamp is written in', () => {
    assert.equal(formatAccountDate('2026-12-09T23:30:00-05:00'), '10 Dec 2026')
  })

  test('an unreadable timestamp shows nothing rather than "Invalid Date"', () => {
    assert.equal(formatAccountDate('not a date'), '')
    assert.equal(formatAccountDate(''), '')
  })

  test('the plan end is exclusive, so midnight on 6 May is the last day, 5 May', () => {
    assert.equal(formatPlanEnd('2027-05-06T00:00:00+00:00'), '5 May 2027')
  })

  test('the plan end crosses a month and a year boundary correctly', () => {
    assert.equal(formatPlanEnd('2027-01-01T00:00:00+00:00'), '31 Dec 2026')
    assert.equal(formatPlanEnd('2027-03-01T00:00:00+00:00'), '28 Feb 2027')
  })

  test('no plan end, or an unreadable one, shows nothing', () => {
    assert.equal(formatPlanEnd(null), '')
    assert.equal(formatPlanEnd('garbage'), '')
  })
})

describe('minutes', () => {
  test('seconds are shown as whole minutes, rounded down', () => {
    assert.equal(wholeMinutes('7200'), '120')
    assert.equal(wholeMinutes('119'), '1')
    assert.equal(wholeMinutes('59'), '0')
    assert.equal(wholeMinutes('0'), '0')
  })

  test('a counter beyond 2^53 does not lose digits', () => {
    assert.equal(wholeMinutes('9223372036854775807'), '153722867280912930')
  })

  test('an unreadable counter is null, not NaN', () => {
    assert.equal(wholeMinutes('abc'), null)
    assert.equal(wholeMinutes(''), null)
    assert.equal(wholeMinutes('-5'), null)
  })

  test('"120 min left of 180"', () => {
    assert.equal(minutesLeftLine({ remaining: '7200', limit: '10800' }), '120 min left of 180')
  })

  test('used minutes come from the limit less what remains, so holds and debt count', () => {
    assert.equal(minutesUsed({ remaining: '7200', limit: '10800' }), '60')
    assert.equal(minutesUsed({ remaining: '20000', limit: '10800' }), '0')
  })

  test('used and left add up to the total even when the seconds do not divide evenly', () => {
    // 100 s total is 1 min, 59 s left is 0 min: used must be 1, not floor(41/60) = 0.
    const q = { remaining: '59', limit: '100' }
    assert.equal(Number(minutesUsed(q)) + Number(wholeMinutes(q.remaining)), Number(wholeMinutes(q.limit)))
    assert.equal(minutesUsed(q), '1')
  })

  test('a quota not yet observed or stale is unavailable', () => {
    assert.equal(quotaUnavailable({ status: 'NOT_INITIALIZED' }), true)
    assert.equal(quotaUnavailable({ status: 'STALE' }), true)
    assert.equal(quotaUnavailable({ status: 'CURRENT_OBSERVED' }), false)
  })

  test('an unreadable quota gives no line', () => {
    assert.equal(minutesLeftLine({ remaining: 'x', limit: '10800' }), '')
  })
})

describe('notes and devices', () => {
  test('notes are a count, not minutes', () => {
    assert.equal(countLeftLine({ remaining: '1', limit: '3' }), '1 left of 3')
  })

  test('a device with no name is still identifiable', () => {
    assert.equal(deviceLabel({ displayName: 'Main booth', platform: 'macos' }), 'Main booth')
    assert.equal(deviceLabel({ displayName: '', platform: 'macos' }), 'Unnamed computer (macos)')
    assert.equal(deviceLabel({ displayName: '  ', platform: '' }), 'Unnamed computer')
  })
})
