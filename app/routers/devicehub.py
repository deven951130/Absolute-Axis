"""DeviceHub 模組（唯讀）。

Absolute-Axis 是主入口，DeviceHub 是設備／電源管理模組（DeviceHub repo:
docs/spec/integration-api.md、architecture AD-10）。

- 只由 Axis 後端呼叫 DeviceHub 的唯讀 API；DEVICEHUB_TOKEN 不會送到瀏覽器。
- 只給 Administrator 看。
- 這裡沒有任何控制功能：控制按鈕只連到 DeviceHub 自己的網址（僅 Tailscale 可用）。
"""
import os
import time

import requests
from fastapi import APIRouter, Depends, HTTPException

from app.utils import get_current_user_obj

router = APIRouter(tags=["devicehub"])

DEVICEHUB_URL = os.getenv("DEVICEHUB_URL", "http://192.168.0.50:8080").rstrip("/")
DEVICEHUB_TOKEN = os.getenv("DEVICEHUB_TOKEN", "")
_CACHE_SECONDS = 5  # 多個分頁同時開著也只打 DeviceHub 一次
_cache = {"ts": 0.0, "data": None}


@router.get("/api/devicehub/summary")
def devicehub_summary(user: dict = Depends(get_current_user_obj)):
    if user.get("role") not in ("admin", "Administrator"):
        raise HTTPException(status_code=403, detail="Administrators only")
    if not DEVICEHUB_TOKEN:
        return {"configured": False}

    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < _CACHE_SECONDS:
        return _cache["data"]
    try:
        r = requests.get(f"{DEVICEHUB_URL}/api/v1/summary",
                         headers={"Authorization": f"Bearer {DEVICEHUB_TOKEN}"}, timeout=4)
    except requests.RequestException:
        return {"configured": True, "error": "DeviceHub 無法連線"}
    if r.status_code != 200:
        # 不轉送 DeviceHub 的錯誤內容，只給狀態碼
        return {"configured": True, "error": f"DeviceHub 回應 HTTP {r.status_code}"}
    data = {"configured": True, "error": None, **r.json()}
    _cache.update(ts=now, data=data)
    return data
