import os
import subprocess

print("Pinging VM Tailscale IP 100.118.53.34...")
res = subprocess.run(["ping", "-n", "2", "100.118.53.34"], capture_output=True, text=True)
print(res.stdout)
