import paramiko

def start_mc_lxc():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Starting Minecraft in screen...")
        cmd = 'cd /root/minecraft && screen -dmS mc bash run.sh'
        client.exec_command(cmd)
        
        print("Sent start command.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    start_mc_lxc()
