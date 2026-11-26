"""
專案目標每日同步工具（給 Claude 排程任務使用，也可手動執行）

用法：
  python scripts/goals_sync.py collect [--date YYYY-MM-DD]   # 從伺服器取專案清單，掃描本機專案，輸出 JSON 到 stdout
  python scripts/goals_sync.py push <updates.json>           # 把整理好的進度推送到伺服器

設定（依序找第一個存在的）：
  1. 環境變數 AXIS_GOALS_URL / AXIS_GOALS_TOKEN
  2. ~/.axis/goals_sync.json（建議：放在 repo 外，不會被誤 commit）
  3. scripts/goals_sync.local.json（已被 .gitignore 排除）
  檔案格式：{"server_url": "http://<Axis 主機>:8000", "token": "<與伺服器 AXIS_GOALS_TOKEN 相同>"}

只使用 Python 標準函式庫。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATHS = [
    os.path.join(os.path.expanduser("~"), ".axis", "goals_sync.json"),
    os.path.join(HERE, "goals_sync.local.json"),
]
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".pio", "target", "bin", "obj"}
MAX_SCAN_FILES = 20000


def load_config():
    cfg = {}
    for path in CONFIG_PATHS:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            break
    url = os.getenv("AXIS_GOALS_URL") or cfg.get("server_url")
    token = os.getenv("AXIS_GOALS_TOKEN") or cfg.get("token")
    if not url or not token:
        sys.exit(f"[goals_sync] 缺少設定：請建立 {CONFIG_PATHS[0]} 或設定 AXIS_GOALS_URL / AXIS_GOALS_TOKEN")
    return url.rstrip("/"), token


def api(method, path, body=None):
    url, token = load_config()
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url + path, data=data, method=method)
    req.add_header("X-Goals-Token", token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        sys.exit(f"[goals_sync] 伺服器回應 {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"[goals_sync] 無法連線 {url}: {e.reason}")


def iso_week_key(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def git(path, *args):
    r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout.strip()


def scan_git(path, day: date):
    since = f"{day.isoformat()} 00:00:00"
    until = f"{(day + timedelta(days=1)).isoformat()} 00:00:00"
    _, branch = git(path, "rev-parse", "--abbrev-ref", "HEAD")
    _, log = git(path, "log", "--all", "--no-merges", f"--since={since}", f"--until={until}",
                 "--date=format:%H:%M", "--pretty=format:%h|%ad|%s")
    commits = []
    for line in log.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append({"hash": parts[0], "time": parts[1], "subject": parts[2]})
    _, names = git(path, "log", "--all", "--no-merges", f"--since={since}", f"--until={until}",
                   "--name-only", "--pretty=format:")
    files = sorted({n for n in names.splitlines() if n.strip()})
    _, status = git(path, "status", "--porcelain")
    dirty = [l[3:] for l in status.splitlines() if l.strip()]
    return {
        "type": "git",
        "branch": branch,
        "commits": commits,
        "files_changed": len(files),
        "changed_files_sample": files[:40],
        "uncommitted_count": len(dirty),
        "uncommitted_sample": dirty[:20],
    }


def scan_mtime(path, day: date):
    start = datetime.combine(day, datetime.min.time()).timestamp()
    end = start + 86400
    changed, scanned = [], 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            scanned += 1
            if scanned > MAX_SCAN_FILES:
                break
            fp = os.path.join(root, fn)
            try:
                m = os.path.getmtime(fp)
            except OSError:
                continue
            if start <= m < end:
                changed.append(os.path.relpath(fp, path))
        if scanned > MAX_SCAN_FILES:
            break
    changed.sort()
    return {
        "type": "files",
        "commits": [],
        "files_changed": len(changed),
        "changed_files_sample": changed[:40],
        "scan_truncated": scanned > MAX_SCAN_FILES,
    }


def collect(day: date):
    data = api("GET", "/api/goals")
    week = iso_week_key(day)
    out = {"date": day.isoformat(), "week": week, "projects": []}
    for p in data.get("projects", []):
        if p.get("status", "active") != "active":
            continue
        entry = {
            "project_id": p["id"],
            "name": p["name"],
            "path": p.get("path", ""),
            "description": p.get("description", ""),
            "weekly_goals": [{k: g[k] for k in ("id", "text", "done")} for g in p.get("weekly_goals", {}).get(week, [])],
            "daily_goals": [{k: g[k] for k in ("id", "text", "done")} for g in p.get("daily_goals", {}).get(day.isoformat(), [])],
            "recent_progress": [{"date": l["date"], "summary": l["summary"]} for l in p.get("progress_log", [])[:3]],
        }
        path = entry["path"]
        if not path:
            entry["activity"] = {"type": "none", "error": "未設定路徑"}
        elif not os.path.isdir(path):
            entry["activity"] = {"type": "none", "error": f"路徑不存在：{path}"}
        elif os.path.exists(os.path.join(path, ".git")):  # worktree／submodule 的 .git 是檔案
            entry["activity"] = scan_git(path, day)
        else:
            entry["activity"] = scan_mtime(path, day)
        out["projects"].append(entry)
    return out


def push(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        body = json.load(f)
    if isinstance(body, list):
        body = {"updates": body}
    res = api("POST", "/api/goals/progress", body)
    print(json.dumps(res, ensure_ascii=False, indent=2))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--date", default=date.today().isoformat())
    p = sub.add_parser("push")
    p.add_argument("file")
    args = ap.parse_args()
    if args.cmd == "collect":
        print(json.dumps(collect(date.fromisoformat(args.date)), ensure_ascii=False, indent=2))
    else:
        push(args.file)


if __name__ == "__main__":
    main()
