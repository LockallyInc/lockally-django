"""Django email backend that delivers through the Lockally API (POST /v1/send).

Set in settings:

    EMAIL_BACKEND = "lockally_django.EmailBackend"
    LOCKALLY_API_KEY = "lk_live_..."     # lk_test_... runs in sandbox
    # LOCKALLY_BASE_URL = "https://api.lockally.com"   # optional override

Then Django's `send_mail`, `EmailMessage`, `EmailMultiAlternatives` and the mail
admin all route through Lockally with no other changes.
"""

from __future__ import annotations

import base64
import uuid
from email.utils import parseaddr
from typing import Any

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class LockallyEmailBackend(BaseEmailBackend):
    def __init__(self, *, api_key: str | None = None, base_url: str | None = None,
                 fail_silently: bool = False, send_api: Any = None, **kwargs: Any) -> None:
        super().__init__(fail_silently=fail_silently)
        self._api_key = api_key or getattr(settings, "LOCKALLY_API_KEY", None)
        self._base_url = base_url or getattr(settings, "LOCKALLY_BASE_URL", None)
        self._send_api = send_api  # injectable for tests

    # -- delivery ---------------------------------------------------------------

    def send_messages(self, email_messages) -> int:
        if not email_messages:
            return 0
        try:
            api = self._get_send_api()
        except Exception:
            if not self.fail_silently:
                raise
            return 0

        sent = 0
        for message in email_messages:
            try:
                api.v1_send_post(self._idempotency_key(), self._to_request(message))
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent

    # -- mapping ----------------------------------------------------------------

    def _to_payload(self, message) -> dict:
        """Map a Django email message onto the /v1/send JSON body. Returns a plain
        dict (JSON keys) so the mapping is unit-testable without the SDK models."""
        payload: dict[str, Any] = {
            "from": _addr(message.from_email),
            "to": [_addr(a) for a in message.to],
        }
        if message.cc:
            payload["cc"] = [_addr(a) for a in message.cc]
        if message.bcc:
            payload["bcc"] = [_addr(a) for a in message.bcc]
        if message.subject:
            payload["subject"] = message.subject

        # Body: `content_subtype` decides whether the primary body is text or html;
        # EmailMultiAlternatives carries the html as a text/html alternative.
        if getattr(message, "content_subtype", "plain") == "html":
            payload["html"] = message.body
        elif message.body:
            payload["text"] = message.body
        for content, mimetype in (getattr(message, "alternatives", None) or []):
            if mimetype == "text/html":
                payload["html"] = content

        headers = dict(getattr(message, "extra_headers", None) or {})
        if getattr(message, "reply_to", None):
            # Lockally has no reply_to field — carry it as a header.
            headers["Reply-To"] = ", ".join(message.reply_to)
        if headers:
            payload["headers"] = headers

        attachments = []
        for attachment in (message.attachments or []):
            filename, content, mimetype = _attachment_parts(attachment)
            if content is None:
                continue
            raw = content.encode() if isinstance(content, str) else content
            attachments.append({
                "filename": filename or "attachment",
                "content_type": mimetype or "application/octet-stream",
                "content_base64": base64.b64encode(raw).decode("ascii"),
            })
        if attachments:
            payload["attachments"] = attachments

        return payload

    def _to_request(self, message):
        from lockally.models.v1_send_post_request import V1SendPostRequest
        return V1SendPostRequest.from_dict(self._to_payload(message))

    # -- client -----------------------------------------------------------------

    def _get_send_api(self):
        if self._send_api is None:
            from lockally import ApiClient, Configuration
            from lockally.api.send_api import SendApi
            cfg = Configuration(access_token=self._api_key)
            if self._base_url:
                cfg.host = self._base_url.rstrip("/")
            self._send_api = SendApi(ApiClient(cfg))
        return self._send_api

    @staticmethod
    def _idempotency_key() -> str:
        return "lk-" + uuid.uuid4().hex


def _addr(value: str) -> str:
    """Extract the bare email address from a possibly `Name <addr>` string."""
    return parseaddr(value)[1] or value


def _attachment_parts(attachment):
    """Django attachments are (filename, content, mimetype) tuples or MIMEBase."""
    if isinstance(attachment, (tuple, list)):
        parts = list(attachment) + [None, None, None]
        return parts[0], parts[1], parts[2]
    return (
        attachment.get_filename(),
        attachment.get_payload(decode=True),
        attachment.get_content_type(),
    )
