"""
API endpoints for language and state selection.

Allows the frontend/WhatsApp bot to discover supported languages and states,
and lets employees switch their preferred language.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.language_config import (
    SUPPORTED_LANGUAGES,
    SUPPORTED_STATES,
    list_supported_languages,
    list_supported_states,
    get_language_config,
    get_state_config,
)
from app.dependencies import get_db

router = APIRouter()


@router.get("/")
async def get_languages():
    """List all supported languages with native names.

    Returns:
        List of languages with code, English name, and native name.
        Use the `code` value to set language on other endpoints.
    """
    return {
        "languages": list_supported_languages(),
        "default": "te",
        "total": len(SUPPORTED_LANGUAGES),
    }


@router.get("/states")
async def get_states():
    """List all supported states with their default languages.

    Each state has a default language and a list of supported languages.
    """
    return {
        "states": list_supported_states(),
        "default": "AP",
        "total": len(SUPPORTED_STATES),
    }


@router.get("/{lang_code}")
async def get_language_details(lang_code: str):
    """Get detailed configuration for a specific language.

    Includes: greeting, error messages, number words, document names.
    """
    if lang_code not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=404,
            detail=f"Language '{lang_code}' not supported. Supported: {list(SUPPORTED_LANGUAGES.keys())}",
        )
    config = get_language_config(lang_code)
    return {
        "code": config.code,
        "name_en": config.name_en,
        "name_native": config.name_native,
        "greeting": config.greeting,
        "number_words_count": len(config.number_words),
        "has_whisper_vocabulary": bool(config.whisper_prompt),
    }


@router.get("/states/{state_code}")
async def get_state_details(state_code: str):
    """Get detailed configuration for a specific state.

    Includes: governance portal, admin hierarchy, supported languages.
    """
    if state_code not in SUPPORTED_STATES:
        raise HTTPException(
            status_code=404,
            detail=f"State '{state_code}' not supported. Supported: {list(SUPPORTED_STATES.keys())}",
        )
    config = get_state_config(state_code)
    return {
        "code": config.code,
        "name_en": config.name_en,
        "name_native": config.name_native,
        "default_language": config.default_language,
        "supported_languages": config.supported_languages,
        "governance_portal_name": config.governance_portal_name,
        "secretariat_name_en": config.secretariat_name_en,
        "secretariat_name_native": config.secretariat_name_native,
        "admin_hierarchy": config.admin_hierarchy,
    }
