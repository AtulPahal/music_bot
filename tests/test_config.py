"""Unit tests for Config models, environment parsing, and validation."""

from __future__ import annotations

import os
from unittest.mock import patch

import discord
import pytest

from bot.config import (
    Config,
    ConfigError,
    _clean_env,
    _parse_bool,
    _parse_color,
    _parse_float,
    _parse_int,
    _parse_int_list,
)


class TestConfigHelpers:
    def test_clean_env(self):
        with patch.dict(os.environ, {"TEST_KEY": "  value # inline comment  "}):
            assert _clean_env("TEST_KEY") == "value"

        with patch.dict(os.environ, {"TEST_KEY": "# entire line comment"}):
            assert _clean_env("TEST_KEY", default="def") == "def"

    def test_parse_bool(self):
        assert _parse_bool("true") is True
        assert _parse_bool("1") is True
        assert _parse_bool("yes") is True
        assert _parse_bool("false") is False
        assert _parse_bool("0") is False
        assert _parse_bool("", default=True) is True

    def test_parse_int(self):
        assert _parse_int("123") == 123
        assert _parse_int("invalid", default=10) == 10

    def test_parse_float(self):
        assert _parse_float("1.5") == 1.5
        assert _parse_float("bad", default=0.5) == 0.5

    def test_parse_int_list(self):
        assert _parse_int_list("123, 456, 789") == [123, 456, 789]
        assert _parse_int_list("") == []

    def test_parse_color(self):
        color = _parse_color("#5865F2", 0)
        assert color.value == 0x5865F2

        color_hex = _parse_color("0x57F287", 0)
        assert color_hex.value == 0x57F287


class TestConfigValidation:
    def test_valid_config(self):
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "mock_token",
            "DISCORD_CLIENT_ID": "123456789",
        }):
            config = Config()
            assert config.DISCORD_BOT_TOKEN == "mock_token"
            assert config.DISCORD_CLIENT_ID == "123456789"
            assert config.DEFAULT_VOLUME == 0.5
            assert config.MAX_QUEUE_LENGTH == 500

    def test_missing_token_raises(self):
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "",
            "DISCORD_CLIENT_ID": "123456789",
        }, clear=True):
            with pytest.raises(ConfigError, match="DISCORD_BOT_TOKEN is required"):
                Config()

    def test_invalid_auth_mode_raises(self):
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "token",
            "DISCORD_CLIENT_ID": "123",
            "YTM_AUTH_MODE": "invalid_mode",
        }):
            with pytest.raises(ConfigError, match="YTM_AUTH_MODE"):
                Config()
