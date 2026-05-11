"""基本的な API エンドポイントのテスト"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# テストはモックなしで main の型・バリデーションのみ確認
from main import _validate_url, _ALLOWED_IMAGE_SUFFIXES, Boilerplate, AutoSettings


class TestValidateUrl:
    def test_https_allowed(self):
        assert _validate_url("https://example.com") is True

    def test_http_rejected(self):
        assert _validate_url("http://example.com") is False

    def test_private_ip_rejected(self):
        assert _validate_url("https://192.168.1.1") is False

    def test_loopback_rejected(self):
        assert _validate_url("https://127.0.0.1") is False

    def test_metadata_ip_rejected(self):
        assert _validate_url("https://169.254.169.254") is False

    def test_invalid_scheme_rejected(self):
        assert _validate_url("file:///etc/passwd") is False


class TestAllowedSuffixes:
    def test_jpg_allowed(self):
        assert ".jpg" in _ALLOWED_IMAGE_SUFFIXES

    def test_png_allowed(self):
        assert ".png" in _ALLOWED_IMAGE_SUFFIXES

    def test_php_not_allowed(self):
        assert ".php" not in _ALLOWED_IMAGE_SUFFIXES

    def test_exe_not_allowed(self):
        assert ".exe" not in _ALLOWED_IMAGE_SUFFIXES


class TestModels:
    def test_boilerplate_defaults(self):
        bp = Boilerplate()
        assert bp.uword_footer == ""
        assert bp.fixed_hashtags == []

    def test_auto_settings_defaults(self):
        s = AutoSettings()
        assert s.generation == []
        assert s.schedules == []
