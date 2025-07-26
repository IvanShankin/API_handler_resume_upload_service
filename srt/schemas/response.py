from datetime import datetime
from pydantic import BaseModel, EmailStr

class UserOut(BaseModel):
    user_id: int