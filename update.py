"""ANA RSS PoC. Python 3.11+ standard library only."""
import argparse
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path
import json
import os
import sys
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

JST = timezone(timedelta(hours=9))
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())


class Cards(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.current = None
        self.items = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = a.get('class', '').split()
        if tag == 'article' and 'c-cardArchive' in classes and any(
            t == 'ul' and '_archives' in c for t, c in self.stack
        ):
            self.current = {'title': '', 'url': '', 'date': ''}
        if self.current is not None:
            if tag == 'a' and 'c-cardArchive__link' in classes:
                self.current['url'] = a.get('href', '')
            if tag == 'time':
                self.current['date'] = a.get('datetime', '')
        if tag not in VOID:
            self.stack.append((tag, classes))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self.current is not None and any(
            'c-cardArchive__heading' in c for _, c in self.stack
        ):
            self.current['title'] += data

    def handle_endtag(self, tag):
        if tag == 'article' and self.current is not None:
            self.items.append(self.current)
            self.current = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


def extract(html, config):
    parser = Cards()
    parser.feed(html)
    items = {}
    for raw in parser.items:
        title = ' '.join(raw['title'].split())
        parts = urlsplit(urljoin(config['url'], raw['url']))
        if not title or not raw['url'] or parts.scheme != 'https' or parts.netloc != urlsplit(config['url']).netloc:
            raise ValueError('Invalid title or article URL; previous feed preserved')
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))
        date = datetime.fromisoformat(raw['date'])
        if date.tzinfo is None:
            date = date.replace(tzinfo=JST)
        items[url] = {'title': title, 'url': url, 'published': date.isoformat()}
    if len(items) < config['minimum_items']:
        raise ValueError('No valid article list; previous feed preserved')
    return list(items.values())


def merge(old, current, now, config):
    previous_count = old.get('last_count', 0)
    if previous_count and len(current) < previous_count * config['minimum_count_ratio']:
        raise ValueError('Article count fell sharply; inspect the website before changing minimum_count_ratio')
    entries = dict(old.get('entries', {}))
    new_count = 0
    for item in current:
        prior = entries.get(item['url'])
        if prior:
            # Stable publication date and GUID avoid re-notifying title corrections.
            entries[item['url']] = dict(prior, title=item['title'])
        else:
            entries[item['url']] = dict(item, first_seen=now)
            new_count += 1
    return {'version': 1, 'last_checked': now, 'last_count': len(current), 'entries': entries}, new_count


def rss_bytes(state, config, base_url):
    ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')
    root = ET.Element('rss', version='2.0')
    channel = ET.SubElement(root, 'channel')
    for k, v in [('title', config['name']), ('link', config['url']),
                 ('description', '公開されている新着タイトル・リンク・日付のみを配信する個人用フィード。'),
                 ('language', 'ja')]:
        ET.SubElement(channel, k).text = v
    if base_url:
        ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link',
                      href=base_url.rstrip('/') + '/feeds/ana.xml', rel='self', type='application/rss+xml')
    entries = sorted(state['entries'].values(), key=lambda x: (datetime.fromisoformat(x['published']), x['url']), reverse=True)
    for entry in entries[:config['feed_limit']]:
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = entry['title']
        ET.SubElement(item, 'link').text = entry['url']
        ET.SubElement(item, 'guid', isPermaLink='true').text = entry['url']
        ET.SubElement(item, 'pubDate').text = format_datetime(datetime.fromisoformat(entry['published']))
    ET.indent(root)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(data)
    temp.replace(path)


def run(config, state_path, output, html, base_url=''):
    old = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    current = extract(html, config)
    state, count = merge(old, current, datetime.now(timezone.utc).isoformat(), config)
    xml = rss_bytes(state, config, base_url)
    ET.fromstring(xml)  # Validate before writing any result.
    atomic_write(output / 'feeds/ana.xml', xml)
    atomic_write(output / 'index.html', ('<!doctype html><html lang="ja"><meta charset="utf-8">'
        '<title>個人用 RSS</title><h1>個人用 RSS</h1>'
        '<p><a href="feeds/ana.xml">ANA 翼の王国・新着記事（非公式）</a></p>'
        '<p>上のリンクのURLをInoreaderに登録してください。</p></html>').encode())
    atomic_write(state_path, (json.dumps(state, ensure_ascii=False, indent=2) + '\n').encode())
    message = f'ANA: fetched={len(current)}, new={count}, stored={len(state["entries"])}, feed={min(len(state["entries"]), config["feed_limit"])}'
    print(message)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(message + '\n')
    return state


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, default=Path('config/ana.json'))
    p.add_argument('--state', type=Path, default=Path('state/ana.json'))
    p.add_argument('--output', type=Path, default=Path('public'))
    p.add_argument('--html-file', type=Path, help='Offline verification only')
    p.add_argument('--base-url', default='')
    args = p.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    if args.html_file:
        html = args.html_file.read_text(encoding='utf-8')
    else:
        request = Request(config['url'], headers={'User-Agent': 'PersonalRSS/0.1 (+daily personal feed)'})
        with urlopen(request, timeout=30) as response:
            if response.status != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
                raise ValueError('Unexpected HTTP response')
            body = response.read(5_000_001)
            if len(body) > 5_000_000:
                raise ValueError('Response too large')
            html = body.decode('utf-8')
    run(config, args.state, args.output, html, args.base_url)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        sys.exit(1)
