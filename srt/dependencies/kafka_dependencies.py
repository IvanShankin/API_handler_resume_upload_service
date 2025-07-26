import asyncio
import json
import os
import socket
from dotenv import load_dotenv
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from confluent_kafka import Producer, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import Consumer, KafkaException, KafkaError
import sys

from fastapi.params import Depends
from rsa.common import extended_gcd

from srt.config import logger, MIN_COMMIT_COUNT_KAFKA
from srt.data_base.models import User
from srt.data_base.data_base import get_db

load_dotenv()
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
KAFKA_TOPIC_CONSUMER = os.getenv('KAFKA_TOPIC_CONSUMER')
KAFKA_TOPIC_PRODUCER = os.getenv('KAFKA_TOPIC_PRODUCER')

admin_client = AdminClient({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})\

producer = None # ниже будет переопределён
consumer_auth = None # ниже будет переопределён


def create_topic(topic_name, num_partitions=1, replication_factor=1):
    """
    Создаёт топик в Kafka.

    :param topic_name: Название топика
    :param num_partitions: Количество партиций
    :param replication_factor: Фактор репликации
    """
    # Создание объекта топика
    new_topic = NewTopic(
        topic_name,
        num_partitions=num_partitions,
        replication_factor=replication_factor
    )

    # Запрос на создание топика
    futures = admin_client.create_topics([new_topic])

    # Ожидание результата
    for topic, future in futures.items():
        try:
            future.result()  # Блокирует выполнение, пока топик не создан
            logger.info(f"Топик '{topic}' успешно создан!")
        except Exception as e:
            logger.error(f"Ошибка при создании топика '{topic}': {e}")


def check_exists_topic(topic_names: list):
    """Проверяет, существует ли топик, если нет, то создаст его"""
    for topic in topic_names:
        cluster_metadata = admin_client.list_topics()
        if not topic in cluster_metadata.topics: # если topic не существует
            create_topic(
                topic_name=topic,
                num_partitions=1,
                replication_factor=1
            )

class ProducerKafka:
    def __init__(self):
        self.conf = {
                'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
                'client.id': socket.gethostname()
            }
        self.producer = Producer(self.conf)

    def sent_message(self, topic: str, key: str, value: str):
        try:
            self.producer.produce(topic=topic, key=key, value=value, callback=self._acked)
            self.producer.flush()
            self.producer.poll(1)
        except KafkaException as e:
            logger.error(f"Kafka error: {e}")

    def _acked(self, err, msg):
        logger.info(f"Kafka new message: err: {err}\nmsg: {msg.value().decode('utf-8')}")



class ConsumerKafka:
    def __init__(self, topic: str):
        self.conf = {'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
                'group.id': 'foo',
                'auto.offset.reset': 'smallest',
                'enable.auto.commit': False,  # отключаем auto-commit
                'on_commit': self.commit_completed} # тут указали в какую функцию попадёт при сохранении
        self.consumer = Consumer(self.conf)
        self.running = True
        self.topic = topic
        check_exists_topic([self.topic])

    # в эту функцию попадём при вызове метода consumer.commit
    def commit_completed(self, err, partitions):
        if err:
            logger.error(str(err))
        else:
            logger.info("сохранили партию kafka")

    # ЭТУ ФУНКЦИЮ ПЕРЕОБРЕДЕЛЯЕМ В НАСТЛЕДУЕМОМ КЛАССЕ,
    # ОНА БУДЕТ ВЫПОЛНЯТЬ ДЕЙСТВИЯ ПРИ ПОЛУЧЕНИИ СООБЩЕНИЯ
    async def worker_topic(self, data:dict):
        pass

    def consumer_run(self):
        try:
            self.consumer.subscribe([self.topic])
            msg_count = 0

            while self.running:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None: continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        sys.stderr.write('%% %s [%d] reached end at offset %d\n' %
                                         (msg.topic(), msg.partition(), msg.offset()))
                    elif msg.error():
                        raise KafkaException(msg.error())
                else:
                    data = json.loads(msg.value().decode('utf-8'))

                    asyncio.run(self.worker_topic(data))

                    msg_count += 1
                    if msg_count % MIN_COMMIT_COUNT_KAFKA == 0:
                        self.consumer.commit(asynchronous=True)
        finally:
            self.consumer.close()

# consumer для топика авторизации
class ConsumerKafkaAuth(ConsumerKafka):
    def __init__(self, topic: str):
        super().__init__(topic)

    async def worker_topic(self, data: dict):
        db_gen = get_db()
        db = await db_gen.__anext__()  # Извлекаем AsyncSession
        result_db = await db.execute(select(User).where(User.user_id == data['user_id']))

        if not result_db.scalar_one_or_none():  # если пользователь с таким id нет
            new_user = User(user_id=int(data['user_id']))
            db.add(new_user)
            await db.commit()
            logger.info(f'Добавлен в БД пользователь с id = {data['user_id']}')
        else:
            logger.info(f'Пользователь с id = {data['user_id']} не будет добавлен, т.к. уже имеется')

producer = ProducerKafka()
consumer_auth = ConsumerKafkaAuth(KAFKA_TOPIC_CONSUMER)


