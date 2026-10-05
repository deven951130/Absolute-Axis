"""DeviceHub 模組（app/routers/devicehub.py）的測試。

app.utils 會連資料庫與 JWT，所以這裡用假的 require_admin 取代，只測本模組自己的行為。
執行：在 repo 根目錄 `python -m pytest tests`
"""
import sys
import types

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

USERS = {
    "Bearer admin": {"username": "sparkle", "role": "Administrator"},
    "Bearer admin-zh": {"username": "管理員", "role": "Administrator"},
    "Bearer member": {"username": "friend", "role": "Member"},
}


def fake_require_admin(authorization: str = Header(None)):
    user = USERS.get(authorization)
    if user is None:
        raise HTTPException(401)
    if user["role"] not in ("admin", "Administrator"):
        raise HTTPException(403)
    return user


_utils = types.ModuleType("app.utils")
_utils.require_admin = fake_require_admin
sys.modules["app.utils"] = _utils

from app.routers import devicehub  # noqa: E402

ADMIN = {"Authorization": "Bearer admin"}


class Resp:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


@pytest.fixture
def dh(monkeypatch):
    calls = []
    state = {"resp": Resp(200, {"id": "01J", "result": "ok", "error": None})}

    def fake_request(method, url, json=None, timeout=None, headers=None):
        calls.append({"method": method, "url": url, "json": json, "headers": headers, "timeout": timeout})
        return state["resp"]

    def fake_get(url, headers=None, timeout=None):
        calls.append({"method": "GET", "url": url, "headers": headers})
        return state["resp"]

    monkeypatch.setattr(devicehub, "DEVICEHUB_URL", "http://192.168.0.50:8080")
    monkeypatch.setattr(devicehub, "DEVICEHUB_TOKEN", "read-tok")
    monkeypatch.setattr(devicehub, "DEVICEHUB_CONTROL_TOKEN", "control-tok")
    monkeypatch.setattr(devicehub.requests, "request", fake_request)
    monkeypatch.setattr(devicehub.requests, "get", fake_get)
    devicehub._cache.update(ts=0.0, data=None)
    app = FastAPI()
    app.include_router(devicehub.router)
    return TestClient(app), calls, state


def test_admin_only(dh):
    c, calls, _ = dh
    for path in ("/api/devicehub/summary", "/api/devicehub/controls"):
        assert c.get(path).status_code == 401
        assert c.get(path, headers={"Authorization": "Bearer member"}).status_code == 403
    r = c.post("/api/devicehub/devices/desktop/commands", headers={"Authorization": "Bearer member"},
               json={"action": "host.sleep", "confirm": True})
    assert r.status_code == 403
    assert calls == []


def test_summary_uses_read_token_and_never_leaks_it(dh):
    c, calls, state = dh
    state["resp"] = Resp(200, {"generated_at": 1, "ui_url": "https://dh.ts.net", "devices": [],
                               "proxmox": {}, "alerts": []})
    r = c.get("/api/devicehub/summary", headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] and body["error"] is None and body["control"] is True
    assert "read-tok" not in r.text and "control-tok" not in r.text
    assert calls[0]["url"] == "http://192.168.0.50:8080/api/v1/summary"
    assert calls[0]["headers"] == {"Authorization": "Bearer read-tok"}
    c.get("/api/devicehub/summary", headers=ADMIN)
    assert len(calls) == 1  # 5 秒快取


def test_summary_not_configured(dh, monkeypatch):
    c, calls, _ = dh
    monkeypatch.setattr(devicehub, "DEVICEHUB_TOKEN", "")
    monkeypatch.setattr(devicehub, "DEVICEHUB_CONTROL_TOKEN", "")
    assert c.get("/api/devicehub/summary", headers=ADMIN).json() == {"configured": False}
    r = c.post("/api/devicehub/devices/desktop/commands", headers=ADMIN, json={"action": "ping"})
    assert r.json() == {"ok": False, "error": "control_not_configured", "http": None}
    assert calls == []


