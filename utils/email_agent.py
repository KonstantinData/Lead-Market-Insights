# -*- coding: utf-8 -*-
"""
utils/email_agent.py

# Explanation
# Robust SMTP client supporting:
# - SMTPS (implicit SSL, e.g. port 465)
# - STARTTLS (submission, e.g. port 587)
#
# Backwards compatible with legacy positional ctor:
#   EmailAgent(host, port, username, password, use_tls=True, timeout=30)
# and keyword ctor:
#   EmailAgent(smtp_server=..., smtp_port=..., username=..., password=..., sender_email=..., timeout=30)
#
# Methods:
#   - send_email(to_email, subject, body, headers=None) -> str | None
#   - send_email_async(to_email, subject, body, headers=None) -> str | None
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid, formatdate
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Self-test trace to verify the loaded module path at runtime
logger.info("EmailAgent module loaded from: %s", __file__)


class EmailAgent:
    def __init__(
        self,
        *args,
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        sender_email: Optional[str] = None,
        use_tls: Optional[bool] = None,
        timeout: int = 30,
        **kwargs: Any,
    ) -> None:
        # Legacy positional mapping
        if smtp_server is None and len(args) >= 4:
            smtp_server = args[0]
            smtp_port = args[1]
            username = args[2]
            password = args[3]
            if use_tls is None and len(args) >= 5:
                use_tls = bool(args[4])
            if (
                "timeout" not in kwargs
                and len(args) >= 6
                and isinstance(args[5], (int, float, str))
            ):
                try:
                    timeout = int(float(args[5]))  # type: ignore[arg-type]
                except Exception:
                    pass

        # Normalize inputs
        self.host = str(smtp_server or "").strip()
        self.port = int(smtp_port) if smtp_port is not None else None
        self.username = username
        self.password = password
        self.sender_email = (
            (sender_email or username or "").strip()
            if sender_email or username
            else None
        )
        # If unset, infer from ENV (SMTP_SECURE=true → prefer TLS)
        if use_tls is None:
            env_secure = os.getenv("SMTP_SECURE")
            use_tls = (
                None
                if env_secure is None
                else (env_secure.strip().lower() in {"1", "true", "yes", "on"})
            )
        self.use_tls = use_tls
        self.timeout = int(timeout) if timeout else 30

        if not self.host or self.port is None or not self.username or not self.password:
            raise ValueError(
                "SMTP configuration incomplete (host/port/username/password required)"
            )

        logger.info(
            "EmailAgent configured host=%s port=%s sender=%s mode=%s",
            self.host,
            self.port,
            self.sender_email or self.username,
            (
                f"implicit-SSL(465)"
                if self.port == 465
                else ("STARTTLS" if (self.port == 587 or self.use_tls) else "PLAIN")
            ),
        )

    # -------------- transport selection --------------

    def _select_transport(self) -> Dict[str, bool]:
        """
        Decide transport based on port and flags.
        465  -> implicit SSL
        587  -> STARTTLS
        else -> STARTTLS if use_tls True, otherwise plain
        """
        port = int(self.port)
        if port == 465:
            return {"ssl": True, "starttls": False}
        if port == 587:
            return {"ssl": False, "starttls": True}
        return {"ssl": False, "starttls": bool(self.use_tls)}

    # -------------- helpers --------------

    def _build_message(
        self,
        to_email: str,
        subject: str,
        body: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = self.sender_email or self.username
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(
            domain=(self.sender_email or self.username or "localhost").split("@")[-1]
        )
        if headers:
            for k, v in headers.items():
                if k and v:
                    msg[k] = v
        msg.set_content(body or "")
        return msg

    # -------------- public API --------------

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        Send an email. Uses SMTP_SSL for 465, SMTP+STARTTLS for 587, or plain/STARTTLS based on use_tls.
        Returns Message-ID if available.
        """
        transport = self._select_transport()
        ctx = ssl.create_default_context()
        msg = self._build_message(to_email, subject, body, headers)

        try:
            if transport["ssl"]:
                # ---- implicit SSL (SMTPS, e.g. OVH 465)
                with smtplib.SMTP_SSL(
                    self.host, self.port, timeout=self.timeout, context=ctx
                ) as server:
                    server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                # ---- plain SMTP, possibly upgraded via STARTTLS
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                    server.ehlo()
                    if transport["starttls"]:
                        server.starttls(context=ctx)
                        server.ehlo()
                    server.login(self.username, self.password)
                    server.send_message(msg)

            return str(msg.get("Message-ID") or "").strip() or None

        except smtplib.SMTPServerDisconnected as e:
            logger.error("SMTP disconnected: %s", e)
            raise
        except smtplib.SMTPAuthenticationError as e:
            logger.error("SMTP auth failed: %s", e)
            raise
        except smtplib.SMTPConnectError as e:
            logger.error("SMTP connect error: %s", e)
            raise
        except smtplib.SMTPException as e:
            logger.error("SMTP error: %s", e)
            raise
        except OSError as e:
            logger.error("Network/OS error while sending email: %s", e)
            raise

    async def send_email_async(
        self,
        to_email: str,
        subject: str,
        body: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Async wrapper via thread pool."""
        return await asyncio.to_thread(
            self.send_email, to_email, subject, body, headers=headers
        )
