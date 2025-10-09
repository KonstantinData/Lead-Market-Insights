# ===================================================================
# File: adapters/email_smtp.py
# Purpose:
#   Implements the IEmailSender interface for sending transactional
#   and HITL-related emails via the existing EmailAgent transport.
#
#   This adapter acts as a thin asynchronous bridge:
#     - Converts sync calls to async if necessary
#     - Normalizes headers
#     - Ensures consistent logging and error handling
#
# Dependencies:
#   • interfaces/email.py     → defines IEmailSender protocol
#   • utils/email_agent.py    → existing EmailAgent class
# ===================================================================

import asyncio
import logging
from typing import Mapping, Optional, Any

from interfaces.email import IEmailSender
from utils.email_agent import EmailAgent


class SmtpEmailSender(IEmailSender):
    """
    Concrete adapter implementing the IEmailSender protocol using
    the system's configured SMTP transport (EmailAgent).

    This ensures that domain logic (e.g., HITL workflows) depend on
    the abstract port rather than a specific SMTP implementation.
    """

    def __init__(self, smtp_agent: Optional[EmailAgent] = None) -> None:
        """
        Initialize the adapter with a provided or default EmailAgent instance.
        """
        self._agent: EmailAgent = smtp_agent or EmailAgent()
        self._logger = logging.getLogger(self.__class__.__name__)

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        """
        Send an email asynchronously. Supports either a truly async
        EmailAgent or a synchronous fallback executed in a thread.

        Args:
            to: Recipient email address
            subject: Email subject line
            body: Plain-text or rendered Jinja message
            headers: Optional custom headers (Run-ID, Audit-ID, etc.)
        """
        headers = dict(headers or {})
        if "X-Sender" not in headers:
            headers["X-Sender"] = getattr(
                self._agent, "sender_email", "unknown@localhost"
            )

        try:
            if hasattr(self._agent, "send_email_async"):
                result = await self._agent.send_email_async(
                    to, subject, body, headers=headers
                )
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._agent.send_email(to, subject, body, headers=headers),
                )

            self._logger.info(
                f"[SMTP-ADAPTER] Email sent to {to!r} (subject={subject!r})"
            )
            return result

        except Exception as exc:
            self._logger.error(
                f"[SMTP-ADAPTER] Failed to send email to {to!r}: {exc}", exc_info=True
            )
            raise


def create_smtp_email_sender() -> SmtpEmailSender:
    """
    Factory helper to obtain a configured SMTP adapter.
    This enables dependency injection and test mocking.
    """
    return SmtpEmailSender()
