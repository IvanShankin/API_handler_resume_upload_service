from datetime import datetime
from pydantic import BaseModel, EmailStr

class UserOut(BaseModel):
    user_id: int

class RequirementsOut(BaseModel):
    requirements_id: int

class ResumeOut(BaseModel):
    resume_id: int

class StartProcessingOut(BaseModel):
    status: str

class IsDeleteOut(BaseModel):
    is_deleted: bool