def test_command_is_forwarded_with_control_token_and_operator(dh):
    c, calls, _ = dh
    r = c.post("/api/devicehub/devices/desktop/commands", headers=ADMIN,
               json={"action": "host.sleep", "confirm": True})
    assert r.status_code == 200 and r.json() == {"ok": True, "id": "01J", "result": "ok", "error": None}
    (call,) = calls
    assert call["method"] == "POST" and call["url"] == "http://192.168.0.50:8080/api/v1/devices/desktop/commands"
    assert call["headers"] == {"Authorization": "Bearer control-tok", "X-DH-Operator": "sparkle"}
    assert call["json"] == {"action": "host.sleep", "params": {}, "confirm": True}
    assert "control-tok" not in r.text


def test_non_ascii_username_is_sanitized(dh):
    c, calls, _ = dh
    c.post("/api/devicehub/devices/desktop/commands", headers={"Authorization": "Bearer admin-zh"},
           json={"action": "ping"})
    assert calls[0]["headers"]["X-DH-Operator"] == "___"


def test_devicehub_errors_do_not_become_axis_401(dh):
    """authFetch 遇到 401 會登出使用者：DeviceHub 的 401／403／428 一律回 200 + ok:false。"""
    c, _, state = dh
    for code, err in ((401, "unauthorized"), (403, "not_allowed"), (428, "confirm_required"),
                      (429, "rate_limited")):
        state["resp"] = Resp(code, {"error": err, "detail": None})
        r = c.post("/api/devicehub/devices/desktop/commands", headers=ADMIN, json={"action": "host.sleep"})
        assert r.status_code == 200 and r.json() == {"ok": False, "error": err, "http": code}
    state["resp"] = Resp(500, ValueError("not json"))
    r = c.post("/api/devicehub/devices/desktop/commands", headers=ADMIN, json={"action": "ping"})
    assert r.json() == {"ok": False, "error": "http_500", "http": 500}


def test_unreachable(dh, monkeypatch):
    c, _, _ = dh

    def boom(*a, **k):
        raise devicehub.requests.ConnectionError("down")

    monkeypatch.setattr(devicehub.requests, "request", boom)
    r = c.post("/api/devicehub/devices/desktop/wake", headers=ADMIN)
    assert r.json() == {"ok": False, "error": "unreachable", "http": None}


@pytest.mark.parametrize("path,body", [
    ("/api/devicehub/devices/..%2Fadmin/commands", {"action": "ping"}),
    ("/api/devicehub/devices/Desktop/commands", {"action": "ping"}),
    ("/api/devicehub/devices/desktop/commands", {"action": "../x"}),
    ("/api/devicehub/devices/desktop/wake", {"via": "a/b"}),
    ("/api/devicehub/proxmox/100/destroy", {"confirm": True}),
    ("/api/devicehub/proxmox/5/start", {}),
])
def test_bad_input_never_reaches_devicehub(dh, path, body):
    c, calls, _ = dh
    r = c.post(path, headers=ADMIN, json=body)
    assert r.status_code in (200, 404) and calls == []
    if r.status_code == 200:
        assert r.json()["error"] == "bad_request"


def test_wake_and_proxmox_paths(dh):
    c, calls, _ = dh
    c.post("/api/devicehub/devices/desktop/wake", headers=ADMIN, json={"via": "esp-server"})
    c.post("/api/devicehub/proxmox/101/start", headers=ADMIN, json={})
    c.post("/api/devicehub/proxmox/100/shutdown", headers=ADMIN, json={"confirm": True})
    assert [(x["url"].split(":8080")[1], x["json"]) for x in calls] == [
        ("/api/v1/devices/desktop/wake", {"via": "esp-server"}),
        ("/api/v1/proxmox/101/start", {"confirm": False}),
        ("/api/v1/proxmox/100/shutdown", {"confirm": True}),
    ]


def test_controls_passthrough(dh):
    c, calls, state = dh
    state["resp"] = Resp(200, {"devices": [{"id": "desktop", "actions": [], "wake": None}], "proxmox": []})
    r = c.get("/api/devicehub/controls", headers=ADMIN)
    assert r.json() == {"ok": True, "devices": [{"id": "desktop", "actions": [], "wake": None}], "proxmox": []}
    assert calls[0]["headers"] == {"Authorization": "Bearer control-tok"}


