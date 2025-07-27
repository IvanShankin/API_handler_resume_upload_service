from srt.dependencies.kafka_dependencies import consumer_auth, producer, admin_client
from srt.dependencies.redis_dependencies import get_redis, redis_client

__all__ = ['consumer_auth', 'producer', 'get_redis', 'redis_client', 'admin_client']