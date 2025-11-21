"""
Translation loader and manager.

Handles loading translations and managing user language preferences.
"""

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository
from .locales import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from .translations import TRANSLATIONS


def get_translator(language: str | None = None) -> Any:
    """
    Get translator function for specified language.

    Args:
        language: Language code (ru, en) or None for default

    Returns:
        Translator function that takes key and returns translated text
    """
    lang = language or DEFAULT_LANGUAGE

    if lang not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language: {lang}, falling back to {DEFAULT_LANGUAGE}")
        lang = DEFAULT_LANGUAGE

    translations = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])

    def translate(key: str, **kwargs: Any) -> str:
        """
        Translate a key to the selected language.

        Args:
            key: Translation key (e.g., "menu.main")
            **kwargs: Variables to interpolate in translation

        Returns:
            Translated text
        """
        # Navigate through nested keys (e.g., "menu.main" -> translations["menu"]["main"])
        parts = key.split(".")
        value = translations

        try:
            for part in parts:
                value = value[part]
        except (KeyError, TypeError):
            logger.warning(f"Translation key not found: {key} (language: {lang})")
            # Fallback to default language
            if lang != DEFAULT_LANGUAGE:
                default_translations = TRANSLATIONS[DEFAULT_LANGUAGE]
                value = default_translations
                try:
                    for part in parts:
                        value = value[part]
                except (KeyError, TypeError):
                    return key  # Return key if not found even in default

        # If value is a string, interpolate variables
        if isinstance(value, str):
            try:
                return value.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing variable in translation {key}: {e}")
                return value

        return str(value)

    return translate


async def set_user_language(
    session: AsyncSession, user_id: int, language: str
) -> bool:
    """
    Set user's preferred language.

    Args:
        session: Database session
        user_id: User ID
        language: Language code (ru, en)

    Returns:
        True if successful, False otherwise
    """
    if language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Invalid language code: {language}")
        return False

    try:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(user_id)

        if not user:
            logger.warning(f"User {user_id} not found")
            return False

        # Update user language (assuming language field exists in User model)
        # If not, we'll need to add it
        await user_repo.update(user_id, language=language)
        await session.commit()

        logger.info(f"Language set to {language} for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error setting user language: {e}")
        await session.rollback()
        return False


async def get_user_language(
    session: AsyncSession, user_id: int
) -> str:
    """
    Get user's preferred language.

    Args:
        session: Database session
        user_id: User ID

    Returns:
        Language code (ru, en) or default language
    """
    try:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(user_id)

        if not user:
            return DEFAULT_LANGUAGE

        # Get language from user
        if user.language:
            return user.language

        return DEFAULT_LANGUAGE

    except Exception as e:
        logger.error(f"Error getting user language: {e}")
        return DEFAULT_LANGUAGE

