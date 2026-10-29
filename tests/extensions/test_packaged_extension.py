"""Exercise actual wheel and release ZIP copies in an isolated stdlib interpreter."""

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WHEEL = ROOT / "dist/rendereye_mcp-1.0.0-py3-none-any.whl"
ZIP = ROOT / "dist/phase56-packages/RenderEyeMCP-Extension-v1.0.0.zip"


@pytest.mark.parametrize("artifact", [WHEEL, ZIP], ids=["wheel-setup", "extension-zip"])
def test_packaged_lifecycle(artifact, tmp_path):
    if not artifact.exists():
        pytest.skip("Build wheel and Phase 5.6 release ZIP first")
    unpacked = tmp_path / "unpacked"
    with zipfile.ZipFile(artifact) as archive:
        archive.extractall(unpacked)
        for source in (ROOT / "extensions/rendereye").glob("*"):
            if source.suffix not in (".py", ".json"):
                continue
            name = source.name
            if artifact == WHEEL:
                name = "rendereye_init.py" if name == "__init__.py" else name
                packaged = unpacked / "rendereye_mcp/_extension_data" / name
            else:
                packaged = unpacked / "rendereye" / name
            assert packaged.read_bytes() == source.read_bytes()
    installed = tmp_path / "installed/rendereye"
    if artifact == WHEEL:
        install = f"sys.path.insert(0, {str(unpacked)!r}); from rendereye_mcp.setup_cmd import install_extension; assert install_extension(Path({str(installed)!r}))"
    else:
        installed = unpacked / "rendereye"
        install = ""
    code = f"""
import sys, os, threading, json
from pathlib import Path
from types import SimpleNamespace
{install}
sys.path.insert(0, {str(installed.parent)!r})
os.environ['RENDEREYE_IPC_PORT'] = '0'
import rendereye
class Context:
    def IsCaptureLoaded(self): return False
    def IsCaptureLoading(self): return False
    def GetCaptureFilename(self): return ''
    def Extensions(self):
        helper = SimpleNamespace(InvokeOntoUIThread=lambda callback: callback())
        return SimpleNamespace(GetMiniQtHelper=lambda: helper)
ctx = Context()
for i in range(3):
    rendereye.register('1.46', ctx)
    assert rendereye._runtime.gui.context is ctx
    rendereye.unregister()
assert not any(t.name.startswith('rendereye-') for t in threading.enumerate())
assert rendereye._runtime is None
"""
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code],
        cwd=tmp_path,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
