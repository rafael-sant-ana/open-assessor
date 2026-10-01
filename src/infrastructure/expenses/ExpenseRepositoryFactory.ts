import type { sheets_v4 } from '@googleapis/sheets';
import type { ExpenseRepository } from '../../providers/ExpenseRepository.js';
import { createSheetsClient } from './googleAuth.js';
import GoogleSheetsExpenseRepository from './GoogleSheetsExpenseRepository.js';
import InMemoryExpenseRepository from './InMemoryExpenseRepository.js';

type Env = Record<string, string | undefined>;

export default class ExpenseRepositoryFactory {
    /**
     * Google Sheets when `SPREADSHEET_ID` is set, otherwise memory (lost on restart).
     * Also validates the sheet, so a misconfiguration fails at startup, not on the first expense.
     */
    static async create(
        env: Env = process.env,
        createClient: (env: Env) => sheets_v4.Sheets = createSheetsClient,
    ): Promise<{ name: string; persistent: boolean; repository: ExpenseRepository }> {
        const spreadsheetId = env.SPREADSHEET_ID?.trim();

        if (!spreadsheetId)
            return {
                name: 'in-memory',
                persistent: false,
                repository: new InMemoryExpenseRepository(),
            };

        return {
            name: 'Google Sheets',
            persistent: true,
            repository: await GoogleSheetsExpenseRepository.create(
                createClient(env),
                spreadsheetId,
            ),
        };
    }
}
