import paramiko

def run_cmd_on_vm(command):
    pve_client = paramiko.SSHClient()
    pve_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pve_client.connect('100.124.203.61', username='root', password='deven951130', timeout=10)
    
    vm_ip = '192.168.0.159'
    vm_user = 'sparkle'
    vm_pass = '951130'
    
    transport = pve_client.get_transport()
    channel = transport.open_channel("direct-tcpip", (vm_ip, 22), ('100.124.203.61', 22))
    
    vm_client = paramiko.SSHClient()
    vm_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    vm_client.connect(vm_ip, username=vm_user, password=vm_pass, sock=channel)
    
    stdin, stdout, stderr = vm_client.exec_command(command)
    out = stdout.read().decode()
    err = stderr.read().decode()
    
    vm_client.close()
    pve_client.close()
    return out, err

# 1. Create Dockerfile on VM
dockerfile_content = """FROM python:3.11-slim
RUN apt-get update && apt-get install -y iputils-ping curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
"""
print("--- Creating Dockerfile on VM ---")
run_cmd_on_vm(f"echo '{dockerfile_content}' > /home/sparkle/Absolute-Axis/Dockerfile")

# 2. Update .env on VM
# We use the token from local .env
token = "eyJhIjoiOGZkYmYxZGE5OWU5YmM0NzY2OGY1YjZjNWQ3YjZkMzciLCJ0IjoiMWYzMDI5MzktMjcxZC00NTBmLTljNDktMmFiNmU5NDhlZDQ0IiwicyI6IjFzNzRNRXczeUZ4WXNPK0VHSkxqUDBtaDIzUU4xeFBSOWhyVXFJUC8wb2s9In0="
env_content = f"""HOST_IP=0.0.0.0
GITHUB_TOKEN=your_github_token_here
CLOUDFLARE_TUNNEL_TOKEN={token}
"""
print("--- Updating .env on VM ---")
run_cmd_on_vm(f"echo '{env_content}' > /home/sparkle/Absolute-Axis/.env")

# 3. Start containers
print("--- Starting containers on VM ---")
out, err = run_cmd_on_vm("cd /home/sparkle/Absolute-Axis && docker compose up -d --build")
print(out)
if err: print("ERR:", err)

# 4. Verify
print("\n--- Verifying container status ---")
out, err = run_cmd_on_vm("docker ps")
print(out)
