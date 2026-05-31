import os
import requests
from fastapi import APIRouter, Depends, HTTPException
from app.utils import get_current_user_obj

router = APIRouter(prefix="/api/github", tags=["github_repos"])

@router.get("/repos")
def get_github_repos(user: dict = Depends(get_current_user_obj)):
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
                # 排除 fork 的專案以保持原創性
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
            return res
        else:
            raise HTTPException(status_code=r.status_code, detail=f"Failed to fetch GitHub repos: HTTP {r.status_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub connection error: {str(e)}")
