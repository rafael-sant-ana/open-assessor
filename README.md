# Open-Assessor

An open-source personal finance assistant that lives in your chat app. Send it a message
like `gastei 50 no burger king` and it records the expense in a Google Spreadsheet you own.

It runs on Telegram today. WhatsApp support is coming back through a separate gateway
(a small Node service around Baileys that the Python app talks to over gRPC).

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
- Not an app. There is no UI beyond the chat and the spreadsheet.

---

## Architecture

```
Telegram  ──▶  ChatProvider  ──▶  MessageHandler  ──▶  LLMProvider
   ▲         (python-telegram-bot)        │       (OpenAI / Claude / Gemini)
   │                                      │
   └──────────────────────────────────────┴──▶  ExpenseRepository
                    reply                          (Google Sheets)
```

Three boundaries. `ChatProvider` is an interface because chat platforms come and go:
Telegram today, WhatsApp through a gateway next. `LLMProvider` is an interface because model vendors change.
`ExpenseRepository` is an interface because storage will move from memory to Google Sheets
(and possibly Postgres later). **Do not add more abstraction than this.** No plugin
registry, no dependency injection container.

The model never touches storage directly. It calls tools (`add_expense`, `list_expenses`),
which are thin adapters over the use cases in `src/open_assessor/application/usecases/`; the use cases
hold the business rules and talk to `ExpenseRepository`.

### Stack

| Concern       | Choice                          |
| ------------- | ------------------------------- |
| Runtime       | Python 3.13+, managed with `uv` |
| Chat          | `python-telegram-bot`           |
| LLM           | OpenAI, Anthropic or Gemini SDK |
| Storage       | Google Sheets API v4            |
| Checks        | `pytest`, `pyright` (strict), `ruff` |
| Logging       | standard `logging`              |

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
- [ ] Expense extraction uses structured output against a schema, validated against that schema.
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
| `data`        | date cell, `DD/MM/YYYY` | resolved date, not the message timestamp |
| `valor`       | number                  | BRL, decimal comma in display locale     |
| `descricao`   | text                    | as written by the user                   |
| `categoria`   | enum                    | see `src/open_assessor/domain/categories.py` |
| `criado_em`   | ISO 8601                | when the row was written                 |
| `message_key` | text                    | `platform:chatId:messageId#n`, for idempotency |
| `user_id`     | text                    | `platform:authorId`, who the expense belongs to |

**Open decision:** does v1 answer questions (`quanto gastei esse mês?`) or only write?
Reading is a separate capability with its own failure modes — defaulting to no.

### Later (not scheduled)

Audio transcription, receipt photos via vision, recurring bills, reminders, monthly
summaries, Postgres instead of Sheets.

---

## Getting started

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (it installs the right Python for you)
- A Telegram bot token from @BotFather
- An OpenAI, Anthropic or Gemini API key
- A Google Cloud project with the Sheets API enabled (v1 only)

### Setup

```bash
git clone https://github.com/rafael-sant-ana/open-assessor.git
cd open-assessor
uv sync
cp .env.example .env
```

Fill in `.env` (the [Telegram bot setup guide](docs/telegram-bot.md) walks through it), then:

```bash
uv run open-assessor
```

### Development

```bash
uv run pytest         # tests
uv run pyright        # type check (strict)
uv run ruff check     # lint
uv run ruff format    # format
uv run check-sheets   # verify Google Sheets storage without an LLM
```

### Google Sheets credentials (v1)

Use a **service account**, not the OAuth consent flow — it's a fraction of the work for a
single-user tool.

1. Google Cloud Console → enable the Google Sheets API → create a service account → create
   a JSON key
2. Save the JSON somewhere outside the repo, point `GOOGLE_APPLICATION_CREDENTIALS` at it
   (or put its contents in `GOOGLE_SERVICE_ACCOUNT_JSON` on platforms without files)
3. Open your spreadsheet → Share → add the service account's email as **Editor**
4. Copy the spreadsheet ID from its URL into `SPREADSHEET_ID`

Step 3 is the one everybody forgets. Without it you get a `404` that looks like the
sheet doesn't exist. The full walkthrough, with troubleshooting, is in the
[Google Sheets setup guide](docs/google-sheets.md).


### Environment

| Variable                         | Required | Description                                   |
| -------------------------------- | -------- | --------------------------------------------- |
| `OPENAI_API_KEY`                 | yes*     | one LLM key is required                        |
| `OPENAI_MODEL`                   | no       | defaults to a small, cheap model               |
| `ANTHROPIC_API_KEY`              | no       | alternative to OpenAI/Gemini (priority: OpenAI, Anthropic, Gemini) |
| `ANTHROPIC_MODEL`                | no       | defaults to `claude-haiku-4-5-20251001`        |
| `GEMINI_API_KEY`                 | no       | alternative to OpenAI/Anthropic                |
| `GEMINI_MODEL`                   | no       | defaults to `gemini-3.6-flash`                 |
| `CHAT_PROVIDER`                  | no       | chat platform: `telegram` (default)            |
| `TELEGRAM_BOT_TOKEN`             | yes      | bot token from @BotFather                      |
| `ALLOWED_USERS`                  | yes*     | comma-separated `platform:id`, e.g. `telegram:123456` |
| `ALLOWED_JIDS`                   | yes*     | WhatsApp JIDs (*one of the two is required); comma-separated, e.g. `5531999999999@s.whatsapp.net` |
| `SPREADSHEET_ID`                 | v1       | from the spreadsheet URL; without it expenses are kept in memory only |
| `GOOGLE_APPLICATION_CREDENTIALS` | v1*      | path to the service account JSON (*one of this and `GOOGLE_SERVICE_ACCOUNT_JSON` when `SPREADSHEET_ID` is set) |
| `GOOGLE_SERVICE_ACCOUNT_JSON`    | v1*      | the service account JSON itself, raw or base64; wins over the path |
| `TIMEZONE`                       | no       | defaults to `America/Sao_Paulo`                |
| `LOG_LEVEL`                      | no       | defaults to `info`                             |

---

## Security

- The Telegram bot token lets anyone control the bot. Keep it in `.env`, which is
  gitignored.
- The service account JSON key grants write access to every sheet it's been shared with.
  Keep it outside the repo.
- The allowlist is your only access control. There is no other authentication.
- Message contents are sent to the configured LLM provider. If that's not acceptable for
  your data, swap in a local model behind `LLMProvider`.

## Known limitations

- WhatsApp is not available until the gateway lands. When it does, it will use Baileys, an
  unofficial client: WhatsApp can break it and in principle ban numbers for automated use.
- Without `SPREADSHEET_ID`, expenses are kept in memory and lost when the process
  restarts. With it they go to Google Sheets. Run one instance per spreadsheet.
- One chat platform per deployment.

## Contributing

Issues and PRs welcome. Before writing code for a new capability, open an issue with:
a literal chat transcript of the intended behavior, the acceptance criteria including
at least three failure cases, and what's explicitly out of scope.

## License

MIT
