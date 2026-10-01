import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import GetCurrentDateTool from './GetCurrentDateTool.js';

describe('GetCurrentDateTool', () => {
    it('returns the day and weekday in the configured timezone', async () => {
        // 02:30 UTC on Oct 2nd is still Thursday Oct 1st in São Paulo.
        const tool = new GetCurrentDateTool(
            () => new Date('2026-10-02T02:30:00Z'),
            'America/Sao_Paulo',
        );

        assert.deepEqual(JSON.parse(await tool.execute()), {
            date: '2026-10-01',
            weekday: 'quinta-feira',
            timezone: 'America/Sao_Paulo',
        });
    });

    it('reads the clock on every call, so a long-running process never goes stale', async () => {
        let now = new Date('2026-10-01T15:00:00Z');
        const tool = new GetCurrentDateTool(() => now, 'America/Sao_Paulo');

        const first = JSON.parse(await tool.execute()).date;
        now = new Date('2026-10-02T15:00:00Z');
        const second = JSON.parse(await tool.execute()).date;

        assert.equal(first, '2026-10-01');
        assert.equal(second, '2026-10-02');
    });
});
