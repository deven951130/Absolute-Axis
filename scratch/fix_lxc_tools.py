import paramiko

def fix_lxc_tools():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Installing missing tools (unzip, screen) inside LXC...")
        # 直接執行 apt 安裝
        cmd = "apt-get update && apt-get install -y unzip screen openjdk-17-jre-headless"
        stdin, stdout, stderr = client.exec_command(cmd)
        print(stdout.read().decode())
        
        print("Now re-running the extraction and start script...")
        cmd_start = """
        cd /root/minecraft
        unzip -o server.zip
        rm server.zip
        # 處理資料夾嵌套
        if [ -d "香草紀元：食旅紀行 Server2.6.1" ]; then
           mv "香草紀元：食旅紀行 Server2.6.1"/* .
        fi
        chmod +x run.sh
        echo "eula=true" > eula.txt
        screen -dmS mc bash run.sh
        """
        client.exec_command(cmd_start)
        print("Finished.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    fix_lxc_tools()
