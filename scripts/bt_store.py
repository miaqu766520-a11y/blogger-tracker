#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blogger-tracker 本地存储 / 增量对比 / 报告生成

数据根目录: 环境变量 BT_DIR 或 当前目录/博主追踪
  博主追踪/
    bloggers.json   博主清单 + 全局配置
    data/<博主>.json 每人一个快照(视频字典 + 首次/最近见到时间 + 数据小历史)
    报告/YYYY-MM-DD.md
    tmp/            抓取临时文件(merge 后可删)
"""
import argparse
import io
import json
import os
import re
import sys
import time
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = os.environ.get('BT_DIR') or os.path.join(os.getcwd(), '博主追踪')


def jload(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def jsave(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def safe(s):
    return re.sub(r'[\\/:*?"<>|\s]+', '_', str(s))[:60] or 'unnamed'


def bloggers_file(root):
    return os.path.join(root, 'bloggers.json')


def data_file(root, name):
    return os.path.join(root, 'data', safe(name) + '.json')


def norm_platform(s):
    s = (s or '').strip().lower()
    if s in ('bilibili', 'b站', 'b', 'bl'):
        return 'bilibili'
    if s in ('douyin', '抖音', 'dy', 'd'):
        return 'douyin'
    return s or 'bilibili'


def extract_uid(platform, home):
    home = (home or '').rstrip('/')
    if platform == 'bilibili':
        m = re.search(r'space\.bilibili\.com/(\d+)', home)
        return m.group(1) if m else home.split('/')[-1]
    m = re.search(r'douyin\.com/user/([^/?]+)', home)
    return m.group(1) if m else home.split('/')[-1]


def video_url(platform, vid):
    if platform == 'bilibili':
        return 'https://www.bilibili.com/video/' + str(vid)
    return 'https://www.douyin.com/video/' + str(vid)


def load_bloggers(root):
    d = jload(bloggers_file(root), None)
    if d is None:
        d = {'_config': {'bili_browser': '', 'douyin_browser': '', 'feishu': {'enabled': False}},
             'bloggers': []}
    d.setdefault('_config', {})
    d['_config'].setdefault('feishu', {'enabled': False})
    d.setdefault('bloggers', [])
    return d


def cmd_init(args):
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, '报告'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'tmp'), exist_ok=True)
    d = load_bloggers(ROOT)
    jsave(bloggers_file(ROOT), d)
    print(json.dumps({'ok': True, 'root': ROOT, 'bloggers': len(d['bloggers'])}, ensure_ascii=False))


def cmd_add(args):
    d = load_bloggers(ROOT)
    plat = norm_platform(args.platform)
    home = args.home.strip()
    for b in d['bloggers']:
        if b.get('home', '').rstrip('/') == home.rstrip('/') or b.get('name') == args.name:
            b['status'] = 'active'
            jsave(bloggers_file(ROOT), d)
            print(json.dumps({'ok': True, 'existed': True, 'name': b['name']}, ensure_ascii=False))
            return
    item = {'name': args.name, 'platform': plat, 'home': home,
            'uid': extract_uid(plat, home), 'status': 'active',
            'tags': args.tags or '', 'added_at': int(time.time())}
    d['bloggers'].append(item)
    jsave(bloggers_file(ROOT), d)
    print(json.dumps({'ok': True, 'existed': False, 'name': args.name, 'platform': plat, 'uid': item['uid']}, ensure_ascii=False))


def cmd_list(args):
    d = load_bloggers(ROOT)
    out = []
    for b in d['bloggers']:
        if b.get('status') != 'active' and not args.all:
            continue
        snap = jload(data_file(ROOT, b['name']), {})
        out.append({'name': b['name'], 'platform': b['platform'], 'home': b['home'],
                    'status': b.get('status'), 'videos': len(snap.get('videos', {})),
                    'updated_at': snap.get('updated_at')})
    print(json.dumps({'config': {k: v for k, v in d['_config'].items() if k != 'feishu'},
                      'feishu_enabled': bool(d['_config'].get('feishu', {}).get('enabled')),
                      'bloggers': out}, ensure_ascii=False))


def cmd_remove(args):
    d = load_bloggers(ROOT)
    for b in d['bloggers']:
        if b['name'] == args.name:
            b['status'] = 'archived'
            jsave(bloggers_file(ROOT), d)
            print(json.dumps({'ok': True, 'archived': args.name}, ensure_ascii=False))
            return
    print(json.dumps({'ok': False, 'error': 'not found: ' + args.name}, ensure_ascii=False))


def cmd_set_browser(args):
    d = load_bloggers(ROOT)
    key = 'bili_browser' if norm_platform(args.platform) == 'bilibili' else 'douyin_browser'
    d['_config'][key] = args.browser_id
    jsave(bloggers_file(ROOT), d)
    print(json.dumps({'ok': True, key: args.browser_id}, ensure_ascii=False))


def cmd_feishu_setup(args):
    d = load_bloggers(ROOT)
    d['_config']['feishu'] = {'enabled': True, 'base': args.base,
                              'bloggers_table': args.bloggers_table,
                              'videos_table': args.videos_table,
                              'creds_from': args.creds_from or ''}
    jsave(bloggers_file(ROOT), d)
    print(json.dumps({'ok': True, 'feishu': d['_config']['feishu']}, ensure_ascii=False))


def extract_json_payload(raw):
    """从混有 CLI 提示行的 stdout 里抠出 JSON(数组或对象)"""
    raw = raw.strip()
    for candidate in (raw,):
        try:
            return json.loads(candidate)
        except Exception:
            pass
    # 找以 [ 或 { 开头的行
    for line in raw.splitlines():
        line = line.strip().strip('"')
        if line.startswith('[') or line.startswith('{'):
            try:
                return json.loads(line)
            except Exception:
                continue
    # 兜底:第一个 [ 到最后一个 ]
    i, j = raw.find('['), raw.rfind(']')
    if i > -1 and j > i:
        return json.loads(raw[i:j + 1])
    raise ValueError('no JSON payload found')


def cmd_merge(args):
    with open(args.json, encoding='utf-8', errors='replace') as f:
        payload = extract_json_payload(f.read())
    if isinstance(payload, dict):
        videos = payload.get('videos') or payload.get('data') or []
    else:
        videos = payload
    now = int(time.time())
    d = load_bloggers(ROOT)
    entry = next((b for b in d['bloggers'] if b['name'] == args.blogger), None)
    if not entry:
        print(json.dumps({'ok': False, 'error': 'blogger not in list: ' + args.blogger}, ensure_ascii=False))
        sys.exit(1)
    plat = norm_platform(entry['platform'])
    snap = jload(data_file(ROOT, args.blogger), None) or {
        'name': args.blogger, 'platform': plat, 'home': entry.get('home'),
        'uid': entry.get('uid'), 'updated_at': 0, 'videos': {}}
    vs = snap['videos']
    new_items, changed = [], 0
    for v in videos:
        vid = str(v.get('id') or '').strip()
        if not vid:
            continue
        nums = {k: v.get(k) for k in ('play', 'digg', 'comm', 'share', 'coll') if isinstance(v.get(k), (int, float))}
        if vid in vs:
            rec = vs[vid]
            diff = {k: n for k, n in nums.items() if n != rec.get(k)}
            if diff:
                changed += 1
                rec.update(nums)
                hist = rec.setdefault('hist', [])
                hist.append({'ts': now, **nums})
                del hist[:-30]
            rec['last_seen'] = now
            if v.get('t'):
                rec['title'] = v['t']
        else:
            rec = {'id': vid, 'title': v.get('t') or '', 'url': video_url(plat, vid),
                   'published': v.get('ct'), 'first_seen': now, 'last_seen': now,
                   'hist': [{'ts': now, **nums}] if nums else []}
            rec.update(nums)
            vs[vid] = rec
            new_items.append({'id': vid, 'title': rec['title'], 'published': rec.get('published')})
    snap['updated_at'] = now
    jsave(data_file(ROOT, args.blogger), snap)
    print(json.dumps({'ok': True, 'blogger': args.blogger, 'fetched': len(videos),
                      'new': new_items, 'changed': changed, 'total': len(vs)}, ensure_ascii=False))


def fmt_nums(rec, plat):
    if plat == 'bilibili':
        parts = []
        if rec.get('play') is not None:
            parts.append('播放' + str(rec['play']))
        if rec.get('comm') is not None:
            parts.append('评' + str(rec['comm']))
        return ' · '.join(parts) or '-'
    parts = []
    for k, label in (('digg', '赞'), ('comm', '评'), ('share', '享'), ('coll', '藏')):
        if rec.get(k) is not None:
            parts.append(label + str(rec[k]))
    return ' · '.join(parts) or '-'


def ts_date(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')
    except Exception:
        return '?'


def heat(rec, plat):
    if plat == 'bilibili':
        return rec.get('play') or 0
    return (rec.get('coll') or 0) + (rec.get('digg') or 0)


def cmd_report(args):
    d = load_bloggers(ROOT)
    now = time.time()
    day_cut = now - args.days * 86400
    rows_new, rows_hot, sections = [], [], []
    actives = [b for b in d['bloggers'] if b.get('status') == 'active']
    for b in actives:
        snap = jload(data_file(ROOT, b['name']), None)
        if not snap or not snap.get('videos'):
            sections.append((b, [], 0))
            continue
        recs = sorted(snap['videos'].values(),
                      key=lambda r: (r.get('published') or r.get('first_seen') or 0), reverse=True)
        for r in recs:
            ts = r.get('published') or r.get('first_seen') or 0
            if r.get('first_seen', 0) >= day_cut or ts >= day_cut:
                rows_new.append((ts, b, r))
            rows_hot.append((heat(r, b['platform']), ts, b, r))
        sections.append((b, recs[:args.top], len(recs)))
    rows_new.sort(key=lambda x: x[0], reverse=True)
    rows_hot.sort(key=lambda x: x[0], reverse=True)

    L = []
    L.append('# 👀 博主追踪报告')
    L.append('')
    L.append('> 生成:' + datetime.now().strftime('%Y-%m-%d %H:%M') +
             ' · 博主 ' + str(len(actives)) + ' 人 · 数据源:本地快照(免费 browser-act 抓取)')
    L.append('')
    L.append('## 🆕 近 ' + str(args.days) + ' 天新发布(' + str(len(rows_new)) + ' 条)')
    L.append('')
    if rows_new:
        L.append('| 日期 | 博主 | 平台 | 标题 | 数据 | 链接 |')
        L.append('|---|---|---|---|---|---|')
        for ts, b, r in rows_new:
            plat_cn = 'B站' if b['platform'] == 'bilibili' else '抖音'
            L.append('| ' + ts_date(ts) + ' | ' + b['name'] + ' | ' + plat_cn + ' | ' +
                     (r.get('title') or '').replace('|', '/')[:50] + ' | ' + fmt_nums(r, b['platform']) +
                     ' | [看](' + (r.get('url') or '') + ') |')
    else:
        L.append('(没有新视频)')
    L.append('')
    L.append('## 🔥 热度 TOP ' + str(min(10, len(rows_hot))) + '(B站按播放 · 抖音按赞+藏)')
    L.append('')
    L.append('| 热度 | 博主 | 标题 | 数据 |')
    L.append('|---|---|---|---|')
    for h, ts, b, r in rows_hot[:10]:
        L.append('| ' + str(h) + ' | ' + b['name'] + ' | ' + (r.get('title') or '').replace('|', '/')[:45] +
                 ' | ' + fmt_nums(r, b['platform']) + ' |')
    L.append('')
    L.append('## 📇 各博主最新 ' + str(args.top) + ' 条')
    L.append('')
    for b, recs, total in sections:
        plat_cn = 'B站' if b['platform'] == 'bilibili' else '抖音'
        L.append('### ' + b['name'] + '(' + plat_cn + ' · 共追踪 ' + str(total) + ' 条)')
        if not recs:
            L.append('- (还没抓过,跑一次「更新追踪」)')
        for r in recs:
            L.append('- ' + ts_date(r.get('published') or r.get('first_seen')) + ' ' +
                     (r.get('title') or '')[:50] + ' — ' + fmt_nums(r, b['platform']))
        L.append('')
    out = os.path.join(ROOT, '报告', datetime.now().strftime('%Y-%m-%d') + '.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L))
    print(json.dumps({'ok': True, 'report': out, 'new': len(rows_new), 'bloggers': len(actives)}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description='blogger-tracker store')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init')
    p_add = sub.add_parser('add')
    p_add.add_argument('--name', required=True)
    p_add.add_argument('--platform', required=True)
    p_add.add_argument('--home', required=True)
    p_add.add_argument('--tags', default='')
    p_list = sub.add_parser('list')
    p_list.add_argument('--all', action='store_true')
    p_rm = sub.add_parser('remove')
    p_rm.add_argument('--name', required=True)
    p_sb = sub.add_parser('set-browser')
    p_sb.add_argument('--platform', required=True)
    p_sb.add_argument('--browser-id', required=True)
    p_fs = sub.add_parser('feishu-setup')
    p_fs.add_argument('--base', required=True)
    p_fs.add_argument('--bloggers-table', required=True)
    p_fs.add_argument('--videos-table', required=True)
    p_fs.add_argument('--creds-from', default='')
    p_mg = sub.add_parser('merge')
    p_mg.add_argument('--blogger', required=True)
    p_mg.add_argument('--json', required=True)
    p_rp = sub.add_parser('report')
    p_rp.add_argument('--days', type=int, default=7)
    p_rp.add_argument('--top', type=int, default=5)
    args = ap.parse_args()
    {'init': cmd_init, 'add': cmd_add, 'list': cmd_list, 'remove': cmd_remove,
     'set-browser': cmd_set_browser, 'feishu-setup': cmd_feishu_setup,
     'merge': cmd_merge, 'report': cmd_report}[args.cmd](args)


if __name__ == '__main__':
    main()
