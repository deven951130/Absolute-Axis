"""Local stand-in for the DeviceHub integration API v0.2 (for viewing the Axis UI only).
Shapes follow DeviceHub docs/spec/integration-api.md; commands change a little state so the
UI can be exercised. Run: python fake_devicehub.py  (listens on 127.0.0.1:18080)"""
import time

import uvicorn
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

READ, CONTROL = "fake-read", "fake-control"
now = lambda: int(time.time())  # noqa: E731

devices = {
    "esp-server": {"id": "esp-server", "name": "esp-server", "type": "esp32", "status": "online",
                   "telemetry": {"temp_c": 28.4, "hum": 71, "rssi": -41, "uptime": 93000},
                   "wdog": {"enabled": False, "host_alive": True, "planned_off": False}},
    "desktop": {"id": "desktop", "name": "桌機", "type": "host", "status": "offline",
                "telemetry": {"cpu": 3, "ram": 41, "disk": 62, "uptime": 0}},
    "laptop": {"id": "laptop", "name": "laptop", "type": "host", "status": "online",
               "telemetry": {"cpu": 12, "ram": 58, "disk": 71, "uptime": 5400}},
}
guests = [
    {"vmid": 100, "name": "axis-main", "type": "qemu", "status": "running", "cpu": 0.07, "mem": 5.1 * 2**30, "maxmem": 16 * 2**30, "uptime": 90000, "self": False},
    {"vmid": 101, "name": "Kali-Linux", "type": "qemu", "status": "stopped", "cpu": 0, "mem": 0, "maxmem": 4 * 2**30, "uptime": 0, "self": False},
    {"vmid": 150, "name": "devicehub", "type": "lxc", "status": "running", "cpu": 0.01, "mem": 0.2 * 2**30, "maxmem": 2**30, "uptime": 90000, "self": True},
]
alerts = [
    {"ts": now() - 3600 * 5, "level": "notice", "message": "🛰️ axis（sparkle）對「laptop」執行 ping：ok"},
    {"ts": now() - 86400 * 2, "level": "recovery", "message": "🟢 esp-server（esp-server）恢復上線（離線 3 分）"},
    {"ts": now() - 86400 * 2 - 200, "level": "alert", "message": "🔴 esp-server（esp-server）已離線超過 2 分"},
]
ACTIONS = {"esp32": ["ping", "pwrbtn.hold", "pwrbtn.press", "sys.reboot"],
           "host": ["host.restart", "host.shutdown", "host.sleep", "ping", "sys.reboot"]}
DANGER = {"pwrbtn.hold", "pwrbtn.press", "sys.reboot", "host.restart", "host.shutdown", "host.sleep"}

app = FastAPI()


def auth(authorization, control=False):
    ok = {f"Bearer {CONTROL}"} | (set() if control else {f"Bearer {READ}"})
    return authorization in ok


def err(status, code):
    return JSONResponse({"error": code, "detail": None}, status_code=status)


@app.get("/api/v1/summary")
def summary(authorization: str = Header(None)):
    if not auth(authorization):
        return err(401, "unauthorized")
    for d in devices.values():
        d["last_seen"] = now() - (5 if d["status"] == "online" else 7200)
    return {"generated_at": now(), "ui_url": "https://devicehub.tail9f124e.ts.net",
            "devices": list(devices.values()),
            "proxmox": {"enabled": True, "error": None,
                        "guests": [{k: v for k, v in g.items() if k != "self"} for g in guests]},
            "alerts": alerts[:10]}


@app.get("/api/v1/controls")
def controls(authorization: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    items = []
    for d in devices.values():
        wake = {"direct": d["id"] == "desktop", "via": ["esp-server"] if d["id"] == "desktop" else []} if d["type"] == "host" else None
        items.append({"id": d["id"], "actions": [{"action": a, "danger": a in DANGER} for a in ACTIONS[d["type"]]], "wake": wake})
    pve = [{"vmid": g["vmid"], "actions": ["shutdown", "reboot", "stop"] if g["status"] == "running" else ["start"]}
           for g in guests if not g["self"]]
    return {"devices": items, "proxmox": pve}


def notice(op, target, action, result):
    alerts.insert(0, {"ts": now(), "level": "notice", "message": f"🛰️ axis（{op}）對「{target}」執行 {action}：{result}"})


@app.post("/api/v1/devices/{device_id}/commands")
async def command(device_id: str, request: Request, authorization: str = Header(None), x_dh_operator: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    body = await request.json()
    d = devices.get(device_id)
    if d is None:
        return err(404, "unknown_device")
    if d["status"] != "online":
        return err(409, "device_offline")
    if body["action"] in DANGER and not body.get("confirm"):
        return err(428, "confirm_required")
    time.sleep(0.6)
    if body["action"] in ("host.sleep", "host.shutdown"):
        d["status"] = "offline"
    notice(x_dh_operator, d["name"], body["action"], "ok")
    return {"id": "01FAKE", "result": "ok", "error": None}


@app.post("/api/v1/devices/{device_id}/wake")
async def wake(device_id: str, authorization: str = Header(None), x_dh_operator: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    devices[device_id]["status"] = "online"
    notice(x_dh_operator, devices[device_id]["name"], "wake", "ok")
    return {"id": "01FAKE", "result": "ok", "error": None}


@app.post("/api/v1/proxmox/{vmid}/{action}")
async def power(vmid: int, action: str, request: Request, authorization: str = Header(None), x_dh_operator: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    body = await request.json()
    g = next((g for g in guests if g["vmid"] == vmid), None)
    if g is None:
        return err(404, "unknown_guest")
    if g["self"]:
        return err(409, "self_protected")
    if action != "start" and not body.get("confirm"):
        return err(428, "confirm_required")
    time.sleep(0.8)
    g["status"] = "running" if action in ("start", "reboot") else "stopped"
    notice(x_dh_operator, f"{g['name']}（{vmid}）", f"pve.{action}", "ok")
    return {"id": "01FAKE", "result": "ok", "error": None}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18080, log_level="warning")
