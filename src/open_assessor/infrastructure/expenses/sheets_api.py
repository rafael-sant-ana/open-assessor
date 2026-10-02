import asyncio
from typing import Any, Protocol

type Params = Any


class SheetsApi(Protocol):
    """The Google Sheets v4 methods the repository uses, with the REST API's parameter names.

    Kept this narrow so tests can stand in for it without faking the whole discovery client.
    """

    async def spreadsheets_get(self, **params: Params) -> dict[str, Any]: ...

    async def spreadsheets_batch_update(self, **params: Params) -> dict[str, Any]: ...

    async def values_get(self, **params: Params) -> dict[str, Any]: ...

    async def values_update(self, **params: Params) -> dict[str, Any]: ...

    async def values_append(self, **params: Params) -> dict[str, Any]: ...


class GoogleSheetsApi:
    """`SheetsApi` over google-api-python-client, which is synchronous: calls run in a thread.

    The client is not thread-safe, so callers must not run two calls at once. The repository
    already runs its operations one at a time.
    """

    def __init__(self, service: Any) -> None:
        self._spreadsheets = service.spreadsheets()

    async def spreadsheets_get(self, **params: Params) -> dict[str, Any]:
        return await self._execute(self._spreadsheets.get(**params))

    async def spreadsheets_batch_update(self, **params: Params) -> dict[str, Any]:
        return await self._execute(self._spreadsheets.batchUpdate(**params))

    async def values_get(self, **params: Params) -> dict[str, Any]:
        return await self._execute(self._spreadsheets.values().get(**params))

    async def values_update(self, **params: Params) -> dict[str, Any]:
        return await self._execute(self._spreadsheets.values().update(**params))

    async def values_append(self, **params: Params) -> dict[str, Any]:
        return await self._execute(self._spreadsheets.values().append(**params))

    @staticmethod
    async def _execute(request: Any) -> dict[str, Any]:
        return await asyncio.to_thread(request.execute)
