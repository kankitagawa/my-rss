# 継続して実装する対象

本ZIPで有効なのはANAのみ。下記は実装待ちを含む要件の記録で、全サイト対応済みを意味しません。

| 対象 | URL | 方針・残課題 |
|---|---|---|
| ANA新着 | https://tsubasa.ana.co.jp/ | 今回のPoC |
| J SPORTSカープ新着 | https://news.jsports.co.jp/tag/カープ/ | Python取得の403を調査 |
| 国内新着旅行記 | https://4travel.jp/domestic/travelogue | PICK UPを除外、旅行日と投稿日を区別、巡回間の取りこぼし確認 |
| 海外新着旅行記 | https://4travel.jp/overseas/travelogue | 国内とは別RSS、構造調査から実装 |
| JazzTokyo全ライターのコラム | https://jazztokyo.org/column/ | ライター横断の今号一覧の網羅性確認、必要に応じて各一覧を統合。全体RSSは今回の取得でXML解析エラー |
| 松和・指定カテゴリー | https://v-matsuwa.cocolog-nifty.com/blog/cat2315990/index.html | 既存RSS https://v-matsuwa.cocolog-nifty.com/blog/rss.xml をカテゴリーで絞る |
| WIRED Computer Science | https://wired.jp/tag/computer-science/ | タグ一覧から抽出 |
| カープ愛・限定コラム全体 | https://www.jsports.co.jp/baseball/carp/loveclub/column/ | 公開一覧だけで新着通知を目指す。403と認証の必要範囲を調査 |
| カープ愛・指定コーナー | https://www.jsports.co.jp/baseball/carp/loveclub/column/#fuyukacolumn | 同一HTMLを共有し別RSS。アンカーに対応する現在の構造は未確認 |

認証情報や会員限定本文は本PoCに含めない。認証が必要なサイトは公開される情報と認証情報の保管を別途設計する。
