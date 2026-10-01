import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import ExpenseRepositoryFactory from './ExpenseRepositoryFactory.js';
import FakeSheets from './FakeSheets.js';
import GoogleSheetsExpenseRepository from './GoogleSheetsExpenseRepository.js';
import InMemoryExpenseRepository from './InMemoryExpenseRepository.js';

describe('ExpenseRepositoryFactory', () => {
    it('falls back to memory when SPREADSHEET_ID is not set', async () => {
        const result = await ExpenseRepositoryFactory.create({});

        assert.equal(result.persistent, false);
        assert.ok(result.repository instanceof InMemoryExpenseRepository);
    });

    it('treats a blank SPREADSHEET_ID as not set', async () => {
        const result = await ExpenseRepositoryFactory.create({ SPREADSHEET_ID: '  ' });

        assert.ok(result.repository instanceof InMemoryExpenseRepository);
    });

    it('uses Google Sheets and prepares the tab when SPREADSHEET_ID is set', async () => {
        const fake = new FakeSheets();
        let receivedEnv: unknown;

        const result = await ExpenseRepositoryFactory.create({ SPREADSHEET_ID: 'abc' }, (env) => {
            receivedEnv = env;
            return fake.asClient();
        });

        assert.equal(result.persistent, true);
        assert.ok(result.repository instanceof GoogleSheetsExpenseRepository);
        assert.ok(fake.tabs.has('gastos'));
        assert.deepEqual(receivedEnv, { SPREADSHEET_ID: 'abc' });
        assert.equal(fake.callsTo('spreadsheets.get')[0].spreadsheetId, 'abc');
    });

    it('fails at startup when the credentials are missing', async () => {
        await assert.rejects(
            ExpenseRepositoryFactory.create({ SPREADSHEET_ID: 'abc' }),
            /GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS/,
        );
    });
});
