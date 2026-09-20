"""Site adapters and stable RSS state for the multi-site reader."""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime, format_datetime
from html import unescape, escape
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
import json
import re
import time
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))


def soup(text):
    return BeautifulSoup(text, 'html.parser')


def clean(text):
    return ' '.join(unescape(text).split())


def date_value(value):
    value = clean(value)
    m = re.search(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日', value)
    if m:
        return datetime(*map(int, m.groups()), tzinfo=JST).isoformat()
    m = re.search(r'(\d{1,2})月\s*(\d{1,2})日,?\s*(\d{4})年', value)
    if m:
        month, day, year = map(int, m.groups())
        return datetime(year, month, day, tzinfo=JST).isoformat()
    # Normalize date-only/list formats without corrupting ISO fractional seconds.
    m = re.fullmatch(r'(\d{4})[./](\d{1,2})[./](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?', value)
    if m:
        y, mo, d, h, mi = m.groups()
        return datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), tzinfo=JST).isoformat()
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt.isoformat()


def item(title, url, published, base, author=''):
    url = urljoin(base, url)
    p = urlsplit(url)
    if p.scheme not in ('https', 'http') or p.hostname != urlsplit(base).hostname or p.username:
        raise ValueError('Unexpected article URL')
    url = urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))
    title = clean(title)
    if not title:
        raise ValueError('Empty article title')
    return dict(title=title, url=url, published=date_value(published), author=clean(author))


class Client:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0'
        self.cache = {}
        self.last = {}
        self.count = 0
        self.events = []

    def get_browser(self, url, selector):
        key = ('browser', url)
        if key in self.cache:
            return self.cache[key]
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(locale='ja-JP', timezone_id='Asia/Tokyo')
                page = context.new_page()
                response = page.goto(url, wait_until='domcontentloaded', timeout=45000)
                status = response.status if response else None
                self.events.append(dict(method='chromium', url=url, status=status))
                if status is None or status >= 400:
                    raise ValueError(f'Chromium HTTP {status}; title={clean(page.title())[:120]}')
                if urlsplit(page.url).hostname != urlsplit(url).hostname:
                    raise ValueError('Browser redirected to another host')
                page.locator(selector).first.wait_for(state='attached', timeout=20000)
                text = page.content()
                if len(text.encode()) > 12_000_000:
                    raise ValueError('Browser response exceeds 12MB')
                self.cache[key] = text
                return text
            finally:
                browser.close()

    def get(self, url):
        if url in self.cache:
            return self.cache[url]
        host = urlsplit(url).netloc
        if host in self.last:
            time.sleep(max(0, 0.7 - (time.monotonic() - self.last[host])))
        for attempt in range(2):
            try:
                response = self.session.get(url, timeout=(10, 30))
                self.last[host] = time.monotonic()
                self.count += 1
                self.events.append(dict(method='http', url=url, status=response.status_code))
                if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                    time.sleep(2)
                    continue
                response.raise_for_status()
                if len(response.content) > 12_000_000:
                    raise ValueError('Response exceeds 12MB')
                result = response.content.decode('utf-8-sig')
                self.cache[url] = result
                return result
            except requests.exceptions.Timeout:
                if attempt:
                    raise
        raise ValueError('No response')


def fetch_html(client, url, cfg):
    """Only configured public lists get one normal browser attempt after HTTP 403."""
    try:
        return client.get(url)
    except requests.HTTPError as exc:
        if not cfg.get('browser_on_403') or exc.response is None or exc.response.status_code != 403:
            raise
        try:
            return client.get_browser(url, cfg['browser_wait_selector'])
        except Exception as browser_error:
            raise ValueError(f'HTTP 403; browser fallback failed: {browser_error}') from browser_error


def parse_html(text, cfg, base):
    s = soup(text)
    kind = cfg['kind']
    if kind == 'jazz':
        region = s.select_one('.wp-easy-query')
        if region is None:
            raise ValueError('JazzTokyo column list missing')
        rows = region.select('li[data-post-id]')
    else:
        rows = s.select(cfg['items'])
    result = []
    for row in rows:
        a = row.select_one(cfg['link'])
        if a is None:
            # Explicitly tolerate only the empty J SPORTS ad slot.
            if kind == 'carp' and not row.get_text(strip=True):
                continue
            raise ValueError('Article link missing')
        title_node = row.select_one(cfg['title']) if cfg.get('title') else a
        if title_node is None:
            raise ValueError('Article title missing')
        title = title_node.get(cfg['title_attr'], '') if cfg.get('title_attr') else title_node.get_text(' ', strip=True)
        if kind == 'carp':
            result.append(dict(title=clean(title), url=urljoin(base, a['href'])))
            continue
        author_node = row.select_one(cfg['author']) if cfg.get('author') else None
        author = author_node.get_text(' ', strip=True) if author_node else ''
        if kind == 'jazz':
            metas = row.select('.entry-meta')
            dated = next((m.get_text(' ', strip=True) for m in metas if re.search(r'\d{4}年\s*—', m.text)), '')
            match = re.search(r'(\d+月\d+日,?\s*\d{4}年)\s*—\s*(.*?)\s*閲覧回数', dated)
            if not match:
                raise ValueError('JazzTokyo publication date missing')
            published, author = match.groups()
        else:
            d = row.select_one(cfg['date'])
            if d is None:
                raise ValueError('Publication date missing')
            published = d.get(cfg.get('date_attr', 'datetime')) or d.get_text(' ', strip=True)
        result.append(item(title, a['href'], published, base, author))
    if not result:
        raise ValueError('0 articles: layout change or access error')
    link = s.select_one(cfg['next']) if cfg.get('next') else None
    next_url = urljoin(base, link['href']) if link and link.get('href') else None
    if kind == 'carp':
        link = next((a for a in s.select('a[href]') if a.text.strip() == '次へ'), None)
        next_url = urljoin(base, link['href']) if link else None
    return result, next_url


