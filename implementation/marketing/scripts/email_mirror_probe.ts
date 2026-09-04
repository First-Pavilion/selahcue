/**
 * The CLIENT half of the email-mirror differential. Not a test — an evaluator.
 *
 * `service_text_reference.py` generates a corpus, gets the REAL Django's verdict for every
 * address in it, then runs this to get the REAL client module's verdict for the same
 * addresses and diffs the two columns. This file exists so that comparison drives the
 * shipping code rather than a description of it: it imports `emailPolicy.ts` itself and
 * holds no copy of any rule.
 *
 * Usage:  node scripts/email_mirror_probe.ts <addresses.json> <verdicts.json>
 *
 * Input is `{"addresses": [...]}`; output is a JSON array of booleans, positionally aligned.
 * File-based rather than argv-based because the corpus is thousands of addresses long and
 * some of them are 321 characters.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { serverWouldAcceptEmail } from '../src/lib/auth/emailPolicy.ts'

const [, , inputPath, outputPath] = process.argv
if (!inputPath || !outputPath) {
  console.error('usage: node scripts/email_mirror_probe.ts <addresses.json> <verdicts.json>')
  process.exit(2)
}

const addresses: string[] = JSON.parse(readFileSync(inputPath, 'utf8')).addresses
writeFileSync(outputPath, JSON.stringify(addresses.map((a) => serverWouldAcceptEmail(a))))
