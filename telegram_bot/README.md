# Attendix Telegram Bot

An additive, standalone Telegram bot integration for **Attendix**, providing fast and secure access to MITS IMS student attendance records, course metrics, and bunk advice calculations.

---

## 🌟 Overview & Architecture

The Telegram Bot is engineered as a **purely additive application** located strictly in `telegram_bot/`. It reuses the underlying MITS IMS scraping and parsing engine without altering, renaming, or breaking the existing Attendix web application, API routes, or web deployment manifests (`Dockerfile`, `Procfile`, `render.yaml`, `vercel.json`).

### Key Features
- **MITS IMS Authentication (`/login`)**: Direct validation with the real MITS IMS portal (`mitsims.in`).
- **Comprehensive Attendance Reports (`/attendance`)**: Overall percentage, aggregate class counters (attended/conducted), and course-by-course breakdown with status indicators:
  - 🟢 **Safe Zone**: $\ge 75\%$
  - 🟡 **Condonation / Warning Zone**: $65\% - 74.99\%$
  - 🔴 **Detention Risk / Critical Zone**: $< 65\%$
- **Subject Attendance (`/subjects`)**: Interactive subject explorer with pagination and detailed metrics.
- **Bunk & Target Advice (`/bunk`)**: Accurate calculations for $75\%$, $80\%$, $85\%$, $90\%$, and Custom Targets:
  - **Bunks Available**: $\lfloor (A / T) - C \rfloor$
  - **Classes Needed to Reach Target**: $\max(0, \lceil (T \times C - A) / (1 - T) \rceil)$
- **User Privacy & Security (`/logout`, `/delete_data`)**:
  - Full data isolation per Telegram ID.
  - Passwords encrypted at rest using AES-GCM / Fernet.
  - Automatic deletion of password messages in Telegram chats.
  - Strict refusal of login commands in public/group chats.

> **Menu Policy Note:** In accordance with the Attendix Bot specifications, the bot's interface strictly omits the following actions (which remain exclusively available on the Attendix web dashboard):
> - ❌ *Download PDF Report*
> - ❌ *Copy Summary*
> - ❌ *Refresh Attendance* (the `/attendance` command automatically fetches the latest data or serves fresh cache).

---

## 🚀 Setup & Local Installation

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14.
- Internet connectivity to reach `http://mitsims.in`.

