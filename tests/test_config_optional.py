"""自架時的選用整合：沒設定就關閉，不再連到原作者家裡的預設 IP／帳號。

檔名以 c 開頭：要比 test_devicehub_module.py（會用假的 app.utils 取代真的）先被收集。
執行：在 repo 根目錄 `python -m pytest tests`
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("AXIS_BASE_PATH", tempfile.mkdtemp(prefix="axis-test-"))
os.environ.setdefault("AXIS_JWT_SECRET", "t" * 64)

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app.routers import github_repos, minecraft, proxmox, system, vm_user  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ADMIN = {"username": "admin", "role": "Administrator"}


def _fresh_import(code: str, env: dict) -> str:
    """在乾淨的環境變數下匯入模組（模組層級的預設值只在匯入時決定）。"""
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("PVE_", "DEVICEHUB_", "MC_", "DYNU_", "AXIS_ADMIN"))}
    base.update({"AXIS_BASE_PATH": tempfile.mkdtemp(prefix="axis-test-"), "AXIS_JWT_SECRET": "t" * 64}, **env)
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, env=base, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip().splitlines()[-1]


# ---------- 預設值 ----------
def test_config_defaults_have_no_home_ips():
    got = json.loads(_fresh_import(
        "import json, app.config as c; print(json.dumps([c.PVE_HOST, c.PVE_CONSOLE_HOST, c.PVE_VM_STORAGE]))", {}))
    assert got == ["", "", "local-lvm"]


def test_console_host_falls_back_to_pve_host():
    got = json.loads(_fresh_import(
        "import json, app.config as c; print(json.dumps([c.PVE_HOST, c.PVE_CONSOLE_HOST]))", {"PVE_HOST": "10.0.0.2"}))
    assert got == ["10.0.0.2", "10.0.0.2"]


def test_devicehub_tokens_ignored_without_url():
    code = ("import json; from app.routers import devicehub as d; "
            "print(json.dumps([d.DEVICEHUB_URL, d.DEVICEHUB_TOKEN, d.DEVICEHUB_CONTROL_TOKEN]))")
    assert json.loads(_fresh_import(code, {"DEVICEHUB_TOKEN": "r", "DEVICEHUB_CONTROL_TOKEN": "c"})) == ["", "", ""]
    assert json.loads(_fresh_import(code, {"DEVICEHUB_URL": "http://hub:8080/", "DEVICEHUB_TOKEN": "r"})) == \
        ["http://hub:8080", "r", ""]


def test_minecraft_defaults():
    code = "import json; from app.routers import minecraft as m; print(json.dumps([m.MC_LXC_IP, m.MC_LXC_PORT, m.MC_PUBLIC_HOST]))"
    assert json.loads(_fresh_import(code, {})) == ["", 25565, ""]
    assert json.loads(_fresh_import(code, {"MC_HOST": "10.0.0.9", "MC_PORT": "abc"})) == ["10.0.0.9", 25565, ""]


# ---------- Proxmox ----------
def test_proxmox_not_configured(monkeypatch):
    monkeypatch.setattr(proxmox, "PVE_HOST", "")
    assert proxmox.get_pve_client() is None
    assert proxmox.list_pve_vms(user=ADMIN) == []
    # 頁面載入用的狀態：200＋configured=false（前端顯示說明卡片，不跳錯誤）
    assert proxmox.get_pve_status(user=ADMIN)["configured"] is False
    # 使用者按下的操作：503＋說明
    for call in (lambda: proxmox.vm_action(100, "pve", "start", user=ADMIN),
                 lambda: proxmox.deploy_vm("ubuntu", user=ADMIN)):
        with pytest.raises(HTTPException) as e:
            call()
        assert e.value.status_code == 503


def test_deploy_needs_root_password(monkeypatch):
    monkeypatch.setattr(proxmox, "PVE_HOST", "10.0.0.2")
    monkeypatch.setattr(proxmox, "PVE_PASS", None)
    with pytest.raises(HTTPException) as e:
        proxmox.deploy_vm("ubuntu", user=ADMIN)
    assert e.value.status_code == 503 and "PVE_PASS" in e.value.detail


def test_console_url(monkeypatch):
    monkeypatch.setattr(vm_user, "PVE_CONSOLE_HOST", "")
    with pytest.raises(HTTPException) as e:
        vm_user.get_console_url(101, "pve", user=ADMIN)
    assert e.value.status_code == 503
    monkeypatch.setattr(vm_user, "PVE_CONSOLE_HOST", "100.64.0.7")
    assert vm_user.get_console_url(101, "pve", user=ADMIN)["url"].startswith("https://100.64.0.7:8006/")


# ---------- Minecraft ----------
def test_minecraft_not_configured(monkeypatch):
    monkeypatch.setattr(minecraft, "MC_LXC_IP", "")
    assert minecraft._check_online() is False
    with pytest.raises(HTTPException) as e:
        minecraft._ssh_exec("echo hi")
    assert e.value.status_code == 503


# ---------- 開源分享 ----------
def test_opensource_has_no_default_author(monkeypatch, tmp_path):
    monkeypatch.setattr(github_repos, "CONFIG_FILE", str(tmp_path / "cfg.json"))
    monkeypatch.setattr(github_repos, "REPOS_FILE", str(tmp_path / "repos.json"))

    def no_network(*a, **k):
        raise AssertionError("沒設定作者時不該呼叫 GitHub")

    monkeypatch.setattr(github_repos.requests, "get", no_network)
    assert github_repos._load_config()["developer_name"] == ""
    assert github_repos._load_repos() == []
    assert github_repos.get_github_config(user=None) == {"developer_name": "", "github_url": ""}


# ---------- 智慧宅控：沒有感測器來源時要標示出來 ----------
@pytest.mark.parametrize("blynk, source", [(None, None), ("tok", "blynk")])
def test_sensors_report_source(monkeypatch, blynk, source):
    def no_network(*a, **k):
        raise system.requests.RequestException("offline")

    monkeypatch.setattr(system, "BLYNK_TOKEN", blynk)
    monkeypatch.setattr(system.requests, "get", no_network)
    monkeypatch.setattr(system.psutil, "sensors_temperatures", lambda: {}, raising=False)  # Windows 沒有這個函式
    monkeypatch.setattr(minecraft, "MC_LXC_IP", "")
    assert system.get_sensors(user=ADMIN)["sensors"]["source"] == source
