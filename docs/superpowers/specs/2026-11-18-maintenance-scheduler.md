# Maintenance-only scheduler safety
Ticket: [Production Platform API runtime](https://app.clickup.com/t/86ak11vwn).

The approved default production stack has maintenance workers only. Beat must not persist unconsumed provider jobs. This code slice does not deploy infrastructure or complete the ticket's operational acceptance criteria.

Requirements:
1. With provider scheduling settings omitted or disabled, beat retains usage.retention_sweep (60 seconds, celery queue), devices.cascade_license_revocations (hourly), and accounts.sweep_expired_credentials (03:30) only. Existing task routing stays intact.
2. Add independent non-secret settings SELAHCUE_BEAT_PROVIDER_PROVISIONING_ENABLED and SELAHCUE_BEAT_PROVIDER_USAGE_ENABLED, both default false. Each controls only its existing providers.sweep/usage.sweep entry and existing cadence/queue. Both may be true for a properly staffed cloud deployment.
3. These settings select schedules, not public cloud admission or credential roles. Never infer them from public feature flags. Maintenance beat retains its role, requires no provider secrets or file mounts, and does not bypass provider worker validation. Usage reconciliation may continue with public admission disabled.
4. Parse opt-ins as explicit booleans; invalid nonempty values fail startup with a fixed diagnostic naming only the setting, never echoing the raw value. Accepted forms follow documented existing boolean conventions.
5. Expose both settings only to the production beat service with off defaults. Enabling them requires operators to deploy and verify the matching dedicated consumers. Do not add consumers or secret mounts in this slice.
6. Tests must import real settings / Celery schedule configuration, test default/off and all combinations, retain maintenance entries, prove public flags alone do not enable schedules, and verify invalid input handling. No broker/network needed. Preserve task-registration and role validation controls.
7. Update root DEPLOYMENT.md, implementation/deploy/README.md and the relevant environment/reference sections to remove the now-fixed unconditional-schedule prerequisite and document exact configuration, rollback, and limitations. No production or cloud qualification claims.
