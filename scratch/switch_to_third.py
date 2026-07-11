import sys
import os
from datetime import datetime

# 確保可以載入 app 模組
sys.path.insert(0, '/app')

from app.routers.minecraft import _deploy_pack_to_lxc, _load_info, _save_info, log_event

def main():
    pack_name = "涟漪之篇0.1.87服务端(优化版本，与当前导入包兼容) (2).zip"
    pack_path = os.path.join("/app/scratch/minecraft_packs", pack_name)
    
    if not os.path.exists(pack_path):
        print(f"ERROR: Cannot find pack at {pack_path}")
        return
        
    info = _load_info()
    current_pack = info.get("active_pack", "") or info.get("server_pack_name", "")
    
    print(f"Starting deployment for: {pack_name}")
    print(f"Current active pack: {current_pack}")
    
    try:
        # 執行切換部署，reset_world 設為 False（還原舊地圖或生成新地圖）
        _deploy_pack_to_lxc(pack_path, current_pack=current_pack, reset_world=False)
        
        info["server_pack_name"] = pack_name
        info["active_pack"] = pack_name
        info["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_info(info)
        
        log_event("sparkle", f"MC_ADMIN: Switched server pack to {pack_name} (via automation script)")
        print("SUCCESS: Switched server pack successfully!")
        
    except Exception as e:
        print(f"ERROR: Switch failed: {e}")

if __name__ == "__main__":
    main()
