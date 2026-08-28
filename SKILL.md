---
name: blogger-tracker
description: "开源博主追踪系统：默认用 browser-act 真实浏览器免费抓 B站/抖音博主最新视频；TikHub 付费 API 为备用引擎（大批量/全历史回填时才启用）。本地 JSON+Markdown 存储，增量发现新视频，生成追踪报告；可选回写飞书多维表。当用户说「加博主」「追踪这个博主」「更新追踪」「谁更新了」「博主追踪报告」「盯一下这个 UP主」「博主最近发了什么」「开源博主追踪」「回填博主历史视频」时触发。依赖 browser-act skill。区别于 douyin-downloader（下载视频本体）与 xiaohongshu-creator-analytics（自己账号后台数据）。"
---

# blogger-tracker · 开源博主追踪系统（免费版）

盯一批 B站/抖音博主，发现新视频、沉淀热度数据、出 Markdown 报告。**全程 0 费用**：抓取走 browser-act 本地真实浏览器（不用任何付费 API），存储全本地。

- B站：公开页免登录，抓 `arc/search` 接口（标题/bvid/播放/评论/发布时间）
- 抖音：需带登录态的浏览器，嗅探 `aweme/post` 接口（标题/aweme_id/赞/评/享/藏/发布时间）
- 单人约 10~15 秒，20 人 ≈ 5 分钟；量大的博主只抓第一页（最新 18~42 条），对「发现新视频」足够

## 前置：先读 browser-act skill

本 skill 全部抓取经 browser-act CLI 完成。**第一批命令前必须先执行**（browser-act skill 的强制要求）：

```bash
browser-act get-skills core --skill-version 2.0.2
```

browser-act 规则全部适用：会话命名、归属判断、用完即关（`browser-act session close <name>`）。

## 数据布局

默认根目录 = **当前工作目录/博主追踪**（环境变量 `BT_DIR` 可改）。所有 bt_store.py 命令在该目录下执行（或先 `export BT_DIR=<路径>`）。

```
博主追踪/
├── bloggers.json      博主清单 + 配置（浏览器 id、飞书开关）
├── data/<博主>.json    每人视频快照（含 first_seen/hist 数据小历史）
├── 报告/YYYY-MM-DD.md  追踪报告
└── tmp/               抓取临时文件（merge 后即可删）
```

脚本：`scripts/bt_store.py`（存储/对比/报告，纯本地无网络）、`scripts/sniffer_douyin.js`（抖音嗅探注入）、`scripts/sniffer_bilibili.js`（B站兜底嗅探注入）。下文 `$BT` = `scripts/bt_store.py` 绝对路径，`$SKILL` = 本 skill 目录。

## 命令一：初始化 / 配置浏览器

仅在 `bloggers.json` 不存在或浏览器未配置时做：

```bash
python $BT init
```

然后 `browser-act browser list`，向用户确认两个浏览器 id（**必须让用户确认，不得自创浏览器**）：

- **B站浏览器**：任意 chrome 类型即可（公开页免登录），选用户已有的通用浏览器
- **抖音浏览器**：desc 中含「抖音登录态」的浏览器；没有 → 引导用户按 browser-act 创建流程（`get-skills advanced` → 说明用途 → 用户确认 → create 导入自己 Chrome），README 有粉丝向说明

确认后写入配置：

```bash
python $BT set-browser --platform bilibili --browser-id <id>
python $BT set-browser --platform douyin    --browser-id <id>
```

## 命令二：加博主

用户给主页链接（`space.bilibili.com/<mid>` 或 `douyin.com/user/<sec_uid>`）。若用户只给名字：B站用 `bilibili/web` 搜索页、抖音用搜索页人工确认主页链接，**不得猜 uid**。

1. `python $BT add --name "<名>" --platform <bilibili|douyin> --home "<主页链接>"`（返回 uid）
2. 紧接着按「命令三」单人抓取流程抓一次入库（验证能抓到 + 建立首批快照）
3. 抓不到 → 从清单 `remove` 并如实告诉用户原因（链接错/需登录/页面风控）

