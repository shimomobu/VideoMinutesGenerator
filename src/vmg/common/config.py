"""設定管理 — config/default.yaml + 環境変数から AppConfig を生成する"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

_DEFAULT_CONFIG_PATH = Path("config/default.yaml")


class ConfigError(Exception):
    pass


class ApiPolicyConfig(BaseModel):
    send_audio: bool
    send_video: bool
    send_transcript: bool
    anonymize_mode: bool


class DiarizationConfig(BaseModel):
    enabled: bool


class PathsConfig(BaseModel):
    input_dir: str
    work_dir: str
    output_dir: str
    log_dir: str


class AppConfig(BaseModel):
    llm_model: str
    ollama_base_url: str
    llm_timeout_seconds: int
    whisper_model: str
    api_policy: ApiPolicyConfig
    diarization: DiarizationConfig
    paths: PathsConfig


def load_config(config_path: str | Path = _DEFAULT_CONFIG_PATH) -> AppConfig:
    config_path = Path(config_path)
    if not config_path.exists():
        raise ConfigError(f"設定ファイルが見つかりません: {config_path}")

    try:
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as e:
        raise ConfigError(f"設定ファイルの読み込みに失敗しました: {e}") from e

    try:
        config = AppConfig(
            llm_model=raw["analysis"]["model"],
            ollama_base_url=raw["analysis"]["base_url"],
            llm_timeout_seconds=int(raw["analysis"]["timeout_seconds"]),
            whisper_model=raw["asr"]["model_size"],
            api_policy=ApiPolicyConfig(**raw["api_policy"]),
            diarization=DiarizationConfig(**raw["diarization"]),
            paths=PathsConfig(
                input_dir=raw["pipeline"]["input_dir"],
                work_dir=raw["pipeline"]["work_dir"],
                output_dir=raw["pipeline"]["output_dir"],
                log_dir=raw["pipeline"]["log_dir"],
            ),
        )
    except (KeyError, ValidationError) as e:
        raise ConfigError(f"設定値が不正です: {e}") from e

    return config
