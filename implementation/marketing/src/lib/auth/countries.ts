/**
 * ISO 3166-1 alpha-2 codes, for the one field the create-account form cannot omit.
 *
 * `register_customer_user` rejects anything where `len(country) != 2` with the SAME
 * `VALIDATION_FAILED` it raises for a bad email, a short password and a blank org name
 * (`services.py`). `MARKETING-PORTAL-GAP-FILL-HANDOFF.md` §4a lists four fields and
 * country is not among them, so a form built from that list alone would fail EVERY
 * signup with an error the UI could not attribute — and the one attribution it must
 * never guess at is the email. `AUTH-LANDING-PAGES-HANDOFF.md` §9 has the real field
 * set: `{idempotencyKey, email, password, orgName, country, displayName, timezone}`.
 *
 * Only the CODES are stored. Names come from `Intl.DisplayNames`, which is in every
 * target browser and already localised, so this module carries ~700 bytes instead of the
 * ~6KB an embedded English name table would cost — and a French-speaking church in
 * Quebec sees French country names without us shipping a translation table.
 *
 * Stored as one space-separated string and split once at module load: the same data as
 * an array literal, about a third of the source bytes, and no per-entry quoting to get
 * wrong.
 */

const ALPHA2 =
  'AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN ' +
  'BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ ' +
  'DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL ' +
  'GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM ' +
  'JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME ' +
  'MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP ' +
  'NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD ' +
  'SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO ' +
  'TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW'

export const COUNTRY_CODES: readonly string[] = Object.freeze(ALPHA2.split(' '))

export interface CountryOption {
  code: string
  label: string
}

/**
 * Codes paired with display names, sorted by name in the user's locale.
 *
 * Falls back to the bare code when `Intl.DisplayNames` is missing or throws for a
 * region — a select full of two-letter codes is worse than one full of names, and far
 * better than a form that cannot be submitted.
 */
export function countryOptions(): CountryOption[] {
  let names: { of(code: string): string | undefined } | null = null
  try {
    names = new Intl.DisplayNames(undefined, { type: 'region' })
  } catch {
    names = null
  }

  const options = COUNTRY_CODES.map((code) => {
    let label = code
    try {
      label = names?.of(code) ?? code
    } catch {
      label = code
    }
    return { code, label }
  })

  try {
    options.sort((a, b) => a.label.localeCompare(b.label))
  } catch {
    // A locale without a collator: alphabetical-by-code is still a usable order.
  }
  return options
}

/**
 * Best guess at the visitor's country from their locale, or `''`.
 *
 * A guess, and pre-selecting one is worth it — this is a required field most people will
 * not expect on a sign-up form, and the alternative is an empty select every church
 * admin has to hunt through. `''` when the locale carries no region (plain `en`), which
 * leaves the field genuinely unselected rather than silently defaulting someone into the
 * wrong country.
 */
export function guessCountry(locale?: string): string {
  const tag = locale ?? (typeof navigator !== 'undefined' ? navigator.language : '')
  if (!tag) return ''
  try {
    const region = new Intl.Locale(tag).maximize().region
    if (region && COUNTRY_CODES.includes(region)) return region
  } catch {
    // Unparseable tag — fall through to no guess.
  }
  return ''
}
