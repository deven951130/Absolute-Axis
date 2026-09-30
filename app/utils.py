import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Header, Depends
import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import NAS_ROOT, JWT_SECRET, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db, User, AuditLog, SessionLocal

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    # Truncate to 72 bytes to avoid bcrypt limit and prevent 500 status
    return pwd_context.verify(plain_password[:72], hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password[:72])

# JWT Auth
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

_QUOTA_CACHE = {}

def get_dir_size(start_path='.'):
    """
    Optimized directory size calculation using os.scandir.
    Includes a 5-second in-memory cache to prevent IO storms.
    """
    now = datetime.now()
    if start_path in _QUOTA_CACHE:
        val, ts = _QUOTA_CACHE[start_path]
        if (now - ts).total_seconds() < 5:
            return val

    total_size = 0
    try:
        with os.scandir(start_path) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False):
                    total_size += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total_size += get_dir_size(entry.path)
    except (PermissionError, OSError):
        pass

    _QUOTA_CACHE[start_path] = (total_size, now)
    return total_size

def log_event(username: str, action: str):
    db: Session = SessionLocal()
    try:
        new_log = AuditLog(username=username, action=action)
        db.add(new_log)
        db.commit()
    except Exception as e:
        print(f"Log error: {e}")
    finally:
        db.close()

def get_current_user_obj(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "): 
        raise HTTPException(status_code=401, detail="Invalid token header")
    token = authorization.split(" ")[1]
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token validation failed")

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
        
    return {"username": user.username, "role": user.role, "avatar": user.avatar, "quota_bytes": user.quota_bytes}

def require_admin(user: dict = Depends(get_current_user_obj)):
    """只允許管理員。用在會影響整台主機或其他使用者的 API（容器、虛擬機、重啟、VM 帳號）。

    前端隱藏按鈕不算保護：一般會員只要帶自己的 token 直接呼叫 API 就能執行，所以一定要在後端檢查。
    """
    if user.get("role") not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="需要管理員權限")
    return user


def get_current_user_obj_optional(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "): 
        return None
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            return None
        return {"username": user.username, "role": user.role, "avatar": user.avatar, "quota_bytes": user.quota_bytes}
    except jwt.PyJWTError:
        return None

def safe_path(rel: str, username: str):
    base = os.path.abspath(os.path.join(NAS_ROOT, username))
    if not os.path.exists(base): 
        os.makedirs(base)
    p = os.path.abspath(os.path.join(base, rel.lstrip("/")))
    if not p.startswith(base): 
        raise HTTPException(status_code=403)
    return p

def init_db_user():
    """第一次啟動時建立管理員帳號。

    只在資料庫裡「一個管理員都沒有」時才建立：名稱來自 AXIS_ADMIN_USER（預設 admin），
    密碼來自 AXIS_ADMIN_PASS。已經有管理員（例如舊版建立的 sparkle，或改過名稱的管理員）就不動，
    所以既有的站台升級後不會多出第二個管理員。
    """
    from app.naming import valid_username, USERNAME_RULE

    db = SessionLocal()
    try:
        if db.query(User).filter(User.role.in_(("admin", "Administrator"))).first():
            return
        username = (os.getenv("AXIS_ADMIN_USER") or "admin").strip()
        admin_pass = (os.getenv("AXIS_ADMIN_PASS") or "").strip()
        if admin_pass.startswith("<") and admin_pass.endswith(">"):
            admin_pass = ""  # 還是範本裡的「<請填入…>」：當作沒填，不能拿公開的字串當管理員密碼
        if not admin_pass:
            print("WARNING: AXIS_ADMIN_PASS not set. Skipping default admin creation.")
            print("Set AXIS_ADMIN_PASS in .env to initialize the admin account.")
            return
        if not valid_username(username):
            print(f"WARNING: AXIS_ADMIN_USER「{username}」不符合規則（{USERNAME_RULE}），未建立管理員。")
            return
        if db.query(User).filter(User.username == username).first():
            # 同名的一般帳號不自動升成管理員，避免把別人的帳號變成管理員
            print(f"WARNING: 帳號「{username}」已存在但不是管理員，未建立管理員；請改用其他 AXIS_ADMIN_USER。")
            return
        new_admin = User(
            username=username,
            password_hash=get_password_hash(admin_pass),
            role="Administrator",
            avatar=""
        )
        db.add(new_admin)
        db.commit()
        print(f"System DB initialized with admin '{username}'.")
    except Exception as e:
        print(f"Init DB error: {e}")
    finally:
        db.close()
