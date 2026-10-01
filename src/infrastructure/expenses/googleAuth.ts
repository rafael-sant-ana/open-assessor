import { auth, sheets, type sheets_v4 } from '@googleapis/sheets';

export const SHEETS_SCOPE = 'https://www.googleapis.com/auth/spreadsheets';

export type GoogleCredentials =
    | { readonly credentials: { client_email: string; private_key: string } }
    | { readonly keyFile: string };

type Env = Record<string, string | undefined>;

/**
 * Service account credentials from `GOOGLE_SERVICE_ACCOUNT_JSON` (the key's JSON, raw or
 * base64 — handy for container secrets) or, failing that, the path in
 * `GOOGLE_APPLICATION_CREDENTIALS`.
 */
export function readGoogleCredentials(env: Env = process.env): GoogleCredentials {
    const inline = env.GOOGLE_SERVICE_ACCOUNT_JSON?.trim();
    if (inline) return { credentials: parseServiceAccount(inline) };

    const keyFile = env.GOOGLE_APPLICATION_CREDENTIALS?.trim();
    if (keyFile) return { keyFile };

    throw new Error(
        'Missing Google credentials: set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS. Check the .env.example',
    );
}

export function createSheetsClient(env: Env = process.env): sheets_v4.Sheets {
    return sheets({
        version: 'v4',
        auth: new auth.GoogleAuth({
            ...readGoogleCredentials(env),
            scopes: [SHEETS_SCOPE],
        }),
    });
}

function parseServiceAccount(raw: string): { client_email: string; private_key: string } {
    let parsed: unknown;
    try {
        const json = raw.startsWith('{') ? raw : Buffer.from(raw, 'base64').toString('utf8');
        parsed = JSON.parse(json);
    } catch {
        throw new Error(
            'GOOGLE_SERVICE_ACCOUNT_JSON must be the service account key JSON, raw or base64-encoded',
        );
    }

    const { client_email, private_key } = (parsed ?? {}) as Record<string, unknown>;
    if (typeof client_email !== 'string' || typeof private_key !== 'string')
        throw new Error(
            'GOOGLE_SERVICE_ACCOUNT_JSON is missing client_email or private_key. Use the JSON key downloaded for the service account',
        );

    return { client_email, private_key };
}
