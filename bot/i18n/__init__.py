"""
Internationalization (i18n) support.

Provides translation functions and language management.
"""

from .loader import get_translator, set_user_language, get_user_language
from .locales import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE

__all__ = [
    "get_translator",
    "set_user_language",
    "get_user_language",
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
]

