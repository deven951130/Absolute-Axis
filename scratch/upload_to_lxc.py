import paramiko
import os
import time

def upload_and_start():
    zip_path = r"c:\Users\tony9\Downloads\test area\【⭐服务端⭐】(开服用，若不清楚请下载客户端\香草纪元：食旅纪行 Server2.6.1.zip"
    lxc_ip = '192.168.0.108'
    
    if not os.path.exists(zip_path):
        print(f"File not found: {zip_path}")
        return

    print("Connecting to LXC 102...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=15)
        
        print("Uploading server.zip to LXC 102 (This will take a minute or two)...")
        sftp = client.open_sftp()
        sftp.put(zip_path, '/root/server.zip')
        sftp.close()
        
        print("Unzipping...")
        cmd_setup = """
        mkdir -p /root/minecraft
        cd /root/minecraft
        unzip -q -o /root/server.zip
        rm /root/server.zip
        
        # Add Memory Limits to JVM Args
        echo "-Xmx9G" >> user_jvm_args.txt
        echo "-Xms9G" >> user_jvm_args.txt
        
        # Agree to EULA
        echo "eula=true" > eula.txt
        
        # Start Minecraft in screen
        screen -dmS mc bash run.sh
        """
        stdin, stdout, stderr = client.exec_command(cmd_setup)
        exit_status = stdout.channel.recv_exit_status()
        print("Server has been started in screen 'mc'!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    upload_and_start()
