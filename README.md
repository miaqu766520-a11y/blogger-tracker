# blogger-tracker · 开源博主追踪系统

> Claude Code skill：盯一批 B站 / 抖音博主，**谁发了新视频、数据怎么样，一目了然**。
> 默认 **0 元**：本地浏览器抓数据，不用任何付费 API；TikHub 付费引擎仅在大批量/全历史回填时按需启用。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-bilibili%20%C2%B7%20douyin-green)]()
[![Cost](https://img.shields.io/badge/%E6%97%A5%E5%B8%B8%E4%BD%BF%E7%94%A8-0%20%E5%85%83-brightgreen)]()

## 目录结构

```
blogger-tracker/
├── SKILL.md                  Claude Code skill 主文件（触发词 + 五命令工作流）
├── README.md                 本文件
├── LICENSE                   MIT
└── scripts/
    ├── bt_store.py           本地存储 / 增量对比 / Markdown 报告（纯 stdlib）
    ├── sniffer_douyin.js     抖音作品接口嗅探器（页内注入）
    ├── sniffer_bilibili.js   B站作品接口嗅探器（兜底）
    ├── tikhub_fetch.py       TikHub 付费引擎（备用：全历史回填/大批量）
    └── feishu_push.py        可选：回写飞书多维表
```

## 它能干什么

| 你说 | 它做 |
|---|---|
| 「加博主 https://space.bilibili.com/xxx」 | 识别平台 → 抓最新视频验证 → 登记进清单 |
| 「更新追踪」 | 逐个博主抓最新视频，和上次对比，新发的标 🆕 |
| 「谁更新了 / 出报告」 | 生成 Markdown 报告：新视频、热度 TOP10、每人最新动态 |

报告长这样（Markdown，丢进 Obsidian / 任何编辑器都能看）：

```
# 👀 博主追踪报告
## 🆕 近 7 天新发布(3 条)
| 日期 | 博主 | 平台 | 标题 | 数据 |
| 08-24 | 数字游牧人 | B站 | 玩转Excel… | 播放92万 · 评141 |
## 🔥 热度 TOP 10 …
## 📇 各博主最新 5 条 …
```

## 安装（3 步）

**前置**：已装 [Claude Code](https://claude.ai/code) 和 Python 3.10+。

1. **装 browser-act**（本 skill 的抓取引擎）：
   ```bash
   uv tool install browser-act-cli --python 3.12
   ```
2. **把本 skill 放进 skills 目录**：
   ```
   ~/.claude/skills/blogger-tracker/   ← 整个文件夹拷进去
   ```
3. **配浏览器**（抖音需要，B站可跳过）：
   抖音要求登录态才能看博主主页。在 Claude Code 里说：
   > 「用 browser-act 创建一个浏览器，导入我的 Chrome，用途：抖音博主追踪」
   
   按提示确认即可（cookie 只存在你本机，不上传——browser-act 官方承诺 local-only）。

完成。之后直接对 Claude 说「加博主 xxx」「更新追踪」就行。

## 常见问题

**Q: 要花钱吗？要 API key 吗？**
日常使用都不要。数据是你的浏览器打开博主主页时顺手"抄"下来的，和你自己刷网页没区别。
唯一付费场景：想一次性回填某博主的**全部历史视频**（翻几十页）或一次刷几十人，可启用 TikHub 引擎（自带 key，按量计费，跑前会报预估请求数让你确认）。

**Q: 会不会被封？**
量小（每天一次、每次每个博主一个页面）和正常浏览无异。工具内置限速（每个博主间隔 2 秒+）。别拿来大规模高频抓。

**Q: 数据存哪？**
当前目录下 `博主追踪/` 文件夹：`bloggers.json`（清单）、`data/`（每人历史快照）、`报告/`（Markdown 报告）。删了重抓即可，无状态。

**Q: 支持哪些平台？**
B站（免登录）、抖音（需登录态浏览器）。小红书 / 快手 / 视频号路线在评估。

**Q: 抖音为什么必须登录？**
抖音网页版不登录看不到完整作品列表。你的登录态只用于你自己电脑上的抓取。

**Q: 能回写飞书多维表吗？**
能（可选）。用自己的飞书自建应用配置 `feishu-setup`，详见 SKILL.md。**不要**用任何别人分享的 appSecret。

## 原理（一句话）

浏览器打开博主主页 → 页面自己会去请求「作品列表」接口（带签名的 JSON）→ 我们把这份 JSON 截下来 → 和本地快照对比，新 ID 就是新视频。

- B站：`api.bilibili.com/x/space/wbi/arc/search`（公开免登录）
- 抖音：`www.douyin.com/aweme/v1/web/aweme/post/`（嗅探截获）

## 免责

仅供个人学习与研究，请遵守各平台用户协议，勿用于商业抓取、转售数据或高频批量采集。
