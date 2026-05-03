"""TASK-00-03: vmg.common.config の単体テスト"""
import pytest
import yaml

from vmg.common.config import AppConfig, ConfigError, load_config


# ── フィクスチャ ──────────────────────────────────────────────────

VALID_YAML_DATA = {
    "asr": {
        "provider": "whisper_local",
        "model_size": "small",
        "language": "ja",
    },
    "analysis": {
        "provider": "ollama",
        "model": "gemma4",
        "base_url": "http://localhost:11434",
        "max_retries": 3,
        "timeout_seconds": 120,
    },
    "api_policy": {
        "send_audio": False,
        "send_video": False,
        "send_transcript": True,
        "anonymize_mode": False,
    },
    "diarization": {
        "enabled": False,
    },
    "pipeline": {
        "input_dir": "data/input",
        "work_dir": "data/work",
        "output_dir": "data/output",
        "log_dir": "logs",
    },
}


@pytest.fixture
def valid_yaml(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml.dump(VALID_YAML_DATA))
    return yaml_file


# ── 正常系 ───────────────────────────────────────────────────────

class TestLoadConfigNormal:
    def test_returns_app_config_instance(self, valid_yaml):
        config = load_config(valid_yaml)
        assert isinstance(config, AppConfig)

    def test_llm_model_loaded(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.llm_model == "gemma4"

    def test_ollama_base_url_loaded(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.ollama_base_url == "http://localhost:11434"

    def test_whisper_model_loaded(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.whisper_model == "small"

    def test_diarization_disabled(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.diarization.enabled is False

    def test_paths_work_dir(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.paths.work_dir == "data/work"

    def test_paths_output_dir(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.paths.output_dir == "data/output"

    def test_paths_input_dir(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.paths.input_dir == "data/input"

    def test_paths_log_dir(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.paths.log_dir == "logs"

    def test_llm_timeout_seconds_loaded(self, valid_yaml):
        """analysis.timeout_seconds が AppConfig.llm_timeout_seconds として読み込まれること"""
        config = load_config(valid_yaml)
        assert config.llm_timeout_seconds == 120

    def test_llm_max_retries_loaded(self, valid_yaml):
        """analysis.max_retries が AppConfig.llm_max_retries として読み込まれること"""
        config = load_config(valid_yaml)
        assert config.llm_max_retries == 3

    def test_default_yaml_timeout_seconds_is_900(self):
        """config/default.yaml の analysis.timeout_seconds が 900 であること（設定値の正規値）"""
        from pathlib import Path
        import yaml as _yaml
        yaml_path = Path(__file__).parents[2] / "config" / "default.yaml"
        data = _yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["analysis"]["timeout_seconds"] == 900


# ── api_policy ───────────────────────────────────────────────────

class TestApiPolicy:
    def test_send_audio_is_false(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.api_policy.send_audio is False

    def test_send_video_is_false(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.api_policy.send_video is False

    def test_send_transcript_is_true(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.api_policy.send_transcript is True

    def test_anonymize_mode_is_false(self, valid_yaml):
        config = load_config(valid_yaml)
        assert config.api_policy.anonymize_mode is False


# ── 必須項目欠落 → ConfigError ────────────────────────────────────

class TestConfigError:
    def test_missing_yaml_file_raises_config_error(self, tmp_path):
        with pytest.raises(ConfigError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_missing_analysis_section_raises_config_error(self, tmp_path):
        bad_data = {k: v for k, v in VALID_YAML_DATA.items() if k != "analysis"}
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text(yaml.dump(bad_data))
        with pytest.raises(ConfigError):
            load_config(yaml_file)

    def test_missing_api_policy_section_raises_config_error(self, tmp_path):
        bad_data = {k: v for k, v in VALID_YAML_DATA.items() if k != "api_policy"}
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text(yaml.dump(bad_data))
        with pytest.raises(ConfigError):
            load_config(yaml_file)

    def test_missing_pipeline_section_raises_config_error(self, tmp_path):
        bad_data = {k: v for k, v in VALID_YAML_DATA.items() if k != "pipeline"}
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text(yaml.dump(bad_data))
        with pytest.raises(ConfigError):
            load_config(yaml_file)

    def test_config_error_message_contains_path(self, tmp_path):
        nonexistent = tmp_path / "nonexistent.yaml"
        with pytest.raises(ConfigError, match=str(nonexistent.name)):
            load_config(nonexistent)
