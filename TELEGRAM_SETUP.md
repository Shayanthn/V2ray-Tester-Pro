# 📱 Telegram Integration Guide

## Overview

The V2Ray Tester Pro automatically posts updates to your Telegram channel with:
- ✅ **Smart Duplicate Detection** - Only posts when configs actually change
- ✅ **Rate Limiting** - Maximum 10 posts per day, minimum 30 minutes between posts
- ✅ **Beautiful Formatting** - Professional Markdown messages
- ✅ **Multi-Client Support** - Links for v2rayN, Clash, SingBox

## Setup Instructions

### Step 1: Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Copy the **Bot Token** (looks like: `1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### Step 2: Add Bot to Your Channel

1. Go to your channel
2. Click **Administrators**
3. Click **Add Administrator**
4. Search for your bot name
5. Give it **Post Messages** permission
6. Save

### Step 3: Configure GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**

**Add these secrets:**

```
Name: TELEGRAM_BOT_TOKEN
Value: 1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

Name: TELEGRAM_CHAT_ID
Value: @your_channel_username
```

> **Note:** Channel username should start with `@` (e.g., `@vpnbuying`)

### Step 4: Test

1. Push a commit or manually trigger the workflow
2. Wait for the workflow to complete
3. Check your channel for the update message!

## Message Format

The bot will post messages like this:

```
🚀 V2Ray Configs - Auto Update

━━━━━━━━━━━━━━━━━━━

✅ Working Servers: 45
📊 Avg Ping: 185 ms
⚡ Avg Speed: 35.2 Mbps
🕐 Updated: 2026-02-01 14:30

📱 Protocols:
  • VLESS: 30
  • VMESS: 10
  • TROJAN: 5

━━━━━━━━━━━━━━━━━━━

📥 Import to Your App:

v2rayN/NG/Matsuri:
https://raw.githubusercontent.com/...

...
```

## Anti-Spam Protection

The system includes multiple layers of spam protection:

### 1. Duplicate Detection
- Calculates MD5 hash of all config URIs
- Only posts if configs actually changed
- Prevents redundant posts

### 2. Rate Limiting
- **Minimum interval:** 30 minutes between posts
- **Daily limit:** Maximum 10 posts per day
- Resets at midnight UTC

### 3. State Tracking
- Stores last post time in `telegram_state.json`
- Persists across workflow runs
- Committed to repository

## Troubleshooting

### Bot not posting

**Check:**
1. Are secrets configured correctly?
2. Is bot admin of channel?
3. Does bot have "Post Messages" permission?
4. Check workflow logs for errors

### Too many posts

The system should prevent this, but if it happens:
1. Check `telegram_state.json` file
2. Verify rate limiting is working
3. Review workflow logs

### Posts not appearing

**Verify:**
1. Bot token is correct
2. Channel username starts with `@`
3. Bot is actually admin
4. Channel is public (or bot has access)

## Manual Control

### Disable Telegram Posts

Create a file named `.disable_telegram_sends` in repository root:

```bash
touch .disable_telegram_sends
git add .disable_telegram_sends
git commit -m "Disable Telegram notifications"
git push
```

### Re-enable

```bash
rm .disable_telegram_sends
git add .disable_telegram_sends
git commit -m "Enable Telegram notifications"
git push
```

## Configuration

All settings are in `core/telegram_publisher.py`:

```python
# Daily post limit
MAX_POSTS_PER_DAY = 10

# Minimum interval between posts (minutes)
MIN_INTERVAL_MINUTES = 30
```

## Files

- `core/telegram_publisher.py` - Main publisher logic
- `utils/telegram_notifier.py` - Low-level Telegram API
- `telegram_state.json` - State tracking (auto-generated)
- `.github/workflows/auto-test.yml` - Workflow integration

---

**Made with ❤️ by V2Ray Tester Pro**
