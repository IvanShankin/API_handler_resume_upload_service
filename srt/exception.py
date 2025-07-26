from fastapi import HTTPException, status
from srt.config import LOGIN_BLOCK_TIME

class InvalidTokenException(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

class TokenExpiredException(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")

class InvalidCredentialsException(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

class UserAlreadyRegistered(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_409_CONFLICT,detail="username already registered")

class UserNotFound(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN,detail="User not found")

class ToManyAttemptsEnter(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS,detail=f"Too many username attempts. Please try again in"
                                                                      f" {LOGIN_BLOCK_TIME.seconds//60} minutes")