import asyncio
import threading

import uvicorn
import os
from dotenv import load_dotenv
from fastapi import FastAPI

from srt.database.database import create_database
from srt.dependencies.kafka_dependencies import consumer_auth
from requests import main_router

load_dotenv()
KAFKA_TOPIC_NAME = os.getenv('KAFKA_TOPIC_NAME')

app = FastAPI()

app.include_router(main_router)

if __name__ == '__main__':
    # Запускаем consumer в отдельном потоке
    def run_consumer():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(consumer_auth.consumer_run())


    consumer_thread = threading.Thread(target=run_consumer)
    consumer_thread.daemon = True # Демонизируем поток, чтобы он завершился при завершении основного потока
    consumer_thread.start()

    asyncio.run(create_database())
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )