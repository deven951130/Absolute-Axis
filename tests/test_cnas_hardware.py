"""NAS 管理頁的硬碟／儲存池資料（GET /api/system/hardware）。

重點：硬碟卡片數量跟著 lsblk 走；SSD／HDD 看 ROTA；smartctl 一定帶 -n standby（不叫醒休眠的硬碟）；
儲存池真的偵測（mdstat、zpool、btrfs），沒有就是空清單（畫面顯示「未使用 RAID」）；
容器內看不到主機掛載點時，已用是 None 並附說明。
檔名以 c 開頭：要比 test_devicehub_module.py（會用假的 app.utils 取代真的）先被收集。
執行：在 repo 根目錄 `python -m pytest tests`
"""
import json
import os
import sys
import tempfile
from types import SimpleNamespace

os.environ.setdefault("AXIS_BASE_PATH", tempfile.mkdtemp(prefix="axis-test-"))
os.environ.setdefault("AXIS_JWT_SECRET", "t" * 64)

import pytest  # noqa: E402

from app.routers import system  # noqa: E402

USER = {"username": "u", "role": "Administrator"}

MDSTAT_DEGRADED = """Personalities : [raid1] [raid6] [raid5] [raid4]
md0 : active raid1 sdb1[1] sda1[0](F)
      976630336 blocks super 1.2 [2/1] [_U]
      bitmap: 2/8 pages [8KB], 65536KB chunk

md1 : active raid5 sde1[3] sdd1[1] sdc1[0]
      1953260544 blocks super 1.2 level 5, 512k chunk, algorithm 2 [3/3] [UUU]

unused devices: <none>
"""

MDSTAT_REBUILD = """Personalities : [raid1]
md2 : active raid1 sdg1[2] sdf1[0]
      976630336 blocks super 1.2 [2/1] [U_]
      [=>...................]  recovery =  8.5% (83026944/976630336) finish=80.2min speed=185664K/sec

unused devices: <none>
"""


def ata_smart(passed=True, reallocated=0, pending=0, hours=12345, temp_raw=36, life=None):
    table = [
        {"id": 5, "name": "Reallocated_Sector_Ct", "value": 100, "raw": {"value": reallocated}},
        {"id": 9, "name": "Power_On_Hours", "value": 90, "raw": {"value": hours}},
        {"id": 194, "name": "Temperature_Celsius", "value": 64, "raw": {"value": temp_raw}},
        {"id": 197, "name": "Current_Pending_Sector", "value": 100, "raw": {"value": pending}},
    ]
    if life is not None:
        table.append({"id": 231, "name": "SSD_Life_Left", "value": life, "raw": {"value": life}})
    return {"smart_status": {"passed": passed}, "ata_smart_attributes": {"table": table}}


NVME_SMART = {
    "smart_status": {"passed": True},
    "temperature": {"current": 41},
    "power_on_time": {"hours": 820},
    "nvme_smart_health_information_log": {"percentage_used": 3, "temperature": 41, "power_on_hours": 820},
}

STANDBY_OUT = json.dumps({"smartctl": {"exit_status": 2, "messages": [
    {"string": "Device is in STANDBY mode, exit(2)", "severity": "information"}]}})


class FakeRunner:
    """取代 system._run_cmd：依指令回傳假的輸出，並記下呼叫過的指令。"""

    def __init__(self, lsblk, smart=None, zpool=None):
        self.lsblk = lsblk
        self.smart = smart or {}
        self.zpool = zpool  # None＝沒有 zpool 指令
        self.calls = []

    def __call__(self, argv, timeout=None):
        self.calls.append(argv)
        if argv[0] == "lsblk":
            return 0, json.dumps({"blockdevices": self.lsblk})
        if argv[0] == "smartctl":
            out = self.smart.get(argv[-1])
            if out is None:
                return None
            return (2 if "STANDBY" in out else 0), out
        if argv[0] == "zpool":
            return self.zpool
        return None


@pytest.fixture
def env(monkeypatch):
    def setup(lsblk, smart=None, zpool=None, mdstat=None, in_container=True):
        runner = FakeRunner(lsblk, smart, zpool)
        monkeypatch.setattr(system, "_run_cmd", runner)
        monkeypatch.setattr(system, "_read_text", lambda path: mdstat if path == "/proc/mdstat" else None)
        monkeypatch.setattr(system, "_in_container", lambda: in_container)
        monkeypatch.setattr(system, "docker_usage_bytes", lambda: None)
        monkeypatch.setattr(system, "get_dir_size", lambda path: 0)
        return runner
    return setup


