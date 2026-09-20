import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import requests
from feedkit import fetch_html, collect, merge_state
from update_all import execute
from test_multi import CFG, NOW, entry, html, Fake


def denied(code=403):
    response=requests.Response(); response.status_code=code
    return requests.HTTPError(str(code),response=response)


class RecoveryTest(unittest.TestCase):
    def test_browser_only_for_configured_403(self):
        client=Mock();client.get.side_effect=denied();client.get_browser.return_value='rendered'
        cfg=dict(CFG,browser_on_403=True,browser_wait_selector='article')
        self.assertEqual(fetch_html(client,CFG['url'],cfg),'rendered')
        client.get_browser.assert_called_once_with(CFG['url'],'article')
        for c,code in [(CFG,403),(cfg,429),(cfg,500)]:
            client.reset_mock();client.get.side_effect=denied(code)
            with self.assertRaises(requests.HTTPError):fetch_html(client,CFG['url'],c)
            client.get_browser.assert_not_called()

    def test_browser_failure_keeps_checkpoint_and_other_site_runs(self):
        cfg=dict(CFG,browser_on_403=True,browser_wait_selector='article')
        other=dict(CFG,id='other',source='https://example.com/other')
        with tempfile.TemporaryDirectory() as d:
            state=Path(d)/'state';state.mkdir();out=Path(d)/'out'
            old,_,_=merge_state({},[entry(1)],NOW,1,cfg)
            path=state/'test.json';path.write_text(json.dumps(old));before=path.read_bytes()
            client=Fake({cfg['source']:denied(),other['source']:html([2])})
            client.get_browser=Mock(side_effect=ValueError('Chromium HTTP 403'))
            report=execute([cfg,other],state,out,client=client)
            self.assertEqual([r['status'] for r in report],['error','ok'])
            self.assertEqual(path.read_bytes(),before)
            self.assertIn('HTTP 403',report[0]['notes'][0])

    def test_matsuwa_uses_only_category_archive(self):
        cfg=dict(CFG,kind='matsuwa_html',source='https://example.com/category',browser_on_403=True,browser_wait_selector='h3.entry-header a')
        text='<h2 class="date-header">2026年9月19日</h2><h3 class="entry-header"><a href="/1">記事</a></h3>'
        client=Fake({cfg['source']:text})
        rows,_,_=collect(cfg,{},client)
        self.assertEqual(client.calls,[cfg['source']])
        self.assertEqual(rows[0]['url'],'https://example.com/1')

    def test_http_success_never_launches_browser(self):
        client=Mock();client.get.return_value='html'
        self.assertEqual(fetch_html(client,CFG['url'],dict(CFG,browser_on_403=True)),'html')
        client.get_browser.assert_not_called()
