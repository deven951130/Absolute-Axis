"""Minecraft 省電（autopause，DeviceHub spec/power-saving.md §6／FR-19c）。

重點：Axis 只看資料目錄的 .paused 與容器狀態判斷「省電中」，不碰遊戲埠、不送 rcon（否則會把伺服器叫醒）；
管理員主動送指令或切換模組包時才先叫醒。
檔名以 c 開頭：要比 test_devicehub_module.py（會用假的 app.utils 取代真的）先被收集。
執行：在 repo 根目錄 `python -m pytest tests`
"""
import os
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("AXIS_BASE_PATH", tempfile.mkdtemp(prefix="axis-test-"))
os.environ.setdefault("AXIS_JWT_SECRET", "t" * 64)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base  # noqa: E402
from app.routers import minecraft, system  # noqa: E402

ADMIN = {"username": "admin", "role": "Administrator"}
STARTED = "2026-10-04T08:00:00.123456789Z"
STARTED_TS = 1791100800.123456789  # 上面的時間（UTC）


class FakeContainer:
    def __init__(self, running=True, env=None):
        env = {"VERSION": "1.20.1", "GENERIC_PACK": "/data/server.zip", "LEVEL": "world",
               "MAX_MEMORY": "9G", "ENABLE_AUTOPAUSE": "TRUE", **(env or {})}
        self.attrs = {
            "Config": {"Env": [f"{k}={v}" for k, v in env.items()]},
            "State": {"Running": running, "StartedAt": STARTED},
            "HostConfig": {"Memory": 12 * 1024 ** 3, "NanoCpus": 8_000_000_000},
        }
        self.calls = []

    def exec_run(self, argv):
        self.calls.append(("exec", argv))
        if argv == [minecraft.RESUME_SCRIPT]:      # 映像的 resume.sh：恢復程序並刪掉 .paused
            flag = Path(minecraft.MC_DATA_DIR) / ".paused"
            if flag.exists():
                flag.unlink()
            return SimpleNamespace(exit_code=0, output=b"")
        if argv[:1] == ["java"]:
            return SimpleNamespace(exit_code=0, output=b'openjdk version "17.0.15"')
        return SimpleNamespace(exit_code=0, output=b"There are 0 of a max of 20 players online:")

    def stop(self, timeout=10):
        self.calls.append(("stop", timeout))

    def start(self):
        self.calls.append(("start",))


@pytest.fixture
def mc(monkeypatch, tmp_path):
    data, packs = tmp_path / "minecraft-data", tmp_path / "packs"
    data.mkdir()
    packs.mkdir()
    container = FakeContainer()
    monkeypatch.setattr(minecraft, "MC_CONTAINER", "axis-mc")
    monkeypatch.setattr(minecraft, "MC_DATA_DIR", str(data))
    monkeypatch.setattr(minecraft, "PACKS_DIR", str(packs))
    monkeypatch.setattr(minecraft, "INFO_FILE", str(tmp_path / "info.json"))
    monkeypatch.setattr(minecraft, "_mc_container", lambda: container)
    monkeypatch.setattr(minecraft, "log_event", lambda *a, **k: None)
    monkeypatch.setattr(minecraft, "_java_version_cache", {})
    monkeypatch.setattr(minecraft, "_power_cache", {"t": 0.0, "v": "unknown"})
    monkeypatch.setattr(minecraft.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))

    def no_port(*a, **k):
        raise AssertionError("省電中不該連遊戲埠")

    container.no_port = no_port
    return container, data


def _pause(data: Path, mtime: float = None):
    flag = data / ".paused"
    flag.write_text("")
    if mtime is not None:
        os.utime(flag, (mtime, mtime))


# ---------- 狀態判斷 ----------
def test_started_at_with_nanoseconds():
    assert minecraft._started_ts({"StartedAt": STARTED}) == pytest.approx(STARTED_TS, abs=1e-3)
    assert minecraft._started_ts({"StartedAt": "garbage"}) == 0.0


def test_power_state(mc):
    container, data = mc
    assert minecraft.mc_power_state(max_age=0) == "running"
    _pause(data)
    assert minecraft.mc_power_state(max_age=0) == "paused"
    # 容器在暫停中被停掉、重開後留下的舊旗標（比這次啟動還舊）不算
    _pause(data, mtime=STARTED_TS - 3600)
    assert minecraft.mc_power_state(max_age=0) == "running"
    container.attrs["State"]["Running"] = False
    _pause(data)
    assert minecraft.mc_power_state(max_age=0) == "stopped"


def test_power_state_without_container_mode(monkeypatch):
    monkeypatch.setattr(minecraft, "MC_CONTAINER", "")
    assert minecraft.mc_power_state(max_age=0) == "unknown"
    assert minecraft.mc_paused() is False


def test_power_state_is_cached(mc):
    container, data = mc
    assert minecraft.mc_power_state() == "running"
    _pause(data)
    assert minecraft.mc_power_state() == "running"          # 10 秒內用快取
    assert minecraft.mc_power_state(max_age=0) == "paused"


# ---------- 省電中不能被 Axis 叫醒 ----------
def test_status_while_paused_does_not_touch_the_port(mc, monkeypatch):
    container, data = mc
    _pause(data)
    monkeypatch.setattr(minecraft, "_check_online", container.no_port)
    got = minecraft.get_mc_status(user=ADMIN)
    assert got["online"] is True
    assert got["server"]["uptime"].startswith("省電中")
    assert got["power"]["state"] == "paused" and got["power"]["autopause"] is True
    assert ("exec", ["rcon-cli", "list"]) not in container.calls
    assert data.joinpath(".paused").exists()                 # 沒有被叫醒


