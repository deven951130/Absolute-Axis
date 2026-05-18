import os
import requests
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from app.utils import get_current_user_obj

router = APIRouter(tags=["smarthome"])

# 預設 Node.js 後端運行的位址 
# 由於 Smart_Home 部署在同一台機器上的 Docker Compose 網路內，通常可用 localhost:3003
SMART_HOME_API_URL = os.getenv("SMART_HOME_API_URL", "http://localhost:3003")

@router.get("/api/smarthome/{series_key}")
def get_smarthome_data(series_key: str, user: dict = Depends(get_current_user_obj)):
    """
    代理前端請求，向 Smart_Home Node.js 後端獲取感測資料
    這樣能避免前端遇到 CORS 問題，並透過 Absolute-Axis 統一身分驗證
    """
    try:
        url = f"{SMART_HOME_API_URL}/api/series/{series_key}/readings?limit=1"
        req = requests.get(url, timeout=3)
        
        if req.status_code == 200:
            data = req.json()
            if data.get("readings") and len(data["readings"]) > 0:
                # 回傳最新的一筆資料
                return data["readings"][0]
            else:
                return {"status": "no_data"}
        
        return {"error": f"Backend returned HTTP {req.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"error": "Smart_Home Backend Offline or Unreachable", "details": str(e)}

@router.post("/api/smarthome/{series_key}/readings")
async def post_smarthome_data(series_key: str, request: Request, x_device_token: str = Header(None)):
    """
    代理硬體請求，讓外部設備(如 ESP32) 可透過 Absolute-Axis 域名直接上傳資料
    將請求原封不動轉發至 Node.js 後端
    """
    if not x_device_token:
        raise HTTPException(status_code=401, detail="Missing x-device-token header")
        
    try:
        body = await request.json()
        url = f"{SMART_HOME_API_URL}/api/series/{series_key}/readings"
        headers = {"x-device-token": x_device_token}
        
        req = requests.post(url, json=body, headers=headers, timeout=5)
        
        # 將 Node.js 的回應轉發回硬體
        return req.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail="Smart_Home Backend Offline")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")
