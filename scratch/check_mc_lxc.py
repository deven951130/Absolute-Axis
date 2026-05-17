import paramiko

def check_mc_running():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Checking screen sessions...")
        stdin, stdout, stderr = client.exec_command('screen -ls')
        print(stdout.read().decode())
        
        print("Checking java process...")
        stdin, stdout, stderr = client.exec_command('ps aux | grep java')
        print(stdout.read().decode())
        
        print("Checking port 25565...")
        stdin, stdout, stderr = client.exec_command('ss -tuln | grep 25565')
        print(stdout.read().decode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_mc_running()
