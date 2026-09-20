import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from feedkit import collect, item, merge_state, parse_html, rss_bytes
from update_all import execute

NOW = '2026-09-19T12:00:00+00:00'
CFG = dict(id='test', name='Test', kind='html', url='https://example.com/', source='https://example.com/', items='article', link='h2 a', date='time', next='a.next', feed_limit=2, max_pages=5)


def entry(i, date='2026-09-19'):
    return item('記事 '+str(i), '/'+str(i), date, 'https://example.com/')


def html(ids, nxt=None):
    return ''.join(f'<article><h2><a href="/{i}">記事 {i}</a></h2><time datetime="2026-09-19"></time></article>' for i in ids) + (f'<a class="next" href="{nxt}">次へ</a>' if nxt else '')


class Fake:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return value


class MultiTest(unittest.TestCase):
    def test_pagination_continues_past_mixed_page(self):
        old, _, _ = merge_state({}, [entry(1), entry(2)], NOW, 2, CFG)
        client = Fake({'https://example.com/': html([3, 2], '/p2'), 'https://example.com/p2': html([2, 1], '/p3')})
        rows, _, _ = collect(CFG, old, client)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual({x['url'] for x in rows}, {'https://example.com/1', 'https://example.com/2', 'https://example.com/3'})

    def test_shifted_page_boundary_stops_after_known_overlap(self):
        old, _, _ = merge_state({}, [entry(i) for i in range(1, 7)], NOW, 6, CFG)
        client = Fake({'https://example.com/': html([9, 8, 7, 6, 5, 4], '/p2')})
        rows, _, _ = collect(CFG, old, client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(len(rows), 6)

    def test_pagination_failure_does_not_advance_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            state, out = Path(d)/'state', Path(d)/'public'
            old, _, _ = merge_state({}, [entry(1)], NOW, 1, CFG)
            state.mkdir(); p=state/'test.json'; p.write_text(json.dumps(old))
            before = p.read_bytes()
            client = Fake({'https://example.com/':html([3], '/p2'), 'https://example.com/p2':OSError('network')})
            result = execute([CFG],state,out,client=client)
            self.assertEqual(result[0]['status'],'error')
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual(len(ET.parse(out/'feeds/test.xml').findall('./channel/item')),1)

    def test_one_failure_keeps_old_feed_and_publishes_other(self):
        with tempfile.TemporaryDirectory() as d:
            state, out = Path(d)/'state', Path(d)/'public'
            other = dict(CFG,id='other',source='https://example.com/other')
            execute([CFG,other],state,out,client=Fake({CFG['source']:html([1]),other['source']:html([2])}))
            before=(out/'feeds/test.xml').read_bytes()
            result=execute([CFG,other],state,out,client=Fake({CFG['source']:ValueError('403'),other['source']:html([3])}))
            self.assertEqual([r['status'] for r in result],['error','warning'])
            self.assertEqual(before,(out/'feeds/test.xml').read_bytes())
            self.assertEqual(result[1]['new'],1)

    def test_migration_preserves_guid_date_and_first_seen(self):
        e=dict(entry(1),first_seen=NOW)
        old=dict(version=1,last_checked=NOW,entries={e['url']:e})
        modified=dict(entry(1,'2026-09-20'),title='修正')
        new,added,changed=merge_state(old,[modified,entry(2)],NOW,2,CFG)
        self.assertEqual((added,changed),(1,1))
        self.assertEqual(new['entries'][e['url']]['published'],e['published'])
        self.assertEqual(new['entries'][e['url']]['first_seen'],NOW)
        self.assertIn(e['url'].encode(),rss_bytes(new,CFG,''))

    def test_recent_discoveries_survive_count_limit(self):
        state,_,_=merge_state({},[entry(i) for i in range(5)],NOW,5,CFG)
        state['last_checked']='2026-09-20T12:00:00+00:00'
        self.assertEqual(len(ET.fromstring(rss_bytes(state,CFG,'')).findall('./channel/item')),5)
        state['last_checked']='2026-11-20T12:00:00+00:00'
        self.assertEqual(len(ET.fromstring(rss_bytes(state,CFG,'')).findall('./channel/item')),2)

    def test_travel_uses_published_date_not_trip_date(self):
        cfg=dict(CFG,date='[data-published-at]',date_attr='data-published-at')
        text='<article><h2><a href="/1">旅行記</a></h2><p data-published-at="2026-09-19"></p><p>旅行日 2014/01/01</p></article>'
        rows,_=parse_html(text,cfg,CFG['url'])
        self.assertTrue(rows[0]['published'].startswith('2026-09-19'))

    def test_xml_escapes_titles(self):
        e=dict(entry(1),title='A & B <旅>')
        state,_,_=merge_state({},[e],NOW,1,CFG)
        self.assertEqual(ET.fromstring(rss_bytes(state,CFG,'')).findtext('./channel/item/title'),e['title'])

    def test_cap_and_empty_list_raise(self):
        old,_,_=merge_state({},[entry(1)],NOW,1,CFG)
        with self.assertRaisesRegex(ValueError,'limit'):
            collect(dict(CFG,max_pages=1),old,Fake({CFG['source']:html([2],'/p2')}))
        with self.assertRaises(ValueError):
            parse_html('<html>Login</html>',CFG,CFG['url'])

    def test_fuyuka_selector_excludes_other_columns(self):
        cfg=dict(CFG,items='#fuyukacolumn article')
        rows,_=parse_html(html([1])+'<div id="fuyukacolumn">'+html([2])+'</div>',cfg,CFG['url'])
        self.assertEqual([r['url'] for r in rows],['https://example.com/2'])


if __name__ == '__main__':
    unittest.main()
