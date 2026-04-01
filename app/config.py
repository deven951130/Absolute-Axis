import os

# ----------------- 資料路徑核心 (Dynamic Environment Detection) -----------------
# 優先偵測 Linux 環境路徑，若不存在則回退至專案根目錄
ALT_BASE = "/home/sparkle/aiot-master"
if os.path.exists(ALT_BASE):
    BASE_PATH = ALT_BASE
    SYS_ROOT = "/"  # SATA 0
else:
    BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SYS_ROOT = "C:\\" if os.name == 'nt' else "/"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(BASE_PATH, 'axis.db')}"
LOG_DB_PATH = os.path.join(BASE_PATH, "logs.json")

# JWT Security Config
JWT_SECRET = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"  # SHA-256 hash output as secure key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 Days

# NAS_ROOT: 優先偵測專用掛載目錄，若無則使用專案內的 nas 目錄
NAS_ALT = os.path.join(BASE_PATH, "nas_storage")
if os.path.exists(NAS_ALT):
    NAS_ROOT = NAS_ALT
else:
    NAS_ROOT = os.path.join(BASE_PATH, "nas")

if not os.path.exists(NAS_ROOT): 
    os.makedirs(NAS_ROOT)

QUOTA_PER_USER = 1 * 1024 * 1024 * 1024  # 1GB 配額
ACTIVE_SESSIONS = {}
SYSTEM_LOGS = []
