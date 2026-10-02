import math

MAX_AMOUNT_CENTS = 100_000_000
"""R$ 1.000.000,00: anything above is far more likely a typo or a misparse."""


def to_cents(amount: object) -> int | None:
    """Converts a BRL decimal amount to integer cents, or `None` if it is not a usable amount."""
    # bool is a subclass of int, but True is not an amount.
    if isinstance(amount, bool) or not isinstance(amount, int | float):
        return None
    if not math.isfinite(amount):
        return None

    # Rounds half up like JavaScript's Math.round; round() would round half to even.
    cents = math.floor(amount * 100 + 0.5)
    if cents <= 0 or cents > MAX_AMOUNT_CENTS:
        return None

    return cents


def format_brl(cents: int) -> str:
    """`5090` → `R$ 50,90`."""
    sign = "-" if cents < 0 else ""
    reais, centavos = divmod(abs(cents), 100)
    thousands = f"{reais:,}".replace(",", ".")
    return f"{sign}R$ {thousands},{centavos:02d}"
