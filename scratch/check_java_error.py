import paramiko

def check_java_error():
    pve_ip = "100.124.203.61"
    pve_user = "root"
    pve_pass = "deven951130"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(pve_ip, username=pve_user, password=pve_pass, timeout=10)
        
        print("[*] Running java command directly to capture startup errors...")
        cmd = "pct exec 102 -- bash -c 'cd /root/minecraft && java @user_jvm_args.txt @libraries/net/minecraftforge/forge/1.20.1-47.4.16/unix_args.txt --help'"
        stdin, stdout, stderr = client.exec_command(cmd)
        print("STDOUT:")
        print(stdout.read().decode())
        print("STDERR:")
        print(stderr.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_java_error()