def disk(name, rota, size=500 * 1024 ** 3, children=None, model="Disk", tran="sata"):
    return {"name": name, "size": size, "type": "disk", "rota": rota, "tran": tran, "mountpoint": None,
            "fstype": None, "uuid": None, "label": None, "model": model, "serial": "S", "vendor": None,
            "children": children or []}


def part(name, mountpoint=None, fstype="ext4", uuid=None, label=None):
    return {"name": name, "size": 1, "type": "part", "rota": None, "tran": None, "mountpoint": mountpoint,
            "fstype": fstype, "uuid": uuid, "label": label, "model": None, "serial": None, "vendor": None}


def test_cards_follow_lsblk_and_type_comes_from_rota(env, tmp_path):
    # 小容量 HDD 與大容量 SSD：舊版「小於 1000GB＝SSD」會兩顆都猜錯
    runner = env(
        lsblk=[
            disk("sda", True, size=320 * 1024 ** 3, children=[part("sda1", mountpoint=str(tmp_path))]),
            disk("sdb", "0", size=4000 * 1024 ** 3),     # 舊版 lsblk 用字串
            disk("nvme0n1", False, tran="nvme"),
            {"name": "loop0", "size": 1, "type": "loop", "rota": False},
            disk("zram0", False),
        ],
        smart={"/dev/sda": json.dumps(ata_smart()), "/dev/sdb": json.dumps(ata_smart(life=88)),
               "/dev/nvme0n1": json.dumps(NVME_SMART)},
    )
    d = system.get_hardware_info(USER)
    assert [x["device"] for x in d["disks"]] == ["/dev/sda", "/dev/sdb", "/dev/nvme0n1"]
    assert [x["type"] for x in d["disks"]] == ["HDD", "SSD", "SSD"]
    assert d["details"]["count"] == 3
    assert d["disks"][0]["used_pct"] is not None and d["disks"][0]["mounts"] == [str(tmp_path)]
    # 每次讀 SMART 都帶 -n standby
    smart_calls = [c for c in runner.calls if c[0] == "smartctl"]
    assert len(smart_calls) == 3
    assert all(c[1:3] == ["-n", "standby"] for c in smart_calls)


def test_standby_disk_is_not_woken_and_reported(env):
    env(lsblk=[disk("sdc", True)], smart={"/dev/sdc": STANDBY_OUT})
    d = system.get_hardware_info(USER)["disks"][0]
    assert d["status"] == "STANDBY" and d["standby"] is True
    assert d["smart"] is None and d["temp"] is None


def test_standby_plain_text_output_is_recognized(env):
    env(lsblk=[disk("sdc", True)], smart={"/dev/sdc": "Device is in SLEEP mode, exit(2)\n"})
    assert system.get_hardware_info(USER)["disks"][0]["status"] == "STANDBY"


def test_smart_key_attributes_ata(env):
    env(lsblk=[disk("sda", True)],
        smart={"/dev/sda": json.dumps(ata_smart(reallocated=8, pending=2, hours=40000, temp_raw=(50 << 16) | 38))})
    d = system.get_hardware_info(USER)["disks"][0]
    assert d["smart"] == {"reallocated": 8, "pending": 2, "power_on_hours": 40000, "life_left": None, "temp": 38}
    assert d["status"] == "WARNING"
    assert d["temp"] == 38


def test_smart_nvme_life_left_and_failing(env):
    failing = dict(NVME_SMART, smart_status={"passed": False})
    env(lsblk=[disk("nvme0n1", False, tran="nvme"), disk("nvme1n1", False, tran="nvme")],
        smart={"/dev/nvme0n1": json.dumps(NVME_SMART), "/dev/nvme1n1": json.dumps(failing)})
    a, b = system.get_hardware_info(USER)["disks"]
    assert a["status"] == "OK"
    assert a["smart"]["life_left"] == 97 and a["smart"]["power_on_hours"] == 820 and a["temp"] == 41
    assert a["smart"]["reallocated"] is None
    assert b["status"] == "FAILING"


