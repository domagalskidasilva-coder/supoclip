from __future__ import annotations

import json
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...ai import (
    _get_missing_llm_key_error,
    _split_llm_name,
    get_google_key_health,
    mask_api_key,
    record_google_key_health,
)
from ...config import MAX_GOOGLE_API_KEYS, Config, get_config
from ...database import get_db
from ...runtime_settings import (
    RUNTIME_SETTING_KEYS,
    decrypt_setting_value,
    encrypt_setting_value,
    get_runtime_setting_rows,
    load_runtime_settings_cache,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# Managed exclusively by the /admin/google-api-keys endpoints below; hidden
# from the generic runtime-settings form.
GOOGLE_KEY_POOL_SETTING = "GOOGLE_API_KEYS"


SETTING_METADATA = {
    "ASSEMBLY_AI_API_KEY": {
        "label": "Chave da API AssemblyAI",
        "description": "Usada para transcrever os vídeos.",
        "input_type": "password",
    },
    "LLM": {
        "label": "Modelo de IA",
        "description": "Provedor e modelo, por exemplo google-gla:gemini-2.5-flash.",
        "input_type": "text",
    },
    "OPENAI_API_KEY": {
        "label": "Chave da API OpenAI",
        "description": "Necessária para modelos openai:*.",
        "input_type": "password",
    },
    "GOOGLE_API_KEY": {
        "label": "Chave da API Google",
        "description": "Necessária para modelos google-gla:* e metadados do YouTube.",
        "input_type": "password",
    },
    "GOOGLE_API_KEYS": {
        "label": "Pool de chaves Google",
        "description": "Gerenciado pelo painel de chaves Google (revezamento automático).",
        "input_type": "password",
    },
    "ANTHROPIC_API_KEY": {
        "label": "Chave da API Anthropic",
        "description": "Necessária para modelos anthropic:*.",
        "input_type": "password",
    },
    "OLLAMA_BASE_URL": {
        "label": "URL base do Ollama",
        "description": "Opcional, para endpoints locais ou hospedados compatíveis com Ollama.",
        "input_type": "text",
    },
    "OLLAMA_API_KEY": {
        "label": "Chave da API Ollama",
        "description": "Opcional, usada por provedores hospedados compatíveis com Ollama.",
        "input_type": "password",
    },
    "YOUTUBE_DATA_API_KEY": {
        "label": "Chave da YouTube Data API",
        "description": "Opcional, provedor alternativo de metadados.",
        "input_type": "password",
    },
    "APIFY_API_TOKEN": {
        "label": "Token da API Apify",
        "description": "Opcional, provedor alternativo de download do YouTube.",
        "input_type": "password",
    },
    "PEXELS_API_KEY": {
        "label": "Chave da API Pexels",
        "description": "Opcional, banco de vídeos para B-roll.",
        "input_type": "password",
    },
}


class RuntimeSettingsUpdate(BaseModel):
    updates: dict[str, str] = Field(default_factory=dict)
    delete_keys: list[str] = Field(default_factory=list)
    prefer_admin_values: dict[str, bool] = Field(default_factory=dict)


def _setting_status(
    setting_key: str, rows: dict[str, dict[str, object]]
):
    env_value = get_config()._get_optional_env(setting_key)
    has_env = bool(env_value)
    row = rows.get(setting_key, {})
    has_admin_value = bool(row.get("encrypted_value"))
    prefer_admin_value = bool(row.get("prefer_admin_value"))
    metadata = SETTING_METADATA[setting_key]

    if has_admin_value and (prefer_admin_value or not has_env):
        source = "admin"
    elif has_env:
        source = "environment"
    else:
        source = "unset"

    return {
        "key": setting_key,
        "label": metadata["label"],
        "description": metadata["description"],
        "input_type": metadata["input_type"],
        "source": source,
        "configured": has_env or has_admin_value,
        "has_admin_value": has_admin_value,
        "has_env_value": has_env,
        "prefer_admin_value": prefer_admin_value,
        "overridden_by_env": has_env and has_admin_value and not prefer_admin_value,
        "updated_at": row.get("updated_at"),
    }


@router.get("/health")
async def admin_health():
    return {"status": "ok"}


@router.get("/runtime-settings")
async def get_runtime_settings(db: AsyncSession = Depends(get_db)):
    rows = await get_runtime_setting_rows(db)
    return {
        "settings": [
            _setting_status(setting_key, rows)
            for setting_key in RUNTIME_SETTING_KEYS
            if setting_key != GOOGLE_KEY_POOL_SETTING
        ]
    }


@router.patch("/runtime-settings")
async def update_runtime_settings(
    payload: RuntimeSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    allowed_keys = set(RUNTIME_SETTING_KEYS) - {GOOGLE_KEY_POOL_SETTING}
    invalid_keys = [
        key
        for key in [
            *payload.updates.keys(),
            *payload.delete_keys,
            *payload.prefer_admin_values.keys(),
        ]
        if key not in allowed_keys
    ]
    if invalid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported setting key(s): {', '.join(sorted(set(invalid_keys)))}",
        )

    if "LLM" in payload.updates:
        config_error = _get_missing_llm_key_error(
            payload.updates["LLM"].strip(), get_config()
        )
        if config_error and "API_KEY is not set" not in config_error:
            raise HTTPException(status_code=400, detail=config_error)

    for setting_key, raw_value in payload.updates.items():
        value = raw_value.strip()
        if not value:
            continue
        encrypted_value = encrypt_setting_value(value)
        await db.execute(
            text(
                """
                INSERT INTO app_settings (setting_key, encrypted_value)
                VALUES (:setting_key, :encrypted_value)
                ON CONFLICT (setting_key) DO UPDATE
                SET encrypted_value = EXCLUDED.encrypted_value,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "setting_key": setting_key,
                "encrypted_value": encrypted_value,
            },
        )

    for setting_key, prefer_admin_value in payload.prefer_admin_values.items():
        await db.execute(
            text(
                """
                UPDATE app_settings
                SET prefer_admin_value = :prefer_admin_value,
                    updated_at = CURRENT_TIMESTAMP
                WHERE setting_key = :setting_key
                """
            ),
            {
                "setting_key": setting_key,
                "prefer_admin_value": prefer_admin_value,
            },
        )

    if payload.delete_keys:
        await db.execute(
            text(
                """
                DELETE FROM app_settings
                WHERE setting_key = ANY(CAST(:setting_keys AS text[]))
                """
            ),
            {"setting_keys": payload.delete_keys},
        )

    await db.commit()
    await load_runtime_settings_cache(db)

    rows = await get_runtime_setting_rows(db)
    return {
        "settings": [
            _setting_status(setting_key, rows)
            for setting_key in RUNTIME_SETTING_KEYS
            if setting_key != GOOGLE_KEY_POOL_SETTING
        ]
    }


# ---------------------------------------------------------------------------
# Google API key pool (1-5 keys with automatic failover)
# ---------------------------------------------------------------------------


class GoogleKeyCreate(BaseModel):
    api_key: str = Field(min_length=10, max_length=200)


class GoogleKeyTest(BaseModel):
    index: int | None = None
    api_key: str | None = Field(default=None, max_length=200)


async def _load_admin_google_keys(db: AsyncSession) -> list[str]:
    """Read the stored (admin-managed) Google key pool, decrypted."""
    rows = await get_runtime_setting_rows(db)
    row = rows.get(GOOGLE_KEY_POOL_SETTING) or {}
    encrypted_value = row.get("encrypted_value")
    if not encrypted_value:
        return []
    try:
        raw = decrypt_setting_value(str(encrypted_value))
    except Exception:
        return []
    return Config._parse_google_api_keys(raw)


async def _save_admin_google_keys(db: AsyncSession, keys: list[str]) -> None:
    if keys:
        encrypted_value = encrypt_setting_value(json.dumps(keys))
        await db.execute(
            text(
                """
                INSERT INTO app_settings (setting_key, encrypted_value)
                VALUES (:setting_key, :encrypted_value)
                ON CONFLICT (setting_key) DO UPDATE
                SET encrypted_value = EXCLUDED.encrypted_value,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "setting_key": GOOGLE_KEY_POOL_SETTING,
                "encrypted_value": encrypted_value,
            },
        )
    else:
        await db.execute(
            text("DELETE FROM app_settings WHERE setting_key = :setting_key"),
            {"setting_key": GOOGLE_KEY_POOL_SETTING},
        )
    await db.commit()
    await load_runtime_settings_cache(db)


def _google_key_entry(index: int, key: str, source: str) -> dict[str, object]:
    """Public-safe representation of one pool entry (never the raw key)."""
    return {
        "index": index,
        "masked_key": mask_api_key(key),
        "source": source,
        "removable": source == "admin",
        "health": get_google_key_health(key),
    }


async def _google_key_pool_response(db: AsyncSession) -> dict[str, object]:
    admin_keys = await _load_admin_google_keys(db)
    entries: list[dict[str, object]] = []
    if admin_keys:
        entries = [
            _google_key_entry(index, key, "admin")
            for index, key in enumerate(admin_keys)
        ]
    else:
        env_key = get_config()._get_optional_env("GOOGLE_API_KEY")
        if env_key:
            entries = [_google_key_entry(0, env_key, "environment")]
    return {
        "keys": entries,
        "min_keys": 1,
        "max_keys": MAX_GOOGLE_API_KEYS,
        "failover_enabled": len(entries) > 1,
    }


def _google_test_model_name() -> str:
    provider, model_name = _split_llm_name(get_config().llm)
    if provider in {"google", "google-gla"} and model_name:
        return model_name
    return "gemini-2.5-flash"


async def _probe_google_key(api_key: str) -> dict[str, object]:
    """Fire a minimal generateContent request to validate one key."""
    model_name = _google_test_model_name()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                url,
                params={"key": api_key},
                json={"contents": [{"parts": [{"text": "ping"}]}]},
            )
    except httpx.HTTPError as exc:
        record_google_key_health(api_key, ok=False, detail=f"network error: {exc}")
        return {"ok": False, "status_code": None, "detail": str(exc)}

    ok = response.status_code == 200
    detail = "OK" if ok else response.text[:300]
    record_google_key_health(
        api_key, ok=ok, detail="OK" if ok else f"HTTP {response.status_code}"
    )
    return {"ok": ok, "status_code": response.status_code, "detail": detail}


