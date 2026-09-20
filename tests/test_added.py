import json
import unittest
from feedkit import collect, date_value, parse_data_page, parse_html
from test_multi import Fake, CFG, NOW, entry


class AddedSitesTest(unittest.TestCase):
    def test_dates_keep_fractional_seconds_and_accept_short_dates(self):
        self.assertEqual(date_value('2026.9.2'), '2026-09-02T00:00:00+09:00')
        self.assertEqual(date_value('2026/9/2 7:05'), '2026-09-02T07:05:00+09:00')
        self.assertEqual(date_value('2026-09-02T07:05:00.123Z'), '2026-09-02T07:05:00.123000+00:00')

    def test_gizmodo_excludes_rankings_and_recommendations(self):
        article=dict(title='新着', slug='new', released_at='2026-09-19T00:00:00Z')
        data={'props': {'pageProps': {'articles': [article, {'isLogly': True, 'loglySlot': 'topTimeline1'}], 'reviewArticles': [dict(article,slug='old')]}, 'props': {'ranking': [dict(article,slug='rank')]}}}
        text='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(data)+'</script><a href="/articles/2/">NEXT</a>'
        rows,nxt=parse_data_page(text,dict(CFG,kind='gizmodo_data'),CFG['url'],1)
        self.assertEqual([r['url'] for r in rows],['https://example.com/article/new/'])
        self.assertEqual(nxt,'https://example.com/articles/2/')

    def test_si_excludes_non_mlb_schema(self):
        rows=[{'@type':'NewsArticle','@id':'https://example.com/'+p,'headline':'記事','datePublished':NOW} for p in ['mlb/new','nfl/other']]
        text=''.join('<article><script type="application/ld+json">'+json.dumps(x)+'</script></article>' for x in rows)
        entries,_=parse_data_page(text,dict(CFG,kind='si_jsonld'),CFG['url'],1)
        self.assertEqual([x['url'] for x in entries],['https://example.com/mlb/new'])

    def test_rss_pagination_collects_more_than_source_feed_limit(self):
        def rss(i):return f'<rss><channel><item><title>記事{i}</title><link>https://example.com/{i}</link><pubDate>Sat, 19 Sep 2026 00:00:00 GMT</pubDate></item></channel></rss>'
        cfg=dict(CFG,kind='rss',page_size=1)
        old=dict(version=2,entries={'https://example.com/1':entry(1)})
        client=Fake({CFG['url']:rss(2),CFG['url']+'?paged=2':rss(1)})
        rows,_,_=collect(cfg,old,client)
        self.assertEqual([x['url'] for x in rows],['https://example.com/2','https://example.com/1'])
        self.assertEqual(len(client.calls),2)

    def test_jcom_uses_complete_image_title_not_short_card_text(self):
        cfg=dict(CFG,link='a',title='img',title_attr='alt',date='time',date_attr='postdate')
        text='<article><a href="/1"></a><img alt="省略されていない記事タイトル"><p>省略さ...</p><time postdate="2026-09-19"></time></article>'
        rows,_=parse_html(text,cfg,CFG['url'])
        self.assertEqual(rows[0]['title'],'省略されていない記事タイトル')

    def test_book_archive_empty_end_is_not_a_layout_error(self):
        rows,nxt=parse_data_page('<div class="enddatas"></div>',dict(CFG,kind='book_html'),CFG['url'],2)
        self.assertEqual((rows,nxt),([],None))
