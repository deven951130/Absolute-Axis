"""多重宇宙頁的容器模式（MC_CONTAINER）：指令走 rcon-cli、切換模組包直接換資料目錄的 zip，不用 SSH。

檔名以 c 開頭：要比 test_devicehub_module.py（會用假的 app.utils 取代真的）先被收集。
執行：在 repo 根目錄 `python -m pytest tests`
"""
import os
import tempfile
import zipfile
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


# ---------- Modrinth 模組包（TYPE=MODRINTH） ----------
def _mrpack(path, mc="1.20.1", index=None):
    import json
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("modrinth.index.json", index if index is not None else json.dumps(
            {"formatVersion": 1, "game": "minecraft", "name": "pack", "files": [],
             "dependencies": {"minecraft": mc, "forge": "47.4.18"}}))
        z.writestr("overrides/config/a.toml", "x")
    return str(path)


MODRINTH_ENV = {"TYPE": "MODRINTH", "MODRINTH_MODPACK": "/data/modpack.mrpack", "GENERIC_PACK": ""}


def _set_env(container, **env):
    base = {"VERSION": "1.20.1", "GENERIC_PACK": "/data/server.zip", "LEVEL": "world", **env}
    container.attrs["Config"]["Env"] = [f"{k}={v}" for k, v in base.items()]


def test_modrinth_pack_goes_to_modrinth_modpack(mc):
    container, data, packs = mc
    _set_env(container, **MODRINTH_ENV)
    (data / "world").mkdir()
    a = _mrpack(packs / "通天之路 [女仆纪元].zip")
    b = _mrpack(packs / "other.mrpack")

    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="通天之路 [女仆纪元].zip"), user=ADMIN)
    assert container.calls == [("stop", 120), ("start",)]
    assert (data / "modpack.mrpack").read_bytes() == open(a, "rb").read()
    assert not (data / "server.zip").exists()
    assert len(list((data / ".axis-worlds").iterdir())) == 1   # 原本的世界另外保留

    # .mrpack 也列在函式庫裡，可以切換；切回來世界還在
    (data / "world").mkdir()
    (data / "world" / "level.dat").write_text("maid world")
    listed = {p["name"]: p for p in minecraft.list_packs(user=ADMIN)["packs"]}
    assert set(listed) == {"通天之路 [女仆纪元].zip", "other.mrpack"} and listed["通天之路 [女仆纪元].zip"]["active"]
    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="other.mrpack"), user=ADMIN)
    assert (data / "modpack.mrpack").read_bytes() == open(b, "rb").read()
    minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="通天之路 [女仆纪元].zip"), user=ADMIN)
    assert (data / "world" / "level.dat").read_text() == "maid world"


@pytest.mark.parametrize("env, make, words", [
    ({}, lambda p: _mrpack(p / "m.zip"), ("Modrinth", "MC_TYPE")),                       # 一般容器收到 Modrinth 包
    (MODRINTH_ENV, lambda p: _zip(p / "m.zip", ["mods/a.jar"]), ("modrinth.index.json",)),  # Modrinth 容器收到一般包
    (MODRINTH_ENV, lambda p: _mrpack(p / "m.zip", mc="1.21.1"), ("1.21.1", "1.20.1")),     # 版本不同
    (MODRINTH_ENV, lambda p: _mrpack(p / "m.zip", index="{not json"), ("modrinth.index.json",)),
    ({"TYPE": "MODRINTH", "MODRINTH_MODPACK": ""}, lambda p: _mrpack(p / "m.zip"), ("MODRINTH_MODPACK",)),
])
def test_modrinth_mismatch_is_refused_before_stopping(mc, env, make, words):
    container, data, packs = mc
    _set_env(container, **env)
    (data / "world").mkdir()
    make(packs)
    with pytest.raises(HTTPException) as e:
        minecraft.switch_pack(minecraft.SwitchPackRequest(pack_name="m.zip"), user=ADMIN)
    assert all(w in e.value.detail for w in words), e.value.detail
    assert container.calls == [] and (data / "world").is_dir()


def test_pack_slug_ignores_extension():
    assert minecraft._pack_slug("abc.mrpack").startswith("abc_")
    assert minecraft._pack_slug("abc.zip").startswith("abc_")
