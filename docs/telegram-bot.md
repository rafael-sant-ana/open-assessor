# Telegram bot setup

open-assessor can talk to you over Telegram instead of WhatsApp. It uses a regular
Telegram bot with long polling, so you don't need a public URL, a spare phone number or a
QR code.

Only **one chat provider runs at a time**. `CHAT_PROVIDER` picks it (`whatsapp` is the
default, `telegram` enables this guide). To use both platforms you need two separate
deployments.

## Setup

### 1. Create the bot with @BotFather

1. In Telegram, open a chat with [@BotFather](https://t.me/BotFather).
2. Send `/newbot`.
3. Choose a display name and a username (the username must end in `bot`).
4. BotFather replies with the bot token, which looks like
   `123456789:PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE`. Copy it and treat it like a password.

### 2. Configure `.env`

```bash
cp .env.example .env   # skip if you already have a .env
```

Set these variables in `.env`:

```env
CHAT_PROVIDER="telegram"
TELEGRAM_BOT_TOKEN="PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE"
```

`TELEGRAM_BOT_TOKEN` is required when `CHAT_PROVIDER=telegram`. You also need an LLM key
(for example `OPENAI_API_KEY`) as described in the README.

The app refuses to start if both `ALLOWED_USERS` and `ALLOWED_JIDS` are empty, so keep a
placeholder value in one of them for now. You will replace it in step 5.

### 3. Start the bot

```bash
npm run dev
```

You should see `Using telegram chat provider` in the logs, followed by
`Telegram conectado!` and `The bot is ready!`.

### 4. Discover your Telegram user id

Open a private chat with your new bot (search for its username and press **Start**) and
send:

```
/meu-id
```

The bot replies with:

```
Seu ID é:
> 123456789
```

That number is your numeric Telegram user id. This command works **even if you are not
allowed yet**; it is answered before the allowlist check. (`/meu-jid` is accepted as an
alias.)

### 5. Add yourself to `ALLOWED_USERS`

Entries use the format `platform:id`, comma-separated. For Telegram the platform is
`telegram`. Mix platforms freely:

```env
ALLOWED_USERS="whatsapp:5531999999999@s.whatsapp.net,telegram:123456789"
```

Telegram-only example:

```env
ALLOWED_USERS="telegram:123456789"
```

Stop the bot (`Ctrl+C`) and start it again so the new value is loaded.

### 6. Verify

Send any text message to the bot, for example `gastei 50 no burger king`. You should see
the typing indicator and then a reply. If nothing happens, see Troubleshooting below.

## Behavior

- **Private chats and text only.** Messages from groups, supergroups and channels are
  ignored, as are non-text messages (photos, voice notes, stickers, files).
- **Long replies are split.** Telegram limits a message to 4096 characters. Longer replies
  are sent as several messages, breaking at a newline when possible.
- **Typing indicator.** While the LLM is generating a response the bot shows "typing...",
  refreshed every 4 seconds until the reply is sent.
- **Allowlist.** Messages from users not in `ALLOWED_USERS` are silently ignored (only
  `/meu-id` is answered).

## Troubleshooting

| Symptom | Cause and fix |
| ------- | ------------- |
| The app exits at startup with an error from Telegram (e.g. `401: Unauthorized`) | The token is invalid or was revoked. Check `TELEGRAM_BOT_TOKEN` for typos or extra spaces, or generate a new one with `/token` in @BotFather. The token is validated at startup, so a bad one fails immediately. |
| `Missing required environment variable: TELEGRAM_BOT_TOKEN` | `CHAT_PROVIDER` is `telegram` but the token is not set in `.env`. |
| `Unsupported CHAT_PROVIDER` | The value must be exactly `whatsapp` or `telegram`. |
| The bot is silent, but `/meu-id` works | Your id is not in `ALLOWED_USERS`, or the entry is malformed. It must be `telegram:<id>` with the numeric id and no spaces inside the entry. Restart after editing `.env`. Set `LOG_LEVEL="debug"` to see `Ignoring message from unauthorized user`. |
| The bot ignores everything, including `/meu-id` | You are messaging from a group or sending non-text content. Use a private chat with plain text. |
| `409 Conflict: terminated by other getUpdates request` in the logs | Two instances are polling with the same token (for example a second terminal, a leftover process or a deployed copy). Stop all but one. |
| Same 409 or no updates, and only one instance is running | A webhook is set on the bot. Long polling requires that no webhook is configured. Remove it by opening `https://api.telegram.org/bot<TOKEN>/deleteWebhook` in a browser, with your real token in place of `<TOKEN>`. |
