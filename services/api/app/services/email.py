"""Account emails: email verification and password reset.

Messages are plain text and never contain patient information. Sending happens after the
response (FastAPI background task), so a slow or failing provider never delays or fails a
request, and the response is the same whether or not an account exists.
"""

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import make_msgid
from typing import Annotated, Protocol

from fastapi import Depends

from app.core.config import EmailBackend, Settings, SmtpSecurity, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str


class EmailSender(Protocol):
    def send(self, message: OutgoingEmail) -> None: ...


class LogSender:
    """Development only: writes the message, including its link, to the log."""

    def send(self, message: OutgoingEmail) -> None:
        logger.warning(
            "Email (development log backend) to=%s subject=%s\n%s",
            message.to,
            message.subject,
            message.text,
        )


class DisabledSender:
    def send(self, message: OutgoingEmail) -> None:
        logger.info("Email not sent (SNEHA_EMAIL_BACKEND=disabled): %s", message.subject)


class SmtpSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: OutgoingEmail) -> None:
        s = self._settings
        mime = MimeMessage()
        mime["From"] = s.email_from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime["Message-ID"] = make_msgid(domain=s.email_from.rsplit("@", 1)[-1].strip("> "))
        mime.set_content(message.text)
        host = s.smtp_host or ""
        timeout = s.smtp_timeout_seconds
        context = ssl.create_default_context()
        if s.smtp_security == SmtpSecurity.SSL:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                host, s.smtp_port, timeout=timeout, context=context
            )
        else:
            server = smtplib.SMTP(host, s.smtp_port, timeout=timeout)
        with server:
            if s.smtp_security == SmtpSecurity.STARTTLS:
                server.starttls(context=context)
            if s.smtp_username and s.smtp_password is not None:
                server.login(s.smtp_username, s.smtp_password.get_secret_value())
            server.send_message(mime)


def get_email_sender(settings: Annotated[Settings, Depends(get_settings)]) -> EmailSender:
    if settings.email_backend == EmailBackend.SMTP:
        return SmtpSender(settings)
    if settings.email_backend == EmailBackend.LOG:
        return LogSender()
    return DisabledSender()


EmailSenderDep = Annotated[EmailSender, Depends(get_email_sender)]


def deliver(sender: EmailSender, message: OutgoingEmail) -> None:
    """Background task: never raises; failures are logged without the message body."""
    try:
        sender.send(message)
    except Exception:
        logger.exception("Could not send email %r to %s", message.subject, message.to)


# ---------------------------------------------------------------- messages


def verification_email(to: str, name: str, link: str, hours: int) -> OutgoingEmail:
    return OutgoingEmail(
        to=to,
        subject="Confirm your email for SNEHA",
        text=(
            f"Hello {name},\n\n"
            "Please confirm that this is your email address by opening this link:\n\n"
            f"{link}\n\n"
            f"The link works once and expires in {hours} hours.\n\n"
            "If you did not create a SNEHA account, you can ignore this email.\n\n"
            "SNEHA"
        ),
    )


def password_reset_email(to: str, name: str, link: str, minutes: int) -> OutgoingEmail:
    return OutgoingEmail(
        to=to,
        subject="Reset your SNEHA password",
        text=(
            f"Hello {name},\n\n"
            "Someone asked to reset the password for your SNEHA account. "
            "To choose a new password, open this link:\n\n"
            f"{link}\n\n"
            f"The link works once and expires in {minutes} minutes. "
            "Resetting signs you out everywhere.\n\n"
            "If you did not ask for this, ignore this email; your password stays the same.\n\n"
            "SNEHA"
        ),
    )
