"""Mutation runner for 17tnw2b1we2 (PR #215): applies ONE source mutation at a time to
selahcue-licensing / selahcue-cloud, runs the relevant tests, reports KILLED / SURVIVED, restores
the file.

IT EDITS SOURCE FILES IN PLACE, so it refuses to start unless
  * the current directory is inside a DEDICATED linked git worktree (not the main checkout, which
    other sessions share), and
  * `git status --porcelain` is empty (everything committed), so a restore can never lose work.
Each file is restored in a `finally` block; at the end the tree is checked clean again.

Exit code: 0 only when EVERY mutation was KILLED. A SURVIVED mutant, a COMPILE-ERROR, a pattern that
no longer matches the source, a name filter that selects nothing, or a dirty tree afterwards all
exit non-zero.

  git worktree add -b mutate-check ../mutate-check <commit>   # a dedicated worktree
  cd ../mutate-check && python3 docs/delivery/goals/17tnw2b1we2-evidence/mutate.py [name-prefix ...]
  python3 docs/delivery/goals/17tnw2b1we2-evidence/mutate.py --self-test   # the guard, no edits
"""
import subprocess, os, sys, re


def git(*args):
    return subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout.strip()


def guard(git_dir, common_dir, porcelain):
    """Why mutation testing must NOT start here, or None."""
    if os.path.realpath(git_dir) == os.path.realpath(common_dir):
        return 'this is the main checkout, not a dedicated linked worktree (git worktree add ...)'
    if porcelain.strip():
        return 'the working tree is not clean; commit or discard first so a restore cannot lose work'
    return None


def self_test():
    cases = [
        ('linked worktree, clean', '/r/.git/worktrees/w', '/r/.git', '', False),
        ('main checkout, clean', '/r/.git', '/r/.git', '', True),
        ('linked worktree, modified file', '/r/.git/worktrees/w', '/r/.git', ' M a.rs\n', True),
        ('linked worktree, untracked file', '/r/.git/worktrees/w', '/r/.git', '?? new.rs\n', True),
        ('main checkout, dirty', '/r/.git', '/r/.git', ' M a.rs\n', True),
    ]
    bad = 0
    for label, gd, cd, porcelain, should_refuse in cases:
        reason = guard(gd, cd, porcelain)
        good = (reason is not None) == should_refuse
        bad += not good
        print(('ok   ' if good else 'FAIL ') + label + (f' -> refused: {reason}' if reason else ' -> accepted'))
    print('self-test:', 'FAILED' if bad else 'passed')
    return 1 if bad else 0


if '--self-test' in sys.argv:
    sys.exit(self_test())

_refusal = guard(git('rev-parse', '--absolute-git-dir'), git('rev-parse', '--path-format=absolute', '--git-common-dir'),
                 git('status', '--porcelain'))
if _refusal:
    sys.exit('REFUSING TO RUN: ' + _refusal)
REPO = git('rev-parse', '--show-toplevel')
ROOT = REPO + '/implementation/desktop'
LIC = ROOT + '/crates/selahcue-licensing/src/'
CLD = ROOT + '/crates/selahcue-cloud/src/'
env=dict(os.environ)
LIC_SUITE=['cargo','test','-p','selahcue-licensing','--no-fail-fast']
CLD_SUITE=['cargo','test','-p','selahcue-cloud','--features','http','--no-fail-fast','--test','test_wire','--test','test_secret_store']

def rep(old,new):
    def f(o):
        assert o.count(old)==1, 'PATTERN NOT FOUND/AMBIGUOUS: '+old[:70]
        return o.replace(old,new,1)
    return f
def app(line):
    return lambda o: o+'\n'+line+'\n'

SESSION_ARGS='''            device_fingerprint: identity.fingerprint.clone(),
            platform: identity.platform.clone(),
            app_version: identity.app_version.clone(),
            display_name: identity.display_name.clone(),
        };
        let body = Self::encode(&request)?;
        let response = self.post(ACTIVATIONS_WITH_SESSION_PATH'''
