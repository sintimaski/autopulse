# Alert Delivery Verification Runbook

This runbook validates that alert delivery is configured and observable from the dashboard.

## 1) Configure sender mode

Set one of the minimal sender configurations:

- Email provider (recommended first):
  - `ALERT_SENDER_MODE=email`
  - `ALERT_EMAIL_PROVIDER=resend` (or `postmark`)
  - `ALERT_EMAIL_API_KEY=...`
  - `ALERT_EMAIL_FROM=alerts@example.com`
- Slack webhook:
  - `ALERT_SENDER_MODE=slack`
  - `ALERT_SLACK_WEBHOOK_URL=...`
- Discord webhook:
  - `ALERT_SENDER_MODE=discord`
  - `ALERT_DISCORD_WEBHOOK_URL=...`
- Multi-channel:
  - `ALERT_SENDER_MODE=composite`
  - combine email + Slack and/or Discord vars above.

## 2) Trigger one evaluation pass

```bash
uv run python -m autopulse_backend.jobs alerts-once
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
