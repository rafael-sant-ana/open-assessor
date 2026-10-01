import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { MAX_AMOUNT_CENTS, formatBRL, toCents } from './money.js';

describe('toCents', () => {
    it('converts decimals to integer cents', () => {
        assert.equal(toCents(50), 5000);
        assert.equal(toCents(50.9), 5090);
    });

    it('does not suffer from float drift', () => {
        assert.equal(toCents(19.99), 1999);
        assert.equal(toCents(0.07), 7);
    });

    it('rejects non-positive, non-finite and non-number values', () => {
        for (const value of [0, -5, NaN, Infinity, '50', null, undefined])
            assert.equal(toCents(value), null);
    });

    it('rejects amounts that round to zero', () => {
        assert.equal(toCents(0.004), null);
    });

    it('rejects amounts above the cap', () => {
        assert.equal(toCents(MAX_AMOUNT_CENTS / 100), MAX_AMOUNT_CENTS);
        assert.equal(toCents(MAX_AMOUNT_CENTS / 100 + 0.01), null);
    });
});

describe('formatBRL', () => {
    it('formats cents with a decimal comma and thousands dot', () => {
        assert.equal(formatBRL(5090), 'R$ 50,90');
        assert.equal(formatBRL(123456), 'R$ 1.234,56');
    });
});