def test_no_smartctl_is_unknown_not_fake_healthy(env):
    env(lsblk=[disk("sda", True)], smart={})
    d = system.get_hardware_info(USER)["disks"][0]
    assert d["status"] == "UNKNOWN" and d["smart"] is None and d["temp"] is None
    assert "smartctl" in d["smart_note"]


def test_host_mounted_disk_explains_why_usage_is_missing(env, tmp_path):
    env(lsblk=[
        disk("sdb", True, children=[part("sdb1")]),                                   # 主機掛載，容器看不到
        disk("sdc", True, children=[part("sdc1", mountpoint=str(tmp_path)), part("sdc2")]),  # 部分看得到
        disk("sdd", True, children=[part("sdd1", fstype="linux_raid_member")]),
    ], smart={})
    b, c, dd = system.get_hardware_info(USER)["disks"]
    assert b["used_pct"] is None and b["used_gb"] is None
    assert b["hidden_partitions"] == 1 and "容器" in b["usage_note"]
    assert c["used_pct"] is not None and c["hidden_partitions"] == 1 and "主機" in c["usage_note"]
    assert dd["used_pct"] is None and "儲存池" in dd["usage_note"]


def test_no_raid_means_empty_pools(env):
    env(lsblk=[disk("sda", True, children=[part("sda1", fstype="btrfs", uuid="u-single")])], smart={},
        mdstat="Personalities : \nunused devices: <none>\n")
    d = system.get_hardware_info(USER)
    assert d["pools"] == []
    assert "raid" not in d                       # 不再回傳寫死的 ONLINE


def test_mdstat_degraded_and_clean():
    pools = system.parse_mdstat(MDSTAT_DEGRADED)
    assert [(p["name"], p["level"], p["status"]) for p in pools] == [
        ("md0", "raid1", "DEGRADED"), ("md1", "raid5", "ONLINE")]
    assert pools[0]["devices"] == ["sdb1", "sda1"]
    assert pools[1]["devices"] == ["sde1", "sdd1", "sdc1"]


def test_mdstat_rebuilding_and_inactive():
    assert system.parse_mdstat(MDSTAT_REBUILD)[0]["status"] == "REBUILDING"
    inactive = "md127 : inactive sdb1[1](S)\n      976630336 blocks super 1.2\n"
    p = system.parse_mdstat(inactive)[0]
    assert p["status"] == "INACTIVE" and p["devices"] == ["sdb1"]
    assert system.parse_mdstat(None) == []


def test_zpool_list_is_used_when_available(env):
    env(lsblk=[], zpool=(0, "tank\tONLINE\nbackup\tDEGRADED\n"))
    pools = system.get_hardware_info(USER)["pools"]
    assert [(p["kind"], p["name"], p["status"]) for p in pools] == [
        ("zfs", "tank", "ONLINE"), ("zfs", "backup", "DEGRADED")]


def test_zfs_members_without_zpool_command(env):
    env(lsblk=[disk("sdb", True, children=[part("sdb1", fstype="zfs_member", label="tank")]),
               disk("sdc", True, children=[part("sdc1", fstype="zfs_member", label="tank")])], smart={})
    (p,) = system.get_hardware_info(USER)["pools"]
    assert p["name"] == "tank" and p["status"] == "UNKNOWN" and p["devices"] == ["sdb1", "sdc1"]
    assert "zpool" in p["note"]


def test_multi_device_btrfs_is_a_pool(env, monkeypatch, tmp_path):
    alloc = tmp_path / "u-pool" / "allocation" / "data" / "raid1"
    alloc.mkdir(parents=True)
    monkeypatch.setattr(system, "BTRFS_SYSFS", str(tmp_path))
    env(lsblk=[disk("sdb", True, children=[part("sdb1", fstype="btrfs", uuid="u-pool", label="data")]),
               disk("sdc", True, children=[part("sdc1", fstype="btrfs", uuid="u-pool", label="data")])], smart={})
    (p,) = system.get_hardware_info(USER)["pools"]
    assert (p["kind"], p["name"], p["level"], p["status"]) == ("btrfs", "data", "btrfs raid1", "ONLINE")


def test_lsblk_missing_reports_error(env, monkeypatch):
    env(lsblk=[])
    monkeypatch.setattr(system, "_run_cmd", lambda argv, timeout=None: None)
    d = system.get_hardware_info(USER)
    assert d["disks"] == [] and d["disks_error"]


