/**
 * Builds the component gallery (`index.html` here) into `node_modules/.tmp/gallery`, for
 * `scripts/shared_components_headless.py`.
 *
 * It is a build, not the dev server, so the browser loads one static folder and no HMR socket
 * is involved. `GALLERY_SRC` points the `@` alias at another checkout's `src` (the script uses
 * it to render the SAME gallery against the audit branch's components and diff the default
 * look); without it, `@` is this checkout's `src`.
 */
import path from 'node:path'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { unsafeOutDir } from './outDir.ts'

const HERE = import.meta.dirname
const PROJECT = path.resolve(HERE, '../..')
const SRC = process.env['GALLERY_SRC'] ? path.resolve(process.env['GALLERY_SRC']) : path.resolve(PROJECT, 'src')
const OUT = process.env['GALLERY_OUT'] ? path.resolve(process.env['GALLERY_OUT']) : path.resolve(PROJECT, 'node_modules/.tmp/gallery')

const refusal = unsafeOutDir(OUT)
if (refusal) throw new Error(`GALLERY_OUT refused: ${refusal}`)

export default defineConfig({
  root: HERE,
  base: './',
  plugins: [vue()],
  resolve: { alias: { '@': SRC } },
  build: { outDir: OUT, emptyOutDir: true },
})
