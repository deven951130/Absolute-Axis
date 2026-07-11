import paramiko
import time

def run_cmd(client, cmd):
    print(f"[Exec]: {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(f"STDOUT:\n{out}")
    if err:
        print(f"STDERR:\n{err}")
    return out, err

def fix_jvm_args():
    px_ip = '192.168.0.138'
    px_user = 'root'
    px_pass = 'deven951130'
    vmid = '102'
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("Connecting to Proxmox Host...")
        client.connect(px_ip, username=px_user, password=px_pass, timeout=10)
        print("Connected successfully!")
        
        # 1. 停止容器
        print("\n--- Step 1: Stopping LXC 102 ---")
        run_cmd(client, f'pct stop {vmid}')
        
        # 2. 掛載容器
        print("\n--- Step 2: Running pct mount ---")
        run_cmd(client, f'pct mount {vmid}')
        
        # 3. 使用 cat << 'EOF' 寫入 JVM 參數，避免 printf 參數轉義錯誤
        jvm_path = f'/var/lib/lxc/{vmid}/rootfs/root/minecraft/user_jvm_args.txt'
        print("\n--- Step 3: Writing optimized JVM args via EOF ---")
        optimized_jvm_args = (
            "-Xms4G\n"
            "-Xmx12G\n"
            "-XX:+UseG1GC\n"
            "-XX:+ParallelRefProcEnabled\n"
            "-XX:MaxGCPauseMillis=200\n"
            "-XX:+UnlockExperimentalVMOptions\n"
            "-XX:+DisableExplicitGC\n"
            "-XX:+AlwaysPreTouch\n"
            "-XX:G1NewSizePercent=30\n"
            "-XX:G1MaxNewSizePercent=40\n"
            "-XX:G1HeapRegionSize=8M\n"
            "-XX:G1ReservePercent=20\n"
            "-XX:G1HeapWastePercent=5\n"
            "-XX:G1MixedGCCountTarget=4\n"
            "-XX:InitiatingHeapOccupancyPercent=15\n"
            "-XX:G1MixedGCLiveThresholdPercent=90\n"
            "-XX:G1RSetUpdatingPauseTimePercent=5\n"
            "-XX:SurvivorRatio=32\n"
            "-XX:+PerfDisableSharedMem\n"
            "-XX:MaxTenuringThreshold=1"
        )
        
        # 透過 SSH 使用 Here Document 寫入
        cmd_write = (
            f"cat << 'EOF' > {jvm_path}\n"
            f"{optimized_jvm_args}\n"
            f"EOF"
        )
        run_cmd(client, cmd_write)
        
        # 驗證寫入
        print("\n--- Step 4: Verifying user_jvm_args.txt content ---")
        run_cmd(client, f'cat {jvm_path}')
        
        # 4. 卸載容器
        print("\n--- Step 5: Running pct unmount ---")
        run_cmd(client, f'pct unmount {vmid}')
        
        # 5. 啟動容器
        print("\n--- Step 6: Starting LXC 102 ---")
        run_cmd(client, f'pct start {vmid}')
        print("\nLXC 102 successfully configured and started!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == '__main__':
    fix_jvm_args()
