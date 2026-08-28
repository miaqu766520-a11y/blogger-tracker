#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blogger-tracker TikHub 引擎（付费·备用路线）

默认抓取永远走 browser-act 免费路线（见 SKILL.md 命令三）。
本脚本仅在需要 **大批量 / 深数据** 时启用：
  - 全历史回填（翻页抓一个博主的全部作品，不只第一页）
  - 大批量省时（API 直连比开浏览器快）
输出与 bt_store.py merge 完全兼容的 JSON 文件，落 博主追踪/tmp/。

Key 读取顺序: 环境变量 TIKHUB_API_KEY → --env 指定的 .env 文件
直连（Node 版 server.js 同款行为）；遇 400 自动重试 3 次。
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = os.environ.get('BT_DIR') or os.path.join(os.getcwd(), '博主追踪')
HOST = 'https://api.tikhub.io'
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def jload(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def read_key(env_path):
    if os.environ.get('TIKHUB_API_KEY'):
        return os.environ['TIKHUB_API_KEY']
    if env_path:
        try:
            import re
            m = re.search(r'^TIKHUB_API_KEY=["\']?([^"\'\r\n]+)',
                          open(env_path, encoding='utf-8', errors='replace').read(), re.M)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
    return ''


def tk_get(key, path, tries=3):
    url = HOST + path
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url)
            req.add_header('Authorization', 'Bearer ' + key)
            # Cloudflare 会 403 掉 Python-urllib 默认 UA，伪装成常规客户端
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            req.add_header('Accept', 'application/json')
            with _OPENER.open(req, timeout=20) as r:
                j = json.loads(r.read().decode('utf-8'))
            code = (j.get('detail') or {}).get('code') or j.get('code')
            if str(code) == '400':
                last = RuntimeError('TikHub 400')
                time.sleep(1.5 * (i + 1))
                continue
            return j
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last or RuntimeError('TikHub request failed')


def tk_data(j):
    return ((j.get('data') or {}).get('data')) or j.get('data') or {}


def fetch_douyin(key, sec_uid, pages):
    """返回 (videos, requests)。app/v3 端点（web 端点数据过期，勿用）"""
    out, reqs, cursor = [], 0, '0'
    for p in range(pages if pages > 0 else 999):
        j = tk_get(key, '/api/v1/douyin/app/v3/fetch_user_post_videos?sec_user_id=%s&max_cursor=%s&count=20'
                   % (urllib.parse.quote(sec_uid, safe=''), cursor))
        reqs += 1
        d = tk_data(j)
        for v in d.get('aweme_list') or []:
            st = v.get('statistics') or {}
            out.append({'id': v.get('aweme_id'), 't': (v.get('desc') or '')[:80],
                        'ct': v.get('create_time'),
                        'digg': st.get('digg_count'), 'comm': st.get('comment_count'),
                        'share': st.get('share_count'), 'coll': st.get('collect_count')})
        if not d.get('has_more') or not d.get('max_cursor'):
            break
        cursor = str(d['max_cursor'])
        time.sleep(0.3)
    return [v for v in out if v['id']], reqs


def fetch_bilibili(key, mid, pages):
    out, reqs = [], 0
    for pn in range(1, (pages if pages > 0 else 50) + 1):
        j = tk_get(key, '/api/v1/bilibili/web/fetch_user_post_videos?uid=%s&pn=%d'
                   % (urllib.parse.quote(str(mid), safe=''), pn))
        reqs += 1
        vlist = ((tk_data(j).get('list')) or {}).get('vlist') or []
        if not vlist:
            break
        for v in vlist:
            out.append({'id': v.get('bvid'), 't': (v.get('title') or '')[:80],
                        'ct': v.get('created'), 'play': v.get('play'), 'comm': v.get('comment')})
        time.sleep(0.3)
    return [v for v in out if v['id']], reqs


def main():
    ap = argparse.ArgumentParser(description='blogger-tracker TikHub engine')
    ap.add_argument('--blogger', help='单个博主名；缺省跑全部 active')
    ap.add_argument('--pages', type=int, default=1, help='每人翻页数；0=全历史(至多 50 页)')
    ap.add_argument('--env', default='', help='含 TIKHUB_API_KEY 的 .env 路径')
    args = ap.parse_args()

    key = read_key(args.env)
    if not key:
        print(json.dumps({'ok': False, 'error': 'no TIKHUB_API_KEY (env or --env file)'}, ensure_ascii=False))
        sys.exit(1)

    cfg = jload(os.path.join(ROOT, 'bloggers.json'), {})
    bloggers = [b for b in cfg.get('bloggers', []) if b.get('status') == 'active']
    if args.blogger:
        bloggers = [b for b in bloggers if b['name'] == args.blogger]
        if not bloggers:
            print(json.dumps({'ok': False, 'error': 'blogger not found: ' + args.blogger}, ensure_ascii=False))
            sys.exit(1)

    tmp_dir = os.path.join(ROOT, 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    results, total_reqs = [], 0
    for b in bloggers:
        name, plat = b['name'], b.get('platform', 'bilibili')
        try:
            if plat == 'douyin':
                videos, reqs = fetch_douyin(key, b['uid'], args.pages)
            else:
                videos, reqs = fetch_bilibili(key, b['uid'], args.pages)
            total_reqs += reqs
            out = os.path.join(tmp_dir, 'tikhub_%s.json' % name)
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(videos, f, ensure_ascii=False)
            results.append({'name': name, 'videos': len(videos), 'pages': reqs, 'file': out})
        except Exception as e:
            results.append({'name': name, 'error': str(e)[:100]})
        time.sleep(0.3)
    print(json.dumps({'ok': True, 'requests': total_reqs, 'results': results}, ensure_ascii=False))


if __name__ == '__main__':
    main()
