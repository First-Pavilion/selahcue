import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'

/** The title `index.html` carries, which is how a folder is recognised as an earlier gallery build. */
export const GALLERY_TITLE = '<title>Shared component gallery</title>'

/**
 * Why the gallery must NOT be built into `dir`, or `null` when it may.
 *
 * Vite empties the output folder before it builds, and setting `emptyOutDir: true` (which the
 * gallery does, so a rebuild does not accumulate files) also turns off Vite's own refusal to
 * empty a folder outside the project. So `GALLERY_OUT=.` or a mistyped path would delete
 * whatever is there (review of PR 173, Shadow 3). A folder is safe when it does not exist, is
 * empty, or already holds a gallery build (an `index.html` with this gallery's title).
 */
export function unsafeOutDir(dir: string): string | null {
  const resolved = path.resolve(dir)
  if (!existsSync(resolved)) return null
  if (!statSync(resolved).isDirectory()) return `${resolved} exists and is not a directory`
  if (readdirSync(resolved).length === 0) return null
  const index = path.join(resolved, 'index.html')
  if (existsSync(index) && readFileSync(index, 'utf8').includes(GALLERY_TITLE)) return null
  return `${resolved} is not empty and does not hold a gallery build, so building there would delete its contents`
}