### 2. Create a Telegram Bot via @BotFather
1. Open Telegram and search for [`@BotFather`](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to choose a name and username (e.g., `AttendixMitsBot`).
3. Copy the **HTTP API Token** provided by BotFather (looks like `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`).

### 3. Install Dependencies
Navigate to the `telegram_bot` directory and install the dedicated dependency requirements:

```bash
cd telegram_bot
pip install -r requirements.txt
```

*(Optional)* If you wish to enable the secondary Playwright browser fallback (the primary scraper uses ultra-fast direct HTTP requests):
```bash
playwright install chromium
```

### 4. Configure Environment Variables
Copy the `.env.example` file to create your local `.env`:

```bash
cp .env.example .env
```

Open `.env` and fill in your variables:

```ini
# 1. Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN=your_token_from_botfather_here

# 2. IMS Base URL
IMS_BASE_URL=http://mitsims.in

# 3. Database Path (SQLite)
DATABASE_PATH=telegram_bot.db

# 4. Credential Encryption Key (Optional)
# Generate a 32-byte Fernet key with:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# If left empty, a key will be auto-generated in telegram_bot/.encryption_key
CREDENTIAL_ENCRYPTION_KEY=

# 5. Performance and Caching
CACHE_TTL_SECONDS=300
MAX_CONCURRENT_SCRAPES=2
```

---

## 🏃 Running the Bot

Run the bot directly using Python:

```bash
# From within the telegram_bot/ folder:
python bot.py

# Or from the repository root:
python telegram_bot/bot.py
```

You will see:
```text
INFO - Database initialized at telegram_bot.db
INFO - Starting Attendix Telegram Bot polling...
```

Open Telegram, search for your bot username, and send `/start`!

---

## 🧪 Running the Test Suite

The test suite validates data normalization, threshold categorization, edge cases, bunk math, concurrency, and multi-user isolation:

```bash
# Run all tests with verbose output:
pytest telegram_bot/tests/ -v
```

All tests mock the MITS IMS portal to ensure predictable and reproducible execution without making unauthorized network requests or exposing student credentials.

---

## ☁️ Deployment Guide & Hosting Evaluation

The Telegram Bot is a **long-running background process** (polling Telegram or running a webhook). Unlike serverless web apps (Vercel), Telegram bots need an active worker process and persistent storage for SQLite.

### 1. Recommended Deployment Options

#### Option A: Dedicated VPS (Oracle Cloud Free Tier, Hetzner, DigitalOcean) — *Most Recommended*
- **Why**: Permanent free tier (e.g., Oracle Cloud Always Free 4-core Ampere ARM / 24GB RAM or AMD micro instances) provides permanent persistent storage, unlimited run time, and full root access for Playwright and Chromium.
- **Process**:
  1. Clone repository.
  2. Setup Python virtual environment: `python3 -m venv venv && source venv/bin/activate`.
  3. Install dependencies: `pip install -r telegram_bot/requirements.txt`.
  4. Create a systemd service file (`/etc/systemd/system/attendix-bot.service`):
     ```ini
     [Unit]
     Description=Attendix Telegram Bot
     After=network.target

     [Service]
     Type=simple
     User=ubuntu
     WorkingDirectory=/home/ubuntu/Attendix/telegram_bot
     ExecStart=/home/ubuntu/Attendix/telegram_bot/venv/bin/python bot.py
     Restart=always
     RestartSec=10
     EnvironmentFile=/home/ubuntu/Attendix/telegram_bot/.env

     [Install]
     WantedBy=multi-user.target
     ```
  5. Enable and start: `sudo systemctl enable --now attendix-bot`.

#### Option B: Render.com (Background Worker)
- **Characteristics**: Render supports Python background workers.
- **Persistent Disk Note**: Free instances on Render spin down and have **ephemeral filesystems** (local SQLite database resets when the instance redeploys). If deploying to Render, attach a Render Persistent Disk (available on paid plans) or connect to an external PostgreSQL database by providing `DATABASE_URL`.
- **Procfile Notice**: Do NOT overwrite the repository's root `Procfile` (which serves the FastAPI web application). Create a separate service on Render pointing to the `telegram_bot` directory.

#### Option C: Railway.app / Fly.io
- **Railway**: Provides lightweight containers. Requires adding a persistent volume mounted at `/app/telegram_bot/data` to retain SQLite data between deploys.
- **Fly.io**: Allows deploying 1 free lightweight micro VM with 1GB persistent volume (`fly volumes create attendix_data -s 1`).

### 2. Free Tier Limitations & Ethical Notice
- **No Lifetime Guarantee**: Free-tier cloud offerings (Render, Railway, Fly.io) change their terms periodically and often enforce monthly credit or sleep quotas.
- **Ephemeral Filesystems**: Any container-based platform without an attached persistent volume will reset the SQLite database on rebuilds. For zero-loss production usage, ensure persistent storage is configured or back up `telegram_bot.db`.
- **No Artificial Keep-Alives**: Attendix does not implement hacky pingers or artificial HTTP keep-alives to circumvent hosting platform sleep rules.

---

## 🔒 Security Best Practices
1. **Never commit `.env` or `.encryption_key`**: Both files are pre-configured in `telegram_bot/.gitignore`.
2. **Encrypted Passwords**: Stored user passwords in `telegram_bot.db` are encrypted using Fernet (AES-128 in CBC mode with HMAC SHA-256).
3. **Session Purge**: Any student can completely wipe their credentials, attendance history, and preferences at any time by sending `/delete_data` or `/logout`.
