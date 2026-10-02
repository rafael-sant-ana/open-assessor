from open_assessor.application.security.allow_list import AllowList
from open_assessor.domain.messages import MessageUser


def test_is_empty_without_configuration():
    assert AllowList.from_env({}).is_empty
    assert AllowList.from_env({"ALLOWED_USERS": " , ", "ALLOWED_JIDS": ""}).is_empty


def test_allows_configured_users_per_platform():
    allow_list = AllowList.from_env({"ALLOWED_USERS": "telegram:123, whatsapp:55@s.whatsapp.net"})

    assert allow_list.is_allowed("telegram", MessageUser("123"))
    assert allow_list.is_allowed("whatsapp", MessageUser("55@s.whatsapp.net"))
    assert not allow_list.is_allowed("whatsapp", MessageUser("123"))
    assert not allow_list.is_allowed("telegram", MessageUser("456"))


def test_reads_legacy_whatsapp_jids():
    allow_list = AllowList.from_env({"ALLOWED_JIDS": "55@s.whatsapp.net"})

    assert allow_list.is_allowed("whatsapp", MessageUser("55@s.whatsapp.net"))


def test_matches_any_alias_of_the_user():
    allow_list = AllowList.from_env({"ALLOWED_USERS": "whatsapp:55@s.whatsapp.net"})

    assert allow_list.is_allowed("whatsapp", MessageUser("99@lid", aliases=("55@s.whatsapp.net",)))
