from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.collection import AsyncCollection

from open_assessor.domain.users import User

DEFAULT_DATABASE = "open_assessor"
COLLECTION = "users"

type Document = dict[str, Any]


class MongoUserRepository:
    """One document per user, keyed by `platform:id`."""

    def __init__(self, collection: AsyncCollection[Document]) -> None:
        """Use `connect` outside tests."""
        self._collection = collection

    @classmethod
    async def connect(cls, url: str) -> tuple["MongoUserRepository", AsyncMongoClient[Document]]:
        """Pings the server so a wrong URL fails at startup. The caller closes the client."""
        client: AsyncMongoClient[Document] = AsyncMongoClient(url)
        try:
            await client.admin.command("ping")
        except Exception:
            await client.close()
            raise
        # Railway's MONGO_URL names no database, so fall back to ours.
        database = client.get_default_database(default=DEFAULT_DATABASE)
        return cls(database[COLLECTION]), client

    async def get(self, user_id: str) -> User | None:
        document = await self._collection.find_one({"_id": user_id})
        return None if document is None else _from_document(document)

    async def save(self, user: User) -> None:
        await self._collection.replace_one({"_id": user.id}, _to_document(user), upsert=True)

    async def delete(self, user_id: str) -> bool:
        result = await self._collection.delete_one({"_id": user_id})
        return result.deleted_count > 0


def _to_document(user: User) -> Document:
    return {
        "_id": user.id,
        "authorized_by": user.authorized_by,
        "created_at": user.created_at,
        "spreadsheet_id": user.spreadsheet_id,
    }


def _from_document(document: Document) -> User:
    return User(
        id=str(document["_id"]),
        authorized_by=str(document.get("authorized_by", "")),
        created_at=str(document.get("created_at", "")),
        spreadsheet_id=document.get("spreadsheet_id"),
    )
