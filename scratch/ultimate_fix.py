import paramiko
import os
import time

def fix_all_and_upload():
    lxc_ip = '192.168.0.108'
    zip_path = r"c:\Users\tony9\Downloads\test area\【⭐服务端⭐】(开服用，若不清楚请下载客户端\香草纪元：食旅纪行 Server2.6.1.zip"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Fixing DNS...")
        client.exec_command('echo "nameserver 8.8.8.8" > /etc/resolv.conf')
        
        print("Installing tools...")
        stdin, stdout, stderr = client.exec_command('apt-get update && apt-get install -y unzip screen openjdk-17-jre-headless')
        exit_status = stdout.channel.recv_exit_status()
        print(stdout.read().decode(errors='ignore'))
        
        print("Cleaning up directory...")
        client.exec_command('rm -rf /root/minecraft; mkdir -p /root/minecraft')
        
        print("Uploading server.zip from Windows to LXC...")
        sftp = client.open_sftp()
        sftp.put(zip_path, '/root/minecraft/server.zip')
        sftp.close()
        
        print("Unzipping and starting...")
        cmd_start = """
        cd /root/minecraft
        unzip -q -o server.zip
        rm server.zip
        if [ -d "香草紀元：食旅紀行 Server2.6.1" ]; then
           mv "香草紀元：食旅紀行 Server2.6.1"/* .
        fi
        if [ -d "香草纪元：食旅纪行 Server2.6.1" ]; then
           mv "香草纪元：食旅纪行 Server2.6.1"/* .
        fi
        
        chmod +x run.sh
        echo "eula=true" > eula.txt
        echo "-Xmx9G" > user_jvm_args.txt
        echo "-Xms9G" >> user_jvm_args.txt
        
        screen -dmS mc bash run.sh
        """
        client.exec_command(cmd_start)
        print("Started! Checking Java processes...")
        time.sleep(5)
        stdin, stdout, stderr = client.exec_command('ps aux | grep java | grep -v grep')
        print("Java status:", stdout.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_all_and_upload()
