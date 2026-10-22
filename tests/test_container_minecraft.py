"""多重宇宙頁的容器模式（MC_CONTAINER）：指令走 rcon-cli、切換模組包直接換資料目錄的 zip，不用 SSH。

檔名以 c 開頭：要比 test_devicehub_module.py（會用假的 app.utils 取代真的）先被收集。
執行：在 repo 根目錄 `python -m pytest tests`
"""
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("AXIS_BASE_PATH", tempfile.mkdtemp(prefix="axis-test-"))
os.environ.setdefault("AXIS_JWT_SECRET", "t" * 64)

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app.routers import minecraft  # noqa: E402

ADMIN = {"username": "admin", "role": "Administrator"}
MEMBER = {"username": "bob", "role": "Member"}


class FakeContainer:
    def __init__(self, env=None, running=True, exec_result=(0, b"")):
        env = {"VERSION": "1.20.1", "GENERIC_PACK": "/data/server.zip", "LEVEL": "world",
               "MAX_MEMORY": "9G", **(env or {})}
        self.attrs = {
            "Config": {"Env": [f"{k}={v}" for k, v in env.items()]},
            "State": {"Running": running, "StartedAt": "2026-09-30T08:02:15Z"},
            "HostConfig": {"Memory": 8 * 1024 ** 3, "NanoCpus": 4_000_000_000},
        }
        self.exec_result = exec_result
        self.calls = []

    def exec_run(self, argv):
        self.calls.append(("exec", argv))
        return SimpleNamespace(exit_code=self.exec_result[0], output=self.exec_result[1])

    def stop(self, timeout=10):
        self.calls.append(("stop", timeout))

    def start(self):
        self.calls.append(("start",))


def _zip(path, names):
    with zipfile.ZipFile(path, "w") as z:
        for n in names:
            z.writestr(n, n)
    return str(path)


@pytest.fixture
def mc(monkeypatch, tmp_path):
    """容器模式＋暫存的資料目錄與函式庫；回傳 (container, data_dir, packs_dir)。"""
    data, packs = tmp_path / "minecraft-data", tmp_path / "packs"
    data.mkdir()
    packs.mkdir()
    container = FakeContainer()
    logs = []
    monkeypatch.setattr(minecraft, "MC_CONTAINER", "axis-mc")
    monkeypatch.setattr(minecraft, "MC_DATA_DIR", str(data))
    monkeypatch.setattr(minecraft, "PACKS_DIR", str(packs))
    monkeypatch.setattr(minecraft, "INFO_FILE", str(tmp_path / "info.json"))
    monkeypatch.setattr(minecraft, "_mc_container", lambda: container)
    monkeypatch.setattr(minecraft, "log_event", lambda *a, **k: logs.append(a))
    monkeypatch.setattr(minecraft, "_java_version_cache", {})

    def no_ssh(*a, **k):
        raise AssertionError("容器模式不該用 SSH")

    monkeypatch.setattr(minecraft.paramiko, "SSHClient", no_ssh)
    container.logs = logs
    return container, data, packs


# ---------- 送指令 ----------
def test_command_goes_through_rcon(mc):
    container, _, _ = mc
    container.exec_result = (0, b"There are 0 of a max of 20 players online: \n\x1b[0m")
    got = minecraft.send_mc_command(minecraft.MCCommandRequest(command="/list"), user=ADMIN)
    assert container.calls == [("exec", ["rcon-cli", "list"])]   # 整條指令是單一參數、不經 shell
    assert got["status"] == "ok" and got["response"] == "There are 0 of a max of 20 players online:"
    assert "axis-mc" in container.logs[0][1]


def test_command_is_not_split_or_interpreted(mc):
    container, _, _ = mc
    minecraft.send_mc_command(minecraft.MCCommandRequest(command="say hi; $(reboot) 'x'"), user=ADMIN)
    assert container.calls == [("exec", ["rcon-cli", "say hi; $(reboot) 'x'"])]


def test_command_admin_only_and_not_empty(mc):
    container, _, _ = mc
    for req, user, code in (("list", MEMBER, 403), ("  ", ADMIN, 400), ("/", ADMIN, 400)):
        with pytest.raises(HTTPException) as e:
            minecraft.send_mc_command(minecraft.MCCommandRequest(command=req), user=user)
        assert e.value.status_code == code
    assert container.calls == []


def test_command_failure_is_reported(mc):
    container, _, _ = mc
    container.exec_result = (1, b"dial tcp 127.0.0.1:25575: connection refused")
    with pytest.raises(HTTPException) as e:
        minecraft.send_mc_command(minecraft.MCCommandRequest(command="list"), user=ADMIN)
    assert e.value.status_code == 500 and "connection refused" in e.value.detail
    assert container.logs == []


