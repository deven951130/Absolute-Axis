import paramiko
import time

def deploy_to_lxc():
    px_ip = '192.168.0.138'
    px_user = 'root'
    px_pass = 'deven951130'
    lxc_ip = '192.168.0.108'
    
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    
    # Connect to VM 100 to copy file to LXC
    vm_client = paramiko.SSHClient()
    vm_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("Connecting to VM 100 to install sshpass...")
        vm_client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
        vm_client.exec_command(f'echo "{vm_pass}" | sudo -S apt-get install -y sshpass')
        time.sleep(2)
        
        print("Transferring server.zip from VM 100 to LXC 102...")
        cmd_transfer = f"sshpass -p '951130' scp -o StrictHostKeyChecking=no /home/sparkle/Absolute-Axis/minecraft-data/server.zip root@{lxc_ip}:/root/server.zip"
        stdin, stdout, stderr = vm_client.exec_command(cmd_transfer)
        exit_status = stdout.channel.recv_exit_status()
        print("Transfer result:", stdout.read().decode())
        if stderr.read().decode():
            print("Transfer stderr:", stderr.read().decode())
        vm_client.close()
        
        # Connect to LXC 102 to unzip and start
        print("Connecting to LXC 102...")
        lxc_client = paramiko.SSHClient()
        lxc_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        lxc_client.connect(lxc_ip, username='root', password='951130', timeout=10)
        
        print("Unzipping and setting up Minecraft on LXC 102...")
        cmd_setup = """
        cd /root
        mkdir -p minecraft
        cd minecraft
        unzip -q -o /root/server.zip
        
        # Add Memory Limits to JVM Args
        echo "-Xmx9G" >> user_jvm_args.txt
        echo "-Xms9G" >> user_jvm_args.txt
        
        # Start Minecraft in a screen session
        screen -dmS mc bash run.sh
        """
        stdin, stdout, stderr = lxc_client.exec_command(cmd_setup)
        exit_status = stdout.channel.recv_exit_status()
        print("Setup complete. Server is starting.")
        lxc_client.close()
        
        # Finally, update Absolute-Axis code to point to new IP
        print("Updating Absolute-Axis backend to monitor new IP...")
        vm_client = paramiko.SSHClient()
        vm_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        vm_client.connect(vm_ip, username=vm_user, password=vm_pass, timeout=10)
        
        # Replace 127.0.0.1 with 192.168.0.108 in system.py
        cmd_update_code = """
        cd /home/sparkle/Absolute-Axis
        sed -i 's/"127.0.0.1", 25565/"192.168.0.108", 25565/g' app/routers/system.py
        echo "951130" | sudo -S docker restart axis-server
        """
        stdin, stdout, stderr = vm_client.exec_command(cmd_update_code)
        exit_status = stdout.channel.recv_exit_status()
        print("Absolute-Axis updated and restarted.")
        vm_client.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    deploy_to_lxc()
