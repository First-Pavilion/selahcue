/**
 * Generate `src/lib/legal/*.generated.ts` from the platform legal drafts in `docs/legal/`.
 *
 *   npm run sync:legal                 rewrite the generated files
 *   npm run sync:legal -- --check      exit 1 if a committed file differs (writes nothing)
 *
 * WHY A GENERATOR AND NOT AN IMPORT. The marketing Docker build context is
 * `implementation/marketing` only, so the build cannot read `docs/legal/` — the markdown
 * would not exist inside the container. The drafts stay the source of truth; this script
 * turns them into typed data that lives INSIDE the build context and is committed, and
 * `tests/legal.test.ts` regenerates in memory and fails if the committed copy differs.
 *
 * Deterministic: same markdown in, byte-identical TypeScript out. No timestamps, no paths
 * other than the repo-relative source, no environment.
 *
 * Test/experiment overrides (both optional): `--src <dir>` reads the drafts from `<dir>`
 * instead of `docs/legal/`; `--out <dir>` writes to `<dir>` instead of `src/lib/legal/`.
 */
import { existsSync, mkdirSync, readFileSync, realpathSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseLegalMarkdown, renderGeneratedModule } from './legal_markdown.ts'

export interface Target {
  /** Repo-relative markdown source. */
  readonly source: string
  /** File name inside `src/lib/legal/`. */
  readonly output: string
  readonly exportName: string
}

export const TARGETS: readonly Target[] = [
  {
    source: 'docs/legal/PRIVACY-POLICY-PLATFORM-DRAFT.md',
    output: 'privacy.generated.ts',
    exportName: 'privacyPolicy',
  },
  {
    source: 'docs/legal/TERMS-OF-SERVICE-PLATFORM-DRAFT.md',
    output: 'terms.generated.ts',
    exportName: 'termsOfService',
  },
]

export const MARKETING_ROOT = fileURLToPath(new URL('../', import.meta.url))
export const REPO_ROOT = resolve(MARKETING_ROOT, '../..')
export const GENERATED_DIR = join(MARKETING_ROOT, 'src/lib/legal')

export interface Generated {
  readonly target: Target
  readonly outPath: string
  readonly content: string
}

/** Parse every draft and return the exact text each generated file should contain. */
export function generateAll(opts: { srcDir?: string; outDir?: string } = {}): Generated[] {
  return TARGETS.map((target) => {
    const sourcePath = opts.srcDir ? join(opts.srcDir, target.source.split('/').pop() ?? '') : join(REPO_ROOT, target.source)
    if (!existsSync(sourcePath)) {
      throw new Error(`legal draft not found: ${sourcePath}`)
    }
    const doc = parseLegalMarkdown(readFileSync(sourcePath, 'utf8'), target.source)
    return {
      target,
      outPath: join(opts.outDir ?? GENERATED_DIR, target.output),
      content: renderGeneratedModule(doc, target.exportName, 'npm run sync:legal (in implementation/marketing)'),
    }
  })
}

export interface Args {
  readonly check: boolean
  readonly srcDir?: string
  readonly outDir?: string
}

const USAGE = 'usage: node scripts/sync_legal.ts [--check] [--src <dir>] [--out <dir>]'

/**
 * Strict: an unknown flag (a typo such as `--chek`) or a missing value is an error, never a
 * silent fall-through into write mode. Returns the parsed args or throws with the usage.
 */
export function parseArgs(argv: readonly string[]): Args {
  let check = false
  let srcDir: string | undefined
  let outDir: string | undefined
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--check') check = true
    else if (a === '--src' || a === '--out') {
      const value = argv[i + 1]
      if (value === undefined || value.startsWith('--')) throw new Error(`${a} needs a directory\n${USAGE}`)
      if (a === '--src') srcDir = value
      else outDir = value
      i++
    } else {
      throw new Error(`unknown argument "${a}"\n${USAGE}`)
    }
  }
  return { check, srcDir, outDir }
}

/** Line endings must not decide drift: a Windows checkout may hand back CRLF. */
export function sameContent(a: string | null, b: string): boolean {
  return a !== null && a.replace(/\r\n/g, '\n') === b.replace(/\r\n/g, '\n')
}

function main(argv: string[]): number {
  const { check, srcDir, outDir } = parseArgs(argv)
  const generated = generateAll({ srcDir, outDir })
  let stale = 0
  for (const g of generated) {
    const current = existsSync(g.outPath) ? readFileSync(g.outPath, 'utf8') : null
    if (check) {
      if (!sameContent(current, g.content)) {
        stale++
        console.error(
          `STALE  ${g.outPath}\n       does not match ${g.target.source}. After editing a draft in docs/legal, run \`npm run sync:legal\` (in implementation/marketing) and commit the regenerated files.`,
        )
      } else {
        console.log(`ok     ${g.outPath}`)
      }
      continue
    }
    mkdirSync(dirname(g.outPath), { recursive: true })
    if (sameContent(current, g.content)) {
      console.log(`same   ${g.outPath}`)
    } else {
      writeFileSync(g.outPath, g.content)
      console.log(`wrote  ${g.outPath}`)
    }
  }
  return stale > 0 ? 1 : 0
}

/**
 * Is this module the entry point? Compared by REAL path on both sides: `process.argv[1]` is
 * the path as typed (possibly a symlink) while `import.meta.url` is already resolved, and a
 * plain comparison of the two silently made `check:legal` exit 0 having checked nothing.
 */
function isEntryPoint(): boolean {
  const entry = process.argv[1]
  if (!entry) return false
  try {
    return realpathSync(entry) === realpathSync(fileURLToPath(import.meta.url))
  } catch {
    return false
  }
}

if (isEntryPoint()) {
  try {
    process.exit(main(process.argv.slice(2)))
  } catch (err) {
    console.error(err instanceof Error ? err.message : err)
    process.exit(2)
  }
}