## 命令三：更新追踪（核心）

`python $BT list` 取 active 博主，按平台分批。**同平台复用同一会话逐人 navigate**；每完成一人 `sleep 2`；每人最多重试 2 次；失败的记入小结不中断整批。会话命名 `bt-<plat>-<随机3位>`，全批跑完统一 close。

### B站分支（每人）

```bash
# 首次或换人时
browser-act --session <S> navigate "https://space.bilibili.com/<mid>/video"
browser-act --session <S> wait stable --timeout 45000
# 1. 从网络日志提取签名 URL（CSV 最后一列，含 w_rid/wts，必须新鲜）
browser-act --session <S> network requests --filter "arc/search" --type xhr,fetch
# 2. 页内凭签名 URL 重取（同域 CORS 放行，wbi 签名短时有效，立即用）
browser-act --session <S> eval "window.__bt=null;fetch('<上一步的完整URL>',{credentials:'include'}).then(function(r){return r.json()}).then(function(d){var l=(d.data&&d.data.list&&d.data.list.vlist)||[];window.__bt=l.map(function(v){return{id:v.bvid,t:(v.title||'').slice(0,80),ct:v.created,play:v.play,comm:v.comment}})}).catch(function(e){window.__bt={err:String(e)}});'fetching'"
sleep 3
# 3. 分块读回（每块 ≤8 条防输出截断；block=ceil(n/8)，n 先看 length）
browser-act --session <S> eval "JSON.stringify(window.__bt&&window.__bt.length)"
browser-act --session <S> eval "JSON.stringify(window.__bt.slice(0,8))"
# ...slice(8,16) 直到读完
# 4. 每块输出用 grep '^\[{' 提取（必须带 { —— 裸 '^\[' 会误抓 "[Update Available]" 提示行），
#    空块（grep 无输出）写 '[]' 兜底；各块拼成完整数组写 博主追踪/tmp/bili_<博主>.json，然后
python $BT merge --blogger "<博主名>" --json 博主追踪/tmp/bili_<博主>.json
```

B站兜底（签名 URL 重取返回 HTML/err）：注入 `scripts/sniffer_bilibili.js` → 点空间页别的 Tab（如「动态」）→ 点回「投稿」→ 读 `window.__caps`。

### 抖音分支（每人，浏览器必须带抖音登录态）

```bash
browser-act --session <S> navigate "https://www.douyin.com/user/<sec_uid>"
browser-act --session <S> wait stable --timeout 45000
# 1. 注入嗅探器（挂钩 fetch+XHR 捕获 aweme/post 响应）
browser-act --session <S> eval "$(cat $SKILL/scripts/sniffer_douyin.js)"   # 须返回 sniffer-ok
# 2. SPA 跳走再跳回 → 页面重发带签名的作品接口，嗅探器截获完整 JSON
browser-act --session <S> eval "var a=document.querySelector('a[href*=\"recommend\"]');a&&a.click();'nav'"
sleep 4
browser-act --session <S> eval "history.back();'back'"
sleep 6
# 3. 确认截获（n≥1 且最后一页 n>0），分块读 data（每块 ≤8 条，grep '^\[{' 提取、空块写 '[]'）
browser-act --session <S> eval "JSON.stringify({n:window.__caps.length,last:window.__caps.length?window.__caps[window.__caps.length-1].d.n:0})"
browser-act --session <S> eval "JSON.stringify(window.__caps[window.__caps.length-1].d.data.slice(0,8))"
# ...slice(8,16) 直到读完（取 __caps 最后一页，含全部 21 条以内）
# 4. 拼成数组写 博主追踪/tmp/dy_<博主>.json，然后
python $BT merge --blogger "<博主名>" --json 博主追踪/tmp/dy_<博主>.json
```

