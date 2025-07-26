import asyncio
import threading

import uvicorn
import os
from dotenv import load_dotenv
from fastapi import FastAPI

from srt.data_base.data_base import create_data_base
from srt.dependencies.kafka_dependencies import consumer_auth

load_dotenv()
KAFKA_TOPIC_NAME = os.getenv('KAFKA_TOPIC_NAME')

app = FastAPI()



if __name__ == '__main__':
    # Запускаем consumer в отдельном потоке
    consumer_thread = threading.Thread(target=consumer_auth.consumer_run)
    consumer_thread.daemon = True  # Демонизируем поток, чтобы он завершился при завершении основного потока
    consumer_thread.start()

    asyncio.run(create_data_base())
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )