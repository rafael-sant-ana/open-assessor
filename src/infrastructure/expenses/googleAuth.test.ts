import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { createSheetsClient, readGoogleCredentials } from './googleAuth.js';

const key = { client_email: 'bot@project.iam.gserviceaccount.com', private_key: 'PRIVATE', extra: 1 };
const json = JSON.stringify(key);
const expected = { client_email: key.client_email, private_key: key.private_key };

describe('readGoogleCredentials', () => {
    it('reads the raw JSON from GOOGLE_SERVICE_ACCOUNT_JSON', () => {
        assert.deepEqual(readGoogleCredentials({ GOOGLE_SERVICE_ACCOUNT_JSON: json }), {
            credentials: expected,
        });
    });

    it('accepts the JSON base64-encoded', () => {
        const base64 = Buffer.from(json).toString('base64');

        assert.deepEqual(readGoogleCredentials({ GOOGLE_SERVICE_ACCOUNT_JSON: base64 }), {
            credentials: expected,
        });
    });

    it('falls back to the key file path', () => {
        assert.deepEqual(readGoogleCredentials({ GOOGLE_APPLICATION_CREDENTIALS: './key.json' }), {
            keyFile: './key.json',
        });
    });

    it('prefers the inline JSON over the path', () => {
        const result = readGoogleCredentials({
            GOOGLE_SERVICE_ACCOUNT_JSON: json,
            GOOGLE_APPLICATION_CREDENTIALS: './key.json',
        });

        assert.ok('credentials' in result);
    });

    it('ignores blank values and names both variables when nothing is set', () => {
        assert.throws(
            () => readGoogleCredentials({ GOOGLE_SERVICE_ACCOUNT_JSON: '  ', GOOGLE_APPLICATION_CREDENTIALS: '' }),
            /GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS/,
        );
    });

    it('rejects JSON that is not valid, without echoing it', () => {
        assert.throws(
            () => readGoogleCredentials({ GOOGLE_SERVICE_ACCOUNT_JSON: '{oops PRIVATE' }),
            (err: Error) => /raw or base64/.test(err.message) && !err.message.includes('PRIVATE'),
        );
    });

    it('rejects a key without client_email or private_key', () => {
        assert.throws(
            () => readGoogleCredentials({ GOOGLE_SERVICE_ACCOUNT_JSON: '{"client_email":"a"}' }),
            /client_email or private_key/,
        );
    });
});

describe('createSheetsClient', () => {
    it('builds a client without touching the network', () => {
        const client = createSheetsClient({ GOOGLE_SERVICE_ACCOUNT_JSON: json });

        assert.equal(typeof client.spreadsheets.values.append, 'function');
    });
});
