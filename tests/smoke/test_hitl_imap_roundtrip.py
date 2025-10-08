from __future__ import annotations

import imaplib
import os
from typing import List

import pytest


REQUIRED_ENV_VARS: List[str] = [
    "HITL_SMOKE_IMAP_HOST",
    "HITL_SMOKE_IMAP_USER",
    "HITL_SMOKE_IMAP_PASSWORD",
]


def test_hitl_imap_roundtrip() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        pytest.skip(
            "Skipping HITL IMAP smoke test; missing environment variables: "
            + ", ".join(missing)
        )

    host = os.environ["HITL_SMOKE_IMAP_HOST"]
    user = os.environ["HITL_SMOKE_IMAP_USER"]
    password = os.environ["HITL_SMOKE_IMAP_PASSWORD"]
    port = int(os.getenv("HITL_SMOKE_IMAP_PORT", "993"))
    mailbox = os.getenv("HITL_SMOKE_IMAP_MAILBOX", "INBOX")

    with imaplib.IMAP4_SSL(host, port) as client:
        status, _ = client.login(user, password)
        assert status == "OK"

        status, _ = client.select(mailbox)
        assert status == "OK", f"Unable to select mailbox {mailbox}"

        client.logout()
