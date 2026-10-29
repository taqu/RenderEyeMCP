"""Tests for Phase 15.1 — tag classification, version normalization, and publishing isolation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from classify_tag import classify  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────────
# Tag classification
# ──────────────────────────────────────────────────────────────────────────────


class TestProductionTags:
    def test_v0_1_0(self):
        r = classify("v0.1.0")
        assert r.kind == "production"
        assert r.version == "0.1.0"

    def test_v1_0_0(self):
        r = classify("v1.0.0")
        assert r.kind == "production"
        assert r.version == "1.0.0"

    def test_v1_2_3(self):
        r = classify("v1.2.3")
        assert r.kind == "production"
        assert r.version == "1.2.3"

    def test_v10_20_30(self):
        r = classify("v10.20.30")
        assert r.kind == "production"
        assert r.version == "10.20.30"

    def test_version_no_error(self):
        r = classify("v0.1.0")
        assert r.error is None


class TestTestTags:
    def test_v0_1_0_test_1(self):
        r = classify("v0.1.0-test.1")
        assert r.kind == "test"
        assert r.version == "0.1.0.dev1"

    def test_v0_1_0_test_2(self):
        r = classify("v0.1.0-test.2")
        assert r.kind == "test"
        assert r.version == "0.1.0.dev2"

    def test_v0_2_0_test_1(self):
        r = classify("v0.2.0-test.1")
        assert r.kind == "test"
        assert r.version == "0.2.0.dev1"

    def test_multi_digit_iteration(self):
        r = classify("v1.0.0-test.10")
        assert r.kind == "test"
        assert r.version == "1.0.0.dev10"

    def test_version_no_error(self):
        r = classify("v0.1.0-test.1")
        assert r.error is None


class TestInvalidTags:
    @pytest.mark.parametrize(
        "tag",
        [
            "v0.1",             # missing patch
            "v0.1.0-test",      # unnumbered test suffix
            "v0.1.0-test.",     # empty iteration
            "v0.1.0-test.0",    # iteration must be >= 1
            "v0.1.0-test.foo",  # non-numeric iteration
            "v0.1.0-debug",     # unknown suffix
            "release-0.1.0",    # wrong prefix
            "0.1.0",            # missing v prefix
            "v0.1.0.1",         # four segments not allowed
            "v0.1.0-test.1.2",  # extra segment
        ],
    )
    def test_invalid(self, tag):
        r = classify(tag)
        assert r.kind == "invalid"
        assert r.version is None
        assert r.error is not None


# ──────────────────────────────────────────────────────────────────────────────
# Version normalization: PEP 440 validity
# ──────────────────────────────────────────────────────────────────────────────


class TestVersionPEP440:
    """Every accepted tag must produce a PEP 440-valid version."""

    def _is_valid_pep440(self, version: str) -> bool:
        try:
            from packaging.version import Version

            Version(version)
            return True
        except Exception:
            return False

    @pytest.mark.parametrize(
        "tag,expected",
        [
            ("v0.1.0", "0.1.0"),
            ("v1.2.3", "1.2.3"),
            ("v1.0.0", "1.0.0"),
            ("v0.1.0-test.1", "0.1.0.dev1"),
            ("v0.1.0-test.2", "0.1.0.dev2"),
            ("v1.0.0-test.5", "1.0.0.dev5"),
        ],
    )
    def test_version_is_pep440(self, tag, expected):
        r = classify(tag)
        assert r.version == expected
        assert self._is_valid_pep440(r.version), f"{r.version!r} is not PEP 440 valid"

    def test_production_sorts_after_test(self):
        """Production version 1.0.0 must sort higher than test 1.0.0.dev3."""
        try:
            from packaging.version import Version

            prod = Version(classify("v1.0.0").version)
            test = Version(classify("v1.0.0-test.3").version)
            assert prod > test, f"Expected {prod} > {test}"
        except ImportError:
            pytest.skip("packaging not installed")


# ──────────────────────────────────────────────────────────────────────────────
# Publishing destination isolation
# ──────────────────────────────────────────────────────────────────────────────


class TestDestinationIsolation:
    """Production tags must not activate TestPyPI; test tags must not activate PyPI."""

    def _would_publish_to_pypi(self, tag: str) -> bool:
        r = classify(tag)
        return r.kind == "production"

    def _would_publish_to_testpypi(self, tag: str) -> bool:
        r = classify(tag)
        return r.kind == "test"

    def _would_publish_either(self, tag: str) -> bool:
        r = classify(tag)
        return r.kind != "invalid"

    # Production tags go only to PyPI
    @pytest.mark.parametrize("tag", ["v0.1.0", "v1.0.0", "v1.2.3"])
    def test_production_tag_goes_to_pypi(self, tag):
        assert self._would_publish_to_pypi(tag) is True

    @pytest.mark.parametrize("tag", ["v0.1.0", "v1.0.0", "v1.2.3"])
    def test_production_tag_not_testpypi(self, tag):
        assert self._would_publish_to_testpypi(tag) is False

    # Test tags go only to TestPyPI
    @pytest.mark.parametrize("tag", ["v0.1.0-test.1", "v0.1.0-test.2", "v1.0.0-test.1"])
    def test_test_tag_goes_to_testpypi(self, tag):
        assert self._would_publish_to_testpypi(tag) is True

    @pytest.mark.parametrize("tag", ["v0.1.0-test.1", "v0.1.0-test.2", "v1.0.0-test.1"])
    def test_test_tag_not_pypi(self, tag):
        assert self._would_publish_to_pypi(tag) is False

    # Invalid tags go nowhere
    @pytest.mark.parametrize(
        "tag",
        ["v0.1", "v0.1.0-test", "v0.1.0-test.0", "v0.1.0-debug", "release-0.1.0"],
    )
    def test_invalid_tag_not_published(self, tag):
        assert self._would_publish_either(tag) is False

    # Mutual exclusivity
    @pytest.mark.parametrize(
        "tag",
        ["v0.1.0", "v0.1.0-test.1", "v1.0.0"],
    )
    def test_exactly_one_destination(self, tag):
        to_pypi = self._would_publish_to_pypi(tag)
        to_test = self._would_publish_to_testpypi(tag)
        # Exactly one of pypi or testpypi, never both
        assert to_pypi != to_test


# ──────────────────────────────────────────────────────────────────────────────
# set_build_version script
# ──────────────────────────────────────────────────────────────────────────────


class TestSetBuildVersion:
    """Unit tests for scripts/set_build_version.py."""

    def _load_module(self):
        spec = importlib.util.spec_from_file_location(
            "set_build_version", REPO_ROOT / "scripts" / "set_build_version.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_module_loads(self):
        mod = self._load_module()
        assert hasattr(mod, "set_pyproject_version")
        assert hasattr(mod, "set_init_version")

    def test_validate_version_accepts_pep440(self):
        mod = self._load_module()
        # Should not raise
        mod._validate_version("1.0.0")
        mod._validate_version("1.0.0.dev1")
        mod._validate_version("0.1.0.dev2")

    def test_validate_version_rejects_empty(self):
        mod = self._load_module()
        with pytest.raises((ValueError, Exception)):
            mod._validate_version("")

    def test_validate_version_rejects_non_version(self):
        mod = self._load_module()
        with pytest.raises((ValueError, Exception)):
            mod._validate_version("not-a-version")


# ──────────────────────────────────────────────────────────────────────────────
# Acceptance table from spec section 11.1
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tag,expected_kind,expected_version",
    [
        ("v0.1.0", "production", "0.1.0"),
        ("v1.2.3", "production", "1.2.3"),
        ("v0.1.0-test.1", "test", "0.1.0.dev1"),
        ("v0.1.0-test.2", "test", "0.1.0.dev2"),
        ("v0.1.0-test.foo", "invalid", None),
        ("v0.1.0-debug", "invalid", None),
        ("v0.1", "invalid", None),
        ("v0.1.0-test.0", "invalid", None),
    ],
)
def test_spec_acceptance_table(tag, expected_kind, expected_version):
    """Verify every row in spec section 11.1 acceptance table."""
    r = classify(tag)
    assert r.kind == expected_kind, f"tag={tag!r}: expected kind={expected_kind!r}, got {r.kind!r}"
    assert r.version == expected_version, (
        f"tag={tag!r}: expected version={expected_version!r}, got {r.version!r}"
    )
