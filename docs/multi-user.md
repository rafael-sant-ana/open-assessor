# Multi-user setup

Each user keeps their expenses in **their own Google Sheet**. Users and the sheet each one
uses are stored in MongoDB, so an admin can add people from the chat without redeploying.

## How it works

1. A new person sends `/meu-id` to the bot and gives the id to an admin.
2. The admin sends `/autorizar <id>`. A bare id is taken to be on the admin's own platform;
   `telegram:123` or `whatsapp:...` names it explicitly.
3. The new user creates a Google Sheet, shares it as **Editor** with the bot's service account
   (the bot prints the address), and sends `/planilha <link of the sheet>`.
4. The bot checks that it can open the sheet, creates the `gastos` tab, and from then on that
   user's expenses go there. Until a sheet is connected, the bot answers every message with
   these instructions instead of saving anything.

Admins can remove someone with `/remover <id>`. Their spreadsheet is left untouched.

| Command | Who | What |
| --- | --- | --- |
| `/meu-id` | anyone | shows your id |
| `/planilha <link>` | authorized users | connects your spreadsheet (no link: shows the instructions) |
| `/autorizar <id>` | admins | lets someone use the bot |
| `/remover <id>` | admins | revokes access |

## Railway

1. In the project, click **New → Database → Add MongoDB**.
2. On the bot service, add the variables:
   - `MONGODB_URL` = `${{MongoDB.MONGO_URL}}`
   - `ADMIN_USERS` = `telegram:<your id>`
3. Keep `GOOGLE_SERVICE_ACCOUNT_JSON` as it is: every user shares their sheet with that same
   service account.
4. Redeploy. The logs should show `Using MongoDB user storage`.

## Migrating from a single spreadsheet

Nothing is lost. On every start, each id in `ADMIN_USERS`, `ALLOWED_USERS` and `ALLOWED_JIDS`
that has no spreadsheet yet gets `SPREADSHEET_ID`. So keep `SPREADSHEET_ID` set and you keep
writing to your current sheet; new users connect their own with `/planilha`. A sheet someone
connected with `/planilha` is never replaced by `SPREADSHEET_ID`.

## Without MongoDB

Leave `MONGODB_URL` unset and the bot behaves as before: users come from `ADMIN_USERS` and
`ALLOWED_USERS`. `/autorizar` and `/planilha` still work, but are forgotten on restart.
