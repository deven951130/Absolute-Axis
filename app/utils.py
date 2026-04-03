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
    return pwd_context.hash(password)

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

def get_dir_size(start_path='.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
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
        
    return {"username": user.username, "role": user.role, "avatar": user.avatar}

def safe_path(rel: str, username: str):
    base = os.path.abspath(os.path.join(NAS_ROOT, username))
    if not os.path.exists(base): 
        os.makedirs(base)
    p = os.path.abspath(os.path.join(base, rel.lstrip("/")))
    if not p.startswith(base): 
        raise HTTPException(status_code=403)
    return p

def init_db_user():
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == "sparkle").first()
        if not admin_user:
            new_admin = User(
                username="sparkle",
                password_hash=get_password_hash("951130"),
                role="Administrator",
                avatar=""
            )
            db.add(new_admin)
            db.commit()
            print("System DB initialized with default admin 'sparkle'.")
    except Exception as e:
        print(f"Init DB error: {e}")
    finally:
        db.close()
