import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from open_assessor.infrastructure.expenses.google_auth import (
    InlineCredentials,
    KeyFile,
    create_sheets_api,
    read_google_credentials,
)

KEY = {"client_email": "bot@project.iam.gserviceaccount.com", "private_key": "PRIVATE", "extra": 1}
RAW = json.dumps(KEY)
EXPECTED = InlineCredentials(KEY["client_email"], KEY["private_key"])  # pyright: ignore[reportArgumentType]


class TestReadGoogleCredentials:
    def test_reads_the_raw_json_from_google_service_account_json(self):
        assert read_google_credentials({"GOOGLE_SERVICE_ACCOUNT_JSON": RAW}) == EXPECTED

    def test_accepts_the_json_base64_encoded(self):
        encoded = base64.b64encode(RAW.encode()).decode()

        assert read_google_credentials({"GOOGLE_SERVICE_ACCOUNT_JSON": encoded}) == EXPECTED

    def test_falls_back_to_the_key_file_path(self):
        assert read_google_credentials({"GOOGLE_APPLICATION_CREDENTIALS": "./key.json"}) == KeyFile(
            "./key.json"
        )

    def test_prefers_the_inline_json_over_the_path(self):
        result = read_google_credentials(
            {"GOOGLE_SERVICE_ACCOUNT_JSON": RAW, "GOOGLE_APPLICATION_CREDENTIALS": "./key.json"}
        )

        assert isinstance(result, InlineCredentials)

    def test_ignores_blank_values_and_names_both_variables_when_nothing_is_set(self):
        with pytest.raises(
            ValueError, match="GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS"
        ):
            read_google_credentials(
                {"GOOGLE_SERVICE_ACCOUNT_JSON": "  ", "GOOGLE_APPLICATION_CREDENTIALS": ""}
            )

    def test_rejects_json_that_is_not_valid_without_echoing_it(self):
        with pytest.raises(ValueError, match="raw or base64") as caught:
            read_google_credentials({"GOOGLE_SERVICE_ACCOUNT_JSON": "{oops PRIVATE"})

        assert "PRIVATE" not in str(caught.value)
        assert caught.value.__cause__ is None

    def test_rejects_a_key_without_client_email_or_private_key(self):
        with pytest.raises(ValueError, match="client_email or private_key"):
            read_google_credentials({"GOOGLE_SERVICE_ACCOUNT_JSON": '{"client_email":"a"}'})


def test_create_sheets_api_builds_a_client_without_touching_the_network():
    private_key = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )
    key = json.dumps({"client_email": KEY["client_email"], "private_key": private_key})

    api = create_sheets_api({"GOOGLE_SERVICE_ACCOUNT_JSON": key})

    assert callable(api.values_append)
