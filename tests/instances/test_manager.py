"""Tests for InstanceManager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from rendereye_mcp.instances.manager import InstanceManager
from rendereye_mcp.instances.models import InstanceOwnership, InstanceStatus


def test_refresh_with_no_processes():
    with patch(
        "rendereye_mcp.instances.manager.discover_renderdoc_instances", return_value=[]
    ), patch(
        "rendereye_mcp.instances.manager.discover_all_windows", return_value=[]
    ):
        mgr = InstanceManager()
        mgr.refresh()
    assert mgr.list_instances() == [] or all(
        i.status == InstanceStatus.EXITED for i in mgr.list_instances()
    )


def test_register_launched_creates_managed_instance():
    mgr = InstanceManager()
    mock_ps = MagicMock()
    mock_ps.is_running.return_value = True
    with patch("psutil.Process", return_value=mock_ps):
        inst = mgr.register_launched(1234, 100.0, "C:/Program Files/RenderDoc/qrenderdoc.exe")
    assert inst.ownership.value == "managed"
    assert inst.process_id == 1234


def test_get_instance_by_id():
    mgr = InstanceManager()
    inst = mgr.register_launched(1234, 100.0, "D:/test.exe")
    found = mgr.get_instance(inst.instance_id)
    assert found is inst


def test_get_instance_by_pid():
    mgr = InstanceManager()
    inst = mgr.register_launched(5678, 200.0, "D:/test.exe")
    found = mgr.get_instance_by_pid(5678)
    assert found is inst


def test_get_nonexistent_instance():
    mgr = InstanceManager()
    assert mgr.get_instance("instance-999999") is None


def test_list_instances_empty():
    mgr = InstanceManager()
    assert mgr.list_instances() == []


def test_list_windows_empty():
    mgr = InstanceManager()
    assert mgr.list_windows() == []


def test_get_window_not_found():
    mgr = InstanceManager()
    assert mgr.get_window("window-000001") is None


def test_instance_id_format():
    mgr = InstanceManager()
    inst = mgr.register_launched(1111, 1.0, "D:/test.exe")
    assert inst.instance_id.startswith("instance-")
    assert len(inst.instance_id) == len("instance-000001")


def test_multiple_instances_unique_ids():
    mgr = InstanceManager()
    inst1 = mgr.register_launched(1111, 1.0, "D:/test.exe")
    inst2 = mgr.register_launched(2222, 2.0, "D:/test.exe")
    assert inst1.instance_id != inst2.instance_id


def test_pid_in_managed_pids_after_register():
    mgr = InstanceManager()
    mgr.register_launched(9876, 1.0, "D:/test.exe")
    assert 9876 in mgr._managed_pids


def test_refresh_keeps_managed_classification():
    from datetime import datetime, timezone

    from rendereye_mcp.instances.models import InstanceRecord, InstanceStatus

    mgr = InstanceManager()
    mgr.register_launched(1234, 100.0, "D:/test.exe")

    # Simulate process still running
    disc = InstanceRecord(
        instance_id="",
        process_id=1234,
        process_create_time=100.0,
        exe_path="D:/test.exe",
        ownership=InstanceOwnership.EXTERNAL,
        status=InstanceStatus.RUNNING,
        last_seen_at=datetime.now(timezone.utc),
    )

    with patch(
        "rendereye_mcp.instances.manager.discover_renderdoc_instances", return_value=[disc]
    ), patch(
        "rendereye_mcp.instances.manager.discover_all_windows", return_value=[]
    ):
        mgr.refresh()

    instances = mgr.list_instances()
    running = [i for i in instances if i.status == InstanceStatus.RUNNING]
    assert len(running) == 1
    assert running[0].ownership == InstanceOwnership.MANAGED
