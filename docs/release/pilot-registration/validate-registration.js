const raw = $input.first().json;
// Deployment configuration; replace only after notice/policy approval. No secrets here.
const apiOrigin = 'https://REPLACE_WITH_API_HOST.invalid';
const noticeVersion = 'REPLACE_WITH_APPROVED_NOTICE';
const errors = [];
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
if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) errors.push('Enter a valid email address.');
if (!/^https:\/\/[^/?#\s]+$/.test(apiOrigin) || apiOrigin.includes('REPLACE') ||
    noticeVersion.includes('REPLACE') || /draft/i.test(noticeVersion))
  errors.push('Pilot registration has not been configured for collection yet.');
return [{ json: { valid: errors.length === 0, errors: [...new Set(errors)].join(' '),
  api_origin: apiOrigin, payload } }];
