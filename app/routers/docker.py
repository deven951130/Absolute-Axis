import json
import subprocess
from fastapi import APIRouter, Depends

from app.models import DockerControlRequest
from app.utils import get_current_user_obj, log_event

router = APIRouter(prefix="/api/docker", tags=["docker"])

@router.get("/containers")
def list_containers(user: dict = Depends(get_current_user_obj)):
    try:
        out = subprocess.check_output("docker ps -a --format '{{json .}}'", shell=True).decode()
        return [json.loads(l) for l in out.strip().split('\n') if l]
    except: 
        return []

@router.post("/control")
def control_docker(req: DockerControlRequest, user: dict = Depends(get_current_user_obj)):
    subprocess.run(["docker", req.action, req.container_id])
    log_event(user["username"], f"Virtual Center: {req.action.upper()} container {req.container_id[:8]}")
    return {"status": "ok"}
