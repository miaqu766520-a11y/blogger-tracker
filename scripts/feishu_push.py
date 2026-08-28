#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blogger-tracker 飞书回写（可选模块）

把本地快照增量写入飞书多维表。仅当 bloggers.json _config.feishu.enabled=true 时运行。
凭证来源（按优先级）:
  1. 环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET
  2. feishu.creds_from 指向的 Node 文件里的 appId/appSecret（复用工作台应用，不另存密钥）
纯 stdlib，无第三方依赖（粉丝友好）。
"""
import io
import json
import os
import re
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT = os.environ.get('BT_DIR') or os.path.join(os.getcwd(), '博主追踪')
API = 'https://open.feishu.cn'

# 飞书是国内服务，必须直连：本机 Clash 等系统代理会让 urllib 走代理导致卡死
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def jload(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def http(method, path, token=None, body=None):
    req = urllib.request.Request(API + path, method=method)
    req.add_header('Content-Type', 'application/json; charset=utf-8')
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    data = json.dumps(body).encode('utf-8') if body is not None else None
    with _OPENER.open(req, data=data, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def get_token(app_id, app_secret):
    r = http('POST', '/open-apis/auth/v3/tenant_access_token/internal',
             body={'app_id': app_id, 'app_secret': app_secret})
    if r.get('code') != 0:
        raise RuntimeError('token failed: ' + str(r.get('msg')))
    return r['tenant_access_token']


def list_all(token, base, table, fields=None):
    items, token_page = [], ''
    while True:
        q = '?page_size=500'
        if token_page:
            q += '&page_token=' + token_page
        r = http('GET', '/open-apis/bitable/v1/apps/%s/tables/%s/records%s' % (base, table, q), token)
        if r.get('code') != 0:
            raise RuntimeError('list failed: ' + str(r.get('msg')))
        d = r.get('data') or {}
        items.extend(d.get('items') or [])
        if not d.get('has_more'):
            return items
        token_page = d.get('page_token') or ''


def fields_of(platform, name, rec):
    plat_cn = 'bilibili' if platform == 'bilibili' else '抖音'
    cid = ('bilibili_' if platform == 'bilibili' else 'douyin_') + str(rec['id'])
    f = {'内容ID': cid, '关联博主': name, '平台': plat_cn,
         '标题': (rec.get('title') or '')[:120], '链接': rec.get('url') or ''}
    if rec.get('published'):
        f['发布时间'] = int(rec['published']) * 1000
    if platform == 'bilibili':
        for k, cn in (('play', '播放量'), ('comm', '评论数')):
            if rec.get(k) is not None:
                f[cn] = rec[k]
    else:
        for k, cn in (('digg', '点赞数'), ('comm', '评论数'), ('share', '分享数'), ('coll', '收藏数')):
            if rec.get(k) is not None:
                f[cn] = rec[k]
    return cid, f


def num(v):
    try:
        return int(v)
    except Exception:
        return None


def main():
    cfg = jload(os.path.join(ROOT, 'bloggers.json'), {})
    fe = (cfg.get('_config') or {}).get('feishu') or {}
    if not fe.get('enabled'):
        print(json.dumps({'ok': True, 'skipped': 'feishu disabled'}, ensure_ascii=False))
        return
    app_id = os.environ.get('FEISHU_APP_ID', '')
    app_secret = os.environ.get('FEISHU_APP_SECRET', '')
    if not (app_id and app_secret) and fe.get('creds_from'):
        try:
            src = open(fe['creds_from'], encoding='utf-8', errors='replace').read()
            m1 = re.search(r"appId:\s*'([^']+)'", src)
            m2 = re.search(r"appSecret:\s*'([^']+)'", src)
            if m1 and m2:
                app_id, app_secret = m1.group(1), m2.group(1)
        except Exception as e:
            print(json.dumps({'ok': False, 'error': 'creds_from read failed: ' + str(e)}, ensure_ascii=False))
            sys.exit(1)
    if not (app_id and app_secret):
        print(json.dumps({'ok': False, 'error': 'no feishu credentials'}, ensure_ascii=False))
        sys.exit(1)

    token = get_token(app_id, app_secret)
    base, vtable = fe['base'], fe['videos_table']
    existing = {}
    for it in list_all(token, base, vtable):
        f = it.get('fields') or {}
        cid = f.get('内容ID')
        if cid:
            existing[str(cid)] = {'rid': it.get('record_id'), 'fields': f}

    new_n = upd_n = skip_n = 0
    errors = []
    # 预扫描总量，便于进度输出（大批量新建时防止被误判卡死）
    todo = []
    data_dir = os.path.join(ROOT, 'data')
    for fn in sorted(os.listdir(data_dir)):
        if fn.endswith('.json'):
            snap = jload(os.path.join(data_dir, fn), None)
            if snap and snap.get('videos'):
                todo.append((snap.get('name') or fn[:-5], snap.get('platform') or 'bilibili', snap))
    total = sum(len(s['videos']) for _, _, s in todo)
    done = 0
    print(json.dumps({'phase': 'push', 'total': total, 'existing': len(existing)}, ensure_ascii=False), flush=True)
    for name, plat, snap in todo:
        for rec in snap['videos'].values():
            cid, fields = fields_of(plat, name, rec)
            try:
                ex = existing.get(cid)
                if not ex:
                    http('POST', '/open-apis/bitable/v1/apps/%s/tables/%s/records' % (base, vtable),
                         token, {'fields': fields})
                    new_n += 1
                else:
                    diff = {k: v for k, v in fields.items()
                            if k not in ('内容ID', '关联博主', '平台') and num(v) != num(ex['fields'].get(k)) and v != ex['fields'].get(k)}
                    if diff:
                        http('PUT', '/open-apis/bitable/v1/apps/%s/tables/%s/records/%s' % (base, vtable, ex['rid']),
                             token, {'fields': diff})
                        upd_n += 1
                    else:
                        skip_n += 1
                time.sleep(0.1)
            except Exception as e:
                errors.append(cid + ': ' + str(e)[:80])
            done += 1
            if done % 20 == 0:
                print(json.dumps({'phase': 'push', 'done': done, 'of': total,
                                  'new': new_n, 'upd': upd_n}, ensure_ascii=False), flush=True)
    print(json.dumps({'ok': True, 'new': new_n, 'updated': upd_n, 'unchanged': skip_n,
                      'errors': errors[:10]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