@router.get("/google-api-keys")
async def list_google_api_keys(db: AsyncSession = Depends(get_db)):
    return await _google_key_pool_response(db)


@router.post("/google-api-keys")
async def add_google_api_key(
    payload: GoogleKeyCreate, db: AsyncSession = Depends(get_db)
):
    new_key = payload.api_key.strip()
    if not new_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")

    admin_keys = await _load_admin_google_keys(db)
    if not admin_keys:
        # Seed the pool with the environment key so the pool fully replaces it
        # (instead of silently shadowing it) once admin management starts.
        env_key = get_config()._get_optional_env("GOOGLE_API_KEY")
        if env_key and env_key != new_key:
            admin_keys = [env_key]

    if new_key in admin_keys:
        raise HTTPException(status_code=400, detail="This API key is already registered")
    if len(admin_keys) >= MAX_GOOGLE_API_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {MAX_GOOGLE_API_KEYS} API keys reached",
        )

    admin_keys.append(new_key)
    await _save_admin_google_keys(db, admin_keys)
    return await _google_key_pool_response(db)


@router.delete("/google-api-keys/{index}")
async def remove_google_api_key(index: int, db: AsyncSession = Depends(get_db)):
    admin_keys = await _load_admin_google_keys(db)
    if not admin_keys:
        raise HTTPException(
            status_code=400,
            detail="The environment GOOGLE_API_KEY cannot be removed from here",
        )
    if index < 0 or index >= len(admin_keys):
        raise HTTPException(status_code=404, detail="API key not found")
    if len(admin_keys) == 1 and not get_config()._get_optional_env("GOOGLE_API_KEY"):
        raise HTTPException(
            status_code=400, detail="At least 1 API key must remain configured"
        )

    admin_keys.pop(index)
    await _save_admin_google_keys(db, admin_keys)
    return await _google_key_pool_response(db)


@router.post("/google-api-keys/test")
async def test_google_api_key(
    payload: GoogleKeyTest, db: AsyncSession = Depends(get_db)
):
    if payload.api_key and payload.api_key.strip():
        result = await _probe_google_key(payload.api_key.strip())
        return {"target": "provided-key", **result}

    if payload.index is None:
        raise HTTPException(status_code=400, detail="Provide index or api_key to test")

    admin_keys = await _load_admin_google_keys(db)
    if admin_keys:
        if payload.index < 0 or payload.index >= len(admin_keys):
            raise HTTPException(status_code=404, detail="API key not found")
        key = admin_keys[payload.index]
    else:
        env_key = get_config()._get_optional_env("GOOGLE_API_KEY")
        if not env_key or payload.index != 0:
            raise HTTPException(status_code=404, detail="API key not found")
        key = env_key

    result = await _probe_google_key(key)
    return {"target": mask_api_key(key), **result}
