/**
 * Checks that expenses can be saved, without involving an LLM or a chat platform:
 * clock, credentials, access to the spreadsheet, then the real AddExpense use case
 * (add → read back → duplicate protection → undo).
 *
 *   pnpm check:sheets          leaves the sheet as it found it
 *   pnpm check:sheets --keep   keeps the test row, to look at it in the spreadsheet
 */
import 'dotenv/config';

import AddExpense from '../src/application/usecases/AddExpense.js';
import { DEFAULT_TIMEZONE, todayIn } from '../src/domain/dates.js';
import { formatBRL } from '../src/domain/expenses/money.js';
import ExpenseRepositoryFactory from '../src/infrastructure/expenses/ExpenseRepositoryFactory.js';

const keep = process.argv.includes('--keep');
const timezone = process.env.TIMEZONE ?? DEFAULT_TIMEZONE;
const userId = 'script:check-sheets';
const messageKey = `script:check-sheets:${Date.now()}#0`;

let failed = false;

function ok(message: string) {
    console.log(`  ✔ ${message}`);
}

function fail(message: string, error?: unknown) {
    failed = true;
    console.log(`  ✘ ${message}`);
    if (error !== undefined) {
        const text = error instanceof Error ? error.message : String(error);
        console.log(`    ${text}`);
        const hint = hintFor(text);
        if (hint) console.log(`    → ${hint}`);
    }
}

function hintFor(message: string): string | undefined {
    if (/Token must be a short-lived token|iat and exp/i.test(message))
        return 'Your computer clock is wrong. Sync it (Windows: Settings → Time & language → Sync now).';
    if (/Invalid JWT Signature/i.test(message))
        return 'Google does not accept this key: it was deleted or disabled, or belongs to another service account. Create a new JSON key for the service account and replace the file.';
    if (/Missing Google credentials/i.test(message))
        return 'Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS in .env.';
    if (/ENOENT|no such file/i.test(message))
        return 'The file in GOOGLE_APPLICATION_CREDENTIALS does not exist. Check the path.';
    if (/not found|404/i.test(message))
        return 'Wrong SPREADSHEET_ID, or the spreadsheet is not shared with the service account email as Editor.';
    if (/permission|403/i.test(message))
        return 'Share the spreadsheet with the service account email as Editor, and enable the Google Sheets API in its project.';
    if (/unexpected headers/i.test(message))
        return 'A "gastos" tab already exists with a different header. Rename it or fix its header.';
    return undefined;
}

async function checkClock() {
    console.log('1. Clock');
    try {
        const response = await fetch('https://www.googleapis.com', {
            method: 'HEAD',
            signal: AbortSignal.timeout(10_000),
        });
        const remote = Date.parse(response.headers.get('date') ?? '');
        if (Number.isNaN(remote)) return ok('Could not read Google time, skipping');

        const skewSeconds = Math.round((Date.now() - remote) / 1000);
        if (Math.abs(skewSeconds) > 60)
            fail(`Your clock is ${Math.abs(skewSeconds)}s ${skewSeconds < 0 ? 'behind' : 'ahead of'} Google's`, 'Google rejects logins when the clock is off by more than a few minutes.');
        else ok(`In sync with Google (off by ${skewSeconds}s). Today is ${todayIn(timezone, new Date())} in ${timezone}`);
    } catch {
        ok('Could not reach Google to compare time, skipping');
    }
}

async function main() {
    console.log('Expense storage check\n');

    await checkClock();

    console.log('2. Storage');
    if (!process.env.SPREADSHEET_ID?.trim()) {
        fail('SPREADSHEET_ID is not set, so expenses would only be kept in memory');
        return;
    }

    let repository;
    try {
        ({ repository } = await ExpenseRepositoryFactory.create());
        ok('Authenticated and the "gastos" tab is ready');
    } catch (error) {
        fail('Could not open the spreadsheet', error);
        return;
    }

    console.log('3. Add an expense (through the AddExpense use case)');
    const addExpense = new AddExpense(repository, () => new Date(), timezone);
    const input = {
        userId,
        messageKey,
        amount: 12.34,
        description: 'teste do check-sheets',
        category: 'outros',
    };

    try {
        const result = await addExpense.execute(input);
        if (result.status !== 'saved') return fail(`Expected "saved", got "${result.status}"`, JSON.stringify(result));
        ok(`Saved ${formatBRL(result.expense.amountCents)} dated ${result.expense.date}`);
    } catch (error) {
        return fail('Writing to the spreadsheet failed', error);
    }

    console.log('4. Read it back');
    try {
        const today = todayIn(timezone, new Date());
        const found = await repository.listBy(userId, { from: today, to: today });
        const row = found.find((e) => e.messageKey === messageKey);
        if (row?.amountCents === 1234 && row.description === input.description) ok('Found it with the right amount and description');
        else fail('The expense was written but could not be read back correctly', JSON.stringify(found));
    } catch (error) {
        fail('Reading from the spreadsheet failed', error);
    }

    console.log('5. Replaying the same message');
    try {
        const replay = await addExpense.execute(input);
        if (replay.status === 'duplicate') ok('Reported as a duplicate, no second row');
        else fail(`Expected "duplicate", got "${replay.status}"`);
    } catch (error) {
        fail('Replay check failed', error);
    }

    console.log('6. Cleanup');
    if (keep) return ok('Kept the test row (--keep). Look for "teste do check-sheets" in the spreadsheet');
    try {
        const removed = await repository.removeLastBy(userId);
        if (removed?.messageKey === messageKey) ok('Removed the test row');
        else fail('Could not find the test row to remove. Delete "teste do check-sheets" by hand');
    } catch (error) {
        fail('Removing the test row failed. Delete "teste do check-sheets" by hand', error);
    }
}

await main();
console.log(failed ? '\nFAILED: expenses cannot be saved yet.' : '\nOK: expenses can be saved.');
process.exit(failed ? 1 : 0);
