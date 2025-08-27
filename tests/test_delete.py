import json
import os

from dotenv import load_dotenv
from confluent_kafka import KafkaError
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from src.database.models import Requirements, Processing
from src.main import app
from src.config import KEY_DELETE_PROCESSING, KEY_DELETE_REQUIREMENTS
from tests.conftest import consumer

load_dotenv()  # Загружает переменные из .env
KAFKA_BOOTSTRAP_SERVERS= os.getenv('KAFKA_BOOTSTRAP_SERVERS')
KAFKA_TOPIC_CONSUMER= os.getenv('KAFKA_TOPIC_CONSUMER')
KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA= os.getenv('KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA')
KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER= os.getenv('KAFKA_TOPIC_PRODUCER_FOR_AI_HANDLER')

async def test_delete_processing(db_session, create_requirements_and_resume, clearing_kafka):
    consumer.subscribe([KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA])

    new_processing = Processing(
        user_id=create_requirements_and_resume['user_id'],
        requirements_id=create_requirements_and_resume['requirements_id'],
        resume_id=create_requirements_and_resume['resume_id']
    )
    db_session.add(new_processing)
    await db_session.commit()
    await db_session.refresh(new_processing)

    async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
    ) as ac:
        response = await ac.request(
            "DELETE",
            "/delete_processing",
            json={"processings_ids": [new_processing.processing_id]},
            headers={"Authorization": f"Bearer {create_requirements_and_resume['access_token']}"}
        )
        assert response.status_code == 200
        data_response = response.json()
        assert data_response['is_deleted'] == True

        result_db = await db_session.execute(select(Processing).where(Processing.processing_id == new_processing.processing_id))

        assert not result_db.scalar_one_or_none() # в БД не должно быть записи

        # Данные с Kafka
        data_kafka = None
        for i in range(40):
            try:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    if i == 39:
                        raise Exception("Не удалось получить сообщение от Kafka!")
                    continue
                if msg.key().decode('utf-8') == KEY_DELETE_PROCESSING:
                    data_kafka = json.loads(msg.value().decode('utf-8'))
                else:
                    raise Exception(f"Ожидался ключ {KEY_DELETE_PROCESSING}, получен {msg.key().decode('utf-8')}")
                break
            except KafkaError as e:
                raise Exception(f"Ошибка Kafka: {e}")

        assert new_processing.processing_id == data_kafka['processings_ids'][0] # через kafka передаётся массив с удалёнными id


async def test_delete_requirements(db_session, redis_session, create_requirements_and_resume, clearing_kafka):
    consumer.subscribe([KAFKA_TOPIC_PRODUCER_FOR_UPLOADING_DATA])

    origin_list_processing = []
    for i in range(5):
        new_processing = Processing(
            user_id=create_requirements_and_resume['user_id'],
            requirements_id=create_requirements_and_resume['requirements_id'],
            resume_id=create_requirements_and_resume['resume_id']
        )
        db_session.add(new_processing)
        await db_session.commit()
        await db_session.refresh(new_processing)

        origin_list_processing.append(new_processing.processing_id)

    # кэшируем данные (не важно какое значение будет)
    await redis_session.set(f'requirements:{create_requirements_and_resume['requirements_id']}', '_')

    async with AsyncClient(
            transport=ASGITransport(app),
            base_url="http://test",
    ) as ac:
        response = await ac.request(
            "DELETE",
            "/delete_requirements",
            json={"requirements_ids": [create_requirements_and_resume['requirements_id']]},
            headers={"Authorization": f"Bearer {create_requirements_and_resume['access_token']}"}
        )
        assert response.status_code == 200
        data_response = response.json()
        assert data_response['is_deleted'] == True

        # проверка связанных обработок с данным требованием
        for processing_id in origin_list_processing:
            result_db = await db_session.execute(select(Processing).where(Processing.processing_id == processing_id))
            assert not result_db.scalar_one_or_none()

        # проверка удалённого requirements
        result_db = await db_session.execute(select(Processing).where(Requirements.requirements_id == create_requirements_and_resume['requirements_id']))
        assert not result_db.scalar_one_or_none()

        # Данные с Kafka
        data_kafka = None
        for i in range(40):
            try:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    if i == 39:
                        raise Exception("Не удалось получить сообщение от Kafka!")
                    continue
                if msg.key().decode('utf-8') == KEY_DELETE_REQUIREMENTS:
                    data_kafka = json.loads(msg.value().decode('utf-8'))
                else:
                    raise Exception(f"Ожидался ключ {KEY_DELETE_REQUIREMENTS}, получен {msg.key().decode('utf-8')}")
                break
            except KafkaError as e:
                raise Exception(f"Ошибка Kafka: {e}")

        for processing_id in origin_list_processing:
            assert processing_id in data_kafka['processings_ids'], f'ID "{processing_id}" нет в вернувшихся данных'

        assert create_requirements_and_resume['requirements_id'] in data_kafka['requirements_ids']

        redis_data = await redis_session.get(f'requirements:{create_requirements_and_resume['requirements_id']}')
        assert not redis_data
