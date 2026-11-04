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
test('nginx repeats identical enforced headers without uninspected server includes', () => {
  const nginx = read('../nginx.conf')
  const serverBlock = nginx.split('server {')[1]!
  assert.doesNotMatch(serverBlock, /^\s*include\s+/m, 'proxy trust guards must be able to inspect every server directive')
  const server = serverBlock.split('location /graphql/')[0]!
  const assets = nginx.match(/location \/assets\/ \{([\s\S]*?)^\s*\}/m)![1]!
  const headers = (body: string) => body.split('\n').map(line => line.trim()).filter(line => /^add_header (?:X-Frame-Options|X-XSS-Protection|X-Content-Type-Options|Referrer-Policy|Content-Security-Policy) /.test(line)).sort()
  assert.equal(headers(server).length, 5)
  assert.deepEqual(headers(assets), headers(server), 'asset add_header overrides must retain the identical security policy')
  const policy = headers(server).find(line => line.startsWith('add_header Content-Security-Policy '))!
  assert.match(policy, / always;$/)
  for (const directive of ["default-src 'none'", "script-src 'self'", "style-src-attr 'none'", "connect-src 'self'", "object-src 'none'", "base-uri 'none'", "form-action 'self'"]) assert.ok(policy.includes(directive), directive)
  assert.ok(!policy.includes('unsafe-inline') && !policy.includes('unsafe-eval'))
})

test('root Docker context remains a narrow allowlist including only the canonical public notice', () => {
  const ignored = read('../Dockerfile.dockerignore')
  assert.match(ignored, /\n\*\*\n/)
  assert.ok(ignored.includes('!docs/release/pilot-registration/notice.json'))
  for (const secret of ['**/.env', '**/.git', '**/node_modules', '**/.venv*']) assert.ok(ignored.includes(secret))
  assert.ok(!read('../Dockerfile').includes('COPY . '))
})
