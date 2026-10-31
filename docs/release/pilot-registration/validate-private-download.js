const value = $input.first().json;
const selected = $('Validate registration').first().json;
const saved = $('Validate saved receipt').first().json;
const fixed = selected.deployment;
const now = Date.now()/1000;
const deny = () => {throw new Error('The selected download could not be confirmed. Return through the same marketing choice to retry. No download is authorized.');};
const keys = ['schema_version','artifact_id','release_id','platform','architectures','sha256','size_bytes','download_url','expires_at'];
if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length !== keys.length ||
    !keys.every(key => Object.hasOwn(value,key)) || value.schema_version !== 1 ||
    value.artifact_id !== fixed.artifact_id || value.release_id !== fixed.release_id ||
    value.platform !== fixed.platform || selected.payload.platform !== fixed.platform ||
    JSON.stringify(value.architectures) !== JSON.stringify(fixed.architectures) ||
    value.sha256 !== fixed.sha256 || value.size_bytes !== fixed.size_bytes ||
    !Number.isSafeInteger(value.expires_at) || value.expires_at <= now ||
    value.expires_at > Math.min(saved.expires_at,1809129599,Math.floor(now)+fixed.max_ttl_seconds) ||
    typeof value.download_url !== 'string' || value.download_url.length > 8192 || /[^\x21-\x7e]/.test(value.download_url)) deny();
// Exact reviewed HTTPS origin and immutable object path; no URL parser ambiguity,
// userinfo, fragment, alternate path encoding or response redirect is accepted.
const prefix = fixed.download_origin+'/'+fixed.object_key+'?';
if (!value.download_url.startsWith(prefix) || value.download_url.includes('#')) deny();
const query = value.download_url.slice(prefix.length).split('&');
if (!query.length || query.length > 20) deny();
const seen = new Set();
for (const pair of query) {
  const pieces = pair.split('=');
  if (pieces.length !== 2) deny();
  let key, content;
  try {key=decodeURIComponent(pieces[0].replace(/\+/g,' ')); content=decodeURIComponent(pieces[1].replace(/\+/g,' '));}
  catch {deny();}
  if (!fixed.signed_query_keys.includes(key) || seen.has(key) || !content || content.length > 2048 ||
      /[^\x20-\x7e]/.test(content) || content.includes(saved.receipt) || content.includes(selected.payload.registration_id)) deny();
  seen.add(key);
}
const escape = text => String(text).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
// Project only approved metadata and the bounded read URL. Receipt, identity and
// contact/church fields never become Form completion input or hidden fields.
const label = 'SelahCue '+fixed.version+' — '+value.platform+' ('+value.architectures.join(', ')+')';
const message = '<p>Your registration has been recorded.</p><p><a href="'+escape(value.download_url)+'" rel="noreferrer noopener">Download '+escape(label)+'</a></p>'+
  '<p>Size: '+value.size_bytes+' bytes<br>SHA-256: '+escape(value.sha256)+'<br>Link expires: '+escape(new Date(value.expires_at*1000).toISOString())+'</p>'+
  '<p>If the link expires, return through the same marketing download choice. Retries do not extend pilot access.</p>';
return [{json:{completion_html:message}}];
