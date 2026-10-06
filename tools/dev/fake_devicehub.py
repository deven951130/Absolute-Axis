"""Local stand-in for the DeviceHub integration API v0.6 (for viewing the Axis UI only).
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


# ---- v0.4 §3.8 裝置帳號（綁定裝置頁籤） ----
accounts = {"esp-server", "desktop", "laptop"}


@app.get("/api/v1/accounts")
def list_accounts(authorization: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    out = []
    for i in sorted(accounts):
        d = devices.get(i)
        out.append({"id": i, "name": d["name"] if d else i, "type": d["type"] if d else None,
                    "status": d["status"] if d else "unknown", "last_seen": d.get("last_seen") if d else None,
                    "connected": bool(d and d["status"] != "unknown")})
    return {"accounts": out}


@app.post("/api/v1/accounts")
async def add_account(request: Request, authorization: str = Header(None), x_dh_operator: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    body = await request.json()
    i = body["id"]
    if i in ("hub", "owner"):
        return err(403, "reserved")
    if i in accounts:
        return err(409, "exists")
    accounts.add(i)
    name = (body.get("name") or i).strip()
    devices[i] = {"id": i, "name": name, "type": "esp32" if body["kind"] == "esp32" else "host",
                  "status": "unknown", "telemetry": {}}
    alerts.insert(0, {"ts": now(), "level": "notice", "message": f"🛰️ axis（{x_dh_operator}）新增裝置帳號「{i}」：ok"})
    return JSONResponse({"id": i, "name": name, "kind": body["kind"], "password": "fake-pw-" + i,
                         "mqtt": {"lan": "192.168.0.50", "tailnet": "100.88.245.58", "port": 1883}}, status_code=201)


@app.delete("/api/v1/accounts/{device_id}")
async def delete_account(device_id: str, request: Request, authorization: str = Header(None),
                         x_dh_operator: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    body = await request.json()
    if not body.get("confirm"):
        return err(428, "confirm_required")
    if device_id == "esp-server":
        return err(409, "protected")
    if device_id not in accounts:
        return err(404, "unknown_account")
    accounts.discard(device_id)
    devices.pop(device_id, None)
    alerts.insert(0, {"ts": now(), "level": "notice", "message": f"🛰️ axis（{x_dh_operator}）移除裝置帳號「{device_id}」：ok"})
    return {"id": device_id, "removed": True}


# ---------- 省電（v0.5 摘要、v0.6 排程設定；DeviceHub power-saving §5.2、§10.6） ----------
POWER_ACTIONS = {"host.sleep": True, "host.shutdown": True, "host.wake": False, "pve.shutdown": True, "pve.start": False}
power = {"paused_until": 0, "rules": {}, "seq": 0}


def power_targets():
    out = [{"target": "desktop", "name": "桌機", "kind": "host", "actions": ["host.sleep", "host.shutdown", "host.wake"]},
           {"target": "laptop", "name": "laptop", "kind": "host", "actions": ["host.sleep", "host.shutdown"]}]
    out += [{"target": f"pve:{g['vmid']}", "name": f"{g['name']}（{'CT' if g['type'] == 'lxc' else 'VM'} {g['vmid']}）",
             "kind": "pve", "actions": ["pve.shutdown", "pve.start"]} for g in guests if not g["self"]]
    return out


def next_run(r):
    import datetime as dt
    if not r["enabled"] or not r["days"]:
        return None
    tz = dt.timezone(dt.timedelta(hours=8))
    t = dt.datetime.now(tz)
    hh, mm = map(int, r["time"].split(":"))
    for add in range(8):
        d = (t + dt.timedelta(days=add)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if str(d.isoweekday()) in r["days"] and d > t:
            return int(d.timestamp())
    return None


def public(r):
    names = {t["target"]: t["name"] for t in power_targets()}
    return r | {"target_name": names.get(r["target"], r["target"]), "next_run_at": next_run(r)}


def check_rule(b, exclude=None):
    t = next((x for x in power_targets() if x["target"] == b.get("target")), None)
    if not str(b.get("name") or "").strip():
        return JSONResponse({"error": "bad_rule", "detail": "name"}, 400)
    if t is None:
        return JSONResponse({"error": "bad_rule", "detail": "target"}, 400)
    if b.get("action") not in t["actions"]:
        return JSONResponse({"error": "bad_rule", "detail": "action"}, 400)
    if b.get("days") and not b.get("time"):
        return JSONResponse({"error": "bad_rule", "detail": "time"}, 400)
    if b.get("action") in ("host.sleep", "host.shutdown") and not b.get("idle_min"):
        return JSONResponse({"error": "bad_rule", "detail": "idle_min"}, 400)
    if not b.get("days") and b.get("action") not in ("host.sleep", "host.shutdown"):
        return JSONResponse({"error": "bad_rule", "detail": "days"}, 400)
    for o in power["rules"].values():
        if o["id"] != exclude and o["target"] == b["target"] and o["time"] == b.get("time") and b.get("days")                 and set(o["days"]) & set(b["days"]) and POWER_ACTIONS[o["action"]] != POWER_ACTIONS[b["action"]]:
            return JSONResponse({"error": "rule_conflict", "detail": "time"}, 409)
    return None


@app.get("/api/v1/power/summary")
def power_summary(authorization: str = Header(None)):
    if not auth(authorization):
        return err(401, "unauthorized")
    rules = [public(r) for r in power["rules"].values()]
    return {"rules": rules, "paused_until": power["paused_until"], "runs": [],
            "savings": {"days": [], "targets": [], "cpu_energy": []}}


@app.get("/api/v1/power/rules")
def power_rules(authorization: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    return {"rules": [public(r) for r in power["rules"].values()], "paused_until": power["paused_until"],
            "targets": power_targets()}


@app.post("/api/v1/power/rules")
async def power_add(request: Request, authorization: str = Header(None), x_dh_operator: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    b = await request.json()
    if not b.get("confirm"):
        return err(428, "confirm_required")
    if (bad := check_rule(b)):
        return bad
    power["seq"] += 1
    rid = f"r-{power['seq']:04x}"
    r = {k: b.get(k) for k in ("name", "target", "action", "days", "time", "window_min", "idle_min", "cpu_below",
                               "notice_min", "enabled")} | {"id": rid, "fail_count": 0, "last_run_at": None,
                                                            "last_result": None, "state": None, "notice_until": None}
    if not r["days"]:
        r["time"] = ""
    power["rules"][rid] = r
    notice(x_dh_operator, r["target"], "power.rule.add", "ok")
    return JSONResponse(public(r), 201)


@app.put("/api/v1/power/rules/{rid}")
async def power_put(rid: str, request: Request, authorization: str = Header(None), x_dh_operator: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    if rid not in power["rules"]:
        return err(404, "unknown_rule")
    b = await request.json()
    if not b.get("confirm"):
        return err(428, "confirm_required")
    if (bad := check_rule(b, exclude=rid)):
        return bad
    power["rules"][rid].update({k: b.get(k) for k in ("name", "target", "action", "days", "time", "window_min",
                                                      "idle_min", "cpu_below", "notice_min", "enabled")})
    return public(power["rules"][rid])


@app.delete("/api/v1/power/rules/{rid}")
async def power_delete(rid: str, request: Request, authorization: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    b = await request.json()
    if not b.get("confirm"):
        return err(428, "confirm_required")
    if power["rules"].pop(rid, None) is None:
        return err(404, "unknown_rule")
    return {"id": rid, "deleted": True}


@app.post("/api/v1/power/rules/{rid}/skip")
def power_skip(rid: str, authorization: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    r = power["rules"].get(rid)
    if r is None:
        return err(404, "unknown_rule")
    if not r["state"]:
        return err(409, "nothing_pending")
    r["state"] = None
    return public(r)


@app.post("/api/v1/power/pause")
async def power_pause(request: Request, authorization: str = Header(None)):
    if not auth(authorization, control=True):
        return err(401, "unauthorized")
    hours = (await request.json()).get("hours")
    power["paused_until"] = 0 if hours == 0 else now() + (12 * 3600 if hours == "until_morning" else int(hours) * 3600)
    return {"paused_until": power["paused_until"]}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18080, log_level="warning")
