"""DeviceHub 模組：智慧宅控的設備、電源與虛擬機（讀取＋控制）。

Absolute-Axis 是主入口，DeviceHub 是設備／電源管理模組（DeviceHub repo:
docs/spec/integration-api.md v0.4、architecture AD-10／AD-11）。

- 只由 Axis 後端呼叫 DeviceHub；DEVICEHUB_TOKEN（讀取）與 DEVICEHUB_CONTROL_TOKEN（控制）
  只放在 .env，不會送到瀏覽器。
- 只給 Administrator；一般會員的請求在這裡就被擋下（require_admin）。
- 控制請求會帶上目前登入的帳號（X-DH-Operator），DeviceHub 會寫進稽核紀錄並推播 Discord。
- DeviceHub 的錯誤一律轉成 HTTP 200 + {"ok": false, "error": 代碼}：前端的 authFetch 遇到 401
  會清掉登入狀態，DeviceHub 那邊的 401（token 錯）不能被當成 Axis 登入失效。
"""
import os
import re
import time

import requests
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.utils import require_admin

router = APIRouter(tags=["devicehub"])

DEVICEHUB_URL = os.getenv("DEVICEHUB_URL", "http://192.168.0.50:8080").rstrip("/")
DEVICEHUB_TOKEN = os.getenv("DEVICEHUB_TOKEN", "")
DEVICEHUB_CONTROL_TOKEN = os.getenv("DEVICEHUB_CONTROL_TOKEN", "")
_CACHE_SECONDS = 5  # 多個分頁同時開著也只打 DeviceHub 一次
_cache = {"ts": 0.0, "data": None}

_DEVICE_ID = re.compile(r"^[a-z0-9-]{1,32}$")          # DeviceHub mqtt-protocol.md 的 device_id
_ACTION = re.compile(r"^[a-z]+(\.[a-z]+)?$")
_PVE_ACTIONS = ("start", "shutdown", "reboot", "stop")
_OPERATOR_BAD = re.compile(r"[^A-Za-z0-9_.@-]")


class CommandBody(BaseModel):
    action: str = Field(max_length=32)
    params: dict = Field(default_factory=dict)
    confirm: bool = False


class WakeBody(BaseModel):
    via: str | None = Field(default=None, max_length=32)


class PowerBody(BaseModel):
    confirm: bool = False


def _operator(user: dict) -> str:
    """X-DH-Operator 只接受 [A-Za-z0-9_.@-]{1,32}；其他字元換成 _（例如中文帳號）。"""
    name = _OPERATOR_BAD.sub("_", str(user.get("username") or ""))[:32]
    return name or "unknown"


def _read_token() -> str:
    # control token 也能讀摘要（spec §3.1）；只設了 control token 時就用它
    return DEVICEHUB_TOKEN or DEVICEHUB_CONTROL_TOKEN


def _fail(error: str, http: int | None = None) -> dict:
    return {"ok": False, "error": error, "http": http}


def _call(method: str, path: str, user: dict, body: dict | None = None, timeout: float = 20) -> dict:
    if not DEVICEHUB_CONTROL_TOKEN:
        return _fail("control_not_configured")
    try:
        r = requests.request(method, f"{DEVICEHUB_URL}{path}", json=body, timeout=timeout,
                             headers={"Authorization": f"Bearer {DEVICEHUB_CONTROL_TOKEN}",
                                      "X-DH-Operator": _operator(user)})
    except requests.RequestException:
        return _fail("unreachable")
    try:
        data = r.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if r.status_code != 200:
        # 只轉送錯誤代碼（短字串），不轉送其他內容
        code = data.get("error") if isinstance(data.get("error"), str) else None
        return _fail((code or f"http_{r.status_code}")[:40], r.status_code)
    _cache.update(ts=0.0, data=None)  # 狀態變了：下一次摘要重新抓
    return {"ok": True, "id": data.get("id"), "result": data.get("result"), "error": data.get("error")}


