import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const nginx = readFileSync(process.env.SELAHCUE_NGINX_CONFIG ?? new URL('../nginx.conf', import.meta.url), 'utf8')
const compose = readFileSync(new URL('../../docker-compose.prod.yml', import.meta.url), 'utf8')
const router = readFileSync(new URL('../src/router/index.ts', import.meta.url), 'utf8')
const emailTasks = readFileSync(new URL('../../api/selahcue_api/apps/accounts/tasks.py', import.meta.url), 'utf8')

test('browser account calls stay same-origin and production edge reaches API in one hop', () => {
  assert.match(compose, /selahcue-web-graphql\.rule=Host\(`\$\{WEBSITE_DOMAIN:\?set WEBSITE_DOMAIN\}`\) && PathPrefix\(`\/graphql\/`\)/)
  assert.match(compose, /selahcue-web-graphql\.service=selahcue-api/)
  assert.match(compose, /SELAHCUE_TRUSTED_PROXY_COUNT:\s*"1"/)
  assert.match(nginx, /location \/graphql\/ \{[\s\S]*?proxy_pass \$selahcue_api\$request_uri;/)
  assert.match(nginx, /proxy_set_header X-Forwarded-Proto \$selahcue_client_proto;/)
  assert.match(nginx, /proxy_set_header Referer "";/)
})

test('email token landing paths remain reachable under their issued names', () => {
  assert.match(router, /path: '\/verify', name: 'verify'/)
  assert.match(router, /path: '\/reset', name: 'reset'/)
  assert.match(emailTasks, /\/verify\?token=/)
  assert.match(emailTasks, /\/reset\?token=/)
})

test('marketing access logs contain only normalized path and safe request metrics', () => {
  const format = /log_format\s+selahcue_safe\s+([^;]+);/.exec(nginx)?.[1]
  assert.ok(format, 'a named content-free access format is required')
  assert.match(format, /\$uri\b/)
  for (const field of ['$request_method', '$status', '$body_bytes_sent', '$request_time']) {
    assert.ok(format.includes(field), `${field} must be available for safe diagnostics`)
  }
  assert.doesNotMatch(format, /\$(?:request(?:_uri)?|args|query_string|http_referer|http_cookie|http_authorization|request_body)\b/)
  assert.match(nginx, /access_log\s+\/dev\/stdout\s+selahcue_safe\s*;/)
  assert.match(nginx, /error_log\s+\/dev\/null\s*;/)
})

test('token landing routes suppress access logs for case and trailing slash variants', () => {
  const landing = /location\s+~\*\s+\^\/\(verify\|reset\)\(\?:\/\|\$\)\s*\{([^}]+)\}/.exec(nginx)?.[1]
  assert.ok(landing)
  assert.match(landing, /access_log\s+off\s*;/)
  assert.match(landing, /try_files\s+\/index\.html\s+=404\s*;/)
})

test('excluded admin and affiliate subpaths return 404 while closed affiliate landing remains', () => {
  for (const location of ['= /admin', '/admin/', '/affiliates/']) {
    assert.ok(nginx.includes(`location ${location} {`), `${location} must be excluded`)
  }
  assert.match(nginx, /location\s+=\s+\/affiliates\s*\{/)
})

test('release manifest revalidates as JSON with its own complete security headers', () => {
  const manifest = /location\s+=\s+\/releases\/current\.json\s*\{([^}]+)\}/.exec(nginx)?.[1]
  assert.ok(manifest)
  assert.match(manifest, /default_type\s+application\/json\s*;/)
  assert.match(manifest, /add_header\s+Cache-Control\s+"no-cache, must-revalidate"\s+always\s*;/)
  for (const header of ['X-Frame-Options', 'X-XSS-Protection', 'X-Content-Type-Options', 'Referrer-Policy', 'Content-Security-Policy']) {
    assert.ok(manifest.includes(`add_header ${header} `), `${header} must not be lost to add_header inheritance`)
  }
})
