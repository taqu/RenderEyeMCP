"""Windows GUI smoke test of wheel-installed discovery, reload, IPC, and reconnect.

Run after uv build --wheel. Uses a unique test extension name, two hidden owned
processes, an ephemeral loopback listener, and a private token. It never replaces
the user's rendereye installation. Reports go under dist/phase56-real.
Capture replay requires separate validation with real compatible .rdc files.
"""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

from rendereye_mcp.config import Config
from rendereye_mcp.ipc.authentication import AuthManager
from rendereye_mcp.ipc.manager import ExtensionConnectionManager
from rendereye_mcp.ipc.transport import IPCTransport
from rendereye_mcp.setup_cmd import detect_renderdoc, install_extension


async def main(args):
    if sys.platform != "win32":
        raise SystemExit("This GUI smoke harness currently supports Windows only")
    executable = args.renderdoc or detect_renderdoc()
    if not executable:
        raise SystemExit("RenderDoc not found; provide --renderdoc")
    root = Path(__file__).resolve().parents[1]
    work = root / "dist" / "phase56-real"
    work.mkdir(parents=True, exist_ok=True)
    name = "rendereye_phase56_" + uuid.uuid4().hex[:8]
    target = Path(os.environ["APPDATA"]) / "qrenderdoc/extensions" / name
    assert not target.exists()
    # Install from wheel resources, not the source checkout.
    wheel = root / "dist/rendereye_mcp-1.0.0-py3-none-any.whl"
    resources = work / name / "_extension_data"
    resources.mkdir(parents=True)
    with zipfile.ZipFile(wheel) as z:
        for item in z.namelist():
            if "/_extension_data/" in item and not item.endswith("/"):
                (resources / Path(item).name).write_bytes(z.read(item))
    import rendereye_mcp.setup_cmd as setup

    previous_resources = setup._EXT_DATA
    processes = []
    transport = None
    auth = None
    try:
        setup._EXT_DATA = resources
        assert install_extension(target)
        auth = AuthManager(token_path=work / (name + "-token.txt"))
        auth.generate()
        manager = ExtensionConnectionManager(auth_manager=auth)
        config = Config()
        config.ipc_port = 0
        transport = IPCTransport(config, conn_manager=manager)
        await transport.start()
        port = transport._server.sockets[0].getsockname()[1]
        report = work / (name + ".json")
        script = work / (name + ".py")
        script.write_text(
            """import importlib, json, os, sys, threading, time, traceback
    from PySide2 import QtCore, QtWidgets
    report = {"python": sys.version, "reloads": []}
    name = NAME
    out = OUTPUT + "." + str(os.getpid()) + ".json"
    try:
        mgr = pyrenderdoc.Extensions()
        report["discovered"] = [str(e.package) for e in mgr.GetInstalledExtensions()]
        for i in range(4):
            error = mgr.LoadExtension(name)
            report["reloads"].append(str(error))
            if error: raise RuntimeError(str(error))
            module = importlib.import_module(name)
            report["runtime_version"] = module._runtime.gui.version
            report["context_type"] = str(type(module._runtime.gui.context))
            time.sleep(.5)
        report["workers"] = [t.name for t in threading.enumerate() if t.name.startswith("rendereye-")]
        time.sleep(15)
        module.unregister()
        report["workers_after_unregister"] = [t.name for t in threading.enumerate() if t.name.startswith("rendereye-")]
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        with open(out, "w") as f: json.dump(report, f, indent=2)
        pyrenderdoc.Extensions().GetMiniQtHelper().InvokeOntoUIThread(lambda: pyrenderdoc.GetMainWindow().Widget().close())
    """.replace("\n    ", "\n")
            .replace("NAME", repr(name))
            .replace("OUTPUT", repr(str(report))),
            encoding="utf-8",
        )
        compile(script.read_text(encoding="utf-8"), str(script), "exec")
        env = os.environ.copy()
        env["RENDEREYE_TOKEN_PATH"] = str(auth.get_token_path())
        env["RENDEREYE_IPC_PORT"] = str(port)
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        for _ in range(2):
            processes.append(
                subprocess.Popen(
                    [executable, "--ui-python", str(script)], env=env, startupinfo=startup
                )
            )
        observations = []
        restarted = False
        results = []
        for i in range(120):
            connections = manager.list_connections()
            if connections:
                observations.append([c.to_dict() for c in connections])
            active = [c for c in connections if c.connected]
            if i >= 28 and len(active) == 2 and not restarted:
                from rendereye_mcp.ipc.protocol import GetGuiStateMessage

                for connection in list(transport._connections):
                    response = await connection.send_request(
                        GetGuiStateMessage(request_id=uuid.uuid4().hex)
                    )
                    results.append({"get_gui_state": response.capture_state})
                for conn in active:
                    result, error = await manager.execute_gui_command(
                        conn.connection_id, "focus_window", {}
                    )
                    results.append(
                        {
                            "command_outcome": result.outcome if result else error,
                            "error": result.error if result else error,
                        }
                    )
                await transport.stop()
                for connection in list(transport._connections):
                    await connection._close()
                auth.generate()
                config.ipc_port = port
                transport = IPCTransport(config, conn_manager=manager)
                await transport.start()
                restarted = True
            if all(p.poll() is not None for p in processes):
                break
            await asyncio.sleep(0.25)
        reports = list(work.glob(report.name + ".*.json"))
        for item in reports:
            print(item.read_text())
        print("SERVER RESTARTED:", restarted, "REQUESTS:", results)
        (work / "request-results.json").write_text(json.dumps(results, indent=2))
        (work / "ipc-observations.json").write_text(
            json.dumps(observations, indent=2), encoding="utf-8"
        )
        print("IPC snapshots:", len(observations))
        data = [json.loads(item.read_text()) for item in reports]
        by_instance = {}
        for snapshot in observations:
            for connection in snapshot:
                by_instance.setdefault(connection["instance_id"], set()).add(
                    connection["connection_id"]
                )
        reconnected = sum(len(ids) >= 2 for ids in by_instance.values()) == 2
        max_active = max((sum(c["connected"] for c in snap) for snap in observations), default=0)
        successful = (
            len(data) == 2
            and restarted
            and reconnected
            and max_active == 2
            and all(not item.get("error") and item["reloads"] == [""] * 4 for item in data)
            and all(not item["workers_after_unregister"] for item in data)
            and all(
                sorted(item["workers"]) == ["rendereye-ipc", "rendereye-state-observer"]
                for item in data
            )
            and len([r for r in results if r.get("get_gui_state") == "unloaded"]) == 2
            and len([r for r in results if r.get("command_outcome") == "unsupported"]) == 2
            and all(p.poll() == 0 for p in processes)
        )
        (work / "summary.json").write_text(
            json.dumps(
                {
                    "passed": successful,
                    "reconnected_instances": 2 if reconnected else 0,
                    "max_active_connections": max_active,
                    "gui_reports": data,
                    "requests": results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print("PROCESSES:", [(p.pid, p.poll()) for p in processes])
        print("Reports:", [str(item) for item in reports])
        if not successful:
            raise RuntimeError("GUI smoke validation incomplete; inspect reports")
    finally:
        if transport is not None:
            await transport.stop()
            for connection in list(transport._connections):
                await connection._close()
        # Only terminate the exact test process created above if its script failed to exit.
        for owned in processes:
            if owned.poll() is None:
                owned.terminate()
                owned.wait(timeout=5)
        if auth is not None:
            auth.cleanup()
        setup._EXT_DATA = previous_resources
        resolved = target.resolve()
        allowed = (Path(os.environ["APPDATA"]) / "qrenderdoc/extensions").resolve()
        assert resolved.parent == allowed and resolved.name == name
        if resolved.exists():
            shutil.rmtree(resolved)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate a built wheel in two owned RenderDoc GUIs"
    )
    parser.add_argument("--renderdoc", help="Path to qrenderdoc.exe")
    asyncio.run(main(parser.parse_args()))
