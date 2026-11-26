"""專案目標追蹤（app/routers/goals.py）的測試。

app.utils 會連資料庫與 JWT，所以這裡用假的 require_admin／get_current_user_obj_optional 取代。
執行：在 repo 根目錄 `python -m pytest tests`
"""
import sys
import types

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

USERS = {
    "Bearer admin": {"username": "sparkle", "role": "Administrator"},
    "Bearer member": {"username": "friend", "role": "Member"},
}


def fake_optional(authorization: str = Header(None)):
    return USERS.get(authorization)


def fake_require_admin(authorization: str = Header(None)):
    user = USERS.get(authorization)
    if user is None:
        raise HTTPException(401)
    if user["role"] not in ("admin", "Administrator"):
        raise HTTPException(403)
    return user


_saved_utils = sys.modules.get("app.utils")
_utils = types.ModuleType("app.utils")
_utils.require_admin = fake_require_admin
_utils.get_current_user_obj_optional = fake_optional
_utils.log_event = lambda *a, **k: None
sys.modules["app.utils"] = _utils
try:
    from app.routers import goals  # noqa: E402
finally:
    # 別讓假模組影響其他測試檔
    if _saved_utils is not None:
        sys.modules["app.utils"] = _saved_utils
    else:
        sys.modules.pop("app.utils", None)

ADMIN = {"Authorization": "Bearer admin"}
MEMBER = {"Authorization": "Bearer member"}
SYNC = {"X-Goals-Token": "sync-secret"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(goals, "GOALS_FILE", str(tmp_path / "project-goals.json"))
    monkeypatch.setenv("AXIS_GOALS_TOKEN", "sync-secret")
    app = FastAPI()
    app.include_router(goals.router)
    return TestClient(app)


def _project(client, name="DeviceHub"):
    r = client.post("/api/goals/projects", json={"name": name, "path": r"E:\github project\DeviceHub"}, headers=ADMIN)
    assert r.status_code == 200
    return r.json()


def _goal(client, pid, kind, key, text="目標"):
    r = client.post(f"/api/goals/projects/{pid}/goals", json={"kind": kind, "key": key, "text": text}, headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()


def test_auth_rules(client):
    assert client.get("/api/goals").status_code == 401
    assert client.get("/api/goals", headers=MEMBER).status_code == 401
    assert client.get("/api/goals", headers={"X-Goals-Token": "wrong"}).status_code == 401
    assert client.get("/api/goals", headers=SYNC).json() == {"projects": [], "last_sync": None}
    assert client.get("/api/goals", headers=ADMIN).status_code == 200
    # 同步 token 只能讀取與推送進度，不能管理專案
    assert client.post("/api/goals/projects", json={"name": "X"}, headers=SYNC).status_code == 401
    assert client.post("/api/goals/projects", json={"name": "X"}, headers=MEMBER).status_code == 403


def test_token_unset_rejects_sync(client, monkeypatch):
    monkeypatch.setenv("AXIS_GOALS_TOKEN", "")
    assert client.get("/api/goals", headers={"X-Goals-Token": ""}).status_code == 401


def test_project_crud_and_duplicate(client):
    p = _project(client)
    assert client.post("/api/goals/projects", json={"name": "devicehub"}, headers=ADMIN).status_code == 400
    r = client.put(f"/api/goals/projects/{p['id']}", json={"status": "paused"}, headers=ADMIN)
    assert r.json()["status"] == "paused"
    assert client.put(f"/api/goals/projects/{p['id']}", json={"status": "bogus"}, headers=ADMIN).status_code == 422
    assert client.delete(f"/api/goals/projects/{p['id']}", headers=ADMIN).status_code == 200
    assert client.get("/api/goals", headers=ADMIN).json()["projects"] == []


@pytest.mark.parametrize("kind,key", [
    ("daily", "2026-W48"),     # Python 3.11 的 date.fromisoformat 會接受這個，必須擋下
    ("daily", "2026-13-40"),
    ("weekly", "2026-11-26"),
    ("weekly", "2026-W60"),
])
def test_bad_goal_keys(client, kind, key):
    p = _project(client)
    r = client.post(f"/api/goals/projects/{p['id']}/goals", json={"kind": kind, "key": key, "text": "x"}, headers=ADMIN)
    assert r.status_code in (400, 422)


def test_goal_toggle_and_delete(client):
    p = _project(client)
    g = _goal(client, p["id"], "weekly", "2026-W48")
    r = client.patch(f"/api/goals/projects/{p['id']}/goals/{g['id']}", json={"done": True}, headers=ADMIN)
    assert r.json()["done"] is True and r.json()["done_by"] == "sparkle"
    r = client.patch(f"/api/goals/projects/{p['id']}/goals/{g['id']}", json={"done": False}, headers=ADMIN)
    assert r.json()["done"] is False and r.json()["done_by"] is None
    assert client.delete(f"/api/goals/projects/{p['id']}/goals/{g['id']}", headers=ADMIN).status_code == 200
    data = client.get("/api/goals", headers=ADMIN).json()
    assert data["projects"][0]["weekly_goals"] == {}  # 空的週次會被清掉


def test_progress_push_is_idempotent_and_marks_goals(client):
    p = _project(client)
    w = _goal(client, p["id"], "weekly", "2026-W48", "Worker 上線")
    d = _goal(client, p["id"], "daily", "2026-11-26", "合併分支")
    body = {"updates": [{
        "project_id": p["id"], "date": "2026-11-26", "summary": "完成 D-26", "commits": 3, "files_changed": 9,
        "completed_goals": [{"goal_id": w["id"], "note": "b9d70bb"}, {"goal_id": "missing", "note": "x"}],
    }]}
    r = client.post("/api/goals/progress", json=body, headers=SYNC)
    assert r.status_code == 200
    assert r.json()["applied"][0]["marked_done"] == [w["id"]]
    client.post("/api/goals/progress", json=body, headers=SYNC)

    proj = client.get("/api/goals", headers=ADMIN).json()["projects"][0]
    assert len(proj["progress_log"]) == 1  # 同日重複推送 = 覆蓋
    wg = proj["weekly_goals"]["2026-W48"][0]
    assert wg["done"] and wg["done_by"] == "claude-sync" and wg["note"] == "b9d70bb"
    assert proj["daily_goals"]["2026-11-26"][0]["done"] is False


def test_progress_push_never_unchecks(client):
    p = _project(client)
    g = _goal(client, p["id"], "daily", "2026-11-26")
    client.patch(f"/api/goals/projects/{p['id']}/goals/{g['id']}", json={"done": True}, headers=ADMIN)
    body = {"updates": [{"project_id": p["id"], "date": "2026-11-26", "summary": "今日無程式異動"}]}
    assert client.post("/api/goals/progress", json=body, headers=SYNC).status_code == 200
    proj = client.get("/api/goals", headers=ADMIN).json()["projects"][0]
    g2 = proj["daily_goals"]["2026-11-26"][0]
    assert g2["done"] is True and g2["done_by"] == "sparkle"


def test_progress_unknown_project_404(client):
    body = {"updates": [{"project_id": "nope", "date": "2026-11-26", "summary": "x"}]}
    assert client.post("/api/goals/progress", json=body, headers=SYNC).status_code == 404
