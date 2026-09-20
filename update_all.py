"""Run every configured site; keep previous feeds on individual failures."""
import argparse
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from feedkit import Client, collect, merge_state, rss_bytes, atomic


def execute(configs, state_dir, output, base_url='', client=None):
    client = client or Client()
    now = datetime.now(timezone.utc).isoformat()
    # Validate every state before publishing anything: corrupt history is not an empty feed.
    states = {}
    for cfg in configs:
        if not re.fullmatch(r'[a-z0-9-]+', cfg['id']):
            raise ValueError('Invalid feed id')
        path = state_dir / (cfg['id'] + '.json')
        old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if old:
            rss_bytes(old, cfg, base_url)
        states[cfg['id']] = old
    report = []
    for cfg in configs:
        key = cfg['id']
        old = states[key]
        path = state_dir / (key + '.json')
        status = dict(id=key, name=cfg['name'], status='ok', fetched=0, new=0, changed=0, notes=[])
        current = old
        try:
            entries, first_count, notes = collect(cfg, old, client)
            current, added, changed = merge_state(old, entries, now, first_count, cfg)
            payload = rss_bytes(current, cfg, base_url)
            atomic(path, (json.dumps(current, ensure_ascii=False, indent=2) + '\n').encode())
            atomic(output / 'feeds' / (key + '.xml'), payload)
            status.update(fetched=len({x['url'] for x in entries}), new=added, changed=changed, notes=notes)
            if notes:
                status['status'] = 'warning'
        except Exception as exc:
            # Never generate an empty replacement for a failed source.
            current = old
            if old:
                atomic(output / 'feeds' / (key + '.xml'), rss_bytes(old, cfg, base_url))
            status.update(status='error', notes=[f'{type(exc).__name__}: {exc}'])
        status['stored'] = len(current.get('entries', {}))
        status['last_success'] = current.get('last_checked')
        file = output / 'feeds' / (key + '.xml')
        status['available'] = file.exists()
        status['feed_items'] = len(ET.fromstring(file.read_bytes()).findall('./channel/item')) if file.exists() else 0
        report.append(status)
        print(f"{key}: {status['status']} fetched={status['fetched']} new={status['new']} changed={status['changed']} feed={status['feed_items']}", flush=True)
        for note in status['notes']:
            print(f'  {note}', flush=True)
    atomic(output / 'status.json', json.dumps(dict(checked_at=now, sites=report), ensure_ascii=False, indent=2).encode())
    rows = []
    outlines = []
    for row in report:
        key = row['id']
        link = f'<a href="feeds/{key}.xml">RSS</a>' if row['available'] else '初回取得待ち'
        notes = ' / '.join(row['notes'])
        rows.append(f"<tr><td>{escape(row['name'])}</td><td>{link}</td><td>{row['status']}</td><td>{row['new']}</td><td>{row['feed_items']}</td><td>{escape(row['last_success'] or '未成功')}</td><td>{escape(notes)}</td></tr>")
        if base_url and row['available']:
            outlines.append(f'<outline type="rss" text="{escape(row["name"], quote=True)}" title="{escape(row["name"], quote=True)}" xmlUrl="{escape(base_url.rstrip("/") + "/feeds/" + key + ".xml", quote=True)}"/>')
    html = '''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>個人用RSS</title><style>body{font-family:system-ui,sans-serif;margin:2rem;line-height:1.6}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:.6rem;text-align:left}th{background:#eef2f6}</style><h1>個人用RSS</h1><p>RSSリンク先のURLをInoreaderに登録してください。タイトル・リンク・日付のみ配信します。</p><p><a href="subscriptions.opml">一括登録用OPML</a> / <a href="status.json">実行結果JSON</a></p>'''
    html += '<p>実行日時（UTC）: ' + now + '</p><table><tr><th>対象</th><th>購読</th><th>状態</th><th>今回追加</th><th>RSS件数</th><th>最終成功（UTC）</th><th>備考</th></tr>' + ''.join(rows) + '</table></html>'
    atomic(output / 'index.html', html.encode())
    atomic(output / 'subscriptions.opml', ('<?xml version="1.0" encoding="UTF-8"?><opml version="2.0"><head><title>個人用RSS</title></head><body>' + ''.join(outlines) + '</body></opml>').encode())
    errors = sum(r['status'] == 'error' for r in report)
    summary = '| Site | Status | New | Changed | RSS items |\n|---|---|---:|---:|---:|\n' + '\n'.join(f"| {r['id']} | {r['status']} | {r['new']} | {r['changed']} | {r['feed_items']} |" for r in report)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(summary + '\n')
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as f:
            f.write(f'errors={errors}\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=Path('config/sites.json'))
    parser.add_argument('--state-dir', type=Path, default=Path('state'))
    parser.add_argument('--output', type=Path, default=Path('public'))
    parser.add_argument('--base-url', default='')
    parser.add_argument('--allow-partial', action='store_true', help='Publish good feeds before workflow reports per-site errors')
    args = parser.parse_args()
    configs = json.loads(args.config.read_text(encoding='utf-8'))['sites']
    if len({x['id'] for x in configs}) != len(configs):
        raise ValueError('Duplicate feed IDs')
    report = execute(configs, args.state_dir, args.output, args.base_url)
    if not args.allow_partial and any(x['status'] == 'error' for x in report):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
