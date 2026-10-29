"""Tests for rendereye_mcp.ipc.authentication."""

from __future__ import annotations

from pathlib import Path

from rendereye_mcp.ipc.authentication import AuthManager


class TestAuthManagerGenerate:
    def test_generate_returns_64_char_hex(self, tmp_path):
        manager = AuthManager(token_path=tmp_path / "token.txt")
        token = manager.generate()
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_generate_writes_token_to_file(self, tmp_path):
        token_path = tmp_path / "token.txt"
        manager = AuthManager(token_path=token_path)
        token = manager.generate()
        assert token_path.exists()
        assert token_path.read_text(encoding="utf-8") == token

    def test_token_file_can_be_read_back(self, tmp_path):
        token_path = tmp_path / "token.txt"
        manager = AuthManager(token_path=token_path)
        token = manager.generate()
        read_back = token_path.read_text(encoding="utf-8")
        assert read_back == token

    def test_generate_returns_different_tokens(self, tmp_path):
        manager = AuthManager(token_path=tmp_path / "token.txt")
        t1 = manager.generate()
        t2 = manager.generate()
        assert t1 != t2

    def test_token_property_returns_token(self, tmp_path):
        manager = AuthManager(token_path=tmp_path / "token.txt")
        token = manager.generate()
        assert manager.token == token


class TestAuthManagerValidate:
    def test_validate_correct_token(self, tmp_path):
        manager = AuthManager(token_path=tmp_path / "token.txt")
        token = manager.generate()
        assert manager.validate(token) is True

    def test_validate_wrong_token(self, tmp_path):
        manager = AuthManager(token_path=tmp_path / "token.txt")
        manager.generate()
        assert manager.validate("wrongtoken") is False

    def test_validate_before_generate_returns_false(self, tmp_path):
        manager = AuthManager(token_path=tmp_path / "token.txt")
        assert manager.validate("anytoken") is False

    def test_validate_empty_string(self, tmp_path):
        manager = AuthManager(token_path=tmp_path / "token.txt")
        manager.generate()
        assert manager.validate("") is False


class TestAuthManagerCleanup:
    def test_cleanup_removes_token_file(self, tmp_path):
        token_path = tmp_path / "token.txt"
        manager = AuthManager(token_path=token_path)
        manager.generate()
        assert token_path.exists()
        manager.cleanup()
        assert not token_path.exists()

    def test_cleanup_no_error_when_file_missing(self, tmp_path):
        token_path = tmp_path / "nonexistent_token.txt"
        manager = AuthManager(token_path=token_path)
        # No generate — file doesn't exist
        manager.cleanup()  # Should not raise


class TestAuthManagerTokenPath:
    def test_get_token_path(self, tmp_path):
        token_path = tmp_path / "custom_token.txt"
        manager = AuthManager(token_path=token_path)
        assert manager.get_token_path() == token_path

    def test_default_token_path_is_in_temp(self):
        import os
        manager = AuthManager()
        path = manager.get_token_path()
        temp_dir = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp")))
        assert path.parent == temp_dir
        assert "rendereye_mcp" in path.name

    def test_write_failure_is_nonfatal(self, tmp_path):
        """Token generation succeeds even if we can't write to the file path."""
        # Use a path in a nonexistent directory
        token_path = tmp_path / "nonexistent_dir" / "token.txt"
        manager = AuthManager(token_path=token_path)
        token = manager.generate()
        # Token should still be generated
        assert len(token) == 64
        # File may not exist, but no exception raised