def onfirst(old,new):  # first occurrence only (session body precedes the key body)
    def f(o):
        assert old in o, 'PATTERN NOT FOUND: '+old[:70]
        return o.replace(old,new,1)
    return f
def onlast(old,new):
    def f(o):
        assert old in o, 'PATTERN NOT FOUND: '+old[:70]
        i=o.rindex(old); return o[:i]+new+o[i+len(old):]
    return f

M=[]
def add(name,f,fn,suite='lic'): M.append((name,f,fn,suite))

# --- reviewers' surviving mutants -------------------------------------------------------
add('S1 session: app_version and display_name swapped','client.rs',onfirst('app_version: identity.app_version.clone(),\n            display_name: identity.display_name.clone(),','app_version: identity.display_name.clone(),\n            display_name: identity.app_version.clone(),'))
add('S2 session: platform from app_version','client.rs',onfirst('platform: identity.platform.clone(),\n            app_version: identity.app_version.clone(),','platform: identity.app_version.clone(),\n            app_version: identity.app_version.clone(),'))
add('S3 session: display_name blank','client.rs',onfirst('display_name: identity.display_name.clone(),','display_name: String::new(),'))
add('S4 enrollment: platform/app_version swapped','client.rs',onlast('platform: identity.platform.clone(),\n            app_version: identity.app_version.clone(),','platform: identity.app_version.clone(),\n            app_version: identity.platform.clone(),'))
add('S4b enrollment: display_name blank','client.rs',onlast('display_name: identity.display_name.clone(),','display_name: String::new(),'))
add('S4c enrollment: idempotency key from fingerprint','client.rs',onlast('idempotency_key: idempotency_key.as_str().to_string(),','idempotency_key: identity.fingerprint.clone(),'))
add('S4d enrollment: fingerprint from display_name','client.rs',onlast('device_fingerprint: identity.fingerprint.clone(),','device_fingerprint: identity.display_name.clone(),'))
add('S4e session: fingerprint blank','client.rs',onfirst('device_fingerprint: identity.fingerprint.clone(),','device_fingerprint: String::new(),'))
add('G1 URL literal with // before graphql','client.rs',app('const _G1: &str = "https://h/graphql/account";'))
add('G4 concat!("graph","ql")','client.rs',app('const _G4: &str = concat!("graph", "ql");'))
add('G8 "Referer" after // on the same line','client.rs',app('const _G8: (&str, &str) = ("a//b", "Referer");'))
add('G2 plain Cookie literal','client.rs',app('const _G2: &str = "Cookie";'))
add('G6 Origin literal','client.rs',app('const _G6: &str = "Origin";'))
add('G7 X-CSRF-Token literal','client.rs',app('const _G7: &str = "X-CSRF-Token";'))
add('X23 bare 429 -> UnexpectedStatus','client.rs',rep('if status == 429 {\n            classify(ErrorCode::RateLimited)\n        } else if (500..600)','if (500..600)'))
add('X25 sign-in lowercases email','client.rs',rep('email: email.to_string(),','email: email.to_lowercase(),'))
add('X26 sign-in trims email','client.rs',rep('email: email.to_string(),','email: email.trim().to_string(),'))
add('M61 missing-field name forwards anything','client.rs',rep("let identifier = !name.is_empty()\n        && name.len() <= 40\n        && name.bytes().all(|b| b.is_ascii_lowercase() || b == b'_');\n    identifier.then_some(name)","let _ = name.len();\n    Some(name)"))
add('M61b missing-field length cap 40 -> 41','client.rs',rep('name.len() <= 40','name.len() <= 41'))
add('X5 code length cap < instead of <=','contract.rs',rep('value.len() <= MAX_CODE_LEN','value.len() < MAX_CODE_LEN'))
# --- new behaviour ------------------------------------------------------------------------
add('N1 INTERNAL 503 flattened to 500','client.rs',rep('ActivationFailure::Server(_) if (500..600).contains(&response.status) => {\n                    ActivationFailure::Server(response.status)\n                }\n                other => other,','other => other,'))
add('N2 blank device token accepted','client.rs',rep('.is_some_and(Self::unusable_bearer)','.is_some_and(|_| false)'))
add('N3 device-token check only empty (whitespace passes)','client.rs',rep('fn unusable_bearer(token: &Token) -> bool {\n        token.is_blank() || token.has_control_characters()','fn unusable_bearer(token: &Token) -> bool {\n        token.is_empty() || token.has_control_characters()'))
add('N4 control characters allowed in bearer','client.rs',rep('token.is_blank() || token.has_control_characters()','token.is_blank()'))
add('N5 activate_with_session sends a blank session','client.rs',rep('        if Self::unusable_bearer(session) {','        if false && Self::unusable_bearer(session) {'))
add('N6 sign_in accepts an unusable session token','client.rs',rep('if Self::unusable_bearer(&parsed.session_token) {','if false && Self::unusable_bearer(&parsed.session_token) {'))
add('N7 sign-in VALIDATION -> ValidationFailed','error.rs',rep('ErrorCode::ValidationFailed => ActivationFailure::SignInInvalidInput,\n',''))
add('N8 sign-in RATE_LIMITED -> RateLimited','error.rs',rep('ErrorCode::RateLimited => ActivationFailure::SignInRateLimited,\n',''))
add('N9 SignInRateLimited retryable','error.rs',rep('ActivationFailure::Server(_)\n                | ActivationFailure::RateLimited','ActivationFailure::Server(_)\n                | ActivationFailure::SignInRateLimited\n                | ActivationFailure::RateLimited'))
add('N10 sign-in copy says activation','error.rs',rep('"too many sign-in attempts from this network; wait a minute before trying again"','"too many activation attempts from this network; wait a minute before trying again"'))
add('N10b sign-in invalid copy says activation','error.rs',rep('"the email address or password is not in a form the platform accepts; \\\n                 check both and try again"','"the activation request is not in a form the platform accepts; \\\n                 check both and try again"'))
add('N11 token metadata defaulted','contract.rs',rep('    pub device: DeviceDto,\n    /// Always present','    pub device: DeviceDto,\n    #[serde(default)]\n    /// Always present'))
add('N12 license expires_at defaulted','contract.rs',rep('    /// Python `isoformat()` — see [`TokenMetaDto::expires_at`]. Always sent by the server.\n    pub expires_at: String,','    #[serde(default)]\n    pub expires_at: String,'))
# --- carried over from round 0 -------------------------------------------------------------
add('M1 serde message forwarded','client.rs',rep('ActivationFailure::Malformed(format!(\n            "the response body {what} (line {}, column {}{field})",\n            error.line(),\n            error.column()\n        ))','ActivationFailure::Malformed(error.to_string())'))
add('M2 parse cap removed','client.rs',rep('if response.body.len() > MAX_RESPONSE_BODY_BYTES {','if false && response.body.len() > MAX_RESPONSE_BODY_BYTES {'))
add('M2b cap off by one (>=)','client.rs',rep('if response.body.len() > MAX_RESPONSE_BODY_BYTES {','if response.body.len() >= MAX_RESPONSE_BODY_BYTES {'))
add('M3 sign-in classified like activation','client.rs',rep('Self::decode(response, ActivationFailure::from_sign_in_code)?','Self::decode(response, |c| ActivationFailure::from_code(c, ActivationPath::AccountSession))?'))
add('M4 code shape unchecked','contract.rs',rep('other if is_code_shaped(other) =>','other =>'))
add('M5 sessions route -> graphql','contract.rs',rep('pub const SESSIONS_PATH: &str = "/v1/sessions";','pub const SESSIONS_PATH: &str = "/graphql/account";'))
add('M6 over-cap error body parsed anyway','client.rs',rep('            return Err(if ok {','            if !ok { return Err(Self::error(&response, classify)); }\n            return Err(if ok {'))
add('M7 unverified account -> PolicyDenied','error.rs',rep('ErrorCode::PolicyDenied => ActivationFailure::AccountNotActive,','ErrorCode::PolicyDenied => ActivationFailure::PolicyDenied,'))
add('M8 bearer dropped from session activation','client.rs',rep('self.post(ACTIVATIONS_WITH_SESSION_PATH, &body, Some(session))?','self.post(ACTIVATIONS_WITH_SESSION_PATH, &body, None)?'))
add('M10 2xx range widened','client.rs',rep('let ok = (200..300).contains(&response.status);','let ok = (200..=300).contains(&response.status);'))
add('M11 trailing slash kept','client.rs',rep("self.base_url.trim_end_matches('/')","self.base_url.as_str()"))
add('M12 transport error -> Malformed','client.rs',rep('.map_err(|e| ActivationFailure::Unreachable(e.to_string()))','.map_err(|e| ActivationFailure::Malformed(e.to_string()))'))
add('M13 error codes case-insensitive','contract.rs',rep('pub fn parse(value: &str) -> Self {\n        match value {','pub fn parse(value: &str) -> Self {\n        match value.to_ascii_uppercase().as_str() {'))
add('M14 missing-field name dropped','client.rs',rep('let field = missing_field(&error.to_string())','let field = None::<&str>'))
add('M15 password trimmed','client.rs',rep('password: password.expose().to_string(),','password: password.expose().trim().to_string(),'))
add('M16 reminted defaulted','contract.rs',rep('    pub reminted: bool,','    #[serde(default)]\n    pub reminted: bool,'))
add('M17 bearer is something else','client.rs',rep('Some(session))?','Some(&Token::new("x")))?'))
add('M18 sign-in NOT_FOUND -> NoActiveLicense','error.rs',rep('ErrorCode::NotFound => ActivationFailure::Coded(ErrorCode::NotFound),','ErrorCode::NotFound => ActivationFailure::NoActiveLicense,'))
add('M19 idempotency key changes per call','client.rs',onfirst('idempotency_key: idempotency_key.as_str().to_string(),','idempotency_key: { static N: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0); format!("{}{}", idempotency_key.as_str(), N.fetch_add(1, std::sync::atomic::Ordering::SeqCst)) },'))
# --- cloud: the wire ----------------------------------------------------------------------
T='transport.rs'
add('W1 content-type header removed',T,rep('            .header("content-type", "application/json")\n            .body(body.to_string());','            .body(body.to_string());'),'cld')
add('W2 content-type text/plain',T,rep('.header("content-type", "application/json")','.header("content-type", "text/plain")'),'cld')
add('W3 bearer never sent',T,rep('        if let Some(t) = bearer {\n            req = req.bearer_auth(t);\n        }\n        let resp = req.send().map_err(|e| TransportError(e.to_string()))?;\n        read_bounded(resp)\n    }\n\n    fn get','        let _ = bearer;\n        let resp = req.send().map_err(|e| TransportError(e.to_string()))?;\n        read_bounded(resp)\n    }\n\n    fn get'),'cld')
add('W4 Cookie header added',T,rep('.header("content-type", "application/json")','.header("content-type", "application/json").header("cookie", "a=b")'),'cld')
add('W5 Origin header added',T,rep('.header("content-type", "application/json")','.header("content-type", "application/json").header("origin", "https://x")'),'cld')
add('W6 Referer header added',T,rep('.header("content-type", "application/json")','.header("content-type", "application/json").header("referer", "https://x")'),'cld')
add('W7 X-CSRFToken header added',T,rep('.header("content-type", "application/json")','.header("content-type", "application/json").header("x-csrftoken", "t")'),'cld')
add('W8 empty bearer sent when none',T,rep('        if let Some(t) = bearer {\n            req = req.bearer_auth(t);\n        }\n        let resp = req.send().map_err(|e| TransportError(e.to_string()))?;\n        read_bounded(resp)\n    }\n\n    fn get','        req = req.bearer_auth(bearer.unwrap_or(""));\n        let resp = req.send().map_err(|e| TransportError(e.to_string()))?;\n        read_bounded(resp)\n    }\n\n    fn get'),'cld')
add('W9 GET gains a content-type',T,rep('        let mut req = self.client.get(url);','        let mut req = self.client.get(url).header("content-type", "application/json");'),'cld')
add('K1 Token::is_blank = is_empty','secret.rs',rep('self.0.trim().is_empty()','self.0.is_empty()'),'cld')
add('K2 Token::has_control_characters = false','secret.rs',rep('self.0.chars().any(char::is_control)','false'),'cld')
add('K3 Token::has_control_characters ignores CR/LF','secret.rs',rep('self.0.chars().any(char::is_control)',"self.0.chars().any(|c| c.is_control() && c != '\\r' && c != '\\n')"),'cld')
# --- round 3 (PR #215): password case, copy, the 429 boundary --------------------------------
add('X28 sign-in lowercases the password','client.rs',rep('password: password.expose().to_string(),','password: password.expose().to_lowercase(),'))
add('N10c sign-in rate-limit copy loses "wait a minute"','error.rs',rep('wait a minute before trying again','try again later'))
add('B1 bare 429 boundary: >= 429','client.rs',rep('if status == 429 {','if status >= 429 {'))
add('B2 bare 429 boundary: 428 and 429','client.rs',rep('if status == 429 {','if (428..=429).contains(&status) {'))
add('B3 bare 429 boundary: 430 instead','client.rs',rep('if status == 429 {','if status == 430 {'))
add('B4 oversized 429 loses its status meaning','client.rs',rep('                Self::status_failure(response.status, &classify)\n            });','                ActivationFailure::UnexpectedStatus(response.status)\n            });'))

