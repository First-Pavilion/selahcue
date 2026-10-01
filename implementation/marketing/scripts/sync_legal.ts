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
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
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

function main(argv: string[]): number {
  const check = argv.includes('--check')
  const flag = (name: string): string | undefined => {
    const at = argv.indexOf(name)
    return at === -1 ? undefined : argv[at + 1]
  }
  const generated = generateAll({ srcDir: flag('--src'), outDir: flag('--out') })
  let stale = 0
  for (const g of generated) {
    const current = existsSync(g.outPath) ? readFileSync(g.outPath, 'utf8') : null
    if (check) {
      if (current !== g.content) {
        stale++
        console.error(`STALE  ${g.outPath}  (does not match ${g.target.source}; run: npm run sync:legal)`)
      } else {
        console.log(`ok     ${g.outPath}`)
      }
      continue
    }
    mkdirSync(dirname(g.outPath), { recursive: true })
    if (current === g.content) {
      console.log(`same   ${g.outPath}`)
    } else {
      writeFileSync(g.outPath, g.content)
      console.log(`wrote  ${g.outPath}`)
    }
  }
  return stale > 0 ? 1 : 0
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exit(main(process.argv.slice(2)))
  } catch (err) {
    console.error(err instanceof Error ? err.message : err)
    process.exit(2)
  }
}
