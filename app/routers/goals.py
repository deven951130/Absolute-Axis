"""
專案目標追蹤 (Project Goals Tracker)

- 每個專案：每週目標（以 ISO 週 key，例如 2026-W48）、每日目標（以日期 key，例如 2026-11-26）、進度日誌
- 資料存於 app/project-goals.json（不進 git）
- 人員操作：僅 Administrator（JWT）
- 排程任務（Claude 每日同步）：以 X-Goals-Token 標頭驗證，token 來自環境變數 AXIS_GOALS_TOKEN
"""
import os
import re
import json
import uuid
import hmac
import threading
from datetime import datetime, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from app.config import BASE_PATH
from app.utils import get_current_user_obj_optional, log_event, require_admin

router = APIRouter(prefix="/api/goals", tags=["goals"])

GOALS_FILE = os.getenv("AXIS_GOALS_FILE", os.path.join(BASE_PATH, "app", "project-goals.json"))
_LOCK = threading.Lock()
MAX_LOG_ENTRIES = 120  # 每專案保留最近 120 筆進度紀錄


# ----------------- 儲存層 -----------------
def _load() -> dict:
    if os.path.exists(GOALS_FILE):
        try:
            with open(GOALS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("projects"), list):
                    return data
        except Exception as e:
            print(f"[GOALS] Failed to read {GOALS_FILE}: {e}")
            raise HTTPException(status_code=500, detail="目標資料檔讀取失敗，請檢查 project-goals.json")
    return {"projects": [], "last_sync": None}


def _save(data: dict):
    os.makedirs(os.path.dirname(GOALS_FILE) or ".", exist_ok=True)
    tmp = GOALS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, GOALS_FILE)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


def _find_project(data: dict, pid: str) -> dict:
    for p in data["projects"]:
        if p["id"] == pid:
            return p
    raise HTTPException(status_code=404, detail="找不到該專案")


def _ensure_shape(p: dict):
    p.setdefault("weekly_goals", {})
    p.setdefault("daily_goals", {})
    p.setdefault("progress_log", [])


# ----------------- 驗證 -----------------
def require_actor(
    x_goals_token: Optional[str] = Header(None),
    user: Optional[dict] = Depends(get_current_user_obj_optional),
) -> str:
    """允許管理員 JWT 或排程任務 token。回傳操作者名稱。"""
    expected = os.getenv("AXIS_GOALS_TOKEN", "")
    if x_goals_token is not None:
        if expected and hmac.compare_digest(x_goals_token, expected):
            return "claude-sync"
        raise HTTPException(status_code=401, detail="Invalid goals token")
    if user and user.get("role") in ("Administrator", "admin"):
        return user["username"]
    raise HTTPException(status_code=401, detail="未授權")


# ----------------- 資料模型 -----------------
class ProjectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    path: str = Field("", max_length=400)
    description: str = Field("", max_length=500)
    status: str = Field("active", pattern="^(active|paused|done)$")


class ProjectPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    path: Optional[str] = Field(None, max_length=400)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, pattern="^(active|paused|done)$")


class GoalIn(BaseModel):
    kind: str = Field(..., pattern="^(weekly|daily)$")
    key: str = Field(..., pattern=r"^(\d{4}-W\d{2}|\d{4}-\d{2}-\d{2})$")
    text: str = Field(..., min_length=1, max_length=300)


class GoalPatch(BaseModel):
    text: Optional[str] = Field(None, min_length=1, max_length=300)
    done: Optional[bool] = None


class GoalCompletion(BaseModel):
    goal_id: str
    note: str = Field("", max_length=300)


class ProgressUpdate(BaseModel):
    project_id: str
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    summary: str = Field(..., min_length=1, max_length=2000)
    commits: int = 0
    files_changed: int = 0
    completed_goals: List[GoalCompletion] = []


class ProgressBatch(BaseModel):
    updates: List[ProgressUpdate]


_WEEK_RE = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_key(kind: str, key: str):
    if kind == "weekly" and not _WEEK_RE.match(key):
        raise HTTPException(status_code=400, detail="每週目標的 key 必須為 YYYY-Www 格式")
    if kind == "daily":
        # 注意：Python 3.11+ 的 date.fromisoformat 也接受 2026-W48，必須先用正規式限定格式
        try:
            if not _DAY_RE.match(key):
                raise ValueError
            date.fromisoformat(key)
        except ValueError:
            raise HTTPException(status_code=400, detail="每日目標的 key 必須為 YYYY-MM-DD 格式")


def _iter_goals(p: dict):
    for bucket in ("weekly_goals", "daily_goals"):
        for key, goals in p.get(bucket, {}).items():
            for g in goals:
                yield bucket, key, goals, g


def _find_goal(p: dict, gid: str):
    for bucket, key, goals, g in _iter_goals(p):
        if g["id"] == gid:
            return bucket, key, goals, g
    raise HTTPException(status_code=404, detail="找不到該目標")