only=[a for a in sys.argv[1:] if not a.startswith('--')]
results={}
selected=[m for m in M if not only or any(m[0].startswith(o) for o in only)]
if not selected:
    sys.exit('no mutation name starts with any of: ' + ', '.join(only))
for name,f,fn,suite in selected:
    p=(LIC if suite=='lic' and f!='secret.rs' and f!='transport.rs' else CLD)+f
    orig=open(p).read()
    try:
        new=fn(orig)
    except AssertionError as e:
        print(name,'->','PATTERN-NOT-FOUND',e,flush=True); results[name]='PATTERN-NOT-FOUND'; continue
    open(p,'w').write(new)
    try:
        r=subprocess.run(LIC_SUITE if suite=='lic' else CLD_SUITE,cwd=ROOT,env=env,capture_output=True,text=True)
        out=r.stdout+r.stderr
        failed=sorted(set(l.split()[1] for l in out.splitlines() if l.startswith('test ') and l.endswith('FAILED')))
        ce='error[' in out or 'could not compile' in out
        status='SURVIVED' if r.returncode==0 else ('COMPILE-ERROR' if ce and not failed else 'KILLED')
        results[name]=status
        print(name,'->',status,len(failed),failed[:3],flush=True)
    finally:
        open(p,'w').write(orig)
dirty=git('status','--porcelain')
if dirty:
    print('TREE NOT CLEAN AFTER THE RUN (restore with git checkout -- <file>):\n'+dirty)
bad={k:v for k,v in results.items() if v!='KILLED'}
print(f'{len(results)} mutations: {len(results)-len(bad)} killed, {len(bad)} not killed', *(f'\n  {k}: {v}' for k,v in bad.items()))
sys.exit(1 if bad or dirty else 0)
