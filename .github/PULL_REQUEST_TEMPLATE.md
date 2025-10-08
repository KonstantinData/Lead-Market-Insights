# HITL Phase 1 — Pending Decisions, Persistence, Templated Email Dispatch

## Summary

Implements Human-in-the-Loop Phase 1:

- No auto-approval (pending `HitlDecision`)
- Filesystem-backed persistence for pending/decision state
- Templated email dispatch with PII masking and correlation headers

## Changes

- `human_in_the_loop/hitl_module.py`: Introduce `HitlDecision` and return `status=None` for approval/info requests.
- `agents/human_in_loop_agent.py`: Add `persist_pending_request()`, `apply_decision()`, `dispatch_request_email()`, reminder wiring hook.
- `templates/loader.py` + `templates/hitl_request_email.txt`: Minimal renderer + HITL request template.
- `agents/email_agent.py`: SMTP client with STARTTLS + credential guard.
- Tests: unit for module, agent, email; e2e pipeline stubs.

## Tests & Coverage

- `pytest -q` → **378 passed**, 2 warnings
- Coverage: **91.35%** (threshold ≥ 50%)
- Key suites:
  - `tests/unit/test_hitl_module.py`
  - `tests/unit/test_human_in_loop_agent.py`
  - `tests/unit/test_utils_email_agent.py`
  - (Optional) `tests/unit/test_hitl_pipeline_e2e.py`

## Configuration & Secrets

- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS=true`
- IMAP (for later phases/inbox agent runs): `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_FOLDER=INBOX`
- Workflow dir: `WORKFLOW_LOG_DIR` (defaults per `config/config.py`)
- Guards: Missing SMTP creds → **fail-fast** (RuntimeError)

## E2E – Manuelle Abnahme (local, plain SMTP)

1. Set credentials (env or `.env` consumed by `config/config.py`):
   ```bash
   set SMTP_HOST=smtp.example.com
   set SMTP_PORT=587
   set SMTP_USERNAME=mailer@example.com
   set SMTP_PASSWORD=********
   set SMTP_USE_TLS=true
   ```