# ---------- 狀態 ----------
def test_status_reads_container(mc, monkeypatch):
    container, _, _ = mc
    container.exec_result = (0, b'openjdk version "17.0.12" 2024-07-16\nOpenJDK Runtime')
    monkeypatch.setattr(minecraft, "_check_online", lambda: True)
    monkeypatch.setattr(minecraft.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    got = minecraft.get_mc_status(user=ADMIN)
    assert got["server"]["uptime"] == "Running"
    assert got["server"]["java_version"] == "openjdk version 17.0.12 2024-07-16"
    assert got["specs"] == {"ram": "8.0 GB", "jvm_heap": "9G (-Xmx9G)", "cpu_threads": 4, "container": "Docker axis-mc"}
    minecraft.get_mc_status(user=ADMIN)
    assert container.calls == [("exec", ["java", "-version"])]    # Java 版本只問一次


# ---------- 切換模組包 ----------
def test_switch_keeps_each_packs_world(mc):
    container, data, packs = mc
    (data / "server.zip").write_text("original pack")
    (data / "world").mkdir()
    (data / "world" / "level.dat").write_text("first world")
    a = _zip(packs / "A.zip", ["mods/a.jar", "libraries/net/minecraftforge/forge/1.20.1-47.4.16/unix_args.txt"])
    b = _zip(packs / "B.zip", ["Pack/mods/b.jar"])

    # 第一次切換：原本那份不在函式庫的 zip 要收進函式庫；不知道歸屬的世界另外保留
    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="A.zip"), user=ADMIN)
    assert container.calls == [("stop", 120), ("start",)]
    assert (packs / "server.zip").read_text() == "original pack"
    assert (data / "server.zip").read_bytes() == open(a, "rb").read()
    assert not (data / "world").exists()
    kept = [p for p in (data / ".axis-worlds").iterdir() if p.name.startswith("unassigned_")]
    assert len(kept) == 1 and (kept[0] / "level.dat").read_text() == "first world"
    assert (data / ".axis-active-pack").read_text() == "A.zip"

    # A 產生了世界 → 切到 B → 再切回 A：A 的世界要回來
    (data / "world").mkdir()
    (data / "world" / "level.dat").write_text("world of A")
    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="B.zip"), user=ADMIN)
    assert not (data / "world").exists()
    assert (data / "server.zip").read_bytes() == open(b, "rb").read()
    listed = {p["name"]: p for p in minecraft.list_packs(user=ADMIN)["packs"]}
    assert listed["A.zip"]["has_world"] and not listed["A.zip"]["active"]
    assert listed["B.zip"]["active"] and not listed["B.zip"]["has_world"]

    (data / "world").mkdir()
    (data / "world" / "level.dat").write_text("world of B")
    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="A.zip"), user=ADMIN)
    assert (data / "world" / "level.dat").read_text() == "world of A"
    assert minecraft.list_packs(user=ADMIN)["active_pack"] == "A.zip"

    # 重置地圖：只刪要切過去那一包的世界，其他包的不動
    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="B.zip", reset_world=True), user=ADMIN)
    assert not (data / "world").exists()
    assert (data / ".axis-worlds" / minecraft._pack_slug("A.zip") / "level.dat").read_text() == "world of A"
    assert not (data / ".axis-worlds" / minecraft._pack_slug("B.zip")).exists()
    assert (kept[0] / "level.dat").read_text() == "first world"
    assert not (data / "server.zip.axis-tmp").exists()


def test_switch_refuses_other_minecraft_version_before_stopping(mc):
    container, data, packs = mc
    (data / "world").mkdir()
    _zip(packs / "old.zip", ["server/libraries/net/minecraftforge/forge/1.18.2-40.2.21/unix_args.txt"])
    with pytest.raises(HTTPException) as e:
        minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="old.zip"), user=ADMIN)
    assert e.value.status_code == 500 and "1.18.2" in e.value.detail and "1.20.1" in e.value.detail
    assert container.calls == [] and (data / "world").is_dir()


AUTO_ENTRYPOINT = ["/bin/sh", "-c", "if [ -f /data/.axis-pack.env ]; then set -a; . /data/.axis-pack.env; "
                   "set +a; fi; exec /image/scripts/start"]


