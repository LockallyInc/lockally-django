import base64
import unittest

from django.conf import settings

if not settings.configured:
    settings.configure(
        EMAIL_BACKEND="lockally_django.EmailBackend",
        LOCKALLY_API_KEY="lk_test_abc",
    )

from django.core.mail import EmailMessage, EmailMultiAlternatives  # noqa: E402

from lockally_django.backend import LockallyEmailBackend  # noqa: E402


class FakeSendApi:
    def __init__(self):
        self.calls = []

    def v1_send_post(self, idempotency_key, request):
        self.calls.append((idempotency_key, request))
        return None


class LockallyEmailBackendTest(unittest.TestCase):
    def test_maps_multipart_message(self):
        msg = EmailMultiAlternatives(
            subject="Your code",
            body="code 123",
            from_email="Acme Alerts <alerts@acme.com>",
            to=["user@example.com", "Second <two@example.com>"],
            cc=["cc@example.com"],
            reply_to=["reply@acme.com"],
        )
        msg.attach_alternative("<b>code 123</b>", "text/html")
        msg.attach("invoice.pdf", b"BYTES", "application/pdf")

        payload = LockallyEmailBackend(send_api=FakeSendApi())._to_payload(msg)

        self.assertEqual(payload["from"], "alerts@acme.com")  # display name stripped
        self.assertEqual(payload["to"], ["user@example.com", "two@example.com"])
        self.assertEqual(payload["cc"], ["cc@example.com"])
        self.assertEqual(payload["subject"], "Your code")
        self.assertEqual(payload["text"], "code 123")
        self.assertEqual(payload["html"], "<b>code 123</b>")
        self.assertEqual(payload["headers"]["Reply-To"], "reply@acme.com")
        self.assertEqual(len(payload["attachments"]), 1)
        att = payload["attachments"][0]
        self.assertEqual(att["filename"], "invoice.pdf")
        self.assertEqual(att["content_type"], "application/pdf")
        self.assertEqual(att["content_base64"], base64.b64encode(b"BYTES").decode())

    def test_html_only_message(self):
        msg = EmailMessage("Hi", "<p>hello</p>", "a@acme.com", ["b@example.com"])
        msg.content_subtype = "html"
        payload = LockallyEmailBackend(send_api=FakeSendApi())._to_payload(msg)
        self.assertEqual(payload["html"], "<p>hello</p>")
        self.assertNotIn("text", payload)

    def test_send_messages_calls_api_with_idempotency_key(self):
        fake = FakeSendApi()
        backend = LockallyEmailBackend(send_api=fake)
        msg = EmailMessage("Hi", "yo", "a@acme.com", ["b@example.com"])

        sent = backend.send_messages([msg])

        self.assertEqual(sent, 1)
        self.assertEqual(len(fake.calls), 1)
        key, request = fake.calls[0]
        self.assertTrue(key.startswith("lk-"))
        # request is a real V1SendPostRequest built via from_dict
        self.assertEqual(request.to_dict()["from"], "a@acme.com")

    def test_fail_silently_swallows_errors(self):
        class Boom(FakeSendApi):
            def v1_send_post(self, *a, **k):
                raise RuntimeError("nope")

        backend = LockallyEmailBackend(send_api=Boom(), fail_silently=True)
        msg = EmailMessage("Hi", "yo", "a@acme.com", ["b@example.com"])
        self.assertEqual(backend.send_messages([msg]), 0)

        backend.fail_silently = False
        with self.assertRaises(RuntimeError):
            backend.send_messages([msg])


if __name__ == "__main__":
    unittest.main()
