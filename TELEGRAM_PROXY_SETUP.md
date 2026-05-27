# 📱 Telegram Proxy Publisher Setup

## Overview

This workflow is fully separate from config publishing and sends **Telegram proxies** (MTProto + SOCKS5) to your channel.

- Workflow file: `.github/workflows/telegram-proxy-publisher.yml`
- Source config: `config/telegram_proxy_sources.json`
- Working pool state: `working_telegram_proxies.json`
- Publisher/rate-limit state: `telegram_proxy_state.json`

Each Telegram message contains **exactly one proxy**.

## Secrets & Variables

Add these in GitHub repository settings:

### Required secrets
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### Optional variable
- `TELEGRAM_CHANNEL_HANDLE` (default: `@vpnbuying`)

## Source lists

Edit `config/telegram_proxy_sources.json`:

- `mtproto_sources`: raw links that contain `tg://proxy?...` or `https://t.me/proxy?...`
- `socks5_sources`: raw links with SOCKS5 lists (`host:port`, `socks5://...`, or JSON)

Collector behavior:
- failing sources are skipped (best-effort)
- common MTProto/SOCKS5 formats are parsed
- duplicates are removed before testing

## Testing behavior

The workflow performs lightweight best-effort testing from GitHub Actions runner:

- TCP connect to `server:port`
- timeout-based filtering
- latency measurement

Only reachable proxies are added to `working_telegram_proxies.json`.

> Note: reachability is measured from the GitHub runner network, not from a specific country.

## Message format

### MTProto message
Includes both link formats for easy connection:
- Primary: `tg://proxy?server=...&port=...&secret=...`
- Alternative: `https://t.me/proxy?server=...&port=...&secret=...`

### SOCKS5 message
Contains server (and auth if available) and Telegram path:
`Settings > Data and Storage > Proxy > Add Proxy > SOCKS5`

Both message types include the same Persian CTA lines used in config messages.

## Rate limiting & anti-duplicate

`telegram_proxy_state.json` enforces:
- daily limit: **30 posts/day**
- sent-proxy hash tracking to prevent reposting the same proxy

`working_telegram_proxies.json` stores:
- tested working proxies
- `sent_to_telegram` and `sent_at` markers

## Cadence

The workflow runs hourly (`7 * * * *`) to avoid overlap spikes with existing workflows and keep posting low-noise.

Even if manually triggered repeatedly, daily posting is capped at 30.