def test_history_proxies_with_read_token(dh):
    c, calls, state = dh
    state["resp"] = Resp(200, {"device_id": "esp-server", "field": "temp_c", "hours": 24, "bucket_s": 300,
                               "points": [{"t": 1, "avg": 28.1, "min": 28.0, "max": 28.2}]})
    r = c.get("/api/devicehub/history/esp-server?field=temp_c&hours=24", headers=ADMIN)
    assert r.status_code == 200 and r.json()["ok"] is True and r.json()["points"][0]["avg"] == 28.1
    assert calls[0]["url"] == "http://192.168.0.50:8080/api/v1/history/esp-server?field=temp_c&hours=24"
    assert calls[0]["headers"] == {"Authorization": "Bearer read-tok"}
    assert "read-tok" not in r.text


def test_history_validates_and_clamps(dh):
    c, calls, _ = dh
    for path in ("/api/devicehub/history/esp-server?field=password",
                 "/api/devicehub/history/ESP?field=temp_c",
                 "/api/devicehub/history/esp-server/fields/../x"):
        r = c.get(path, headers=ADMIN)
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert r.json()["error"] == "bad_request"
    assert calls == []
    c.get("/api/devicehub/history/esp-server?field=hum&hours=99999", headers=ADMIN)
    assert calls[-1]["url"].endswith("field=hum&hours=720")


def test_history_admin_only(dh):
    c, calls, _ = dh
    assert c.get("/api/devicehub/history/esp-server?field=temp_c", headers={"Authorization": "Bearer member"}).status_code == 403
    assert c.get("/api/devicehub/history/esp-server/fields").status_code == 401
    assert calls == []


def test_history_fields(dh):
    c, calls, state = dh
    state["resp"] = Resp(200, {"device_id": "esp-server", "fields": ["temp_c", "hum"]})
    r = c.get("/api/devicehub/history/esp-server/fields", headers=ADMIN)
    assert r.json() == {"ok": True, "device_id": "esp-server", "fields": ["temp_c", "hum"]}


# ---------- 裝置綁定（DeviceHub integration-api.md §3.8） ----------

def test_accounts_admin_only(dh):
    c, calls, _ = dh
    member = {"Authorization": "Bearer member"}
    assert c.get("/api/devicehub/accounts", headers=member).status_code == 403
    assert c.post("/api/devicehub/accounts", headers=member, json={"id": "node1", "kind": "esp32"}).status_code == 403
    assert c.request("DELETE", "/api/devicehub/accounts/node1", headers=member, json={"confirm": True}).status_code == 403
    assert calls == []


def test_account_list_only_passes_known_fields(dh):
    c, calls, state = dh
    state["resp"] = Resp(200, {"accounts": [
        {"id": "desktop", "name": "桌機", "type": "host", "status": "online", "last_seen": 1, "connected": True,
         "secret": "x"}]})
    body = c.get("/api/devicehub/accounts", headers=ADMIN).json()
    assert body == {"ok": True, "accounts": [{"id": "desktop", "name": "桌機", "type": "host", "status": "online",
                                               "last_seen": 1, "connected": True}]}
    assert calls[0]["headers"]["Authorization"] == "Bearer control-tok"


def test_account_add_forwards_and_returns_password_uncached(dh):
    c, calls, state = dh
    state["resp"] = Resp(201, {"id": "node1", "name": "客廳", "kind": "esp32", "password": "s3cret",
                               "mqtt": {"lan": "192.168.0.50", "tailnet": "100.88.245.58", "port": 1883}})
    r = c.post("/api/devicehub/accounts", headers=ADMIN, json={"id": "node1", "name": " 客廳 ", "kind": "esp32"})
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert r.json() == {"ok": True, "id": "node1", "name": "客廳", "kind": "esp32", "password": "s3cret",
                        "mqtt": {"lan": "192.168.0.50", "tailnet": "100.88.245.58", "port": 1883}}
    call = calls[0]
    assert (call["method"], call["url"].endswith("/api/v1/accounts")) == ("POST", True)
    assert call["json"] == {"id": "node1", "name": "客廳", "kind": "esp32"}
    assert call["headers"]["X-DH-Operator"] == "sparkle"


