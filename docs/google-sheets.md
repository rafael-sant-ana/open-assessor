# Google Sheets storage setup

open-assessor saves every expense as a row in a Google spreadsheet that you own. It talks to
the Sheets API with a **service account**: a robot Google identity that has access only to
the spreadsheets you share with it. That is much less work than the OAuth consent flow for a
single-user tool.

If `SPREADSHEET_ID` is not set, the app still runs but keeps expenses **in memory**: they
are lost when the process restarts, and it logs a warning at startup.

## Setup

### 1. Create a Google Cloud project and enable the Sheets API

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create a project
   (or pick an existing one).
2. Go to **APIs & Services → Library**, search for **Google Sheets API** and click
   **Enable**.

### 2. Create a service account and a key

1. Go to **IAM & Admin → Service Accounts → Create service account**. Any name works, for
   example `open-assessor`. No project roles are needed.
2. Open the new service account, go to **Keys → Add key → Create new key → JSON**. A JSON
   file is downloaded. It grants write access to every sheet shared with the account, so
   treat it like a password: keep it **outside the repository** and never put it in a Docker
   image layer.
3. Note the service account's email, which looks like
   `open-assessor@your-project.iam.gserviceaccount.com`.

### 3. Create the spreadsheet and share it with the service account

1. Create a new, empty spreadsheet in Google Sheets.
2. Click **Share**, paste the service account's email and give it the **Editor** role.

This is the step everybody forgets. Without it the API answers `404`, which looks like the
spreadsheet doesn't exist.

3. Copy the spreadsheet ID from its URL: the part between `/d/` and `/edit`.

```
https://docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit
```

### 4. Configure `.env`

```env
SPREADSHEET_ID="THIS_IS_THE_ID"
GOOGLE_APPLICATION_CREDENTIALS="./google-service-account.json"
```

`GOOGLE_APPLICATION_CREDENTIALS` is the path to the JSON key from step 2.

**On a container platform** there is usually no file to point at. Set
`GOOGLE_SERVICE_ACCOUNT_JSON` instead, to the **contents** of the JSON key (as a platform
secret). It can be the raw JSON or its base64 encoding, which is safer if your platform
mangles quotes and newlines:

```bash
base64 -w0 google-service-account.json   # Linux; on macOS use: base64 -i google-service-account.json
```

If both variables are set, `GOOGLE_SERVICE_ACCOUNT_JSON` wins.

### 5. Check the setup, then start the bot

```bash
uv run check-sheets   # adds a test row, reads it back and removes it
uv run open-assessor
```

You should see `Using Google Sheets expense storage` in the logs. On the first run the app
creates the `gastos` tab, with its header and number formats. Send `gastei 50 no burger
king` and a new row appears.

## The `gastos` tab

The bot owns this tab. It only appends rows (and deletes one when you undo an expense); it
never sorts or rewrites them.

| Column        | Content                                                          |
| ------------- | ---------------------------------------------------------------- |
| `data`        | the expense day, a real date shown as `DD/MM/YYYY`               |
| `valor`       | the amount in BRL, a real number shown as currency                |
| `descricao`   | text, as written by you                                          |
| `categoria`   | one of the categories in `src/open_assessor/domain/categories.py`              |
| `criado_em`   | when the row was written, ISO 8601                               |
| `message_key` | `platform:chatId:messageId#n`, used so a replayed message never creates a second row |
| `user_id`     | `platform:authorId`, who the expense belongs to                   |

`data` and `valor` are typed cells, so `SUM`, pivot tables and charts work on them directly.

### Adding charts and summaries

Put them on **other tabs**, and have them reference whole columns such as `gastos!A:G`, so
they keep working as rows are added or an expense is undone. Don't type into the `gastos`
tab, don't rename or reorder its columns, and don't sort it.

## Behavior

- **Existing tab.** If a `gastos` tab already exists with exactly the header above, it is
  used as is. If its header is different the app refuses to start and never overwrites it.
- **Retries.** Rate limits (`429`), server errors and network errors are retried up to
  three times with a short backoff. If it still fails, the bot tells you the expense was
  **not** saved.
- **Single process.** The bot remembers which messages it already saved in memory, loaded
  once from the sheet at startup. Run one instance per spreadsheet.
- **Formulas are not run.** Values are written as plain data, so a description such as
  `=HYPERLINK(...)` is stored as text and never executed.

## Troubleshooting

| Symptom | Cause and fix |
| ------- | ------------- |
| `Missing Google credentials: set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS` | `SPREADSHEET_ID` is set but no credentials are. Set one of the two variables from step 4. |
| `GOOGLE_SERVICE_ACCOUNT_JSON must be the service account key JSON, raw or base64-encoded` | The value is not valid JSON. Paste the whole file contents, or its base64 encoding, with no extra characters. |
| `GOOGLE_SERVICE_ACCOUNT_JSON is missing client_email or private_key` | The JSON is not a service account key. Download a new key as described in step 2. |
| The app exits at startup with `404` / `Requested entity was not found` | The spreadsheet ID is wrong, or the spreadsheet was not shared with the service account as **Editor** (step 3). |
| `403` / `The caller does not have permission` | The service account has only Viewer access. Change it to **Editor**. |
| `403` / `Google Sheets API has not been used in project ... or it is disabled` | Enable the Google Sheets API in the same project that owns the service account (step 1). |
| `The "gastos" tab has unexpected headers` | A tab named `gastos` exists with a different header. Rename or delete it, or fix its header to match the table above. |
| `invalid_grant` or `Invalid JWT Signature` | The key was deleted or revoked, or the machine's clock is badly off. Create a new key and check the system time. |
| The startup warning `SPREADSHEET_ID is not set` | Expected when running without a sheet; expenses are kept in memory only. |
