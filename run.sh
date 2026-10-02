#!/usr/bin/env bash
# Menu for the common project tasks. Pick by number, or pass the name directly:
#   ./run.sh          shows the menu
#   ./run.sh check    runs one task (bot, sheets, test, types, lint, format, check, sync)
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

run() {
    case "$1" in
        bot)    uv run open-assessor ;;
        sheets) uv run check-sheets ;;
        test)   uv run pytest ;;
        types)  uv run pyright ;;
        lint)   uv run ruff check ;;
        format) uv run ruff format && uv run ruff check --fix ;;
        check)  uv run ruff format --check && uv run ruff check && uv run pyright && uv run pytest -q ;;
        sync)   uv sync ;;
        *)      echo "Unknown task: $1" >&2; return 1 ;;
    esac
}

if [[ $# -gt 0 ]]; then
    run "$1"
    exit
fi

tasks=(bot sheets test types lint format check sync)
labels=(
    "Start the bot"
    "Check Google Sheets storage"
    "Run the tests"
    "Type check (pyright)"
    "Lint (ruff)"
    "Format and auto-fix"
    "Everything CI would run"
    "Install / update dependencies"
)

echo "open-assessor"
for i in "${!tasks[@]}"; do
    printf "  %d) %s\n" "$((i + 1))" "${labels[$i]}"
done
printf "  q) Quit\n\n"

read -rp "> " choice
[[ "$choice" == "q" || -z "$choice" ]] && exit 0

if [[ "$choice" =~ ^[0-9]+$ ]] && ((choice >= 1 && choice <= ${#tasks[@]})); then
    run "${tasks[$((choice - 1))]}"
else
    run "$choice"
fi
