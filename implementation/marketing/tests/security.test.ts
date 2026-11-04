import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const read = (path: string) => readFileSync(new URL(path, import.meta.url), 'utf8')
test('public marketing PR code gets read-only checkout without persisted credentials', () => {
  const job = read('../../../.github/workflows/ci.yml').split('\n  marketing:\n')[1]!.split('\n  audit:')[0]!
  assert.match(job, /permissions:\n {6}contents: read/)
  assert.match(job, /uses: actions\/checkout@[^\n]+\n {8}with:\n {10}persist-credentials: false/)
  assert.match(job, /run: npm audit --audit-level=high\s*\n/)
  assert.match(job, /docker build --pull/)
  assert.match(job, /security_headers_headless.py/)
})
test('production build disables package lifecycle hooks and matches supported CI Node', () => {
  assert.equal(read('../.npmrc').trim(), 'ignore-scripts=true')
  assert.match(read('../Dockerfile'), /^FROM node:22-alpine AS builder/m)
  assert.match(read('../Dockerfile'), /COPY implementation\/marketing\/package.json implementation\/marketing\/package-lock.json implementation\/marketing\/.npmrc/)
})
test('nginx shares enforced CSP across document and cache locations', () => {
  const nginx = read('../nginx.conf')
  const headers = read('../security-headers.conf')
  assert.equal((nginx.match(/include \/etc\/nginx\/security-headers.conf;/g) ?? []).length, 2)
  assert.match(headers, /add_header Content-Security-Policy .* always;/)
  for (const directive of ["default-src 'none'", "script-src 'self'", "style-src-attr 'none'", "connect-src 'self'", "object-src 'none'", "base-uri 'none'", "form-action 'self'"]) assert.ok(headers.includes(directive), directive)
  assert.ok(!headers.includes('unsafe-inline') && !headers.includes('unsafe-eval'))
})

test('root Docker context remains a narrow allowlist including only the canonical public notice', () => {
  const ignored = read('../Dockerfile.dockerignore')
  assert.match(ignored, /\n\*\*\n/)
  assert.ok(ignored.includes('!docs/release/pilot-registration/notice.json'))
  for (const secret of ['**/.env', '**/.git', '**/node_modules', '**/.venv*']) assert.ok(ignored.includes(secret))
  assert.ok(!read('../Dockerfile').includes('COPY . '))
})
