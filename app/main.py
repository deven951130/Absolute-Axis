from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from sqlalchemy import text

# Config mapping & Routers
from app.config import BASE_PATH, ALLOWED_ORIGINS
from app.database import engine, Base
from app.utils import init_db_user
from app.routers import auth, admin, user, system, docker, nas, proxmox, minecraft, smart_home, vm_user, gigs, feedback, github_repos

app = FastAPI(title="Absolute Axis Server")

# Initialize Database Tables
Base.metadata.create_all(bind=engine)

# 自動升級資料庫欄位 (為 gigs 資料表在舊庫中新增 reject_reason 欄位)
try:
    with engine.begin() as conn:
        res = conn.execute(text("PRAGMA table_info(gigs);")).fetchall()
        cols = [r[1] for r in res]
        if "reject_reason" not in cols:
            conn.execute(text("ALTER TABLE gigs ADD COLUMN reject_reason VARCHAR;"))
            print("[DB_UPGRADE] Column 'reject_reason' added to table 'gigs' successfully.")
except Exception as e:
    print(f"[DB_UPGRADE] Warning: failed to auto-upgrade gigs table schema: {e}")

# 自動升級資料庫欄位 (為 gigs 資料表在舊庫中新增 contact 欄位)
try:
    with engine.begin() as conn:
        res = conn.execute(text("PRAGMA table_info(gigs);")).fetchall()
        cols = [r[1] for r in res]
        if "contact" not in cols:
            conn.execute(text("ALTER TABLE gigs ADD COLUMN contact VARCHAR;"))
            print("[DB_UPGRADE] Column 'contact' added to table 'gigs' successfully.")
except Exception as e:
    print(f"[DB_UPGRADE] Warning: failed to auto-upgrade gigs table schema for contact: {e}")

# 自動升級資料庫欄位 (為 users 資料表在舊庫中新增 status 欄位)
try:
    with engine.begin() as conn:
        res = conn.execute(text("PRAGMA table_info(users);")).fetchall()
        cols = [r[1] for r in res]
        if "status" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR DEFAULT 'Approved';"))
            print("[DB_UPGRADE] Column 'status' added to table 'users' successfully.")
except Exception as e:
    print(f"[DB_UPGRADE] Warning: failed to auto-upgrade users table schema: {e}")

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
app.include_router(vm_user.router)
app.include_router(gigs.router)
app.include_router(feedback.router)
app.include_router(github_repos.router)


# ----------------- 靜態與首頁路由 -----------------
# 注意：這行必須放在所有 API 路由之後，以免遮蔽 API
app.mount("/static", StaticFiles(directory=os.path.join(BASE_PATH, "static")), name="static")

# 擺放首頁入口之動態注入與路由映射
import time as _time

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
@app.get("/multiverse")
@app.get("/login")
@app.get("/gigs")
@app.get("/code-share")
@app.get("/feedback-hub")
def home():
    index_path = os.path.join(BASE_PATH, "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        # 注入版本號，使用即時時間戳確保每次請求均破除瀏覽器快取
        html = html.replace("?v=AXIS_VER", f"?v={int(_time.time())}")
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        return HTMLResponse(content=html, headers=headers)
    return HTMLResponse(content="<h1>Index.html not found in static/</h1>", status_code=404)



@app.get("/logo.jpg")
def logo():
    logo_path = os.path.join(BASE_PATH, "static", "logo.jpg")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    return HTMLResponse(status_code=404)
