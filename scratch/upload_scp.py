import paramiko
from scp import SCPClient
import time

def progress(filename, size, sent):
    if sent % (size // 10 + 1) == 0 or sent == size:
        print(f"{filename}: {sent}/{size}")

def upload_and_start_scp():
    lxc_ip = '192.168.0.108'
    zip_path = r"e:\absolute axis\scratch\mc_temp.zip"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to LXC...")
        client.connect(lxc_ip, username='root', password='951130', timeout=30)
        
        print("Uploading via SCP...")
        with SCPClient(client.get_transport(), progress=progress) as scp:
            scp.put(zip_path, '/root/minecraft/server.zip')
            
        print("Unzipping...")
        cmd_start = """
        cd /root/minecraft
        unzip -q -o server.zip
        rm server.zip
        chmod +x run.sh
        echo "eula=true" > eula.txt
        echo "-Xmx9G" > user_jvm_args.txt
        echo "-Xms9G" >> user_jvm_args.txt
        screen -dmS mc bash run.sh
        """
        stdin, stdout, stderr = client.exec_command(cmd_start)
        print("Unzip stdout:", stdout.read().decode())
        print("Unzip stderr:", stderr.read().decode())
        
        print("Checking processes...")
        time.sleep(5)
        stdin, stdout, stderr = client.exec_command('ps aux | grep java | grep -v grep')
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    upload_and_start_scp()
