# SelahCue Platform API

This root contains the Django + Strawberry backend for SelahCue Admin licensing and future customer account surfaces.

Current slice:

- Staff Admin GraphQL endpoint: `/graphql/admin`
- Customer Account GraphQL endpoint: `/graphql/account`
- Desktop command API stubs under `/v1`
- Billing/provider webhook stub under `/webhooks/billing/<provider>`
- Domain app boundaries for accounts, billing, app license keys, Bible catalogue, entitlements, downloads, audit, and outbox-oriented work
- Durable customer-organisation creation/search for staff Admin GraphQL
- Durable app license-key issuance for staff Admin GraphQL: finite validity window, reason capture, idempotency key, masked metadata, show-once full key response, hash/fingerprint persistence, and audit event

The current implementation is a foundation plus the first Admin-side license-key issuance slice. It does not activate devices, issue device tokens, grant Bible entitlements, issue download leases, serve licensed Bible text, sync billing providers, store provider/signing secrets, or sign desktop policies. Header-derived actors remain a local/test development bridge until real staff IdP and customer identity are implemented.

Open owner decisions before production behaviour:

- Staff IdP, MFA, session TTL, and emergency access
- Customer identity model
- Hosting, database, object store, and KMS/secrets provider
- Policy envelope cryptographic suite and key rotation
- First licensed translations, territories, offline grace, deletion SLA, export/copy caps, and provider reporting payloads
- Retention/deletion periods by data class

Local verification, from the repository root after installing dependencies into a throwaway environment:

```bash
/private/tmp/selahcue-api-venv/bin/python -m pytest implementation/api/tests -q
/private/tmp/selahcue-api-venv/bin/python implementation/api/manage.py check
/private/tmp/selahcue-api-venv/bin/python -m compileall implementation/api
```
