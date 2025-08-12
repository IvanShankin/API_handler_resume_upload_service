import asyncio
import os
import shutil
import time
from datetime import datetime, timedelta, UTC
from pathlib import Path
from dotenv import load_dotenv
from jose import jwt
from redis import Redis

load_dotenv()  # Загружает переменные из .env
KAFKA_BOOTSTRAP_SERVERS= os.getenv('KAFKA_BOOTSTRAP_SERVERS')
KAFKA_TOPIC_CONSUMER= os.getenv('KAFKA_TOPIC_CONSUMER')
KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA= os.getenv('KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA')
KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER= os.getenv('KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER')
MODE = os.getenv('MODE')
SECRET_KEY = os.getenv('SECRET_KEY')
ACCESS_TOKEN_EXPIRE_MINUTES = float(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
ALGORITHM = os.getenv('ALGORITHM')

# этот импорт необходимо указывать именно тут для корректного импорта .tests.env
import pytest_asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func
from confluent_kafka.cimpl import NewTopic, TopicPartition

from srt.database.database import create_database, get_db
from srt.database.models import User, Requirements, Resume, Processing
from srt.dependencies import get_redis, admin_client
from srt.config import logger

from confluent_kafka import Consumer

PATH_TO_TEST_DIRECTORY = 'file_for_test'

TOPIC_LIST = [KAFKA_TOPIC_CONSUMER, KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA, KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER]

conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': 'test-group-' + str(os.getpid()),  # Уникальный group.id для каждого запуска тестов
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': 'false',  # Отключаем авто-коммит
    'isolation.level': 'read_committed'
}

consumer = Consumer(conf)


@pytest_asyncio.fixture(scope='session', autouse=True)
async def create_database_fixture():
    if MODE != "TEST":
        raise Exception("Используется основная БД!")

    await create_database()

@pytest_asyncio.fixture(scope='session', autouse=True)
async def check_kafka_connection():
    try:
        admin_client.list_topics(timeout=10)
    except Exception:
        raise Exception("Не удалось установить соединение с Kafka!")

@pytest_asyncio.fixture
async def db_session()->AsyncSession:
    """Соединение с БД"""
    db_gen = get_db()
    session = await db_gen.__anext__()
    try:
        yield session
    finally:
        await session.close()

@pytest_asyncio.fixture
async def redis_session()->Redis:
    """Соединение с redis"""
    redis_gen = get_redis()
    session = await redis_gen.__anext__()
    try:
        yield session
    finally:
        await session.aclose()
        await asyncio.sleep(1)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clearing_db(db_session: AsyncSession):
    """Очищает базу банных"""
    # удаляем обязательно в таком порядке
    await db_session.execute(delete(Processing))
    await db_session.execute(delete(Requirements))
    await db_session.execute(delete(Resume))
    await db_session.execute(delete(User))
    await db_session.commit()

@pytest_asyncio.fixture(scope="function")
async def clearing_redis(redis_session):
    """Очищает redis"""
    await redis_session.flushdb()

@pytest_asyncio.fixture(scope='session', autouse=True)
async def create_directory():
    """Создаёт директорию для хранения файлов и после тестов удаляет её"""
    if not os.path.isdir(PATH_TO_TEST_DIRECTORY):
        Path(PATH_TO_TEST_DIRECTORY).mkdir()
    yield
    shutil.rmtree(PATH_TO_TEST_DIRECTORY)


@pytest_asyncio.fixture(scope='function')
async def clearing_kafka():
    """Очищает топик у kafka с которым работаем, путём его пересоздания"""
    max_retries = 7

    # Сбрасываем позицию consumer перед очисткой
    consumer.unsubscribe()
    for topic in TOPIC_LIST:
        try:
            consumer.assign([TopicPartition(topic, 0, 0)])
            consumer.seek(TopicPartition(topic, 0, 0))
        except Exception as e:
            logger.warning(f"Failed to reset consumer for topic {topic}: {e}")

    # Получаем метаданные кластера
    cluster_metadata = admin_client.list_topics()
    for kafka_topic_name in TOPIC_LIST:
        # Проверяем существование топика
        topic_exists = kafka_topic_name in cluster_metadata.topics

        # Проверяем существует ли топик перед удалением
        if topic_exists:
            admin_client.delete_topics(topics=[kafka_topic_name])

            # Ждём подтверждения удаления
            for _ in range(max_retries):
                current_metadata = admin_client.list_topics()
                if kafka_topic_name not in current_metadata.topics:
                    break
                time.sleep(1)
            else:
                logger.warning(f"Топик {kafka_topic_name} всё ещё существует после попыток удаления.")

        admin_client.create_topics([NewTopic(topic=kafka_topic_name, num_partitions=1, replication_factor=1)])
        time.sleep(2)  # даём Kafka 2 секунды на инициализацию

        # Проверяем создание топика
        for _ in range(max_retries):
            current_metadata = admin_client.list_topics()
            if kafka_topic_name in current_metadata.topics:
                break
            time.sleep(1)
        else:
            raise RuntimeError(f"Failed to create topic {kafka_topic_name}")

async def reset_requests_start_processing(redis_session, user_id):
    await redis_session.delete(f'start_processing:{user_id}')

@pytest_asyncio.fixture(scope="function")
async def create_user(db_session: AsyncSession)->dict:
    """
    Создает тестового пользователя и возвращает данные о нём
    :return: dict {'user_id', 'access_token'}
    """
    result_db = await db_session.execute(func.max(User.user_id))
    max_user_id = result_db.scalar_one_or_none()

    if max_user_id:
        new_user_id = max_user_id + 1
    else:
        new_user_id = 1

    new_user = User(user_id = new_user_id)
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)

    to_encode = {"sub": str(new_user.user_id)}.copy()

    # Установка времени истечения токена
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Добавляем поле с временем истечения
    to_encode.update({"exp": expire})

    # Кодируем данные в JWT токен
    access_token = jwt.encode(
        to_encode,  # Данные для кодирования
        SECRET_KEY,  # Секретный ключ из конфига
        algorithm=ALGORITHM  # Алгоритм шифрования
    )

    return {
        "user_id": new_user.user_id,
        "access_token": access_token,
    }

@pytest_asyncio.fixture(scope="function")
async def create_requirements_and_resume(db_session: AsyncSession, create_user)->dict:
    """
    Создает требования
    :return: dict {'user_id', 'access_token', 'requirements_id', 'resume_id', 'requirements', 'resume'}
    """
    new_requirements = Requirements(
        user_id=create_user['user_id'],
        requirements='Требования к резюме'
    )
    new_resume = Resume(
        user_id=create_user['user_id'],
        resume='Тестовое резюме'
    )
    db_session.add(new_requirements)
    db_session.add(new_resume)
    await db_session.commit()
    await db_session.refresh(new_requirements)
    await db_session.refresh(new_resume)

    return {
        'user_id': create_user['user_id'],
        'access_token': create_user['access_token'],
        'requirements_id': new_requirements.requirements_id,
        'resume_id': new_resume.resume_id,
        'requirements': new_requirements.requirements,
        'resume': new_resume.resume
    }