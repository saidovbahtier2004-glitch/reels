# Uzbek Telegram bot: video downloader, song recognition, song search

Python 3.12 · aiogram 3 · yt-dlp · FFmpeg · Docker. No payments, no subscriptions, and **the bot has no usage limits of its own** (it only queues work when more than `MAX_PARALLEL_JOBS` jobs run at once, to protect the server).

## Features
| Feature | How |
|---|---|
| Download public videos (Instagram Reels, TikTok, YouTube, many more) | Send a link → press **🎬 Video** or **🎵 MP3** |
| Identify a song | Send a video / audio file / voice message, or send a link and press **🔍 Qo'shiqni aniqlash** |
| Search songs | Type the title or artist → Apple Music, Deezer and YouTube Music links |
| Uzbek (Latin) UI | Inline buttons + a menu keyboard |

## What is free and what is not (read this first)
* **The code, Telegram bot, yt-dlp, FFmpeg, song search (iTunes Search + Deezer public APIs): free**, no keys needed.
* **Song recognition needs an external API, and none is unlimited and free forever.** Pick one:
  * **ACRCloud**: has a free trial (currently ~14 days); then paid.
  * **AudD**: has a limited free trial; then paid per request.
  * Without a key the bot still works; recognition simply says it is not configured (`RECOGNITION_PROVIDER=none`).
  * Check each provider's current pricing and terms before relying on them; I could not verify them from this environment.
* **24/7 hosting is the only unavoidable cost.** The bot must run on a server, not your iPhone:
  * Truly free options (e.g. Oracle Cloud "Always Free" VM) usually require a credit card for identity verification and can be fiddly to set up from a phone. Free tiers of other hosts change often and many sleep or forbid long-running bots; check current terms.
  * Cheap paid VPS (roughly a few USD/month) is the simplest reliable choice.

## Limits you cannot remove (Telegram, not the bot)
* Bot can send files up to **50 MB**. Larger videos are re-downloaded at lower quality (720p → 480p → 360p); if still too large you get a message.
* Bot can receive files up to **20 MB** for song recognition.

## Legal / safety
Only public content that yt-dlp can fetch anonymously is downloaded. The bot does not log in, use cookies, bypass private accounts, DRM, or other access controls. Instagram frequently requires a login, so **some Instagram links will fail**; that is expected and intentional. Download only content you have the right to use. Links to local/private network addresses are rejected.

## Step 1: Keep your secrets safe
* **Never paste your bot token into chat, GitHub, or source code.** It lives only in an environment variable called `BOT_TOKEN`.
* If you ever exposed it: in Telegram open **@BotFather → /mybots → your bot → API Token → Revoke current token**, and use the new one.
* `.env` is in `.gitignore`; only `.env.example` (empty placeholders) is committed.

## Step 2: (Optional) get a recognition API key
**ACRCloud:** sign up at console.acrcloud.com → *Audio & Video Recognition* → create a project with the *ACRCloud Music* bucket → note **Host**, **Access Key**, **Access Secret**. Set `RECOGNITION_PROVIDER=acrcloud`.
**AudD:** sign up at dashboard.audd.io → copy the API token. Set `RECOGNITION_PROVIDER=audd`.

## Step 3: Deploy on a VPS (works from an iPhone)
1. Rent a small Ubuntu 22.04/24.04 VPS (1 GB RAM is enough) from any provider.
2. On your iPhone install an SSH app (e.g. Termius). Connect to the server with the details the provider gives you.
3. On the server, run:
   ```bash
   curl -fsSL https://get.docker.com | sh
   git clone https://github.com/saidovbahtier2004-glitch/reels.git
   cd reels/telegram-bot
   cp .env.example .env
   nano .env        # fill BOT_TOKEN etc. (type it in the terminal, NOT in chat). Save: Ctrl+O, Enter, Ctrl+X
   chmod 600 .env
   docker compose up -d --build
   docker compose logs -f     # you should see "Started as @yourbot"; Ctrl+C to leave logs
   ```
   (On Termius for iPhone, use the on-screen *Ctrl* key button for Ctrl+O / Ctrl+X.)
4. The container restarts automatically after crashes or reboots (`restart: unless-stopped`).
5. Open Telegram, send `/start` to your bot.

### Updating
```bash
cd reels/telegram-bot && git pull && docker compose up -d --build
```
Video sites change often; **rebuild every few weeks** (command above) to get the newest yt-dlp, or downloads may start failing.

### Other platforms
Any host that runs a Docker container 24/7 and lets you set environment variables works: set `BOT_TOKEN` (and optional keys) as secrets, do not upload `.env`. The bot uses long polling, so it needs no public port or domain.

## Local development
```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt     # needs ffmpeg installed
python -m pytest                        # 24 tests
BOT_TOKEN=... python -m bot
```

## Test status (honest report)
* ✅ Passing automated tests: config, URL safety, recognition/search parsing, ACRCloud signing, keyboards, the aiogram handlers (with a fake Telegram), real FFmpeg audio extraction, and real yt-dlp download/size-limit logic against a local HTTP server.
* ❌ **Not tested yet:** real Telegram connection, real YouTube/TikTok/Instagram downloads, iTunes/Deezer/AudD/ACRCloud network calls, and the Docker image build. The development sandbox blocked those network hosts and had no Docker daemon. Verify on your server with the checklist below.

### Checklist after deploying
1. `/start` shows the Uzbek menu.
2. Type `Imagine Dragons Believer` → result buttons open.
3. Send a public YouTube link → 🎬 Video returns a video.
4. Send a voice message of a playing song → song card (requires API key).

## Project layout
```
bot/config.py       env settings        bot/downloader.py  yt-dlp
bot/handlers.py     Telegram logic      bot/recognizer.py  AudD / ACRCloud
bot/keyboards.py    buttons             bot/search.py      iTunes + Deezer
bot/texts.py        Uzbek strings       bot/media.py       FFmpeg
bot/links.py        URL safety          tests/             pytest
```
