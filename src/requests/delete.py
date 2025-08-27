import os

from dotenv import load_dotenv

from redis import Redis
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from src.access import get_current_user
from src.dependencies import producer, get_redis
from src.schemas.request import DeleteProcessingRequest,DeleteRequirementsRequest
from src.schemas.response import IsDeleteOut
from src.database.models import User, Requirements, Processing
from src.database.database import get_db
from src.config import  logger, KEY_DELETE_PROCESSING, KEY_DELETE_REQUIREMENTS


load_dotenv()
KAFKA_TOPIC_NAME = os.getenv('KAFKA_TOPIC_NAME')
KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA = os.getenv('KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA')
KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER = os.getenv('KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER')

router = APIRouter()

@router.delete('/delete_processing', response_model=IsDeleteOut, description="Удалит только указанные обработки")
async def delete_processing(
    data: DeleteProcessingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        if not data.processings_ids:
            return IsDeleteOut(is_deleted=False)

        # Один запрос для удаления всех указанных processing_id
        result = await db.execute(
            delete(Processing)
            .where(Processing.processing_id.in_(data.processings_ids))
            .where(Processing.user_id == current_user.user_id)
        )
        await db.commit()

        # проверяем, сколько строк было удалено
        if result.rowcount > 0:
            producer.sent_message(
                KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA,
                KEY_DELETE_PROCESSING, {'processings_ids': data.processings_ids, 'user_id': current_user.user_id}
            )
            return IsDeleteOut(is_deleted=True)

        return IsDeleteOut(is_deleted=False)
    except Exception as e:
        logger.error(f"Ошибка при удалении processing: '{str(e)}'")
        await db.rollback()
        return IsDeleteOut(is_deleted=False)


@router.delete('/delete_requirements', response_model=IsDeleteOut, description="Удалит требования и все обработки связанные с ним")
async def delete_requirements(
    data: DeleteRequirementsRequest,
    current_user: User = Depends(get_current_user),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
):
    try:
        if not data.requirements_ids:
            return IsDeleteOut(is_deleted=False)

        # получаем ID processing, которые будут удалены
        deleted_processings = await db.execute(
            select(Processing.processing_id)
            .where(
                    (Processing.requirements_id.in_(data.requirements_ids)) &
                    (Processing.user_id == current_user.user_id)
                )
        )

        deleted_processing_ids = [row[0] for row in deleted_processings]

        # удаляем связанные processing
        await db.execute(
            delete(Processing)
            .where(
                    (Processing.processing_id.in_(deleted_processing_ids)) &
                    (Processing.user_id == current_user.user_id)  # проверка прав
            )
        )

        # удаляем сами requirements
        result = await db.execute(
            delete(Requirements)
            .where(
                and_(
                    Requirements.requirements_id.in_(data.requirements_ids),
                    Requirements.user_id == current_user.user_id
                )
            )
        )

        await db.commit()

        # проверяем, сколько строк было удалено
        if result.rowcount > 0:
            # удаляем в redis
            for requirements_id in data.requirements_ids:
                await redis.delete(f'requirements:{requirements_id}')

            producer.sent_message(
                KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA,
                KEY_DELETE_REQUIREMENTS,
                {
                    'processings_ids': deleted_processing_ids,
                    'requirements_ids': data.requirements_ids,
                    'user_id': current_user.user_id
                }
            )
            return IsDeleteOut(is_deleted=True)

        return IsDeleteOut(is_deleted=False)
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при удалении requirements: '{str(e)}'")