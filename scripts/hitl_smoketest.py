# Explanation:
# Smoke test that exercises the same nested SMTP wiring (settings.smtp.*)
# and sends a test message to an organizer address or HITL operator fallback.

import asyncio
import sys
from types import SimpleNamespace
from pathlib import Path

# Ensure repo root is on sys.path when running as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.config import settings  # noqa: E402
from utils.email_agent import EmailAgent  # noqa: E402


def _build_comm_backend() -> SimpleNamespace:
    smtp = settings.smtp
    required = ("host", "port", "username", "password", "sender")
    missing = [k for k in required if not getattr(smtp, k, None)]
    if missing:
        raise RuntimeError(f"Incomplete SMTP config: missing {', '.join(missing)}")

    email_agent = EmailAgent(
        host=smtp.host,
        port=int(smtp.port),
        username=smtp.username,
        password=smtp.password,
        sender=smtp.sender,
        use_tls=bool(getattr(smtp, "secure", True)),
    )
    return SimpleNamespace(email=email_agent)


async def main() -> None:
    backend = _build_comm_backend()

    # Prefer explicit TEST_EVENT_ORGANIZER_EMAIL if you set one, else HITL operator
    to_addr = (
        getattr(settings, "test_event_organizer_email", None)
        or settings.hitl.operator_email
    )
    if not to_addr:
        raise RuntimeError(
            "No recipient configured. Set TEST_EVENT_ORGANIZER_EMAIL or HITL_OPERATOR_EMAIL."
        )

    subject = "HITL smoke test · Lead-Market-Insights"
    body = (
        "This is a smoke test for the HITL email wiring.\n\n"
        "If you received this, the SMTP integration is working correctly.\n"
    )
    headers = {"X-Run-ID": "smoketest", "X-HITL": "1", "X-Component": "HITL-SmokeTest"}

    msg_id = backend.email.send_email(to_addr, subject, body, headers=headers)
    print(f"Smoke test sent. message_id={msg_id} to={to_addr}")


if __name__ == "__main__":
    asyncio.run(main())