@router.get("/api/devicehub/summary")
def devicehub_summary(user: dict = Depends(require_admin)):
    token = _read_token()
    if not token:
        return {"configured": False}

    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < _CACHE_SECONDS:
        return _cache["data"]
    try:
        r = requests.get(f"{DEVICEHUB_URL}/api/v1/summary",
                         headers={"Authorization": f"Bearer {token}"}, timeout=4)
    except requests.RequestException:
        return {"configured": True, "error": "DeviceHub 無法連線"}
    if r.status_code != 200:
        # 不轉送 DeviceHub 的錯誤內容，只給狀態碼
        return {"configured": True, "error": f"DeviceHub 回應 HTTP {r.status_code}"}
    data = {"configured": True, "error": None, "control": bool(DEVICEHUB_CONTROL_TOKEN), **r.json()}
    _cache.update(ts=now, data=data)
    return data


@router.get("/api/devicehub/controls")
def devicehub_controls(user: dict = Depends(require_admin)):
    if not DEVICEHUB_CONTROL_TOKEN:
        return _fail("control_not_configured")
    try:
        r = requests.get(f"{DEVICEHUB_URL}/api/v1/controls",
                         headers={"Authorization": f"Bearer {DEVICEHUB_CONTROL_TOKEN}"}, timeout=4)
    except requests.RequestException:
        return _fail("unreachable")
    if r.status_code != 200:
        return _fail(f"http_{r.status_code}", r.status_code)
    return {"ok": True, **r.json()}


@router.post("/api/devicehub/devices/{device_id}/commands")
def devicehub_command(device_id: str, body: CommandBody, user: dict = Depends(require_admin)):
    if not _DEVICE_ID.match(device_id) or not _ACTION.match(body.action):
        return _fail("bad_request", 400)
    return _call("POST", f"/api/v1/devices/{device_id}/commands", user,
                 {"action": body.action, "params": body.params, "confirm": body.confirm})


@router.post("/api/devicehub/devices/{device_id}/wake")
def devicehub_wake(device_id: str, body: WakeBody | None = None, user: dict = Depends(require_admin)):
    via = body.via if body else None
    if not _DEVICE_ID.match(device_id) or (via is not None and not _DEVICE_ID.match(via)):
        return _fail("bad_request", 400)
    return _call("POST", f"/api/v1/devices/{device_id}/wake", user, {"via": via} if via else {})


@router.post("/api/devicehub/proxmox/{vmid}/{action}")
def devicehub_power(vmid: int, action: str, body: PowerBody | None = None, user: dict = Depends(require_admin)):
    if action not in _PVE_ACTIONS or not 100 <= vmid <= 999999999:
        return _fail("bad_request", 400)
    # 關機最多等 DeviceHub 一段時間（它會等 Proxmox 的工作完成）
    return _call("POST", f"/api/v1/proxmox/{vmid}/{action}", user,
                 {"confirm": bool(body and body.confirm)}, timeout=60)


# ---------- 歷史紀錄（DeviceHub integration-api.md §3.1a；智慧宅控「歷史」頁籤） ----------
_HISTORY_FIELDS = ("temp_c", "hum", "cpu", "ram", "disk", "rssi")


def _read_get(path: str, timeout: float = 8) -> dict:
    token = _read_token()
    if not token:
        return _fail("not_configured")
    try:
        r = requests.get(f"{DEVICEHUB_URL}{path}", headers={"Authorization": f"Bearer {token}"}, timeout=timeout)
    except requests.RequestException:
        return _fail("unreachable")
    if r.status_code != 200:
        return _fail(f"http_{r.status_code}", r.status_code)
    try:
        data = r.json()
    except ValueError:
        return _fail("bad_response")
    return {"ok": True, **data} if isinstance(data, dict) else _fail("bad_response")


@router.get("/api/devicehub/history/{device_id}/fields")
def devicehub_history_fields(device_id: str, user: dict = Depends(require_admin)):
    if not _DEVICE_ID.match(device_id):
        return _fail("bad_request", 400)
    return _read_get(f"/api/v1/history/{device_id}/fields")


