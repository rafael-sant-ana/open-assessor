import os
import uuid
from collections.abc import AsyncIterator

import pytest

from open_assessor.infrastructure.users.in_memory_user_repository import InMemoryUserRepository
from open_assessor.infrastructure.users.mongo_user_repository import MongoUserRepository
from open_assessor.infrastructure.users.user_repository_factory import create_user_repository
from tests.infrastructure.users.user_repository_contract import UserRepositoryContract

MONGODB_TEST_URL = os.environ.get("MONGODB_TEST_URL", "")


class TestInMemoryUserRepository(UserRepositoryContract):
    @pytest.fixture
    async def repo(self) -> InMemoryUserRepository:
        return InMemoryUserRepository()


@pytest.mark.skipif(not MONGODB_TEST_URL, reason="set MONGODB_TEST_URL to run against MongoDB")
class TestMongoUserRepository(UserRepositoryContract):
    @pytest.fixture
    async def repo(self) -> AsyncIterator[MongoUserRepository]:
        _, client = await MongoUserRepository.connect(MONGODB_TEST_URL)
        # A throwaway collection per test, so runs never see each other's users.
        collection = client["open_assessor_test"][f"users_{uuid.uuid4().hex}"]
        yield MongoUserRepository(collection)
        await collection.drop()
        await client.close()


async def test_factory_uses_memory_when_mongodb_url_is_not_set():
    created = await create_user_repository({"MONGODB_URL": "  "})

    assert not created.persistent
    assert isinstance(created.repository, InMemoryUserRepository)
    await created.close()
