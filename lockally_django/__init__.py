from lockally_django.backend import LockallyEmailBackend

# Django resolves EMAIL_BACKEND = "lockally_django.EmailBackend" to this name.
EmailBackend = LockallyEmailBackend

__all__ = ["EmailBackend", "LockallyEmailBackend"]
__version__ = "0.1.0"
