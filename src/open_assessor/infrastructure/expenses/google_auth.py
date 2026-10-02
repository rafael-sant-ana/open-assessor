import base64
import binascii
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]

from open_assessor.infrastructure.expenses.sheets_api import GoogleSheetsApi

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
_TOKEN_URI = "https://oauth2.googleapis.com/token"


@dataclass(frozen=True, slots=True)
class InlineCredentials:
    client_email: str
    private_key: str


@dataclass(frozen=True, slots=True)
class KeyFile:
    path: str


type GoogleCredentials = InlineCredentials | KeyFile


def read_google_credentials(env: Mapping[str, str] = os.environ) -> GoogleCredentials:
    """Service account credentials from `GOOGLE_SERVICE_ACCOUNT_JSON` (the key's JSON, raw or
    base64 — handy for container secrets) or, failing that, the path in
    `GOOGLE_APPLICATION_CREDENTIALS`."""
    inline = env.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if inline:
        return _parse_service_account(inline)

    key_file = env.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if key_file:
        return KeyFile(key_file)

    raise ValueError(
        "Missing Google credentials: set GOOGLE_SERVICE_ACCOUNT_JSON or "
        "GOOGLE_APPLICATION_CREDENTIALS. Check the .env.example"
    )


def create_sheets_api(env: Mapping[str, str] = os.environ) -> GoogleSheetsApi:
    match read_google_credentials(env):
        case InlineCredentials(client_email, private_key):
            credentials = service_account.Credentials.from_service_account_info(  # pyright: ignore[reportUnknownMemberType]
                {
                    "client_email": client_email,
                    "private_key": private_key,
                    "token_uri": _TOKEN_URI,
                },
                scopes=[SHEETS_SCOPE],
            )
        case KeyFile(path):
            credentials = service_account.Credentials.from_service_account_file(  # pyright: ignore[reportUnknownMemberType]
                path, scopes=[SHEETS_SCOPE]
            )

    # The discovery document ships with the library, so this does not touch the network.
    service: Any = build(  # pyright: ignore[reportUnknownVariableType]
        "sheets", "v4", credentials=credentials, cache_discovery=False
    )
    return GoogleSheetsApi(service)


def _parse_service_account(raw: str) -> InlineCredentials:
    try:
        text = raw if raw.startswith("{") else base64.b64decode(raw, validate=True).decode()
        parsed: object = json.loads(text)
    except (ValueError, binascii.Error):
        # Never echo the value: it holds a private key.
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON must be the service account key JSON, raw or base64-encoded"
        ) from None

    fields: dict[str, object] = parsed if isinstance(parsed, dict) else {}  # pyright: ignore[reportUnknownVariableType]
    client_email, private_key = fields.get("client_email"), fields.get("private_key")
    if not isinstance(client_email, str) or not isinstance(private_key, str):
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is missing client_email or private_key. "
            "Use the JSON key downloaded for the service account"
        )

    return InlineCredentials(client_email, private_key)
