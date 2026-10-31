const raw = $input.first().json;
// The generator prefixes the single reviewed, nonsecret deployment configuration.
// Browser query/form fields can never replace it.
const apiOrigin = deployment.api_origin;
const noticeVersion = deployment.notice_version;
const errors = [];
const identifier = value => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(value) && !/replace|draft/i.test(value);
const origin = value => typeof value === 'string' && /^https:\/\/[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(value) && !/replace/i.test(value);
const platforms = {Windows:['x86_64'], Ubuntu:['x86_64'], macOS:['x86_64','aarch64']};
const keys = ['schema_version','api_origin','notice_version','form_path','artifact_id','release_id','version','platform','architectures','sha256','size_bytes','object_key','download_origin','signed_query_keys','max_ttl_seconds'];
const forbidden = new Set(['receipt','registration_id','email','name','full_name','phone','church_name','openai_api_key','deepgram_api_key','redirect','url','response-content-disposition']);
const configValid = deployment && typeof deployment === 'object' && Object.keys(deployment).length === keys.length &&
  keys.every(key => Object.hasOwn(deployment,key)) && deployment.schema_version === 1 &&
  origin(apiOrigin) && origin(deployment.download_origin) &&
  ['notice_version','form_path','artifact_id','release_id','version'].every(key => identifier(deployment[key])) &&
  Object.hasOwn(platforms,deployment.platform) && Array.isArray(deployment.architectures) &&
  JSON.stringify(deployment.architectures) === JSON.stringify(platforms[deployment.platform]) &&
  typeof deployment.sha256 === 'string' && /^[a-f0-9]{64}$/.test(deployment.sha256) &&
  Number.isSafeInteger(deployment.size_bytes) && deployment.size_bytes > 0 && deployment.size_bytes <= 20*1024**3 &&
  typeof deployment.object_key === 'string' && deployment.object_key.startsWith('pilot/'+deployment.release_id+'/'+deployment.sha256+'/') &&
  /^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$/.test(deployment.object_key.slice(('pilot/'+deployment.release_id+'/'+deployment.sha256+'/').length)) &&
  Number.isSafeInteger(deployment.max_ttl_seconds) && deployment.max_ttl_seconds >= 1 && deployment.max_ttl_seconds <= 300 &&
  Array.isArray(deployment.signed_query_keys) && deployment.signed_query_keys.length >= 1 && deployment.signed_query_keys.length <= 20 &&
  new Set(deployment.signed_query_keys).size === deployment.signed_query_keys.length &&
  deployment.signed_query_keys.every(key => typeof key === 'string' && /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(key) && !forbidden.has(key.toLowerCase()));
if (!configValid) errors.push('Pilot registration and download delivery have not been configured yet.');
const read = (label, max = 200, optional = false) => {
  const value = raw[label] === undefined && optional ? '' : raw[label];
  if (typeof value !== 'string' || value.length > max || /[\x00-\x1f\x7f]/.test(value)) {
    errors.push('Check the form field values and try again.');
    return '';
  }
  if (!optional && !value.trim()) errors.push('Complete all required fields.');
  return value.trim();
};
const payload = {
  schema_version: 1,
  registration_id: read('registration_id', 36),
  platform: read('platform', 20),
  full_name: read('Full name'), email: read('Email', 254).toLowerCase(),
  phone: read('Phone (optional)', 50, true), church_name: read('Church name'),
  church_role: read('Role at church'), church_city: read('Church city'),
  church_country: read('Church country'), notice_version: noticeVersion,
};
if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(payload.registration_id))
  errors.push('Return to the marketing page to start or resume this registration.');
if (!['Windows', 'Ubuntu', 'macOS'].includes(payload.platform))
  errors.push('Return to the marketing page and select your platform.');
else if (payload.platform !== deployment.platform)
  errors.push('This form is for the package shown above. Return to the marketing page and choose the matching platform.');
if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) errors.push('Enter a valid email address.');
return [{ json: { valid: errors.length === 0, errors: [...new Set(errors)].join(' '),
  api_origin: apiOrigin, deployment, payload } }];