@router.get("/api/devicehub/history/{device_id}")
def devicehub_history(device_id: str, field: str, hours: int = 24, user: dict = Depends(require_admin)):
    if not _DEVICE_ID.match(device_id) or field not in _HISTORY_FIELDS:
        return _fail("bad_request", 400)
    hours = max(1, min(int(hours), 720))
    return _read_get(f"/api/v1/history/{device_id}?field={field}&hours={hours}")


# ---------- 裝置綁定（DeviceHub integration-api.md §3.8、FR-18；智慧宅控「綁定裝置」頁籤） ----------
_ACCOUNT_ID = re.compile(r"^[a-z][a-z0-9-]{1,30}$")
_ACCOUNT_KINDS = ("esp32", "windows", "linux")


class AccountBody(BaseModel):
    id: str = Field(max_length=64)
    name: str | None = Field(default=None, max_length=80)
    kind: str = Field(max_length=16)


def _account_call(method: str, path: str, user: dict, body: dict | None = None) -> tuple[dict, int | None]:
    """(DeviceHub 的 JSON, 狀態碼)；錯誤時 JSON 是 _fail(...)。只轉送白名單欄位。"""
    if not DEVICEHUB_CONTROL_TOKEN:
        return _fail("control_not_configured"), None
    try:
        r = requests.request(method, f"{DEVICEHUB_URL}{path}", json=body, timeout=20,
                             headers={"Authorization": f"Bearer {DEVICEHUB_CONTROL_TOKEN}",
                                      "X-DH-Operator": _operator(user)})
    except requests.RequestException:
        return _fail("unreachable"), None
    try:
        data = r.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if r.status_code not in (200, 201):
        code = data.get("error") if isinstance(data.get("error"), str) else None
        return _fail((code or f"http_{r.status_code}")[:40], r.status_code), r.status_code
    return data, r.status_code


@router.get("/api/devicehub/accounts")
def devicehub_accounts(user: dict = Depends(require_admin)):
    data, _ = _account_call("GET", "/api/v1/accounts", user)
    if data.get("ok") is False:
        return data
    keep = ("id", "name", "type", "status", "last_seen", "connected")
    accounts = [{k: a.get(k) for k in keep} for a in data.get("accounts", []) if isinstance(a, dict)]
    return {"ok": True, "accounts": accounts}


@router.post("/api/devicehub/accounts")
def devicehub_account_add(body: AccountBody, user: dict = Depends(require_admin)):
    if not _ACCOUNT_ID.match(body.id) or body.kind not in _ACCOUNT_KINDS:
        return _fail("bad_request", 400)
    name = (body.name or "").strip() or None
    data, _ = _account_call("POST", "/api/v1/accounts", user, {"id": body.id, "name": name, "kind": body.kind})
    if data.get("ok") is False:
        return data
    _cache.update(ts=0.0, data=None)
    mqtt = data.get("mqtt") if isinstance(data.get("mqtt"), dict) else {}
    out = {
        "ok": True, "id": data.get("id"), "name": data.get("name"), "kind": data.get("kind"),
        "password": data.get("password"),  # 只出現這一次；不寫日誌、不快取
        "mqtt": {k: mqtt.get(k) for k in ("lan", "tailnet", "port")},
    }
    return JSONResponse(out, headers={"Cache-Control": "no-store"})


@router.delete("/api/devicehub/accounts/{device_id}")
def devicehub_account_delete(device_id: str, body: PowerBody | None = None, user: dict = Depends(require_admin)):
    if not _ACCOUNT_ID.match(device_id):
        return _fail("bad_request", 400)
    data, _ = _account_call("DELETE", f"/api/v1/accounts/{device_id}", user,
                            {"confirm": bool(body and body.confirm)})
    if data.get("ok") is False:
        return data
    _cache.update(ts=0.0, data=None)
    return {"ok": True, "id": data.get("id"), "removed": bool(data.get("removed"))}
