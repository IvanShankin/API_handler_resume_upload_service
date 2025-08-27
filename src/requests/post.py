import os
import pymupdf as fitz

from docx import Document
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv

from redis import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends
from fastapi import UploadFile, File

from src.access import get_current_user
from src.dependencies import producer, get_redis
from src.schemas.request import RequirementsRequest, ResumeRequest, StartProcessingRequest
from src.schemas.response import RequirementsOut, ResumeOut, StartProcessingOut
from src.database.models import User, Requirements, Resume, Processing
from src.database.database import get_db
from src.config import STORAGE_TIME_REQUIREMENTS, STORAGE_TIME_RESUME, ALLOWED_EXTENSIONS, \
    MAX_CHAR_RESUME, MAX_CHAR_REQUIREMENTS, KEY_NEW_REQUEST, KEY_NEW_RESUME, KEY_NEW_REQUIREMENTS, \
    RATE_LIMIT_START_PROCESSING_IN_MINUTES, START_PROCESSING_BLOCK_TIME
from src.exception import (NotFoundData, NoRights, InvalidFileFormat, CorruptedFile, TooManyCharacters,
                           EmptyFileException, ToManyRequest)


load_dotenv()
KAFKA_TOPIC_NAME = os.getenv('KAFKA_TOPIC_NAME')
KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA = os.getenv('KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA')
KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER = os.getenv('KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER')

router = APIRouter()

async def extract_text_from_file(file: UploadFile, extensions: str, user_id: int) -> str:
    try:
        if extensions == '.pdf':
            content = await file.read()
            doc = fitz.open(stream=content, filetype="pdf")
            text = ""
            for page in doc:
                page_text = page.get_text()
                text += ' '.join(line.strip() for line in page_text.splitlines() if line.strip())
            await file.seek(0)# Важно: перемотка файла для возможного повторного чтения
            return text
        elif extensions == '.docx':
            content = await file.read()
            doc = Document(BytesIO(content))  # Используем BytesIO как файлоподобный объект
            await file.seek(0)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        else:
            return (await file.read()).decode('utf-8')
    except Exception:
        raise CorruptedFile(file.filename)

async def add_requirements(
        user_id: int,
        requirements: str,
    redis_client: Redis,
    db: AsyncSession
)-> RequirementsOut:
    new_requirements = Requirements(
        user_id=user_id,
        requirements=requirements
    )
    db.add(new_requirements)
    await db.commit()
    await db.refresh(new_requirements)

    # сохраняем в redis
    await redis_client.setex(f"requirements:{new_requirements.requirements_id}", STORAGE_TIME_REQUIREMENTS, requirements)

    producer.sent_message(
        topic=KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA,
        key=KEY_NEW_REQUIREMENTS,
        value={
            'requirements_id': new_requirements.requirements_id,
            'user_id': user_id,
            'requirements': requirements
        }
    )
    return RequirementsOut(requirements_id=new_requirements.requirements_id)

async def add_resume(
    user_id: int,
    resume: str,
    redis_client: Redis,
    db: AsyncSession
)->ResumeOut:
    new_resume = Resume(
        user_id=user_id,
        resume=resume
    )
    db.add(new_resume)
    await db.commit()
    await db.refresh(new_resume)

    # сохраняем в redis
    await redis_client.setex(f"resume:{new_resume.resume_id}", STORAGE_TIME_RESUME, resume)

    producer.sent_message(
        topic=KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA,
        key=KEY_NEW_RESUME,
        value={
            'resume_id': new_resume.resume_id,
            'user_id': user_id,
            'resume': new_resume.resume
        }
    )

    return ResumeOut(resume_id=new_resume.resume_id)

@router.post('/create_requirements/text', response_model=RequirementsOut)
async def create_requirements_text(
        data: RequirementsRequest,
        current_user: User = Depends(get_current_user),
        redis_client: Redis = Depends(get_redis),
        db: AsyncSession = Depends(get_db)
):
    return await add_requirements(current_user.user_id, data.requirements, redis_client, db)



