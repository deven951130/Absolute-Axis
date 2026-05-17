import paramiko
import time

def reboot_and_fix():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # 1. Connect to Proxmox Host to hard reset the VM
        print("Connecting to Proxmox...")
        client.connect('192.168.0.138', username='root', password='deven951130', timeout=10)
        
        print("Stopping VM 100...")
        client.exec_command('qm stop 100')
        time.sleep(3)
        print("Starting VM 100...")
        client.exec_command('qm start 100')
        client.close()
        
        print("Waiting 45 seconds for VM to boot up...")
        time.sleep(45)
        
        # 2. Connect to VM to lower the RAM allocation
        vm_client = paramiko.SSHClient()
        vm_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print("Connecting to VM...")
        vm_client.connect('192.168.0.159', username='sparkle', password='951130', timeout=15)
        
        print("Fixing user_jvm_args.txt to use 8G instead of 10G (to prevent OOM crash)...")
        # Remove the 10G lines and append 8G
        cmd = """
        cd /home/sparkle/Absolute-Axis/minecraft-data
        sed -i '/-Xmx10G/d' user_jvm_args.txt
        sed -i '/-Xms10G/d' user_jvm_args.txt
        echo "-Xmx8G" >> user_jvm_args.txt
        echo "-Xms8G" >> user_jvm_args.txt
        """
        vm_client.exec_command(cmd)
        
        print("Restarting docker container...")
        cmd_restart = 'echo "951130" | sudo -S docker start axis-mc'
        vm_client.exec_command(cmd_restart)
        
        print("VM Rebooted and Minecraft Memory Reduced to 8GB to prevent crash.")
        vm_client.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    reboot_and_fix()
