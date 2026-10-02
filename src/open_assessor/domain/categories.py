from typing import Literal, TypeGuard, get_args

type Category = Literal[
    "alimentacao",
    "transporte",
    "moradia",
    "saude",
    "lazer",
    "educacao",
    "outros",
]

CATEGORIES: tuple[Category, ...] = get_args(Category.__value__)


def is_category(value: object) -> TypeGuard[Category]:
    return value in CATEGORIES
