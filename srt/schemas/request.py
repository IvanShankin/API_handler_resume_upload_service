from typing import List

from pydantic import BaseModel, Field, HttpUrl
from srt.config import MAX_CHAR_REQUIREMENTS, MAX_CHAR_RESUME


class RequirementsRequest(BaseModel):
    requirements: str = Field(..., max_length=MAX_CHAR_REQUIREMENTS)

class ResumeRequest(BaseModel):
    resume: str = Field(..., max_length=MAX_CHAR_RESUME)

class StartProcessingRequest(BaseModel):
    requirements_id: int
    resume_id: int
    callback_url: HttpUrl

class DeleteProcessingRequest(BaseModel):
    processings_ids: List[int]

class DeleteRequirementsRequest(BaseModel):
    requirements_ids: List[int]