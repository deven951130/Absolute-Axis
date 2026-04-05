import os
import glob
from fastapi import APIRouter, Depends, HTTPException
from app.utils import get_current_user_obj, log_event

router = APIRouter(tags=["thermal"])

HWMON_ROOT = "/sys/class/hwmon"

@router.get("/api/thermal/status")
def get_thermal_status(user: dict = Depends(get_current_user_obj)):
    """
    掃描系統中的 hwmon 感測器，獲取溫度與風扇狀態。
    """
    if not os.path.exists(HWMON_ROOT):
        return {"sensors": [], "fans": [], "error": "Hardware monitoring not available on this platform."}

    sensors = []
    fans = []
    
    # 遍歷所有 hwmon 節點
    for hw_path in glob.glob(f"{HWMON_ROOT}/hwmon*"):
        try:
            with open(f"{hw_path}/name", "r") as f:
                hw_name = f.read().strip()
        except:
            hw_name = "unknown"

        # 1. 抓取溫度 (temp*_input)
        for temp_file in glob.glob(f"{hw_path}/temp*_input"):
            try:
                base = temp_file.replace("_input", "")
                label_file = f"{base}_label"
                label = "Temperature"
                if os.path.exists(label_file):
                    with open(label_file, "r") as f: label = f.read().strip()
                
                with open(temp_file, "r") as f:
                    val = int(f.read().strip()) / 1000.0
                
                sensors.append({
                    "id": os.path.basename(temp_file),
                    "name": f"{hw_name} ({label})",
                    "value": round(val, 1)
                })
            except: continue

        # 2. 抓取風扇 (fan*_input) 與對應的 PWM
        for fan_file in glob.glob(f"{hw_path}/fan*_input"):
            try:
                fan_id = os.path.basename(fan_file).replace("_input", "")
                idx = fan_id.replace("fan", "")
                
                # 讀取轉速
                with open(fan_file, "r") as f:
                    rpm = int(f.read().strip())
                
                pwm_val = 0
                pwm_mode = 2 # 預設自動 (2)
                pwm_path = f"{hw_path}/pwm{idx}"
                
                if os.path.exists(pwm_path):
                    with open(pwm_path, "r") as f:
                        pwm_val = int(f.read().strip())
                    
                    mode_path = f"{pwm_path}_enable"
                    if os.path.exists(mode_path):
                        with open(mode_path, "r") as f:
                            pwm_mode = int(f.read().strip())

                fans.append({
                    "id": fan_id,
                    "hw": hw_name,
                    "path": hw_path,
                    "index": idx,
                    "rpm": rpm,
                    "pwm": pwm_val,
                    "mode": "manual" if pwm_mode == 1 else "auto"
                })
            except: continue

    return {"sensors": sensors, "fans": fans}

@router.post("/api/thermal/set")
def set_fan_speed(data: dict, user: dict = Depends(get_current_user_obj)):
    """
    設定特定風扇的 PWM 轉速。
    data 格式: {"path": "/sys/class/hwmon/hwmonX", "index": "1", "value": 150, "mode": "manual"}
    """
    hw_path = data.get("path")
    idx = data.get("index")
    val = data.get("value")
    mode = data.get("mode", "manual")

    if not hw_path or not idx:
        raise HTTPException(status_code=400, detail="Missing parameters")

    pwm_path = f"{hw_path}/pwm{idx}"
    mode_path = f"{pwm_path}_enable"

    try:
        # 1. 切換模式 (1=manual, 2=auto)
        m_val = "1" if mode == "manual" else "2"
        if os.path.exists(mode_path):
            os.system(f"echo {m_val} | sudo tee {mode_path}")
        
        # 2. 設定數值 (僅在手動模式下有效，但寫入通常不會報錯)
        if mode == "manual" and val is not None:
            val = max(0, min(255, int(val)))
            os.system(f"echo {val} | sudo tee {pwm_path}")
            
        log_event(user["username"], f"THERMAL: Set fan {idx} on {os.path.basename(hw_path)} to {mode} (PWM: {val})")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set PWM: {str(e)}")
