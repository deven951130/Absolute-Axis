import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Config mapping & Routers
from app.config import BASE_PATH
from app.routers import auth, admin, user, system, docker, nas

app = FastAPI(title="Absolute Axis Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- 路由掛載 (Router Inclusion) -----------------
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(user.router)
app.include_router(system.router)
app.include_router(docker.router)
app.include_router(nas.router)


# ----------------- 靜態與首頁路由 -----------------
@app.get("/")
def home():
    # 改為導向 static 目錄底下的檔案
    index_path = os.path.join(BASE_PATH, "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Index.html not found in static/</h1>", status_code=404)

@app.get("/logo.jpg")
def logo():
    logo_path = os.path.join(BASE_PATH, "static", "logo.jpg")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    return HTMLResponse(status_code=404)