# ----------------- 讀取 -----------------
@router.get("")
def get_all(actor: str = Depends(require_actor)):
    """完整資料（前端與排程任務共用）"""
    return _load()


# ----------------- 專案 CRUD -----------------
@router.post("/projects")
def create_project(req: ProjectIn, user: dict = Depends(require_admin)):
    with _LOCK:
        data = _load()
        if any(p["name"].lower() == req.name.strip().lower() for p in data["projects"]):
            raise HTTPException(status_code=400, detail="已有同名專案")
        proj = {
            "id": _new_id(),
            "name": req.name.strip(),
            "path": req.path.strip(),
            "description": req.description.strip(),
            "status": req.status,
            "created_at": _now(),
            "weekly_goals": {},
            "daily_goals": {},
            "progress_log": [],
        }
        data["projects"].append(proj)
        _save(data)
    log_event(user["username"], f"GOALS: Added project [{proj['name']}]")
    return proj


@router.put("/projects/{pid}")
def update_project(pid: str, req: ProjectPatch, user: dict = Depends(require_admin)):
    with _LOCK:
        data = _load()
        p = _find_project(data, pid)
        for field, val in req.model_dump(exclude_none=True).items():
            p[field] = val.strip() if isinstance(val, str) else val
        _save(data)
    return p


@router.delete("/projects/{pid}")
def delete_project(pid: str, user: dict = Depends(require_admin)):
    with _LOCK:
        data = _load()
        p = _find_project(data, pid)
        data["projects"] = [x for x in data["projects"] if x["id"] != pid]
        _save(data)
    log_event(user["username"], f"GOALS: Deleted project [{p['name']}]")
    return {"status": "ok"}


# ----------------- 目標 CRUD -----------------
@router.post("/projects/{pid}/goals")
def add_goal(pid: str, req: GoalIn, user: dict = Depends(require_admin)):
    _validate_key(req.kind, req.key)
    with _LOCK:
        data = _load()
        p = _find_project(data, pid)
        _ensure_shape(p)
        bucket = "weekly_goals" if req.kind == "weekly" else "daily_goals"
        goal = {
            "id": _new_id(),
            "text": req.text.strip(),
            "done": False,
            "done_at": None,
            "done_by": None,
            "note": "",
            "created_at": _now(),
        }
        p[bucket].setdefault(req.key, []).append(goal)
        _save(data)
    return goal


@router.patch("/projects/{pid}/goals/{gid}")
def patch_goal(pid: str, gid: str, req: GoalPatch, user: dict = Depends(require_admin)):
    with _LOCK:
        data = _load()
        p = _find_project(data, pid)
        _, _, _, g = _find_goal(p, gid)
        if req.text is not None:
            g["text"] = req.text.strip()
        if req.done is not None:
            g["done"] = req.done
            g["done_at"] = _now() if req.done else None
            g["done_by"] = user["username"] if req.done else None
            if not req.done:
                g["note"] = ""
        _save(data)
    return g


@router.delete("/projects/{pid}/goals/{gid}")
def delete_goal(pid: str, gid: str, user: dict = Depends(require_admin)):
    with _LOCK:
        data = _load()
        p = _find_project(data, pid)
        bucket, key, goals, g = _find_goal(p, gid)
        goals.remove(g)
        if not goals:
            del p[bucket][key]
        _save(data)
    return {"status": "ok"}


# ----------------- 進度同步（排程任務 / 手動） -----------------
@router.post("/progress")
def push_progress(req: ProgressBatch, actor: str = Depends(require_actor)):
    """
    寫入每日進度。同一專案同一天重複推送會覆蓋前一筆（冪等）。
    completed_goals 只會「標記完成」，不會取消使用者手動勾選的狀態。
    """
    applied = []
    with _LOCK:
        data = _load()
        for u in req.updates:
            p = _find_project(data, u.project_id)
            _ensure_shape(p)
            entry = {
                "date": u.date,
                "summary": u.summary.strip(),
                "commits": max(0, u.commits),
                "files_changed": max(0, u.files_changed),
                "source": actor,
                "updated_at": _now(),
            }
            p["progress_log"] = [e for e in p["progress_log"] if not (e["date"] == u.date and e.get("source") == actor)]
            p["progress_log"].append(entry)
            p["progress_log"].sort(key=lambda e: e["date"], reverse=True)
            p["progress_log"] = p["progress_log"][:MAX_LOG_ENTRIES]

            marked = []
            for c in u.completed_goals:
                try:
                    _, _, _, g = _find_goal(p, c.goal_id)
                except HTTPException:
                    continue
                if not g["done"]:
                    g["done"] = True
                    g["done_at"] = _now()
                    g["done_by"] = actor
                    g["note"] = c.note.strip()
                    marked.append(g["id"])
            applied.append({"project_id": p["id"], "marked_done": marked})
        data["last_sync"] = {"at": _now(), "by": actor, "projects": len(req.updates)}
        _save(data)
    log_event(actor, f"GOALS: Progress sync for {len(req.updates)} project(s)")
    return {"status": "ok", "applied": applied}
