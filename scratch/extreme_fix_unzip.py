import paramiko

def extreme_fix_unzip():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Checking where the files are...")
        # 也許解壓到了子目錄？
        stdin, stdout, stderr = client.exec_command('find /root/minecraft -maxdepth 2')
        print(stdout.read().decode())
        
        # 強制將所有檔案從子目錄移動到 /root/minecraft
        cmd = "cd /root/minecraft && mv */* . 2>/dev/null; mv * . 2>/dev/null; chmod +x run.sh"
        client.exec_command(cmd)
        
        print("Final attempt to start...")
        client.exec_command('cd /root/minecraft && screen -dmS mc bash run.sh')
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    extreme_fix_unzip()
