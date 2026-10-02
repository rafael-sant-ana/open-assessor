import json


def to_json(value: object) -> str:
    """Compact JSON that keeps accents readable, like JavaScript's JSON.stringify."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
