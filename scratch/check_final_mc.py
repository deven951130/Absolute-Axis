import paramiko

def check_mc_status():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("--- Checking Network Port 25565 ---")
        stdin, stdout, stderr = client.exec_command('ss -tuln | grep 25565')
        print(stdout.read().decode().strip() or "Port not listening yet.")
        
        print("\n--- Checking Java Processes ---")
        stdin, stdout, stderr = client.exec_command('ps aux | grep java | grep -v grep')
        print(stdout.read().decode().strip() or "No Java process found.")
        
        print("\n--- Checking Latest Log (tail -n 15) ---")
        stdin, stdout, stderr = client.exec_command('tail -n 15 /root/minecraft/logs/latest.log 2>/dev/null')
        log_output = stdout.read().decode().strip()
        print(log_output if log_output else "No latest.log found yet.")
        
        print("\n--- Checking screen output ---")
        # dump the screen output using hardcopy
        client.exec_command('screen -S mc -X hardcopy /root/screen_dump.txt')
        import time
        time.sleep(1)
        stdin, stdout, stderr = client.exec_command('cat /root/screen_dump.txt 2>/dev/null')
        screen_output = stdout.read().decode().strip()
        print(screen_output[-500:] if screen_output else "No screen dump available.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_mc_status()
