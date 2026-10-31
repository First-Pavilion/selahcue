import assert from 'node:assert/strict'
import test from 'node:test'
import { parsePilotConfig, pilotEntryState, loadPilotConfig, registrationLink, registrationIdentity } from '../src/lib/pilot/downloads.ts'

const now = Date.parse('2026-11-01T12:00:00Z')
const ready = () => ({
  schema_version: 1, enabled: true,
  form_origin: 'https://registration.example.org',
  notice: { approved: true, version: 'pilot-v1', url: 'https://selahcue.example.org/pilot-privacy', data_owner: 'Pilot coordinator', retention_days: 180 },
  entries: [{ platform: 'Windows', architecture: 'x64', version: '0.1.0-pilot.1', release_id: 'pilot-1', expires_at: '2027-04-30T23:59:59Z', available: true, registration_url: 'https://registration.example.org/form/pilot-windows' }],
})

test('valid configuration exposes only the configured registration URL and exact metadata', () => {
  const c = parsePilotConfig(ready())
  assert.equal(c.entries[0]?.version, '0.1.0-pilot.1')
  assert.equal(pilotEntryState(c, 'Windows', 'x64', now).url, ready().entries[0]?.registration_url)
  assert.equal(pilotEntryState(c, 'Ubuntu', 'x64', now).status, 'unavailable')
})
test('disabled deployment needs no invented settings and provides no navigation', () => {
  const c = parsePilotConfig({ schema_version: 1, enabled: false })
  assert.equal(pilotEntryState(c, 'Windows', 'x64', now).url, undefined)
})
test('expiry is enforced at the exact boundary, also after the page clock advances', () => {
  const c = parsePilotConfig(ready())
  const expires = Date.parse(c.entries[0]!.expires_at)
  assert.equal(pilotEntryState(c, 'Windows', 'x64', expires - 1).status, 'ready')
  assert.equal(pilotEntryState(c, 'Windows', 'x64', expires).status, 'expired')
  assert.equal(pilotEntryState(c, 'Windows', 'x64', expires + 1).url, undefined)
})
test('unavailable entry never exposes a form URL', () => {
  const x=ready(); x.entries[0]!.available=false
  assert.equal(pilotEntryState(parsePilotConfig(x),'Windows','x64',now).url,undefined)
})
test('unsupported architectures cannot borrow a different platform package', () => {
  const c=parsePilotConfig(ready())
  assert.equal(pilotEntryState(c,'Windows','arm64',now).url,undefined)
  assert.equal(pilotEntryState(c,'macOS','x64',now).url,undefined)
})
test('missing or unapproved collection policy fails closed', () => {
  for (const field of ['version','url','data_owner','retention_days']) {
    const x=ready() as unknown as {notice:Record<string,unknown>}; delete x.notice[field]
    assert.throws(()=>parsePilotConfig(x))
  }
  const x=ready(); x.notice.approved=false; assert.throws(()=>parsePilotConfig(x))
  x.notice.approved=true; x.notice.version='DRAFT-v1'; assert.throws(()=>parsePilotConfig(x))
})
test('unsafe or non-form navigation is rejected instead of becoming a bucket bypass', () => {
  for (const url of ['http://registration.example.org/form/a','javascript:alert(1)','https://evil.example/form/a','https://registration.example.org/releases/app.exe','https://user:pass@registration.example.org/form/a','https://registration.example.org/form/a#token','https://registration.example.org/form/a?receipt=x']) {
    const x=ready(); x.entries[0]!.registration_url=url; assert.throws(()=>parsePilotConfig(x),url)
  }
})
test('unknown download URL fields and duplicate targets are rejected', () => {
  const x=ready(); Object.assign(x.entries[0]!,{download_url:'https://bucket.example/a.exe'}); assert.throws(()=>parsePilotConfig(x))
  const y=ready(); y.entries.push({...y.entries[0]!}); assert.throws(()=>parsePilotConfig(y))
})
test('invalid timestamps, platform, release labels and architectures fail closed', () => {
  for(const [key,value] of [['expires_at','tomorrow'],['expires_at','2027-04-31T23:59:59Z'],['expires_at','2027-04-30'],['platform','Linux'],['architecture','universal'],['version',''],['release_id','']]) {
    const x=ready(); Object.assign(x.entries[0]!,{[key]:value}); assert.throws(()=>parsePilotConfig(x),key+' '+value)
  }
})
test('fetch uses same-origin configuration without browser personal data or credentials', async()=>{
  let seen:RequestInit|undefined
  const c=await loadPilotConfig(async(url,init)=>{
    assert.equal(url,'/pilot-downloads.json'); seen=init
    return new Response(JSON.stringify(ready()),{headers:{'Content-Type':'application/json'}})
  })
  assert.equal(c.enabled,true); assert.equal(seen?.cache,'no-store'); assert.equal(seen?.credentials,'omit')
})
test('non-JSON, failed fetch, oversized responses and invalid payloads reject for retry', async()=>{
  for(const response of [new Response('<html>SPA</html>',{headers:{'Content-Type':'text/html'}}), new Response('{}',{status:503}), new Response('x'.repeat(40000),{headers:{'Content-Type':'application/json'}}),new Response('{}',{headers:{'Content-Type':'application/json'}})]) {
    await assert.rejects(()=>loadPilotConfig(async()=>response))
  }
  await assert.rejects(()=>loadPilotConfig(async()=>{throw new Error('network')}))
})

const uuid = '4def836a-5c29-4f42-831d-af259324eeae'
test('registration handoff includes only stable untrusted identity and platform, no PII/auth', () => {
  const u=new URL(registrationLink('https://registration.example.org/form/pilot','Ubuntu',uuid))
  assert.deepEqual([...u.searchParams.keys()],['registration_id','platform'])
  assert.equal(u.searchParams.get('registration_id'),uuid)
  assert.equal(u.searchParams.get('platform'),'Ubuntu')
  assert.throws(()=>registrationLink('https://registration.example.org/form/pilot','Windows','not-a-uuid'))
})
test('same attempt retains UUID across re-click/reload; explicit reset alone rotates it', () => {
  const values=new Map<string,string>()
  const storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)}}
  let calls=0
  const generate=()=>{calls++;return uuid}
  assert.equal(registrationIdentity(storage,'Windows:x64:pilot-1',generate),uuid)
  assert.equal(registrationIdentity(storage,'Windows:x64:pilot-1',generate),uuid)
  assert.equal(calls,1)
  registrationIdentity(storage,'Windows:x64:pilot-1',generate,true)
  assert.equal(calls,2)
  assert.equal([...values.values()][0],uuid)
})
test('storage failure or corrupt UUID cannot silently replace an ambiguous registration',()=>{
  const broken={getItem:()=>{throw new Error('blocked')},setItem:()=>{}}
  assert.throws(()=>registrationIdentity(broken,'x',()=>uuid))
  const corrupt={getItem:()=> 'bad',setItem:()=>{throw new Error('must not overwrite')}}
  assert.throws(()=>registrationIdentity(corrupt,'x',()=>uuid))
})


test('JSON-like media types do not pass the configuration boundary', async()=>{
  await assert.rejects(()=>loadPilotConfig(async()=>new Response(JSON.stringify(ready()),{headers:{'Content-Type':'application/jsonp'}})))
})
