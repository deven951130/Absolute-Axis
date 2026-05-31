import paramiko
import time

def fix_jvm_args():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("[*] Rewriting user_jvm_args.txt with corrected InitiatingHeapOccupancyPercent option...")
        jvm_args = """-Xmx14G
-Xms14G
-Dforge.readTimeout=300
-XX:+UseG1GC
-XX:+ParallelRefProcEnabled
-XX:MaxGCPauseMillis=200
-XX:+UnlockExperimentalVMOptions
-XX:+DisableExplicitGC
-XX:+AlwaysPreTouch
-XX:G1NewSizePercent=30
-XX:G1MaxNewSizePercent=40
-XX:G1HeapRegionSize=8m
-XX:G1ReservePercent=20
-XX:G1HeapWastePercent=5
-XX:G1MixedGCCountTarget=4
-XX:InitiatingHeapOccupancyPercent=15
-XX:G1MixedGCLiveThresholdPercent=90
-XX:G1RSetUpdatingPauseTimePercent=5
-XX:SurvivorRatio=32
-XX:+PerfDisableSharedMem
-XX:MaxTenuringThreshold=1
"""
        safe_jvm_args = jvm_args.replace("'", "'\\''")
        stdin, stdout, stderr = client.exec_command(f"pct exec 102 -- bash -c \"cat << 'EOF' > /root/minecraft/user_jvm_args.txt\n{safe_jvm_args}\nEOF\"")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("[*] Verifying JVM options by running Java directly...")
        cmd_verify = "pct exec 102 -- bash -c 'cd /root/minecraft && java @user_jvm_args.txt @libraries/net/minecraftforge/forge/1.20.1-47.4.16/unix_args.txt --help'"
        stdin, stdout, stderr = client.exec_command(cmd_verify)
        err = stderr.read().decode().strip()
        if "Error" in err or "Unrecognized VM option" in err:
            print("[-] JVM options verification failed:")
            print(err)
            return
        else:
            print("[+] JVM options verification succeeded!")

        print("[*] Resetting failed status and starting minecraft.service...")
        client.exec_command("pct exec 102 -- systemctl reset-failed minecraft.service")
        client.exec_command("pct exec 102 -- systemctl start minecraft.service")
        
        print("[*] Waiting 5 seconds for initialization...")
        time.sleep(5)
        
        print("=== Minecraft service status ===")
        stdin, stdout, stderr = client.exec_command("pct exec 102 -- systemctl status minecraft.service")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_jvm_args()
