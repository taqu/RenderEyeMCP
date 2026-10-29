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
        ("v1.2.3-test.1", "test", "1.2.3.dev1"),
        ("v0.1.0-test.foo", "invalid", None),
        ("v0.1.0-debug", "invalid", None),
        ("v0.1", "invalid", None),
        ("v0.1.0-test.0", "invalid", None),
    ],
)
def test_spec_acceptance_table(tag, expected_kind, expected_version):
    """Verify every row in the phase15.1 acceptance table."""
    r = classify(tag)
    assert r.kind == expected_kind, f"tag={tag!r}: expected kind={expected_kind!r}, got {r.kind!r}"
    assert r.version == expected_version, (
        f"tag={tag!r}: expected version={expected_version!r}, got {r.version!r}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Workflow YAML structure validation
# ──────────────────────────────────────────────────────────────────────────────


class TestWorkflowStructure:
    """Verify each workflow YAML has the correct publishing isolation."""

    PYPI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-pypi.yml"
    TESTPYPI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-testpypi.yml"

    def _load_yaml(self, path: Path) -> dict:
        try:
            import yaml
        except ImportError:
            pytest.skip("pyyaml not installed")
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _raw_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_workflow_files_exist(self):
        assert self.PYPI_WORKFLOW.exists(), "publish-pypi.yml not found"
        assert self.TESTPYPI_WORKFLOW.exists(), "publish-testpypi.yml not found"

    def test_pypi_workflow_name(self):
        data = self._load_yaml(self.PYPI_WORKFLOW)
        assert data["name"] == "Publish to PyPI"

    def test_testpypi_workflow_name(self):
        data = self._load_yaml(self.TESTPYPI_WORKFLOW)
        assert data["name"] == "Publish to TestPyPI"

    def test_pypi_workflow_has_no_testpypi_job(self):
        data = self._load_yaml(self.PYPI_WORKFLOW)
        jobs = data.get("jobs", {})
        assert "publish-testpypi" not in jobs, (
            "publish-pypi.yml must not contain a publish-testpypi job"
        )

    def test_testpypi_workflow_has_no_pypi_job(self):
        data = self._load_yaml(self.TESTPYPI_WORKFLOW)
        jobs = data.get("jobs", {})
        assert "publish-pypi" not in jobs, (
            "publish-testpypi.yml must not contain a publish-pypi job"
        )

    def test_pypi_workflow_has_publish_pypi_job(self):
        data = self._load_yaml(self.PYPI_WORKFLOW)
        jobs = data.get("jobs", {})
        assert "publish-pypi" in jobs, "publish-pypi.yml must contain a publish-pypi job"

    def test_testpypi_workflow_has_publish_testpypi_job(self):
        data = self._load_yaml(self.TESTPYPI_WORKFLOW)
        jobs = data.get("jobs", {})
        assert "publish-testpypi" in jobs, (
            "publish-testpypi.yml must contain a publish-testpypi job"
        )

    def test_pypi_workflow_environment_is_pypi(self):
        data = self._load_yaml(self.PYPI_WORKFLOW)
        job = data["jobs"]["publish-pypi"]
        env = job.get("environment", {})
        name = env.get("name") if isinstance(env, dict) else env
        assert name == "pypi", f"publish-pypi job environment must be 'pypi', got {name!r}"

    def test_testpypi_workflow_environment_is_testpypi(self):
        data = self._load_yaml(self.TESTPYPI_WORKFLOW)
        job = data["jobs"]["publish-testpypi"]
        env = job.get("environment", {})
        name = env.get("name") if isinstance(env, dict) else env
        assert name == "testpypi", (
            f"publish-testpypi job environment must be 'testpypi', got {name!r}"
        )

    def test_pypi_workflow_publish_job_has_oidc_permission(self):
        data = self._load_yaml(self.PYPI_WORKFLOW)
        job = data["jobs"]["publish-pypi"]
        perms = job.get("permissions", {})
        assert perms.get("id-token") == "write", (
            "publish-pypi job must have id-token: write"
        )

    def test_testpypi_workflow_publish_job_has_oidc_permission(self):
        data = self._load_yaml(self.TESTPYPI_WORKFLOW)
        job = data["jobs"]["publish-testpypi"]
        perms = job.get("permissions", {})
        assert perms.get("id-token") == "write", (
            "publish-testpypi job must have id-token: write"
        )

    def test_pypi_workflow_build_job_lacks_oidc_permission(self):
        data = self._load_yaml(self.PYPI_WORKFLOW)
        job = data["jobs"]["build"]
        perms = job.get("permissions", {})
        assert perms.get("id-token") != "write", (
            "build job in publish-pypi.yml must not have id-token: write"
        )

    def test_testpypi_workflow_build_job_lacks_oidc_permission(self):
        data = self._load_yaml(self.TESTPYPI_WORKFLOW)
        job = data["jobs"]["build"]
        perms = job.get("permissions", {})
        assert perms.get("id-token") != "write", (
            "build job in publish-testpypi.yml must not have id-token: write"
        )

    def test_pypi_workflow_uses_pypi_action(self):
        text = self._raw_text(self.PYPI_WORKFLOW)
        assert "pypa/gh-action-pypi-publish" in text, (
            "publish-pypi.yml must use pypa/gh-action-pypi-publish"
        )
        # Must NOT contain TestPyPI repository URL
        assert "test.pypi.org/legacy" not in text, (
            "publish-pypi.yml must not reference test.pypi.org/legacy"
        )

    def test_testpypi_workflow_uses_testpypi_url(self):
        text = self._raw_text(self.TESTPYPI_WORKFLOW)
        assert "test.pypi.org/legacy" in text, (
            "publish-testpypi.yml must publish to https://test.pypi.org/legacy/"
        )

    def test_pypi_workflow_trigger_pattern(self):
        data = self._load_yaml(self.PYPI_WORKFLOW)
        # pyyaml parses the bare 'on' key as Python True (YAML boolean alias)
        on = data.get("on") or data.get(True)
        tags = on["push"]["tags"]
        assert "v*" in tags, "publish-pypi.yml must trigger on v* tags"

    def test_testpypi_workflow_trigger_pattern(self):
        data = self._load_yaml(self.TESTPYPI_WORKFLOW)
        on = data.get("on") or data.get(True)
        tags = on["push"]["tags"]
        assert any("test" in t for t in tags), (
            "publish-testpypi.yml must trigger on test-release tag patterns"
        )

    def test_pypi_workflow_rejects_test_tags_in_classify(self):
        text = self._raw_text(self.PYPI_WORKFLOW)
        # Must reference a guard against non-production tags
        assert "production" in text, (
            "publish-pypi.yml classify job must validate kind == production"
        )

    def test_testpypi_workflow_rejects_production_tags_in_classify(self):
        text = self._raw_text(self.TESTPYPI_WORKFLOW)
        # Must reference a guard against non-test tags
        assert "kind" in text and "test" in text, (
            "publish-testpypi.yml classify job must validate kind == test"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Phase 15.1 acceptance table (full spec)
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tag,testpypi_publishes,pypi_publishes",
    [
        ("v0.1.0",       False, True),
        ("v0.1.0-test.1", True, False),
        ("v0.1.0-test.2", True, False),
        ("v1.2.3",       False, True),
        ("v1.2.3-test.1", True, False),
        ("v1.2.3-debug", False, False),
        ("v1.2",         False, False),
    ],
)
def test_phase15_1_acceptance_table(tag, testpypi_publishes, pypi_publishes):
    """Verify the phase15.1 acceptance table for tag routing."""
    r = classify(tag)
    actual_pypi = r.kind == "production"
    actual_testpypi = r.kind == "test"
    assert actual_pypi == pypi_publishes, (
        f"tag={tag!r}: PyPI expected={pypi_publishes}, got kind={r.kind!r}"
    )
    assert actual_testpypi == testpypi_publishes, (
        f"tag={tag!r}: TestPyPI expected={testpypi_publishes}, got kind={r.kind!r}"
    )
