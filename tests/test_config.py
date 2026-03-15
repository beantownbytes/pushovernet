import os
from pathlib import Path

import pytest

from pushovernet.config import PushoverConfig
from pushovernet.exceptions import PushoverConfigError


class TestFromToml:
    def test_load_valid_config(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[pushover]\ntoken = "tok123"\nuser_key = "usr456"\n'
            'default_device = "phone"\ndefault_priority = 1\ndefault_sound = "cosmic"\n'
        )
        config = PushoverConfig.from_toml(config_file)
        assert config.token == "tok123"
        assert config.user_key == "usr456"
        assert config.default_device == "phone"
        assert config.default_priority == 1
        assert config.default_sound == "cosmic"

    def test_load_minimal_config(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[pushover]\ntoken = "tok"\nuser_key = "usr"\n')
        config = PushoverConfig.from_toml(config_file)
        assert config.token == "tok"
        assert config.user_key == "usr"
        assert config.default_device == ""
        assert config.default_priority == 0
        assert config.default_sound == ""

    def test_missing_file(self, tmp_path):
        with pytest.raises(PushoverConfigError, match="not found"):
            PushoverConfig.from_toml(tmp_path / "nonexistent.toml")

    def test_missing_section(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[other]\nkey = "val"\n')
        with pytest.raises(PushoverConfigError, match="Missing \\[pushover\\] section"):
            PushoverConfig.from_toml(config_file)

    def test_missing_required_key(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('[pushover]\ntoken = "tok"\n')
        with pytest.raises(PushoverConfigError, match="Missing required config key"):
            PushoverConfig.from_toml(config_file)


class TestFromEnv:
    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("PUSHOVER_TOKEN", "env_tok")
        monkeypatch.setenv("PUSHOVER_USER_KEY", "env_usr")
        config = PushoverConfig.from_env()
        assert config.token == "env_tok"
        assert config.user_key == "env_usr"

    def test_missing_env_vars(self, monkeypatch):
        monkeypatch.delenv("PUSHOVER_TOKEN", raising=False)
        monkeypatch.delenv("PUSHOVER_USER_KEY", raising=False)
        with pytest.raises(PushoverConfigError, match="environment variables"):
            PushoverConfig.from_env()

    def test_partial_env_vars(self, monkeypatch):
        monkeypatch.setenv("PUSHOVER_TOKEN", "tok")
        monkeypatch.delenv("PUSHOVER_USER_KEY", raising=False)
        with pytest.raises(PushoverConfigError):
            PushoverConfig.from_env()


class TestFromAwsSecret:
    def test_missing_boto3(self, monkeypatch):
        import pushovernet._aws as aws_mod

        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def mock_import(name, *args, **kwargs):
            if name == "boto3":
                raise ImportError("No module named 'boto3'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", mock_import)
        with pytest.raises(PushoverConfigError, match="boto3"):
            PushoverConfig.from_aws_secret("test/secret")
