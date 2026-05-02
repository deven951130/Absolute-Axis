import os

# ----------------- 資料路徑核心 (Dynamic Environment Detection) -----------------
# 優先讀取環境變數，若無則自動偵測
ALT_BASE = "/home/sparkle/aiot-master"
if os.path.exists(ALT_BASE):
    BASE_PATH = ALT_BASE
else:
    BASE_PATH = os.getenv("AXIS_BASE_PATH", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# NAS_ROOT: 優先偵測專用掛載目錄
NAS_ROOT = os.getenv("AXIS_NAS_PATH", os.path.join(BASE_PATH, "nas"))

if not os.path.exists(NAS_ROOT): 
    # Fallback to nas_storage if it exists (legacy support)
    NAS_ALT = os.path.join(BASE_PATH, "nas_storage")
    if os.path.exists(NAS_ALT):
        NAS_ROOT = NAS_ALT
    else:
        os.makedirs(NAS_ROOT)

# 系統根路徑偵測 (用於磁碟空間計算)
SYS_ROOT = "/" if (os.name != 'nt' or os.path.exists(ALT_BASE)) else "C:\\"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(BASE_PATH, 'axis.db')}"
LOG_DB_PATH = os.path.join(BASE_PATH, "logs.json")

# JWT Security Config
JWT_SECRET = os.getenv("AXIS_JWT_SECRET", "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 Days

# PVE Config
PVE_HOST = os.getenv("PVE_HOST", "100.124.203.61")
PVE_USER = os.getenv("PVE_USER", "root@pam")
PVE_PASS = os.getenv("PVE_PASS", "deven951130")

QUOTA_PER_USER = 1 * 1024 * 1024 * 1024  # 1GB 配額
ACTIVE_SESSIONS = {}
SYSTEM_LOGS = []
