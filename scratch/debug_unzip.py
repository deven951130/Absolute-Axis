import paramiko

def debug_unzip_linux():
    lxc_ip = '192.168.0.108'
    zip_path = r"c:\Users\tony9\Downloads\test area\【⭐服务端⭐】(开服用，若不清楚请下载客户端\香草纪元：食旅纪行 Server2.6.1.zip"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Re-uploading server.zip just to check...")
        sftp = client.open_sftp()
        sftp.put(zip_path, '/root/server.zip')
        sftp.close()
        
        print("Checking unzip -l inside Linux...")
        stdin, stdout, stderr = client.exec_command('unzip -l /root/server.zip | tail -n 20')
        print(stdout.read().decode())
        
        print("Trying to unzip specifically run.sh...")
        client.exec_command('mkdir -p /root/test_unzip && cd /root/test_unzip && unzip /root/server.zip run.sh server.jar')
        import time
        time.sleep(2)
        stdin, stdout, stderr = client.exec_command('ls -la /root/test_unzip')
        print(stdout.read().decode())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    debug_unzip_linux()
