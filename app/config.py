import os
import sys

# ----------------- 資料路徑核心 (Dynamic Environment Detection) -----------------
# 優先讀取環境變數，若無則自動偵測當前專案根目錄
BASE_PATH = os.getenv("AXIS_BASE_PATH", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# NAS_ROOT: 優先偵測環境變數，其次為 BASE_PATH/nas，再次為 nas_storage (legacy)
NAS_ROOT = os.getenv("AXIS_NAS_PATH", os.path.join(BASE_PATH, "nas"))

if not os.path.exists(NAS_ROOT):
    # Fallback to nas_storage if it exists (legacy support)
    NAS_ALT = os.path.join(BASE_PATH, "nas_storage")
    if os.path.exists(NAS_ALT):
        NAS_ROOT = NAS_ALT
    else:
        os.makedirs(NAS_ROOT)

# 系統根路徑偵測 (用於磁碟空間計算)
SYS_ROOT = os.getenv("AXIS_SYS_ROOT", "/" if os.name != 'nt' else "C:\\")

SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(BASE_PATH, 'axis.db')}"
LOG_DB_PATH = os.path.join(BASE_PATH, "logs.json")

# JWT Security Config - 強制從環境變數讀取，不允許明碼預設值
_jwt_secret = os.getenv("AXIS_JWT_SECRET")
if not _jwt_secret:
    print("FATAL ERROR: AXIS_JWT_SECRET environment variable is not set.")
    print("Please copy .env.example to .env and fill in all required values.")
    sys.exit(1)
JWT_SECRET = _jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 Days

# PVE Config - 從環境變數讀取，無明碼預設值
PVE_HOST = os.getenv("PVE_HOST", "192.168.0.138")
PVE_USER = os.getenv("PVE_USER", "root@pam")
PVE_PASS = os.getenv("PVE_PASS")

# IoT Config
BLYNK_TOKEN = os.getenv("BLYNK_TOKEN")

# CORS Config
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")]

QUOTA_PER_USER = 100 * 1024 * 1024 * 1024  # 100GB 配額
ACTIVE_SESSIONS = {}
SYSTEM_LOGS = []