def test_switch_applies_pack_version_when_container_reads_pack_env(mc):
    container, data, packs = mc
    container.attrs["Config"]["Entrypoint"] = AUTO_ENTRYPOINT
    container.start = lambda: container.calls.append(("start", (data / ".axis-pack.env").read_text()))
    _zip(packs / "old.zip", ["转世/libraries/net/minecraftforge/forge/1.19.2-43.4.16/forge-1.19.2-43.4.16-server.jar"])
    _zip(packs / "new.zip", ["libraries/net/minecraftforge/forge/1.20.1-47.4.0/unix_args.txt"])
    _zip(packs / "plain.zip", ["mods/a.jar"])

    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="old.zip"), user=ADMIN)
    # 版本要在啟動之前寫好
    assert container.calls == [("stop", 120), ("start", "VERSION=1.19.2\nFORGE_VERSION=43.4.16\n")]

    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="new.zip"), user=ADMIN)
    assert (data / ".axis-pack.env").read_text() == "VERSION=1.20.1\nFORGE_VERSION=47.4.0\n"

    # 看不出版本的包：刪掉覆寫，回到 .env 的設定
    container.start = lambda: container.calls.append(("start",))
    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="plain.zip"), user=ADMIN)
    assert not (data / ".axis-pack.env").exists()


def test_switch_refuses_java21_pack_before_stopping(mc):
    container, data, packs = mc
    container.attrs["Config"]["Entrypoint"] = AUTO_ENTRYPOINT
    _zip(packs / "new.zip", ["libraries/net/minecraftforge/forge/1.20.6-50.1.0/unix_args.txt"])
    with pytest.raises(HTTPException) as e:
        minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="new.zip"), user=ADMIN)
    assert "Java 21" in e.value.detail and container.calls == []
    assert not (data / ".axis-pack.env").exists()


@pytest.mark.parametrize("version,want", [("1.19.2", False), ("1.20.1", False), ("1.20.4", False),
                                          ("1.20.5", True), ("1.21", True), ("1.21.1", True)])
def test_needs_java21(version, want):
    assert minecraft._needs_java21(version) is want


@pytest.mark.parametrize("env", [{"LEVEL": ""}, {"GENERIC_PACK": ""}, {"GENERIC_PACK": "/data/../etc/x.zip"},
                                 {"LEVEL": "../x"}])
def test_switch_needs_container_settings(mc, env):
    container, data, packs = mc
    container.attrs["Config"]["Env"] = [f"{k}={v}" for k, v in
                                        {"VERSION": "1.20.1", "GENERIC_PACK": "/data/server.zip", "LEVEL": "world",
                                         **env}.items()]
    _zip(packs / "A.zip", ["mods/a.jar"])
    with pytest.raises(HTTPException) as e:
        minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="A.zip"), user=ADMIN)
    assert e.value.status_code == 500
    assert container.calls == []


def test_switch_rejects_non_zip(mc):
    container, _, packs = mc
    (packs / "bad.zip").write_text("not a zip")
    with pytest.raises(HTTPException) as e:
        minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="bad.zip"), user=ADMIN)
    assert "zip" in e.value.detail and container.calls == []


def test_active_pack_cannot_be_deleted_and_uninstall_is_refused(mc):
    container, data, packs = mc
    _zip(packs / "A.zip", ["mods/a.jar"])
    (data / ".axis-active-pack").write_text("A.zip")
    with pytest.raises(HTTPException) as e:
        minecraft.delete_pack("A.zip", user=ADMIN)
    assert e.value.status_code == 400 and (packs / "A.zip").exists()
    with pytest.raises(HTTPException) as e:
        minecraft.uninstall_server_pack(user=ADMIN)
    assert e.value.status_code == 400 and container.calls == []


def test_container_missing_is_503(monkeypatch):
    monkeypatch.setattr(minecraft, "MC_CONTAINER", "no-such-container-for-axis-test")
    with pytest.raises(HTTPException) as e:
        minecraft._mc_container()
    assert e.value.status_code == 503


# ---------- compose 設定 ----------
@pytest.mark.skipif(shutil.which("docker") is None, reason="沒有 docker CLI")
@pytest.mark.parametrize("extra, want", [("", "TRUE"), ("MC_ALLOW_FLIGHT=FALSE\n", "FALSE")])
def test_compose_allow_flight(tmp_path, extra, want):
    env = tmp_path / "test.env"
    env.write_text(f"AXIS_JWT_SECRET={'t' * 64}\nCOMPOSE_PROFILES=minecraft\n{extra}", encoding="utf-8")
    repo = Path(__file__).resolve().parents[1]
    out = subprocess.run(["docker", "compose", "-f", "docker-compose.yml", "--env-file", str(env), "config", "--format", "json"],
                         cwd=repo, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    svc = json.loads(out.stdout)["services"]["minecraft-server"]
    assert svc["environment"]["ALLOW_FLIGHT"] == want
