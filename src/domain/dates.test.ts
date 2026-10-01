import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { isValidIsoDate, todayIn, weekdayIn } from './dates.js';

describe('isValidIsoDate', () => {
    it('accepts real calendar days', () => {
        assert.equal(isValidIsoDate('2026-10-01'), true);
        assert.equal(isValidIsoDate('2028-02-29'), true);
    });

    it('rejects impossible days and other formats', () => {
        for (const value of [
            '2026-02-30',
            '2027-02-29',
            '2026-13-01',
            '01/10/2026',
            '2026-1-1',
            '',
            42,
            null,
        ])
            assert.equal(isValidIsoDate(value), false);
    });
});

describe('todayIn', () => {
    it('uses the timezone, not UTC', () => {
        // 02:30 UTC on Oct 2nd is still Oct 1st in São Paulo (UTC-3).
        const now = new Date('2026-10-02T02:30:00Z');

        assert.equal(todayIn('America/Sao_Paulo', now), '2026-10-01');
        assert.equal(todayIn('UTC', now), '2026-10-02');
    });
});

describe('weekdayIn', () => {
    it('returns the Portuguese weekday in the timezone', () => {
        const now = new Date('2026-10-01T15:00:00Z');

        assert.equal(weekdayIn('America/Sao_Paulo', now), 'quinta-feira');
    });
});
