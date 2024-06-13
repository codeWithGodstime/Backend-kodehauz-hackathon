
from abc import ABC, abstractmethod
from redis import Redis

from app.core.config import settings


class StoreInterface(ABC):
    @abstractmethod
    def put(self, key) -> None:
        pass

    @abstractmethod
    def remove(self, key) -> str:
        pass

    @abstractmethod
    def check(self, key) -> bool:
        pass


class MapStore(StoreInterface):
    store = set()

    def put(self, key) -> None:
        self.store.add(key)

    def remove(self, key) -> str:
        if key in self.store:
            self.store.remove(key)
        return key

    def check(self, key) -> bool:
        return key in self.store

    def __repr__(self) -> str:
        return str(self.store)


class RedisStore(StoreInterface):
    redis: Redis

    def __init__(self, host: str, password: str, port: str) -> None:
        self.redis = Redis(
            host=host,
            port=port,
            password=password,
            db=0,
            decode_responses=True,
        )

    def put(self, key) -> None:
        self.redis.setex(key, settings.INVALID_JWT_EXPIRE, 'true')

    def remove(self, key) -> str:
        entry = self.redis.get(key)
        self.redis.delete(key)
        return entry

    def check(self, key) -> bool:
        entry = self.redis.get(key)
        return entry and entry == 'true'

    def __repr__(self) -> str:
        return str(self.redis)
