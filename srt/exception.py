from fastapi import HTTPException, status
from srt.config import LOGIN_BLOCK_TIME

class InvalidFileFormat(HTTPException):
    def __init__(self, allowed_extensions):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Неподдерживаемый формат файла. Разрешены: {', '.join(allowed_extensions)}')

class CorruptedFile(HTTPException):
    def __init__(self, file_name: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Повреждённый Файл: {file_name}')

class EmptyFileException(HTTPException):
    def __init__(self, file_name: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Файл {file_name} пуст!')

class InvalidTokenException(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

class TokenExpiredException(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")

class InvalidCredentialsException(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

class NoRights(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN,detail="Нет прав на получение этого ресурса!")

class NotFoundData(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Запрашиваемые данные не найдены")

class UserAlreadyRegistered(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_409_CONFLICT,detail="username already registered")

class TooManyCharacters(HTTPException):
    def __init__(self, max_length_char: int):
        super().__init__(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,detail="Слишком большое количество символов. максимум: {}")

class ToManyAttemptsEnter(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS,detail=f"Too many username attempts. Please try again in"
                                                                      f" {LOGIN_BLOCK_TIME.seconds//60} minutes")


