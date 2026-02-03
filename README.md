# Telegram Ticker Digest (Free)

This project collects messages from your Telegram groups/channels, extracts ticker mentions (e.g. `$BTC`), and sends you a daily digest at **9:00 AM**. It uses **your Telegram user account** (MTProto) so it can access groups/channels you already belong to.

> **Why this design?** Telegram bots can only see messages in chats they are added to. Using a user account via Telethon gives you the full access you asked for, while staying free.

## Features
- Continuous message ingestion from all joined groups/channels.
- Ticker extraction and mention counts.
- Daily digest at 09:00 (local time) sent to your Telegram **Saved Messages** (or a target chat).
- SQLite storage (no extra services required).

## Requirements
- Python 3.10+
- Telegram API credentials (free)

## Setup
1. Create an app at https://my.telegram.org/apps and grab `API_ID` and `API_HASH`.
2. Copy the example env file and fill it in:
   ```bash
   cp .env.example .env
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
### 1) Start ingestion (keeps running)
```bash
python app.py ingest
```
This connects your account, listens to new messages, and stores them in `data/ticker_digest.db`.

### 2) Run a one-off daily digest
```bash
python app.py digest
```
This generates a digest for the last 24 hours and sends it to your **Saved Messages** (or the chat you set).

### 3) Run the built-in scheduler (daily at 09:00)
```bash
python app.py schedule
```
This keeps running and sends a digest every day at 09:00.

## Configuration
All config is via environment variables:

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_API_ID` | ✅ | Telegram API ID from my.telegram.org |
| `TELEGRAM_API_HASH` | ✅ | Telegram API hash |
| `TELEGRAM_SESSION` | ✅ | Session file name (e.g. `ticker_session`) |
| `TARGET_CHAT` | ❌ | Chat ID or username to send digest to (default: `me`) |
| `DIGEST_HOUR` | ❌ | Digest hour in 24h format (default: `9`) |
| `DIGEST_MINUTE` | ❌ | Digest minute (default: `0`) |

## Notes
- First run will prompt for your phone number and login code.
- For best results, leave ingestion running 24/7 and the scheduler running in a separate process (or use cron for `digest`).
- Ticker extraction matches `$ABC`, `ABC`, and `#ABC` (2-6 letters), and filters obvious stopwords.

## Free Hosting Ideas
- Local machine + cron
- Always-free VM (Oracle Cloud Free Tier)
- Home server/Raspberry Pi

## Disclaimer
Use responsibly and respect Telegram’s Terms of Service. Only access chats you are legitimately part of.
