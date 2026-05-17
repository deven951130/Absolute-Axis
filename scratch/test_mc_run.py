import paramiko

def test_mc_run():
    lxc_ip = '192.168.0.108'
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Checking java version...")
        stdin, stdout, stderr = client.exec_command('java -version')
        print("STDOUT:", stdout.read().decode().strip())
        print("STDERR:", stderr.read().decode().strip())
        
        print("\nChecking file layout...")
        stdin, stdout, stderr = client.exec_command('ls -la /root/minecraft/')
        print(stdout.read().decode().strip())
        
        print("\nRunning run.sh directly to capture error...")
        stdin, stdout, stderr = client.exec_command('cd /root/minecraft/ && bash run.sh', timeout=15)
        
        import time
        time.sleep(5) # wait for error to appear
        
        try:
            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            if out: print("STDOUT:", out)
            if err: print("STDERR:", err)
        except Exception as read_e:
            print("Process might be running successfully in foreground:", read_e)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    test_mc_run()
