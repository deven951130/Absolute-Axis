from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

# Config mapping & Routers
from app.config import BASE_PATH, ALLOWED_ORIGINS
from app.database import engine, Base
from app.utils import init_db_user
from app.routers import auth, admin, user, system, docker, nas, proxmox, minecraft, smart_home

app = FastAPI(title="Absolute Axis Server")

# Initialize Database Tables
Base.metadata.create_all(bind=engine)
init_db_user()

# CORS - 讀取環境變數 ALLOWED_ORIGINS，預設值為 * 向下相容
# 生產環境請在 .env 中設定 ALLOWED_ORIGINS=https://absoluteaxis.dpdns.org
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
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
app.include_router(proxmox.router)
app.include_router(minecraft.router)
app.include_router(smart_home.router)


# ----------------- 靜態與首頁路由 -----------------
# 注意：這行必須放在所有 API 路由之後，以免遮蔽 API
app.mount("/static", StaticFiles(directory=os.path.join(BASE_PATH, "static")), name="static")

# 動態版本號注入，讀取 APP_VERSION 環境變數（預設為當前時間戳）
import time as _time
_APP_VERSION = os.getenv("APP_VERSION", str(int(_time.time())))

@app.get("/")
@app.get("/introduce")
@app.get("/price")
@app.get("/main")
@app.get("/virtal")
@app.get("/iot")
@app.get("/axcloud")
@app.get("/nas")
@app.get("/axai")
@app.get("/livedata")
@app.get("/system")
@app.get("/idmanage")
def home():
    index_path = os.path.join(BASE_PATH, "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        # 注入版本號，替換靜態資源的 ?v= 佔位符
        html = html.replace("?v=AXIS_VER", f"?v={_APP_VERSION}")
        return HTMLResponse(content=html)
    return HTMLResponse(content="<h1>Index.html not found in static/</h1>", status_code=404)

@app.get("/logo.jpg")
def logo():
    logo_path = os.path.join(BASE_PATH, "static", "logo.jpg")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    return HTMLResponse(status_code=404)