def rss_items(text, cfg):
    root = ET.fromstring(text)
    all_items = root.findall('./channel/item')
    if not all_items:
        raise ValueError('RSS has no items')
    selected = []
    for node in all_items:
        if cfg.get('category') and cfg['category'] not in [c.text for c in node.findall('category')]:
            continue
        selected.append(item(node.findtext('title', ''), node.findtext('link', ''), node.findtext('pubDate', ''), cfg['url']))
    if not selected:
        raise ValueError('No matching category in RSS')
    return selected


def parse_data_page(text, cfg, base, page):
    """Public data embedded in the page or used by its own article list."""
    kind = cfg['kind']
    if kind == 'cinema_json':
        rows = json.loads(text)
        entries = [item(x['title'], x['url'], x['date'], cfg['url']) for x in rows]
        next_url = None
    elif kind == 'si_jsonld':
        s = soup(text)
        rows = [json.loads(x.string) for x in s.select('article script[type="application/ld+json"]')]
        entries = [item(x['headline'], x['@id'], x['datePublished'], cfg['url'], x.get('author', {}).get('name', ''))
                   for x in rows if x.get('@type') == 'NewsArticle' and urlsplit(x.get('@id', '')).path.startswith('/mlb/')]
        a = next((a for a in s.select('a[href]') if a.get_text(strip=True) == 'Next'), None)
        next_url = urljoin(base, a['href']) if a else None
    elif kind == 'gizmodo_data':
        s = soup(text)
        script = s.select_one('#__NEXT_DATA__')
        rows = json.loads(script.string)['props']['pageProps']['articles']
        entries = [item(x['title'], '/article/' + x['slug'] + '/', x['released_at'], cfg['url'])
                   for x in rows if not x.get('isLogly')]
        a = next((a for a in s.select('a[href]') if a.get_text(strip=True) == 'NEXT'), None)
        next_url = urljoin(base, a['href']) if a else None
    elif kind == 'book_html':
        page_cfg = dict(cfg, items='#list .module-list-articles__item' if page == 1 else '.module-list-articles__item')
        if page > 1 and 'enddatas' in text and not soup(text).select('.module-list-articles__item'):
            return [], None
        entries, _ = parse_html(text, page_cfg, base)
        next_url = (cfg['url'] + f'readmore?p={page + 1}&offset={page * 12}&category=all'
                    if 'enddatas' not in text else None)
    else:
        raise ValueError('Unknown data adapter')
    if not entries:
        raise ValueError('0 articles: public data changed or unavailable')
    return entries, next_url


def matsuwa_archive(text, cfg):
    s = soup(text)
    result = []
    for h in s.select('h3.entry-header'):
        a = h.select_one('a[href]')
        d = h.find_previous('h2', class_='date-header')
        if not a or not d:
            raise ValueError('Matsuwa archive layout changed')
        result.append(item(a.text, a['href'], d.text, cfg['url']))
    if not result:
        raise ValueError('Empty Matsuwa archive')
    return result