抖音兜底：`__caps` 为空 → 等 5s 再读一次；仍空 → 重新 navigate 用户页重试（注入会随整页刷新失效，需重新注入）；两次失败 → 检查是否弹出验证码/登录墙（截图），需要人工时按 browser-act 升级阶梯（solve-captcha / headed / remote-assist）交给用户。

### merge 返回

`{"new":[{id,title,published}], "changed":m, "total":N}` —— `new` 即本次新发现视频。汇总所有博主的 new 作为「谁更新了」的答案；tmp 文件 merge 后删除。

## 命令三补充：TikHub 引擎（付费·仅大批量/深数据时启用）

**默认永远是 browser-act 免费路线。** 仅当满足以下任一条件才用 TikHub，且**启用前必须向用户说明并按预估请求数征得同意**（按量计费）：

- 全历史回填（用户说「把 xx 的历史视频都抓来」「回填」）——browser-act 只抓第一页，TikHub 可翻页到全量
- 大批量省时（一次刷几十人不想等浏览器）
- browser-act 路线被风控/登录态失效且用户有 key

```bash
# 单人单页（≈1 请求）
python $SKILL/scripts/tikhub_fetch.py --blogger "<名>" --pages 1 --env <.env路径>
# 全历史回填（翻页到完，至多 50 页；先估算页数≈作品数/20 再跑）
python $SKILL/scripts/tikhub_fetch.py --blogger "<名>" --pages 0 --env <.env路径>
# 产出 博主追踪/tmp/tikhub_<名>.json 后照常 merge
python $BT merge --blogger "<名>" --json 博主追踪/tmp/tikhub_<名>.json
```

Key 读取：环境变量 `TIKHUB_API_KEY` → `--env` 文件。注意抖音必须走 app/v3（web 端点数据过期）；B站列表无收藏数（要收藏 TopN 得逐条 fetch_one_video，请求数=视频数，先报价再跑）。

## 命令四：出报告

```bash
python $BT report --days 7 --top 5
```

生成 `博主追踪/报告/YYYY-MM-DD.md`（🆕新发布 / 🔥热度TOP10 / 📇各博主最新N条）。控制台同步一句小结；报告路径交给用户（Obsidian 库内可直接看）。

## 命令五（可选）：回写飞书

仅当 `bloggers.json` 的 `_config.feishu.enabled=true` 时，在 merge 全部完成后执行：

```bash
python $SKILL/scripts/feishu_push.py
```

把本地快照增量写入飞书多维表（博主表/视频表，字段映射：B站=标题/链接/封面/发布时间/播放量/评论数，抖音=标题/链接/发布时间/赞/评/享/藏；内容ID 加平台前缀去重）。配置方式：

```bash
python $BT feishu-setup --base <base_id> --bloggers-table <tbl...> --videos-table <tbl...> [--creds-from <server.js路径>]
```

凭证优先读 `--creds-from` 指定的 Node 文件里的 `appId/appSecret`（复用现有工作台应用，不另存密钥）；粉丝无配置则整步跳过，**绝不向粉丝索取或分发任何 appSecret**。

## 纪律红线

1. **先 `get-skills core`** 再发任何 browser-act 命令；browser 创建/删除必须走用户确认门
2. 会话用完即关；不使用别的会话（ownership 规则）；两人之间 sleep 2，单批失败不中断
3. eval 读取一律分块 ≤8 条，防 CLI 输出截断（实测教训）；merge 输入只认 `{id,t,ct,play,comm,digg,share,coll}` 字段
4. 抖音签名 URL **不可**页内重取（返回 HTML），只能嗅探截获；B站反之（签名 URL 可重取，SPA 返回会整页刷新清空注入）——两条路线不得互换
5. 临时文件只进 `博主追踪/tmp/`，merge 后即删；报告只进 `博主追踪/报告/`
6. 遇验证码/登录墙不盲目重试，按升级阶梯交人工
7. TikHub 为付费备用引擎：默认绝不启用；启用前报预估请求数并征得用户同意；禁止用它跑命令三的日常更新（那是 browser-act 的活）
