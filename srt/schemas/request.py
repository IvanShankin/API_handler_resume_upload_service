from pydantic import BaseModel, EmailStr

class RequirementsRequest(BaseModel):
    requirements: str


class ResumeRequest(BaseModel):
    resume: str

class StartProcessingRequest(BaseModel):
    requirements_id: int
    resume_id: int