@router.post('/create_requirements/file', response_model=RequirementsOut)
async def create_requirements_file(
    file: UploadFile = File(..., max_size=10_000_000),  # 10MB лимит
    current_user: User = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
):
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise InvalidFileFormat(ALLOWED_EXTENSIONS)

    requirements = await extract_text_from_file(file, file_ext, current_user.user_id)
    if len(requirements) > MAX_CHAR_REQUIREMENTS:
        raise TooManyCharacters(MAX_CHAR_REQUIREMENTS)

    if len(requirements) == 0:
        raise EmptyFileException(file.filename)

    return await add_requirements(current_user.user_id, requirements, redis_client, db)


@router.post('/create_resume/text', response_model=ResumeOut)
async def create_resume_text(
        data: ResumeRequest,
        current_user: User = Depends(get_current_user),
        redis_client: Redis = Depends(get_redis),
        db: AsyncSession = Depends(get_db)
):
    return await add_resume(current_user.user_id, data.resume, redis_client, db)



@router.post('/create_resume/file', response_model=ResumeOut)
async def create_resume_file(
    file: UploadFile = File(..., max_size=10_000_000),  # 10MB лимит
    current_user: User = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
):
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise InvalidFileFormat(ALLOWED_EXTENSIONS)

    resume = await extract_text_from_file(file, file_ext, current_user.user_id)
    if len(resume) > MAX_CHAR_RESUME:
        raise TooManyCharacters(MAX_CHAR_RESUME)

    if len(resume) == 0:
        raise EmptyFileException(file.filename)

    return await add_resume(current_user.user_id, resume, redis_client, db)


@router.post('/start_processing', response_model=StartProcessingOut)
async def start_processing(
    data: StartProcessingRequest,
    current_user: User = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
):
    if await redis_client.get(f'start_processing_bloc:{current_user.user_id}'):
        raise ToManyRequest(START_PROCESSING_BLOCK_TIME.seconds)

    # получаем текущее количество запросов
    quantity_requests = await redis_client.get(f'start_processing:{current_user.user_id}')
    quantity_requests = int(quantity_requests) if quantity_requests else 0

    # если лимит превышен
    if quantity_requests >= RATE_LIMIT_START_PROCESSING_IN_MINUTES:
        await redis_client.setex(
            f'start_processing_bloc:{current_user.user_id}',
            START_PROCESSING_BLOCK_TIME,
            "blocked" # значение может быть любое
        )
        raise ToManyRequest(START_PROCESSING_BLOCK_TIME.seconds)

    # инкрементируем счётчик
    if quantity_requests == 0:
        await redis_client.setex(f'start_processing:{current_user.user_id}',60,  1)
    else:
        await redis_client.incr(f'start_processing:{current_user.user_id}')

    requirements = await redis_client.get(f'requirements:{data.requirements_id}')
    if not requirements:
        requirements_from_db = await db.execute(select(Requirements).where(Requirements.requirements_id == data.requirements_id))
        requirements = requirements_from_db.scalar_one_or_none()
        if not requirements:
            raise NotFoundData() #  ошибка 404
        if requirements.user_id != current_user.user_id:
            raise NoRights() # ошибка 403
        requirements = requirements.requirements # получаем требования к резюме

    resume = await redis_client.get(f'resume:{data.resume_id}')
    if not resume:
        resume_from_db = await db.execute(select(Resume).where(Resume.resume_id == data.resume_id))
        resume = resume_from_db.scalar_one_or_none()
        if not resume:
            raise NotFoundData() #  ошибка 404
        if resume.user_id != current_user.user_id:
            raise NoRights() # ошибка 403
        resume = resume.resume # получаем требования к резюме

    new_processing = Processing(user_id=current_user.user_id, requirements_id=data.requirements_id, resume_id=data.resume_id)
    db.add(new_processing)
    await db.commit()
    await db.refresh(new_processing)

    producer.sent_message(
        topic=KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER,
        key=KEY_NEW_REQUEST,
        value={
            'callback_url': str(data.callback_url),
            'processing_id': new_processing.processing_id,
            'user_id': current_user.user_id,
            'resume_id': data.resume_id,
            'requirements_id': data.requirements_id,
            'requirements': requirements,
            'resume': resume
        }
    )

    return StartProcessingOut(status='Processing started')

