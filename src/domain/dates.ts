export type Clock = () => Date;

/** Inclusive range of calendar days, `YYYY-MM-DD`. */
export interface DateRange {
    readonly from: string;
    readonly to: string;
}

export const DEFAULT_TIMEZONE = 'America/Sao_Paulo';

const ISO_DAY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** True for a real calendar day written as `YYYY-MM-DD` (rejects `2026-02-30`). */
export function isValidIsoDate(value: unknown): value is string {
    if (typeof value !== 'string') return false;

    const match = ISO_DAY.exec(value);
    if (!match) return false;

    const [year, month, day] = [match[1], match[2], match[3]].map(Number) as [
        number,
        number,
        number,
    ];
    const date = new Date(Date.UTC(year, month - 1, day));

    return (
        date.getUTCFullYear() === year &&
        date.getUTCMonth() === month - 1 &&
        date.getUTCDate() === day
    );
}

/** The calendar day `now` falls on in `timezone`, as `YYYY-MM-DD`. */
export function todayIn(timezone: string, now: Date): string {
    // The en-CA locale formats dates as YYYY-MM-DD.
    return new Intl.DateTimeFormat('en-CA', {
        timeZone: timezone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
    }).format(now);
}

/** Weekday name of `now` in `timezone`, in Portuguese (e.g. `quinta-feira`). */
export function weekdayIn(timezone: string, now: Date): string {
    return new Intl.DateTimeFormat('pt-BR', {
        timeZone: timezone,
        weekday: 'long',
    }).format(now);
}
