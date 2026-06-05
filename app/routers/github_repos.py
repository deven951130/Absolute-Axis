import os
import json
import requests
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.utils import get_current_user_obj, log_event
from app.config import BASE_PATH

router = APIRouter(prefix="/api/github", tags=["github_repos"])

REPOS_FILE = os.path.join(BASE_PATH, "app", "github-repos.json")

class RepoCreate(BaseModel):
    name: str
    full_name: str
    description: str = ""
    stars: int = 0
    forks: int = 0
    language: str = "JavaScript"
    html_url: str

def _load_repos() -> list:
    if os.path.exists(REPOS_FILE):
        try:
            with open(REPOS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if token and token != "your_github_token_here":
        headers["Authorization"] = f"token {token}"
        
    try:
        r = requests.get("https://api.github.com/users/deven951130/repos?sort=updated", headers=headers, timeout=10)
        if r.status_code == 200:
            repos_data = r.json()
            res = []
            for repo in repos_data:
                if repo.get("fork"):
                    continue
                res.append({
                    "name": repo.get("name"),
                    "full_name": repo.get("full_name"),
                    "description": repo.get("description"),
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "language": repo.get("language"),
                    "html_url": repo.get("html_url"),
                    "updated_at": repo.get("updated_at")
                })
            _save_repos(res)
            return res
    except Exception as e:
        print(f"Error pre-loading GitHub repos: {e}")
    return []

def _save_repos(repos: list):
    with open(REPOS_FILE, "w", encoding="utf-8") as f:
        json.dump(repos, f, indent=4, ensure_ascii=False)


@router.get("/repos")
def get_github_repos(user: dict = Depends(get_current_user_obj)):
    """獲取所有開源專案"""
    return _load_repos()


@router.post("/repos")
def add_github_repo(req: RepoCreate, user: dict = Depends(get_current_user_obj)):
    """新增開源專案（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員管理專案")
        
    repos = _load_repos()
    
    for r in repos:
        if r["name"].lower() == req.name.lower():
            raise HTTPException(status_code=400, detail="專案名稱已存在")
            
    from datetime import datetime
    new_repo = {
        "name": req.name,
        "full_name": req.full_name,
        "description": req.description,
        "stars": req.stars,
        "forks": req.forks,
        "language": req.language,
        "html_url": req.html_url,
        "updated_at": datetime.now().isoformat()
    }
    repos.insert(0, new_repo)
    _save_repos(repos)
    
    log_event(user["username"], f"GITHUB_ADMIN: Added custom repo {req.name}")
    return {"status": "ok", "repo": new_repo}


@router.delete("/repos/{name}")
def delete_github_repo(name: str, user: dict = Depends(get_current_user_obj)):
    """刪除開源專案（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員管理專案")
        
    repos = _load_repos()
    filtered_repos = [r for r in repos if r["name"].lower() != name.lower()]
    
    if len(filtered_repos) == len(repos):
        raise HTTPException(status_code=404, detail="找不到指定專案")
        
    _save_repos(filtered_repos)
    
    log_event(user["username"], f"GITHUB_ADMIN: Deleted repo {name}")
    return {"status": "ok"}