def test_docker_usage_real_numbers_and_cache(monkeypatch):
    calls = []

    class FakeClient:
        def df(self):
            calls.append(1)
            return {"LayersSize": 1000, "Containers": [{"SizeRw": 10}, {"SizeRw": None}],
                    "Volumes": [{"UsageData": {"Size": 200}}, {"UsageData": {"Size": -1}}],
                    "BuildCache": [{"Size": 5, "Shared": False}, {"Size": 7, "Shared": True}]}

    monkeypatch.setitem(sys.modules, "docker", SimpleNamespace(from_env=lambda timeout=None: FakeClient()))
    monkeypatch.setattr(system, "_DOCKER_USAGE_CACHE", {"ts": 0.0, "bytes": None})
    assert system.docker_usage_bytes() == 1215
    assert system.docker_usage_bytes() == 1215
    assert len(calls) == 1                       # 5 分鐘內用快取


def test_docker_usage_unavailable_is_none(monkeypatch):
    def boom(timeout=None):
        raise RuntimeError("no socket")
    monkeypatch.setitem(sys.modules, "docker", SimpleNamespace(from_env=boom))
    monkeypatch.setattr(system, "_DOCKER_USAGE_CACHE", {"ts": 0.0, "bytes": None})
    assert system.docker_usage_bytes() is None


# ---------- 部署前在 axis-main（Proxmox VM 100）實機看到的三個問題 ----------
QEMU_SMART_UNAVAILABLE = json.dumps({
    "device": {"name": "/dev/sdb", "type": "scsi", "protocol": "SCSI"},
    "smart_support": {"available": False},
    "temperature": {"current": 0, "drive_trip": 0},
})


def test_virtual_disks_are_not_hdd_and_skip_smartctl(env, tmp_path):
    # QEMU 把虛擬硬碟標成旋轉式（ROTA=1）；smartctl 回不支援 SMART 卻帶 temperature 0
    runner = env(lsblk=[disk("sda", True, model="QEMU HARDDISK"),
                        disk("sdb", True, model="QEMU HARDDISK",
                             children=[part("sdb1", mountpoint=str(tmp_path))]),
                        disk("sdc", False, model="VBOX HARDDISK")],
                 smart={"/dev/sdb": QEMU_SMART_UNAVAILABLE})
    disks = system.get_hardware_info(USER)["disks"]
    assert [d["type"] for d in disks] == ["VIRTUAL"] * 3
    for d in disks:
        assert d["status"] == "VIRTUAL" and d["smart"] is None and d["temp"] is None
        assert "實體主機" in d["smart_note"]
    assert not [c for c in runner.calls if c[0] == "smartctl"]
    assert disks[1]["used_pct"] is not None


def test_smart_unavailable_does_not_report_zero_degrees(env):
    # 實體硬碟接在不轉 SMART 的 USB 外接盒：一樣不能顯示 0°C
    env(lsblk=[disk("sde", True, model="USB 3.0 Bridge")], smart={"/dev/sde": QEMU_SMART_UNAVAILABLE})
    d = system.get_hardware_info(USER)["disks"][0]
    assert d["type"] == "HDD"
    assert d["status"] == "UNKNOWN" and d["smart"] is None and d["temp"] is None
    assert "沒有提供 SMART" in d["smart_note"]


def test_missing_udev_data_is_not_called_no_filesystem(env):
    # 容器沒掛 /run/udev：lsblk 的 FSTYPE 全空 → 說讀不到，而不是「沒有檔案系統」
    def bare(name):
        return part(name, fstype=None)
    env(lsblk=[disk("sda", True, children=[bare("sda1"), bare("sda2")]),
               disk("sdb", True, children=[bare("sdb1")])], smart={})
    for d in system.get_hardware_info(USER)["disks"]:
        assert "沒有檔案系統" not in d["usage_note"]
        assert "/run/udev" in d["usage_note"]
    # 有讀到檔案系統資訊時，真的沒有檔案系統的硬碟照舊
    env(lsblk=[disk("sda", True, children=[part("sda1", fstype="ext4", mountpoint=None)]),
               disk("sdb", True)], smart={})
    assert system.get_hardware_info(USER)["disks"][1]["usage_note"] == "沒有檔案系統"


def test_compose_mounts_host_udev_read_only():
    text = open(os.path.join(os.path.dirname(__file__), "..", "docker-compose.yml"), encoding="utf-8").read()
    assert "- /run/udev:/run/udev:ro" in text
