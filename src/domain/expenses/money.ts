/** R$ 1.000.000,00: anything above is far more likely a typo or a misparse. */
export const MAX_AMOUNT_CENTS = 100_000_000;

/** Converts a BRL decimal amount to integer cents, or `null` if it is not a usable amount. */
export function toCents(amount: unknown): number | null {
    if (typeof amount !== 'number' || !Number.isFinite(amount)) return null;

    const cents = Math.round(amount * 100);
    if (cents <= 0 || cents > MAX_AMOUNT_CENTS) return null;

    return cents;
}

/** `5090` → `R$ 50,90`. */
export function formatBRL(cents: number): string {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL',
    })
        .format(cents / 100)
        .replace(/ /g, ' ');
}
