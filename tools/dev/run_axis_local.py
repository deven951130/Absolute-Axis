"""Run the Absolute-Axis checkout locally for UI checks (127.0.0.1:18000).

- BASE_PATH is a temp dir (the app writes axis.db / logs.json / nas there); its static/ is a
  directory junction to the checkout, so edits show up on reload.
- Random JWT secret and admin password (never printed); an admin session token is minted and
  written to axis-local-token.txt for the browser's localStorage.
- DeviceHub points at fake_devicehub.py (127.0.0.1:18080).
- `--bare`: no DeviceHub either, i.e. what a fresh self-hosted install looks like with only the two
  required settings (every optional integration shows "未設定").
"""
import os
import pathlib
import secrets
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
REPO = HERE.parent.parent
base = pathlib.Path(tempfile.mkdtemp(prefix="axis-local-"))
subprocess.run(["cmd", "/c", "mklink", "/J", str(base / "static"), str(REPO / "static")],
               check=True, capture_output=True)
ADMIN = "admin"
BARE = "--bare" in sys.argv
os.environ.update({
    "AXIS_BASE_PATH": str(base),
    "AXIS_JWT_SECRET": secrets.token_hex(32),
    "AXIS_ADMIN_USER": ADMIN,
    "AXIS_ADMIN_PASS": secrets.token_urlsafe(18),
    "DOCKER_HOST": "tcp://127.0.0.1:1",
    "ALLOWED_ORIGINS": "",
})
for k in ("PVE_HOST", "MC_HOST", "DEVICEHUB_URL", "DEVICEHUB_TOKEN", "DEVICEHUB_CONTROL_TOKEN"):
    os.environ.pop(k, None)
if not BARE:
    os.environ.update({
        "DEVICEHUB_URL": "http://127.0.0.1:18080",
        "DEVICEHUB_TOKEN": "fake-read",
        "DEVICEHUB_CONTROL_TOKEN": "fake-control",
    })
os.chdir(REPO)
sys.path.insert(0, str(REPO))

import uvicorn  # noqa: E402

from app.main import app  # noqa: E402
from app.utils import create_access_token  # noqa: E402

(HERE / "axis-local-token.txt").write_text(create_access_token({"sub": ADMIN}))
uvicorn.run(app, host="127.0.0.1", port=18000, log_level="warning")
