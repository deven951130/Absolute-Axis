from pydantic import BaseModel
from typing import Optional

class ActionRequest(BaseModel): 
    action: str

class MessageRequest(BaseModel): 
    message: str

class LoginRequest(BaseModel): 
    username: str
    password: str

class DockerControlRequest(BaseModel): 
    container_id: str
    action: str

class ItemRequest(BaseModel): 
    path: str
    name: Optional[str] = None

class CreateUserRequest(BaseModel): 
    username: str
    password: str
    role: str = "Member"

class ProfileUpdate(BaseModel):
    new_name: Optional[str] = None
    new_pass: Optional[str] = None
    avatar: Optional[str] = None

class AdminUserUpdate(BaseModel):
    target_user: str
    new_pass: Optional[str] = None
    new_role: Optional[str] = None

class ShareRequest(BaseModel):
    path: str
    target_user: str

class ToggleRequest(BaseModel):
    path: str

class DeployVMRequest(BaseModel):
    os_internal_name: str
    container_name: str
    cpu_cores: int = 2
    ram_gb: int = 4
