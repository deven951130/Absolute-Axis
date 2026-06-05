import os
import json
import requests
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.utils import get_current_user_obj, log_event, get_current_user_obj_optional
from app.config import BASE_PATH

router = APIRouter(prefix="/api/github", tags=["github_repos"])

REPOS_FILE = os.path.join(BASE_PATH, "app", "github-repos.json")
CONFIG_FILE = os.path.join(BASE_PATH, "app", "github-config.json")

class RepoCreate(BaseModel):
    name: str
    full_name: str
    description: str = ""
    stars: int = 0
    forks: int = 0
    language: str = "JavaScript"
    html_url: str

class GithubConfig(BaseModel):
    developer_name: str
    github_url: str
    github_token: Optional[str] = ""

def _load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "developer_name": "deven951130",
        "github_url": "https://github.com/deven951130",
        "github_token": ""
    }

def _save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def _get_effective_token() -> str:
    config = _load_config()
    cfg_token = config.get("github_token", "").strip()
    if cfg_token:
        return cfg_token
    env_token = os.getenv("GITHUB_TOKEN")
    if env_token and env_token != "your_github_token_here":
        return env_token
    return ""

def _load_repos() -> list:
    if os.path.exists(REPOS_FILE):
        try:
            with open(REPOS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    config = _load_config()
    dev_name = config.get("developer_name", "deven951130")
    
    token = _get_effective_token()
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
        
    try:
        r = requests.get(f"https://api.github.com/users/{dev_name}/repos?sort=updated", headers=headers, timeout=10)
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


@router.get("/parse-url")
def parse_github_url(url: str, user: dict = Depends(get_current_user_obj)):
    """解析 GitHub 專案連結並取得 metadata（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員管理專案")
        
    url = url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="請提供有效的 GitHub 連結")
        
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if "github.com" not in parsed.netloc.lower():
            raise HTTPException(status_code=400, detail="僅支援 github.com 網域的連結")
            
        path = parsed.path.strip("/")
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="無法解析的 GitHub 專案路徑，格式應為 https://github.com/owner/repo")
            
        owner = parts[0]
        repo = parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"連結解析失敗: {str(e)}")
        
    token = _get_effective_token()
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"
        
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        r = requests.get(api_url, headers=headers, timeout=10)
        if r.status_code == 200:
            repo_data = r.json()
            return {
                "name": repo_data.get("name"),
                "full_name": repo_data.get("full_name"),
                "description": repo_data.get("description") or "",
                "stars": repo_data.get("stargazers_count", 0),
                "forks": repo_data.get("forks_count", 0),
                "language": repo_data.get("language") or "JavaScript",
                "html_url": repo_data.get("html_url")
            }
        elif r.status_code == 404:
            raise HTTPException(status_code=404, detail="找不到該專案，請確認專案是否存在且為公開專案")
        else:
            detail_msg = f"GitHub API 回傳錯誤: {r.status_code}"
            try:
                err_json = r.json()
                if "message" in err_json:
                    detail_msg += f" ({err_json['message']})"
            except Exception:
                pass
            raise HTTPException(status_code=400, detail=detail_msg)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"請求 GitHub API 發生錯誤: {str(e)}")


@router.get("/config")
def get_github_config(user: dict = Depends(get_current_user_obj_optional)):
    """取得開源專案作者配置資訊"""
    config = _load_config()
    res = {
        "developer_name": config.get("developer_name", "deven951130"),
        "github_url": config.get("github_url", "https://github.com/deven951130")
    }
    if user and user.get("role") in ("admin", "Administrator"):
        res["has_token"] = bool(config.get("github_token", "").strip())
    return res


@router.post("/config")
def update_github_config(req: GithubConfig, user: dict = Depends(get_current_user_obj)):
    """更新開源專案作者配置資訊（管理員限定）"""
    role = user.get("role", "")
    if role not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="僅限管理員管理專案設定")
        
    old_config = _load_config()
    
    new_token = req.github_token.strip() if req.github_token else ""
    if new_token == "••••••••••••••••":
        new_token = old_config.get("github_token", "")
        
    new_config = {
        "developer_name": req.developer_name.strip(),
        "github_url": req.github_url.strip(),
        "github_token": new_token
    }
    
    if not new_config["developer_name"] or not new_config["github_url"]:
        raise HTTPException(status_code=400, detail="名字與連結不得為空")
        
    _save_config(new_config)
    
    # 如果開發者名稱改變了，自動清除專案快取，促使重新向新帳號拉取
    if old_config.get("developer_name", "").lower() != new_config["developer_name"].lower():
        if os.path.exists(REPOS_FILE):
            try:
                os.remove(REPOS_FILE)
                log_event(user["username"], f"GITHUB_ADMIN: Cleared repos cache because developer_name changed to {new_config['developer_name']}")
            except Exception as e:
                print(f"Error removing cache file: {e}")
                
    log_event(user["username"], f"GITHUB_ADMIN: Updated author profile config to {new_config['developer_name']}")
    return {"status": "ok", "config": {
        "developer_name": new_config["developer_name"],
        "github_url": new_config["github_url"]
    }}