def test_status_while_running_still_checks_the_port(mc, monkeypatch):
    container, _ = mc
    calls = []
    monkeypatch.setattr(minecraft, "_check_online", lambda: calls.append(1) or True)
    got = minecraft.get_mc_status(user=ADMIN)
    assert calls == [1] and got["power"]["state"] == "running"


def test_dashboard_sensors_do_not_touch_the_port_while_paused(monkeypatch):
    monkeypatch.setattr(system, "mc_paused", lambda: True)
    monkeypatch.setattr(system, "BLYNK_TOKEN", None)
    monkeypatch.setattr(system.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(system.psutil, "sensors_temperatures", lambda: {}, raising=False)

    def no_socket(*a, **k):
        raise AssertionError("省電中不該連遊戲埠")

    monkeypatch.setattr(system.socket, "socket", no_socket)
    got = system.get_sensors(user=ADMIN)["minecraft"]
    assert got["online"] is True and got["paused"] is True


# ---------- 管理員主動操作時先叫醒 ----------
def test_command_wakes_the_server_first(mc):
    container, data = mc
    _pause(data)
    minecraft.send_mc_command(minecraft.MCCommandRequest(command="list"), user=ADMIN)
    assert container.calls == [("exec", [minecraft.RESUME_SCRIPT]), ("exec", ["rcon-cli", "list"])]
    assert not data.joinpath(".paused").exists()


def test_command_while_running_does_not_call_resume(mc):
    container, _ = mc
    minecraft.send_mc_command(minecraft.MCCommandRequest(command="list"), user=ADMIN)
    assert container.calls == [("exec", ["rcon-cli", "list"])]


def test_pack_switch_wakes_before_stopping(mc, tmp_path):
    container, data = mc
    _pause(data)
    pack = tmp_path / "packs" / "new-pack.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("mods/a.jar", "x")
    minecraft._deploy_pack_to_container(str(pack))
    names = [c[0] if c[0] != "exec" else c[1][0] for c in container.calls]
    assert names.index(minecraft.RESUME_SCRIPT) < names.index("stop")
    assert ("stop", 120) in container.calls and ("start",) in container.calls


# ---------- 每分鐘記錄與統計 ----------
@pytest.fixture
def power_db(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'axis.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(minecraft, "SessionLocal", sessionmaker(bind=engine))
    yield
    engine.dispose()


def test_record_and_summarise(power_db):
    for state, n, day in (("paused", 3, "2026-10-04"), ("running", 2, "2026-10-04"),
                          ("paused", 5, "2026-10-01"), ("stopped", 1, "2026-09-20"), ("unknown", 4, "2026-10-04")):
        for _ in range(n):
            minecraft.record_power_minute(state, day=day)
    got = minecraft.power_summary(today="2026-10-04")
    assert got["today"] == {"running_min": 2, "paused_min": 3, "stopped_min": 0}
    assert got["week"] == {"running_min": 2, "paused_min": 8, "stopped_min": 0}   # 09-20 不在最近 7 天；unknown 不記


def test_status_includes_summary(mc, power_db, monkeypatch):
    container, data = mc
    minecraft.record_power_minute("paused")
    _pause(data)
    monkeypatch.setattr(minecraft, "_check_online", container.no_port)
    got = minecraft.get_mc_status(user=ADMIN)["power"]
    assert got["today"]["paused_min"] == 1 and got["week"]["paused_min"] == 1


def test_logger_records_every_interval(mc, power_db):
    container, data = mc
    _pause(data)
    import threading
    stop = threading.Event()
    thread = minecraft.start_power_logger(interval=0.05, stop=stop)
    deadline = time.time() + 3
    while time.time() < deadline and minecraft.power_summary()["today"]["paused_min"] < 2:
        time.sleep(0.05)
    stop.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert minecraft.power_summary()["today"]["paused_min"] >= 2
    assert data.joinpath(".paused").exists()                 # 記錄不會叫醒伺服器


# ---------- compose 設定 ----------
@pytest.mark.skipif(shutil.which("docker") is None, reason="沒有 docker CLI")
@pytest.mark.parametrize("extra, want_enabled, want_seconds", [("", "TRUE", "900"),
                                                               ("MC_AUTOPAUSE=FALSE\nMC_AUTOPAUSE_SECONDS=300\n", "FALSE", "300")])
def test_compose_autopause_settings(tmp_path, extra, want_enabled, want_seconds):
    env = tmp_path / "test.env"
    env.write_text(f"AXIS_JWT_SECRET={'t' * 64}\nCOMPOSE_PROFILES=minecraft\n{extra}", encoding="utf-8")
    repo = Path(__file__).resolve().parents[1]
    out = subprocess.run(["docker", "compose", "-f", "docker-compose.yml", "--env-file", str(env), "config", "--format", "json"],
                         cwd=repo, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    import json
    svc = json.loads(out.stdout)["services"]["minecraft-server"]
    assert svc["environment"]["ENABLE_AUTOPAUSE"] == want_enabled
    assert svc["environment"]["AUTOPAUSE_TIMEOUT_EST"] == want_seconds
    assert svc["environment"]["AUTOPAUSE_TIMEOUT_INIT"] == want_seconds
    assert svc["environment"]["MAX_TICK_TIME"] == "-1"
    assert "CAP_NET_RAW" in svc["cap_add"]
