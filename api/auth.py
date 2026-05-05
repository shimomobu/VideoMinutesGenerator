"""API キー認証 dependency"""
from __future__ import annotations

from fastapi import Header, HTTPException

from vmg.common.config import load_config


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """X-API-Key ヘッダを検証する。api_key 未設定時は認証スキップ（開発モード）。"""
    try:
        expected = load_config().api_key
    except Exception:
        return
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
