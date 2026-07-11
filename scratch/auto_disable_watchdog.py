import paramiko
import time

PVE_IP = '192.168.0.138'
PVE_USER = 'root'
PVE_PASS = 'deven951130'
VMID = '102'

def run(client, cmd):
    print(f"[Exec]: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out: print(f"  OUT: {out}")
    if err: print(f"  ERR: {err}")
    return out, err

def main():
    print("==================================================")
    print("Auto Disable Minecraft Watchdog Tool")
    print("==================================================")
    print("Waiting for PVE SSH to come online...")
    
    attempt = 1
    client = None
    while True:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            c.connect(PVE_IP, username=PVE_USER, password=PVE_PASS, timeout=2)
            print(f"\n[Attempt #{attempt}] Connected successfully!")
            client = c
            break
        except Exception as e:
            print(f"[Attempt #{attempt}] Connecting... {type(e).__name__}", end='\r')
            c.close()
            attempt += 1
            time.sleep(1)

    try:
        # 1. 停止容器
        print("\n--- Step 1: Stopping LXC 102 ---")
        run(client, f"pct stop {VMID}")
        time.sleep(2)

        # 2. 鎖定自啟動為 0（先確保安全，等我們修改好再啟動）
        run(client, f"sed -i 's/onboot: 1/onboot: 0/g' /etc/pve/lxc/{VMID}.conf")

        # 3. 掛載磁碟
        print("\n--- Step 2: Mounting LXC 102 rootfs ---")
        run(client, f"pct mount {VMID}")

        # 4. 修改 max-tick-time=-1 停用 Minecraft 內置 watchdog
        print("\n--- Step 3: Modifying server.properties to disable watchdog ---")
        properties_path = f"/var/lib/lxc/{VMID}/rootfs/root/minecraft/server.properties"
        
        # 讀取原本的 max-tick-time 值
        run(client, f"grep max-tick-time {properties_path}")
        
        # 使用 sed 將其改為 -1
        # 如果不存在 max-tick-time 則在末尾加上，如果存在則替換
        modify_cmd = (
            f"if grep -q 'max-tick-time=' {properties_path}; then "
            f"  sed -i 's/max-tick-time=.*/max-tick-time=-1/g' {properties_path}; "
            f"else "
            f"  echo 'max-tick-time=-1' >> {properties_path}; "
            f"fi"
        )
        run(client, modify_cmd)
        
        # 驗證修改
        run(client, f"grep max-tick-time {properties_path}")

        # 5. 卸載磁碟
        print("\n--- Step 4: Unmounting rootfs ---")
        run(client, f"pct unmount {VMID}")

        # 6. 恢復開機自啟動為 1
        print("\n--- Step 5: Restoring onboot to 1 ---")
        run(client, f"sed -i 's/onboot: 0/onboot: 1/g' /etc/pve/lxc/{VMID}.conf")

        # 7. 手動啟動容器進行最終載入
        print("\n--- Step 6: Starting container to verify ---")
        run(client, f"pct start {VMID}")

        print("\n==================================================")
        print("SUCCESS: Minecraft Watchdog disabled (max-tick-time=-1)!")
        print("==================================================")

    except Exception as e:
        print(f"Error during modification: {e}")
    finally:
        client.close()

if __name__ == '__main__':
    main()
