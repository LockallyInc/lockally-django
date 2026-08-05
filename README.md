# Lockally for Django

Official Django email backend for [Lockally](https://lockally.com). Send
transactional email through Django's standard mail API — `send_mail`,
`EmailMessage`, `EmailMultiAlternatives`, and the admin — with no code changes.

## Install

```bash
pip install lockally-django
```

## Configure

```python
# settings.py
EMAIL_BACKEND = "lockally_django.EmailBackend"
LOCKALLY_API_KEY = "lk_live_xxx"          # lk_test_xxx runs in sandbox (no real send)
# LOCKALLY_BASE_URL = "https://api.lockally.com"   # optional override
```

## Use

```python
from django.core.mail import EmailMultiAlternatives

msg = EmailMultiAlternatives(
    subject="Your OTP code",
    body="Your code is 847291.",
    from_email="alerts@yourdomain.com",
    to=["user@example.com"],
    reply_to=["support@yourdomain.com"],
)
msg.attach_alternative("<p>Your code is <b>847291</b>.</p>", "text/html")
msg.send()
```

## Notes

- **Reply-To** and any `extra_headers` are delivered via the message headers
  (Lockally has no separate `reply_to` field).
- **Attachments** are sent as base64 (10 MB each). Inline/CID images are sent as
  regular attachments.
- Each message carries a generated `Idempotency-Key`.
- `fail_silently=True` is honored.

Built on the official [`lockally`](https://pypi.org/project/lockally/) Python client.

## License

MIT
