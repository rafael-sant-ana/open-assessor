# Open-Assessor

An open-source personal finance assistant that lives in WhatsApp. Send it a message like
`gastei 50 no burger king` and it records the expense in a Google Spreadsheet you own.

Inspired by [meuassessor.com](https://meuassessor.com).

---

## Why

Most expense trackers fail because logging an expense takes too many taps. WhatsApp is
already open. The "message yourself" habit already exists. This just makes that habit
queryable.

## Non-goals

- Not a bank integration. It never touches your money, reads your statements, or asks
  for banking credentials.
- Not a multi-tenant SaaS. One deployment serves one person (or one household).
- Not an app. There is no UI beyond WhatsApp and the spreadsheet.

---

## Architecture

```
WhatsApp  ──▶  WhatsAppProvider  ──▶  MessageHandler  ──▶  LLMProvider
   ▲             (Baileys)                  │              (OpenAI)
   │                                        │
   └────────────────────────────────────────┴──▶  ExpenseRepository
                    reply                            (Google Sheets)
```

Three boundaries, one implementation each. `WhatsAppProvider` is an interface because
Baileys is an unofficial reverse-engineered client that breaks on WhatsApp updates, and
we may need to swap it for the official Cloud API. `LLMProvider` is an interface because
model vendors change. **Do not add more abstraction than this.** No factories, no plugin
registry, no dependency injection container.

### Stack

| Concern       | Choice                          |
| ------------- | ------------------------------- |
| Runtime       | Node.js 20+, TypeScript         |
| WhatsApp      | `@whiskeysockets/baileys`       |
| LLM           | to-define                       |
| Storage       | Google Sheets API v4            |
| Validation    | `zod`                           |
| Logging       | `pino`                          |

---

## Roadmap

### v0 — Walking skeleton

**Goal:** a message sent to the bot's WhatsApp number reaches an LLM and the reply comes
back in the same chat. No finance logic at all.

Done when:

- [ ] Pairing via QR code on first run; credentials persisted to disk
- [ ] Restarting the process does **not** require rescanning the QR
- [ ] Transient disconnects reconnect automatically with exponential backoff
- [ ] `loggedOut` is handled distinctly: log a clear error and exit, don't retry forever
- [ ] Only JIDs in `ALLOWED_JIDS` get a response; everything else is silently ignored
- [ ] Only 1:1 text messages are processed; groups, audio, images, stickers, reactions
      and status updates are ignored (logged at debug level)
- [ ] The bot's own outgoing messages never trigger a reply loop
- [ ] LLM errors (timeout, 429, 5xx) produce a human-readable reply, not silence
- [ ] Deployed somewhere that stays up, with a `Dockerfile` and documented deploy steps

> The allowlist is not optional. Without it, anyone who discovers the number gets a free
> LLM proxy billed to you.

**Open decision:** is v0 stateless (each message is an independent completion) or does it
carry conversation history? Pick one and write down why — it constrains v1.

### v1 — Expenses to spreadsheet

**Goal:** `gastei 50 no burger king` results in a correct new row in a Google Sheet.

Done when:

- [ ] Incoming text is classified: `expense` vs `other`. Non-expenses fall back to v0
      behavior (plain LLM reply), they are not force-parsed into rows.
- [ ] Expense extraction uses structured output against a schema, validated with `zod`.
      No regex parsing of free-form model text.
- [ ] Relative dates resolve correctly in `America/Sao_Paulo` (`ontem`, `sexta passada`,
      no date → today)
- [ ] The bot replies with what it saved, so a misparse is visible immediately
- [ ] `desfazer` (or equivalent) removes the last row this user created
- [ ] Missing amount or missing description → the bot asks, it does not guess
- [ ] A Sheets write failure is retried; if it still fails the user is told the expense
      was **not** saved
- [ ] Replaying the same WhatsApp message ID never creates a duplicate row

**Sheet schema** — sheet named `gastos`, first row is headers:

| Column        | Format                  | Notes                                    |
| ------------- | ----------------------- | ---------------------------------------- |
| `data`        | `DD/MM/YYYY`            | resolved date, not the message timestamp |
| `valor`       | number                  | BRL, decimal comma in display locale     |
| `descricao`   | text                    | as written by the user                   |
| `categoria`   | enum                    | see `src/domain/categories.ts`           |
| `criado_em`   | ISO 8601                | when the row was written                 |
| `message_id`  | text                    | WhatsApp message ID, for idempotency     |

**Open decision:** does v1 answer questions (`quanto gastei esse mês?`) or only write?
Reading is a separate capability with its own failure modes — defaulting to no.

### Later (not scheduled)

Audio transcription, receipt photos via vision, recurring bills, reminders, monthly
summaries, Postgres instead of Sheets.

---

## Getting started

### Prerequisites

- Node.js 20+
- A spare phone number for the bot (WhatsApp will be linked to it)
- An OpenAI API key
- A Google Cloud project with the Sheets API enabled (v1 only)

### Setup

```bash
git clone https://github.com/YOUR_USER/assessor.git
cd assessor
npm install
cp .env.example .env
```

Fill in `.env`, then:

```bash
npm run dev
```

A QR code prints to the terminal on first run. Scan it from the bot's phone:
**WhatsApp → Settings → Linked devices → Link a device**. Credentials are written to
`AUTH_STATE_PATH` and reused on subsequent runs.

### Google Sheets credentials (v1)

Use a **service account**, not the OAuth consent flow — it's a fraction of the work for a
single-user tool.

1. Google Cloud Console → create a service account → create a JSON key
2. Save the JSON somewhere outside the repo, point `GOOGLE_APPLICATION_CREDENTIALS` at it
3. Open your spreadsheet → Share → add the service account's email as **Editor**
4. Copy the spreadsheet ID from its URL into `SPREADSHEET_ID`

Step 3 is the one everybody forgets. Without it you get a `404` that looks like the
sheet doesn't exist.

### Environment

| Variable                         | Required | Description                                   |
| -------------------------------- | -------- | --------------------------------------------- |
| `OPENAI_API_KEY`                 | yes      |                                               |
| `OPENAI_MODEL`                   | no       | defaults to a small, cheap model               |
| `ALLOWED_JIDS`                   | yes      | comma-separated, e.g. `5531999999999@s.whatsapp.net` |
| `AUTH_STATE_PATH`                | no       | defaults to `./.auth`                          |
| `SPREADSHEET_ID`                 | v1       | from the spreadsheet URL                       |
| `GOOGLE_APPLICATION_CREDENTIALS` | v1       | path to the service account JSON               |
| `TIMEZONE`                       | no       | defaults to `America/Sao_Paulo`                |
| `LOG_LEVEL`                      | no       | defaults to `info`                             |

---

## Security

- `.auth/` contains credentials that grant **full access to the linked WhatsApp account**.
  It is gitignored. Never commit it, never put it in a public Docker image layer.
- The service account JSON key grants write access to every sheet it's been shared with.
  Keep it outside the repo.
- The allowlist is your only access control. There is no other authentication.
- Message contents are sent to OpenAI. If that's not acceptable for your data, swap in a
  local model behind `LLMProvider`.

## Known limitations

- Baileys is unofficial. WhatsApp can and does break it, and in principle can ban numbers
  for automated use. Use a spare number, don't blast messages.
- One WhatsApp session per deployment.
- No test coverage of the Baileys layer; it's exercised manually.

## Contributing

Issues and PRs welcome. Before writing code for a new capability, open an issue with:
a literal WhatsApp transcript of the intended behavior, the acceptance criteria including
at least three failure cases, and what's explicitly out of scope.

## License

MIT
