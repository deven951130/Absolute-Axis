import paramiko
import os

def final_manual_unzip():
    lxc_ip = '192.168.0.108'
    zip_path = r"c:\Users\tony9\Downloads\test area\【⭐服务端⭐】(开服用，若不清楚请下载客户端\香草纪元：食旅纪行 Server2.6.1.zip"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Cleaning /root/minecraft...")
        client.exec_command('rm -rf /root/minecraft; mkdir -p /root/minecraft')
        
        print("Re-uploading and unzipping using absolute path...")
        sftp = client.open_sftp()
        sftp.put(zip_path, '/root/minecraft/server.zip')
        sftp.close()
        
        # 使用更簡單的解壓指令，直接解壓到當前目錄
        cmd = """
        cd /root/minecraft
        unzip -o server.zip
        rm server.zip
        # 處理可能的層級
        if [ -d "香草紀元：食旅紀行 Server2.6.1" ]; then
           mv "香草紀元：食旅紀行 Server2.6.1"/* .
        fi
        chmod +x run.sh
        echo "eula=true" > eula.txt
        echo "-Xmx9G" >> user_jvm_args.txt
        echo "-Xms9G" >> user_jvm_args.txt
        screen -dmS mc bash run.sh
        """
        stdin, stdout, stderr = client.exec_command(cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    final_manual_unzip()
