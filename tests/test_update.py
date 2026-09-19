import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from update import extract, run

CONFIG = {'name': 'Test', 'url': 'https://tsubasa.ana.co.jp/', 'feed_limit': 100,
          'minimum_items': 1, 'minimum_count_ratio': 0.5}


def card(slug='one', title='旅 &amp; 音楽', date='2026-09-19'):
    return f'<article class="c-cardArchive"><a class="c-cardArchive__link" href="/{slug}/"><h2 class="c-cardArchive__heading">{title}</h2><time datetime="{date}"></time></a><img src="x"><a href="/tag/food/">tag</a></article>'


def page(*cards):
    return '<ul class="c-grid _archives">' + ''.join(cards) + '</ul>'


class UpdateTest(unittest.TestCase):
    def test_ignores_other_sections_and_deduplicates(self):
        items = extract(card('advert') + page(card(), card()), CONFIG)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], '旅 & 音楽')
        self.assertEqual(items[0]['url'], 'https://tsubasa.ana.co.jp/one/')

    def test_stable_repeat_and_old_items_retained(self):
        with tempfile.TemporaryDirectory() as d:
            state, out = Path(d) / 'state.json', Path(d) / 'public'
            run(CONFIG, state, out, page(card()))
            first = (out / 'feeds/ana.xml').read_bytes()
            run(CONFIG, state, out, page(card()))
            self.assertEqual(first, (out / 'feeds/ana.xml').read_bytes())
            run(CONFIG, state, out, page(card('two', date='2026-09-20')))
            root = ET.parse(out / 'feeds/ana.xml')
            self.assertEqual(len(root.findall('./channel/item')), 2)
            self.assertEqual(len(json.loads(state.read_text())['entries']), 2)

    def test_failure_preserves_feed_and_state(self):
        with tempfile.TemporaryDirectory() as d:
            state, out = Path(d) / 'state.json', Path(d) / 'public'
            run(CONFIG, state, out, page(card('one'), card('two'), card('three')))
            before = (state.read_bytes(), (out / 'feeds/ana.xml').read_bytes())
            for bad in ['<html>login</html>', page(card(date='bad')), page(card())]:
                with self.assertRaises(ValueError):
                    run(CONFIG, state, out, bad)
                self.assertEqual(before, (state.read_bytes(), (out / 'feeds/ana.xml').read_bytes()))


if __name__ == '__main__':
    unittest.main()
