import asyncio
import os
import re
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telethon import TelegramClient, events

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "ticker_digest.db"

STOPWORDS = {
    "THE",
    "AND",
    "FOR",
    "WITH",
    "THIS",
    "THAT",
    "FROM",
    "YOUR",
    "ABOUT",
    "WHAT",
    "WHEN",
    "WHERE",
    "HOW",
    "WILL",
    "HAVE",
    "JUST",
    "LIKE",
    "COIN",
    "TOKEN",
    "GROUP",
    "CHANNEL",
}

TICKER_REGEX = re.compile(r"(?:\$|#)?\b([A-Z]{2,6})\b")


def load_config():
    load_dotenv()
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    session = os.getenv("TELEGRAM_SESSION", "ticker_session")
    target_chat = os.getenv("TARGET_CHAT", "me")
    digest_hour = int(os.getenv("DIGEST_HOUR", "9"))
    digest_minute = int(os.getenv("DIGEST_MINUTE", "0"))

    if not api_id or not api_hash:
        raise RuntimeError("Missing TELEGRAM_API_ID or TELEGRAM_API_HASH")

    return {
        "api_id": int(api_id),
        "api_hash": api_hash,
        "session": session,
        "target_chat": target_chat,
        "digest_hour": digest_hour,
        "digest_minute": digest_minute,
    }


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                chat_title TEXT,
                message_id INTEGER NOT NULL,
                sender_id INTEGER,
                message_date TEXT NOT NULL,
                text TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS messages_unique
            ON messages(chat_id, message_id)
            """
        )
        conn.commit()


def extract_tickers(text: str) -> list[str]:
    if not text:
        return []
    candidates = [match.group(1) for match in TICKER_REGEX.finditer(text.upper())]
    return [ticker for ticker in candidates if ticker not in STOPWORDS]


def store_message(message):
    if not message.message:
        return
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO messages
                (chat_id, chat_title, message_id, sender_id, message_date, text)
            VALUES
                (?, ?, ?, ?, ?, ?)
            """,
            (
                message.chat_id,
                getattr(message.chat, "title", None),
                message.id,
                message.sender_id,
                message.date.isoformat(),
                message.message,
            ),
        )
        conn.commit()


def load_messages_since(since: datetime):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute(
            """
            SELECT chat_title, message_date, text
            FROM messages
            WHERE message_date >= ?
            ORDER BY message_date ASC
            """,
            (since.isoformat(),),
        )
        return cursor.fetchall()


def build_digest(since: datetime) -> str:
    rows = load_messages_since(since)
    ticker_counts: Counter[str] = Counter()
    ticker_samples: dict[str, list[str]] = defaultdict(list)

    for chat_title, message_date, text in rows:
        tickers = extract_tickers(text or "")
        for ticker in tickers:
            ticker_counts[ticker] += 1
            if len(ticker_samples[ticker]) < 3:
                preview = (text or "").strip().replace("\n", " ")
                if preview:
                    ticker_samples[ticker].append(preview[:160])

    if not ticker_counts:
        return "Daily Telegram Ticker Digest\n\nNo ticker mentions found in the last 24 hours."

    lines = [
        "Daily Telegram Ticker Digest",
        f"Window: {since.strftime('%Y-%m-%d %H:%M')} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    for ticker, count in ticker_counts.most_common(15):
        lines.append(f"${ticker} — {count} mentions")
        for sample in ticker_samples[ticker]:
            lines.append(f"  • {sample}")
        lines.append("")

    return "\n".join(lines).strip()


async def run_ingest(client: TelegramClient):
    init_db()

    @client.on(events.NewMessage)
    async def handler(event):
        store_message(event.message)

    print("Ingestion running. Press Ctrl+C to stop.")
    await client.run_until_disconnected()


async def run_digest(client: TelegramClient, target_chat: str):
    init_db()
    since = datetime.now() - timedelta(days=1)
    digest = build_digest(since)
    await client.send_message(target_chat, digest)
    print("Digest sent.")


async def run_scheduler(client: TelegramClient, target_chat: str, hour: int, minute: int):
    init_db()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_digest,
        "cron",
        hour=hour,
        minute=minute,
        args=[client, target_chat],
    )
    scheduler.start()
    print(f"Scheduler running. Daily digest at {hour:02d}:{minute:02d}.")
    await client.run_until_disconnected()


async def main():
    config = load_config()
    client = TelegramClient(config["session"], config["api_id"], config["api_hash"])

    mode = (os.getenv("MODE") or "").strip().lower()
    if len(os.sys.argv) > 1:
        mode = os.sys.argv[1].strip().lower()

    if mode not in {"ingest", "digest", "schedule"}:
        raise RuntimeError("Usage: python app.py [ingest|digest|schedule]")

    async with client:
        if mode == "ingest":
            await run_ingest(client)
        elif mode == "digest":
            await run_digest(client, config["target_chat"])
        else:
            await run_scheduler(
                client,
                config["target_chat"],
                config["digest_hour"],
                config["digest_minute"],
            )


if __name__ == "__main__":
    asyncio.run(main())
