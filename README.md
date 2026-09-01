# blogger-tracker · Open-Source Creator Tracker

> A Claude Code skill that keeps watch on a list of Bilibili / Douyin creators — **who posted a new video and how it's performing, at a glance**.
> **Free by default**: data is captured with your own local browser, no paid API involved; the TikHub paid engine is only enabled on demand for bulk jobs or full-history backfill.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-bilibili%20%C2%B7%20douyin-green)]()
[![Cost](https://img.shields.io/badge/daily%20use-free-brightgreen)]()

## Project Layout

```
blogger-tracker/
├── SKILL.md                  Main skill file (trigger words + five-command workflow)
├── README.md                 This file
├── LICENSE                   MIT
└── scripts/
    ├── bt_store.py           Local storage / incremental diff / Markdown reports (pure stdlib)
    ├── sniffer_douyin.js     Douyin posts-API sniffer (injected into the page)
    ├── sniffer_bilibili.js   Bilibili posts-API sniffer (fallback)
    ├── tikhub_fetch.py       TikHub paid engine (backup: full-history backfill / bulk runs)
    └── feishu_push.py        Optional: write results back to a Feishu (Lark) Base table
```

## What It Does

| You say | It does |
|---|---|
| "Add creator https://space.bilibili.com/xxx" | Detects the platform → fetches latest videos to verify → adds to your watch list |
| "Update tracking" | Fetches each creator's latest videos, diffs against last run, flags new ones with 🆕 |
| "Who updated? / Give me a report" | Generates a Markdown report: new videos, top 10 by engagement, latest activity per creator |

A report looks like this (Markdown — drop it into Obsidian or any editor):

```
# 👀 Creator Tracking Report
## 🆕 New in the Last 7 Days (3)
| Date | Creator | Platform | Title | Stats |
| 08-24 | Digital Nomad | Bilibili | Mastering Excel… | 920K views · 141 comments |
## 🔥 Top 10 by Engagement …
## 📇 Latest 5 per Creator …
```

## Installation (3 Steps)

**Prerequisites**: [Claude Code](https://claude.ai/code) and Python 3.10+ installed.

1. **Install browser-act** (the scraping engine behind this skill):
   ```bash
   uv tool install browser-act-cli --python 3.12
   ```
2. **Drop this skill into your skills directory**:
   ```
   ~/.claude/skills/blogger-tracker/   ← copy the whole folder in
   ```
3. **Set up a browser** (needed for Douyin; skippable for Bilibili):
   Douyin requires a logged-in session to view a creator's full video list. Tell Claude Code:
   > "Use browser-act to create a browser, import my Chrome profile, purpose: Douyin creator tracking"

   Confirm when prompted (cookies stay on your machine and are never uploaded — browser-act officially guarantees local-only storage).

Done. From now on just tell Claude: "Add creator xxx" or "Update tracking".

## FAQ

**Q: Does it cost money? Do I need an API key?**
No and no for daily use. Data is "copied" from the creator pages your browser already loads — no different from you browsing the page yourself. The only paid scenario: backfilling a creator's **entire video history** (dozens of pages) or scanning dozens of creators at once, where you can enable the TikHub engine (bring your own key, pay per use; it reports an estimated request count for your confirmation before running).

**Q: Will I get banned?**
The volume is tiny (once a day, one page per creator) — indistinguishable from normal browsing. Built-in rate limiting (2+ seconds between creators). Don't use it for large-scale, high-frequency scraping.

**Q: Where is the data stored?**
In a `博主追踪/` folder under the working directory: `bloggers.json` (watch list), `data/` (per-creator history snapshots), `报告/` (Markdown reports). Stateless — delete and re-fetch anytime.

**Q: Which platforms are supported?**
Bilibili (no login needed) and Douyin (logged-in browser required). Xiaohongshu / Kuaishou / WeChat Channels are under evaluation.

**Q: Why does Douyin require login?**
Douyin's web version hides the complete video list from logged-out visitors. Your login session is only used for scraping on your own machine.

**Q: Can it write back to a Feishu (Lark) Base table?**
Yes (optional). Configure `feishu-setup` with your own Feishu custom app — see SKILL.md for details. **Never** use an appSecret shared by someone else.

## How It Works (One Sentence)

The browser opens the creator's page → the page itself requests the "video list" API (signed JSON) → we intercept that JSON → diff against the local snapshot; any new video ID is a new video.

- Bilibili: `api.bilibili.com/x/space/wbi/arc/search` (public, no login)
- Douyin: `www.douyin.com/aweme/v1/web/aweme/post/` (captured via sniffing)

## Disclaimer

For personal study and research only. Please respect each platform's terms of service — do not use for commercial scraping, data resale, or high-frequency bulk collection.
