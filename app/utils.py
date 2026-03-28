import os
import json
import hashlib
import secrets
from datetime import datetime
from fastapi import HTTPException, Header

from app.config import USER_DB_PATH, ACTIVE_SESSIONS, SYSTEM_LOGS, NAS_ROOT

def get_dir_size(start_path='.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def log_event(user: str, action: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] [{user}] {action}"
    SYSTEM_LOGS.append(entry)
    if len(SYSTEM_LOGS) > 50: 
        SYSTEM_LOGS.pop(0)

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode()).hexdigest()

def read_db():
    if not os.path.exists(USER_DB_PATH):
        s1 = secrets.token_hex(8)
        db = {"sparkle": {"salt": s1, "hash": hash_password("951130", s1), "role": "Administrator", "avatar": ""}}
        with open(USER_DB_PATH, "w") as f: json.dump(db, f)
        return db
    with open(USER_DB_PATH, "r") as f: 
        return json.load(f)

def write_db(db):
    with open(USER_DB_PATH, "w") as f: 
        json.dump(db, f, indent=4)

def get_current_user_obj(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "): 
        raise HTTPException(status_code=401)
    token = authorization.split(" ")[1]
    if token not in ACTIVE_SESSIONS: 
        raise HTTPException(status_code=401)
    username = ACTIVE_SESSIONS[token]
    db = read_db()
    if username not in db: 
        raise HTTPException(status_code=401)
    user_data = db[username]
    user_data["username"] = username
    return user_data

def safe_path(rel: str, username: str):
    base = os.path.abspath(os.path.join(NAS_ROOT, username))
    if not os.path.exists(base): 
        os.makedirs(base)
    p = os.path.abspath(os.path.join(base, rel.lstrip("/")))
    if not p.startswith(base): 
        raise HTTPException(status_code=403)
    return p
