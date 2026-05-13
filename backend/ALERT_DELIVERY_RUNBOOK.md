# Alert Delivery Verification Runbook

This runbook validates that alert delivery is configured and observable from the dashboard.

## 1) Configure sender mode

Set one of the minimal sender configurations:

- Email provider (recommended first):
  - `ALERT_SENDER_MODE=email`
  - `ALERT_EMAIL_PROVIDER=resend` (or `postmark`)
  - `ALERT_EMAIL_API_KEY=...`
  - `ALERT_EMAIL_FROM=alerts@example.com`
- Email (zero-config dev outbox; writes `.eml` locally):
  - `ALERT_SENDER_MODE=email`
  - `ALERT_EMAIL_PROVIDER=file`
  - optional: `ALERT_EMAIL_FILE_OUTBOX_DIR=./.lumonox/emails`
  - optional: `ALERT_EMAIL_FROM=alerts@localhost`
- Email (no SaaS, requires local MTA present):
  - `ALERT_SENDER_MODE=email`
  - `ALERT_EMAIL_PROVIDER=sendmail`
  - optional: `ALERT_SENDMAIL_PATH=/usr/sbin/sendmail`
- Email (no SaaS, requires SMTP server reachable):
  - `ALERT_SENDER_MODE=email`
  - `ALERT_EMAIL_PROVIDER=smtp`
  - `ALERT_EMAIL_SMTP_HOST=127.0.0.1` (or your SMTP host)
  - optional: `ALERT_EMAIL_SMTP_PORT=25`
  - optional: `ALERT_EMAIL_SMTP_USE_TLS=true`
  - optional: `ALERT_EMAIL_SMTP_USERNAME=...`
  - optional: `ALERT_EMAIL_SMTP_PASSWORD=...`
- Slack webhook:
  - `ALERT_SENDER_MODE=slack`
  - `ALERT_SLACK_WEBHOOK_URL=...`
  - Payload shape matches Slack Incoming Webhooks: JSON `{"text": "<summary>"}` (no Block Kit in MVP).
- Discord webhook:
  - `ALERT_SENDER_MODE=discord`
  - `ALERT_DISCORD_WEBHOOK_URL=...`
- Multi-channel:
  - `ALERT_SENDER_MODE=composite`
  - combine email + Slack and/or Discord vars above.

**Outbound webhook URL rules (dashboard project settings + global `ALERT_*_WEBHOOK_URL`):**

- **Staging / production (`LUMONOX_ENV`):** `https` only; host must resolve to **public** unicast addresses (private IPs, loopback, and link-local are rejected). No userinfo in the URL.
- **Development:** same as above for `https`, or **`http` only to `127.0.0.1` / `localhost`** for local receivers.
- **Pacing:** set `ALERT_WEBHOOK_MIN_INTERVAL_SECONDS` (default `1`, use `0` to disable spacing) to avoid hammering a destination when multiple channels fire in one evaluation. Pacing is **DB-coordinated** via the `alert_webhook_pacing` table so multi-replica deployments share the same minimum interval per webhook URL; the helper degrades to in-process pacing when the DB is unreachable so a transient DB outage cannot stall alert delivery.

**Operator-health alerts gate:** the `alerts` subsystem row on `GET /dashboard/operator-health` surfaces `alerts.webhook.send.failed` / `alerts.webhook.validation_rejected` counters in its summary on every non-zero value. It flips to `degraded` only when send failures reach `5` or validation rejections reach `10` per process — so a single transient failure (DNS blip, one-off 503, one bad URL pasted into the dashboard) is visible but does not page operators. See `ALERTS_WEBHOOK_*_DEGRADED_THRESHOLD` constants in `backend/src/lumonox_backend/api/routes/health.py`.

## 2) Trigger one evaluation pass

```bash
uv run python -m lumonox_backend.jobs alerts-once
```

The command prints the number of successfully sent alerts in that run.

## 3) Validate dispatch observability

Open the dashboard Alerts page and verify dispatch rows include:

- `status` (`sent`, `failed`, or `skipped`)
- `reason_code` for failures/skips
- `attempt_count`
- `delivered_at` (for successful sends)
- `provider_message_id` when available

Use the **Failed only** filter to quickly review actionable delivery failures.

## 4) Notification mute, snooze, and acknowledge (project settings)

These fields live on `GET`/`PUT` `/dashboard/alert-settings` (dashboard session required for `PUT`; API key fallback is read-only for policy changes).

| Field | Behavior |
|-------|----------|
| `notifications_muted` | When `true`, the scheduled alert job **does not send** error-spike or outage alerts for this project. Heuristics still appear in the UI. |
| `notifications_snoozed_until` | UTC timestamp; while `now` is before this instant, sends are skipped (same as mute for delivery). Past timestamps are treated as inactive. |
| `last_notifications_acknowledged_at` | Read-only marker set when `PUT` includes `"acknowledge_notifications": true`. Does not change thresholds; use for operator bookkeeping. |
| `acknowledge_notifications` | Optional write-only flag on `PUT` only. |

**Test alerts** (`POST /dashboard/alert-test`) still run when muted/snoozed so channels can be verified without waiting for a real incident.