@pytest.mark.parametrize("body", [
    {"id": "Node1", "kind": "esp32"}, {"id": "n", "kind": "esp32"}, {"id": "node1;x", "kind": "esp32"},
    {"id": "node1", "kind": "toaster"},
])
def test_account_add_validates_before_devicehub(dh, body):
    c, calls, _ = dh
    assert c.post("/api/devicehub/accounts", headers=ADMIN, json=body).json()["error"] == "bad_request"
    assert calls == []


def test_account_errors_stay_http_200_with_code(dh):
    c, _, state = dh
    state["resp"] = Resp(409, {"error": "exists", "detail": None})
    r = c.post("/api/devicehub/accounts", headers=ADMIN, json={"id": "desktop", "kind": "windows"})
    assert r.status_code == 200 and r.json() == {"ok": False, "error": "exists", "http": 409}


def test_account_delete_sends_confirm(dh):
    c, calls, state = dh
    state["resp"] = Resp(200, {"id": "node1", "removed": True})
    r = c.request("DELETE", "/api/devicehub/accounts/node1", headers=ADMIN, json={"confirm": True})
    assert r.json() == {"ok": True, "id": "node1", "removed": True}
    assert calls[0]["method"] == "DELETE" and calls[0]["json"] == {"confirm": True}
    r = c.request("DELETE", "/api/devicehub/accounts/node1", headers=ADMIN)
    assert calls[1]["json"] == {"confirm": False}


# ---------- 省電摘要（DeviceHub FR-19，integration-api §3.1b；唯讀） ----------
def test_power_summary_proxies_whitelisted_fields(dh):
    c, calls, state = dh
    devicehub._power_cache.update(ts=0.0, data=None)
    state["resp"] = Resp(200, {
        "rules": [{"id": "r-1", "name": "夜間", "target_name": "桌機", "action": "host.shutdown", "days": "12345",
                   "time": "02:00", "enabled": True, "next_run_at": 1, "last_result": None, "state": None,
                   "created_by": "owner", "secret": "x"}],
        "paused_until": 0, "runs": [{"rule_name": "夜間", "started_at": 1, "finished_at": 2, "result": "ok",
                                     "detail": None, "extra": 1}],
        "savings": {"days": ["2026-10-05"], "targets": [{"target_name": "桌機", "off_h_total": 5.0,
                                                         "est_kwh_saved": 0.3, "watts": {"on": 60}}],
                    "cpu_energy": [{"name": "pve-host", "kwh": [0.5], "kwh_total": 0.5, "device_id": "pve-host"}]}})
    r = c.get("/api/devicehub/power", headers=ADMIN).json()
    assert calls[0]["url"] == "http://192.168.0.50:8080/api/v1/power/summary"
    assert calls[0]["headers"] == {"Authorization": "Bearer read-tok"}
    assert r["ok"] is True and r["rules"][0]["name"] == "夜間"
    assert "created_by" not in r["rules"][0] and "secret" not in r["rules"][0] and "extra" not in r["runs"][0]
    assert "watts" not in r["savings"]["targets"][0] and "device_id" not in r["savings"]["cpu_energy"][0]
    assert "minecraft" in r
    c.get("/api/devicehub/power", headers=ADMIN)
    assert len(calls) == 1                                   # cached 30 s


def test_power_summary_old_hub_and_admin_only(dh):
    c, calls, state = dh
    devicehub._power_cache.update(ts=0.0, data=None)
    assert c.get("/api/devicehub/power", headers={"Authorization": "Bearer member"}).status_code == 403
    assert calls == []
    state["resp"] = Resp(404, {"detail": "Not Found"})       # DeviceHub without FR-19
    r = c.get("/api/devicehub/power", headers=ADMIN).json()
    assert r["ok"] is False and r["error"] == "http_404"