def collect(cfg, old, client):
    known = old.get('entries', {})
    kind = cfg['kind']
    notes = []
    if kind == 'matsuwa_html':
        entries = matsuwa_archive(fetch_html(client, cfg['source'], cfg), cfg)
        if known and not any(x['url'] in known for x in entries):
            notes.append('過去履歴との重なりなし。カテゴリー一覧の掲載範囲を確認してください。')
        return entries, len(entries), notes
    if kind == 'rss_category':
        entries = rss_items(client.get(cfg['source']), cfg)
        if known and not any(x['url'] in known for x in entries):
            entries += matsuwa_archive(client.get(cfg['url']), cfg)
            if not any(x['url'] in known for x in entries):
                notes.append('過去履歴との重なりなし。長期停止中の記事は取りこぼした可能性があります。')
        return entries, len(entries), notes
    collected = []
    url = cfg['source']
    visited = set()
    first_count = 0
    max_pages = cfg.get('max_pages', 20)
    # Bootstrap takes one page; existing PoC ANA also gets a deliberate one-page migration.
    bootstrap = not known or old.get('version', 1) < 2
    for page in range(1, max_pages + 1):
        if url in visited:
            raise ValueError('Pagination loop; previous history retained')
        visited.add(url)
        text = fetch_html(client, url, cfg)
        if kind == 'ana_api':
            raw = json.loads(text)
            if not isinstance(raw, list) or not raw:
                raise ValueError('ANA API returned no articles')
            current = [item(soup(x['title']['rendered']).get_text(), x['link'], x['date'], cfg['url']) for x in raw]
            next_url = cfg['source'] + '&page=' + str(page + 1) if len(raw) == cfg['page_size'] else None
        elif kind == 'rss':
            current = rss_items(text, cfg)
            separator = '&' if '?' in cfg['source'] else '?'
            next_url = (cfg['source'] + separator + 'paged=' + str(page + 1)
                        if len(current) >= cfg['page_size'] else None)
        elif kind in ('cinema_json', 'si_jsonld', 'gizmodo_data', 'book_html'):
            current, next_url = parse_data_page(text, cfg, url, page)
        else:
            current, next_url = parse_html(text, cfg, url)
        if page == 1:
            first_count = len(current)
        if kind == 'carp':
            for entry in current:
                if entry['url'] in known:
                    entry.update(published=known[entry['url']]['published'])
                else:
                    detail = soup(client.get(entry['url']))
                    date = detail.select_one('.p-detail__date')
                    if date is None:
                        raise ValueError('J SPORTS article date unavailable')
                    entry.update(item(entry['title'], entry['url'], date.text, cfg['url']))
        collected.extend(current)
        # Page offsets shift as new entries arrive; requiring a wholly known page
        # can miss the stopping point even with a complete previous snapshot.
        overlap = len({x['url'] for x in collected if x['url'] in known})
        enough_overlap = bool(known) and overlap >= min(3, len(known))
        if bootstrap or not next_url or enough_overlap:
            break
        if urlsplit(next_url).hostname != urlsplit(cfg['url']).hostname:
            raise ValueError('Pagination changed host')
        # Detect sites that ignore page parameter instead of silently declaring success.
        if page > 1 and {x['url'] for x in current}.issubset({x['url'] for x in collected[:-len(current)]}):
            raise ValueError('Repeated pagination content')
        url = next_url
    else:
        raise ValueError(f'Pagination limit {max_pages} reached; increase max_pages after checking the site')
    if known and not any(x['url'] in known for x in collected):
        notes.append('過去履歴との重なりなし。取得範囲を確認してください。')
    return collected, first_count, notes


def merge_state(old, entries, now, first_count, cfg):
    # Migration preserves GUIDs and publication dates from PoC.
    previous = old.get('first_page_count')
    if previous and first_count < previous * cfg.get('minimum_count_ratio', 0.25):
        raise ValueError('Article count fell sharply; previous history retained')
    merged = dict(old.get('entries', {}))
    added = changed = 0
    for entry in entries:
        url = entry['url']
        if url in merged:
            prev = merged[url]
            if entry['title'] != prev['title'] or entry.get('author', '') != prev.get('author', ''):
                merged[url] = dict(prev, title=entry['title'], author=entry.get('author', ''))
                changed += 1
        else:
            merged[url] = dict(entry, first_seen=now)
            added += 1
    # Never prune the deduplication history. RSS itself has a configurable cap.
    return dict(version=2, entries=merged, last_checked=now, first_page_count=first_count), added, changed


def ordered(state):
    return sorted(state['entries'].values(), key=lambda x: (datetime.fromisoformat(x['published']), x['url']), reverse=True)


def rss_bytes(state, cfg, base_url):
    ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')
    ET.register_namespace('dc', 'http://purl.org/dc/elements/1.1/')
    root = ET.Element('rss', version='2.0')
    channel = ET.SubElement(root, 'channel')
    for tag, value in [('title', cfg['name']), ('link', cfg['url']), ('language', cfg.get('language', 'ja')), ('description', '公開タイトル・リンク・日付をまとめた非公式の個人用フィード')]:
        ET.SubElement(channel, tag).text = value
    if base_url:
        ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link', href=base_url.rstrip('/') + '/feeds/' + cfg['id'] + '.xml', rel='self', type='application/rss+xml')
    # Keep at least 30 days of discoveries, even when a burst exceeds the normal cap.
    reference = datetime.fromisoformat(state['last_checked'])
    all_entries = ordered(state)
    top = {x['url'] for x in all_entries[:cfg.get('feed_limit', 500)]}
    selected = [x for x in all_entries if x['url'] in top or
                (reference - datetime.fromisoformat(x.get('first_seen', state['last_checked']))).total_seconds() <= 30 * 86400]
    for entry in selected:
        node = ET.SubElement(channel, 'item')
        ET.SubElement(node, 'title').text = entry['title']
        ET.SubElement(node, 'link').text = entry['url']
        ET.SubElement(node, 'guid', isPermaLink='true').text = entry['url']
        ET.SubElement(node, 'pubDate').text = format_datetime(datetime.fromisoformat(entry['published']))
        if entry.get('author'):
            ET.SubElement(node, '{http://purl.org/dc/elements/1.1/}creator').text = entry['author']
    ET.indent(root)
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    ET.fromstring(data)
    return data


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(data)
    temp.replace(path)
