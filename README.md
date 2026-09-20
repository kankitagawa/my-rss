# 個人用RSS 統合版 v1.1

GitHub Actions + Python + GitHub Pages。毎朝 **日本時間6:17頃** に20本のRSSを更新します。ANA PoCのRSS URL・記事ID・履歴を引き継ぎます。

## 今回の更新操作

ANAのPoCからでも、9本の統合版からでも、この一式で更新できます。既存のRSS URLは変えません。


1. ZIPを展開し、`my-rss` フォルダーの**中身**を、既存の [my-rss](https://github.com/kankitagawa/my-rss) に **Add file → Upload files** で上書きします。リポジトリのルートに `update_all.py`、`feedkit.py`、`config`、`tests` がある配置にします。ZIP自体はアップロードしません。
2. `.github/workflows/update.yml` も同梱の新しい内容に置き換えます。アップロードできない場合は、GitHubで既存ファイルを開き鉛筆ボタン（Edit）から全文を置き換え、**Commit changes**。フォルダーがまだなければ **Add file → Create new file** でパスを入力します。
3. **既存の `state` フォルダーは削除・上書きしません。** ZIPには実運用の履歴を含めていません。`state/ana.json` が残っていれば自動移行します。ANAのInoreader登録をやり直す必要はありません。
4. Pages設定は変更せず、**Actions → Update RSS → Run workflow** を1回実行します。追加ライブラリは自動でインストールされるため、PC側でのPython導入は不要です。
5. `build`、`deploy`、`check-results` が緑色になったら [公開ページ](https://kankitagawa.github.io/my-rss/) を開き、追加RSSをInoreaderへ登録します。公開ページのOPMLから一括登録も可能です（ANAは登録済みなので重複登録に注意）。

**重要：古い `update.yml` のままではANAだけが更新されます。** 新版では実行コマンドが `python update_all.py`、ジョブが3個になります。

## RSS一覧

| 対象 | RSSファイル | 取得方法 |
|---|---|---|
| ANA 翼の王国 | `ana.xml`（従来と同じ） | 公開WordPress API、30件ずつ |
| 国内の新着旅行記 | `4travel-domestic.xml` | 新着一覧と「もっと見る」。旅行日ではなく投稿日を使用 |
| 海外の新着旅行記 | `4travel-overseas.xml` | `category=new` を指定。人気順を混ぜない |
| JazzTokyo全ライター | `jazztokyo.xml` | Columnカテゴリーのライター横断一覧。著者名も収録 |
| 松和「日記・コラム・つぶやき」 | `matsuwa.xml` | 既存RSSのカテゴリー抽出。履歴と重ならないときはカテゴリーHTMLも取得 |
| WIRED Computer Science | `wired-computer-science.xml` | タグ一覧。広告枠を除外 |
| J SPORTS カープ新着 | `jsports-carp.xml` | タグ一覧を巡回。未取得記事のみ詳細ページで日付を補完 |
| カープ愛倶楽部・限定コラム全体 | `jsports-loveclub.xml` | ログイン前に見えるタイトル・リンク・日付のみ |
| カープ愛倶楽部・ふゆっぴコラム | `jsports-fuyuka.xml` | 上記ページの `#fuyukacolumn` だけ |

今回追加した11本：

| 対象 | RSSファイル | 取得方法 |
|---|---|---|
| Sports Illustrated MLB | `si-mlb.xml` | MLBの新着アーカイブ。ページ内の構造化データと次ページ |
| 地球の歩き方・特派員 | `arukikata-tokuhain.xml` | 特派員の新着一覧と次ページ。著者名も収録 |
| ザ・シネマ | `thecinema.xml` | コラム画面が使う公開JSON |
| J:magazine 映画コラム | `jcom-movie-column.xml` | 映画コラム一覧。省略されていない画像の説明からタイトル取得 |
| 好書好日 コラム | `book-asahi-column.xml` | 「記事一覧」と「もっと見る」の公開HTML。連載シリーズの入口は除外 |
| 小説丸・書店員さん おすすめ本コラム | `shosetsu-fbs.xml` | 既存のカテゴリーRSSと次ページ |
| Gizmodo Japan | `gizmodo.xml` | 新着一覧の埋め込みデータと次ページ。広告・ランキングを除外 |
| Gadget Gate | `gadget-gate.xml` | 既存RSSと次ページ |
| DIME ガジェット | `dime-gadget.xml` | カテゴリーの記事一覧と次ページ。タイトルは一覧の表記（省略形を含む） |
| GetNavi デジタル・ガジェット | `getnavi-gadgets.xml` | 既存のカテゴリーRSSと次ページ |
| 高校野球ドットコム | `hb-nippon.xml` | 新着記事一覧と次ページ。ランキング欄は除外 |

RSS URLは `https://kankitagawa.github.io/my-rss/feeds/ファイル名`。
「限定コラム全体」にはふゆっぴの記事も含まれます。両方を購読すると同じ記事が2つのフィードに出ます。

「週末大冒険」は既存RSSをInoreaderに直接登録済みのため、本システムでは再配信しません。

## 差分・保持・初回動作

- 記事URLを固定IDとして履歴と照合し、未取得記事を追加します。既知記事はタイトル・著者の修正のみ反映し、GUIDと公開日は維持します。
- URL・タイトル・公開日などの履歴は `state/*.json` に保存し、自動で削除しません。
- RSSには公開日順の最新500件（旅行記は1,000件）と、**初めて取得してから30日以内の記事すべて**を収録します。大量更新でも新着が件数上限で即座に消えない仕組みです。30日を過ぎても最新件数以内なら残ります。
- ANA・旅行記・J SPORTSタグ一覧は初回1ページ分から開始します。その後、前回確認済みの記事が累計3件見つかるまで、または一覧の終端まで巡回します（履歴が3件未満なら履歴件数を使用）。記事の追加でページ境界がずれても停止できます。
- 今回の追加サイトも初回は先頭ページ（公開JSON・一覧が1つだけなら掲載分）から開始します。2回目以降は、ページを遡れる9サイトで既知記事との重なりまで巡回します。
- ANAはPoCからの初回移行時に30件取得します。既存6件はそのまま保持し、残り24件が追加される見込みです。PoC時の午前0時の公開日は既知記事で維持します。
- ページ分割しない一覧は掲載分を初回にまとめて取り込みます。**JazzTokyoは初回854件、限定コラム全体は221件**を今回の検証で取得しました。初回の未読件数が多くなることは想定どおりです。
- 作者別ページから記事一覧を作り直す必要はなく、JazzTokyoの既存の横断一覧を使います。記事の公開日で全著者をまとめて並べます。
- 閲覧用の画像・本文は配信しません。限定記事の本文はリンク先で通常どおりログインして読みます。Cookieやパスワードの設定は不要です。

## 取りこぼしに関する実際の範囲

毎日チェックできた公開一覧・API内の未取得記事を追加します。初回より前の全アーカイブ収集、削除済み記事、公開一覧から外れた記事、サイト側で遡れない期間までの完全回収は保証しません。

- ザ・シネマは公開JSONに収録された記事（検証時10件）、J:magazineは映画コラム一覧の掲載分（37件）が範囲です。掲載外になった記事は取得できません。
- 小説丸の対象カテゴリーは、確認時の最新記事が2025年3月28日でした。新着がない日も過去記事を保持します。
- Gizmodoは元のRSS20件だけに依存せず、新着一覧の次ページを遡ります。小説丸・Gadget Gate・GetNaviのRSSにもページ巡回を実装しています。
- フォートラベルの新着リストにはサイト側の掲載範囲があります。「もっと見る」が終わった場合、全過去記事が存在するとは限りません。
- WIREDは現在取得できるタグ一覧20件、限定コラムは現在の公開一覧、JazzTokyoは現在のColumn横断一覧が対象です。
- 巡回上限は通常20ページ（J SPORTSは10ページ）。上限に達したらそのサイトはエラーにし、履歴を進めません。次回以降も再試行可能です。必要なら `config/sites.json` の `max_pages` を増やします。
- 過去の取得履歴と現在の一覧が一切重ならない場合は、公開ページに注意を表示します。サイトから消えた記事や既知URLの後ろに後日挿入された記事まで完全検知するものではありません。

## 一部のサイトが失敗した場合

そのサイトの状態を更新せず、履歴から前回のRSSを再構成します。他サイトは取得・公開を続けます。
初回取得に失敗して履歴がない対象はRSSリンクを出さず「初回取得待ち」と表示します。
取得の途中のページが失敗した場合にも、そのサイトの履歴を途中まで進めません。

公開後に `check-results` が赤色になります。これは「成功分を公開できたが、一部サイトが失敗」の意味です。公開ページの状態・備考、Actionsの `Generate RSS` を確認してください。
`warning` は履歴との重なりがない等の注意、`error` はそのサイトの更新失敗です。通知メールの有無はGitHubアカウントの通知設定によります。

履歴自体が壊れている場合は全体を停止し、既存の公開サイトを維持します。履歴を空として扱って既存RSSを消すことはしません。

## ファイル構成

- `update_all.py`：全対象の実行・失敗分の保持・公開ページとOPMLの生成
- `feedkit.py`：取得・サイト別抽出・差分・RSS生成
- `config/sites.json`：対象、CSSセレクター、件数、巡回上限
- `.github/workflows/update.yml`：毎日実行・履歴コミット・Pages公開・失敗表示
- `requirements.txt`：検証したライブラリのバージョン
- `tests/test_added.py`：追加サイトの日付・広告除外・RSSページ巡回等のテスト
- `tests/test_multi.py`：差分・移行・失敗分離・ページ巡回等のテスト
- `update.py` / `config/ana.json` / `tests/test_update.py`：旧PoC互換用。新ワークフローからは `update_all.py` を使用
- `state/`：GitHub側で既存ファイルを保持、新サイトの分は自動生成
- `public/`：実行時に生成、Pagesへ渡す。GitHubへのソース配置には不要

## 任意：PCで確認

Python 3.12で、展開した `my-rss` 内から実行します。

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m unittest discover -s tests -v
py -3 update_all.py --base-url https://kankitagawa.github.io/my-rss
```

ローカルで生成した `state` を実運用リポジトリへ上書きしないでください。

## 運用とサービス仕様

GitHub Freeの公開リポジトリ・標準Ubuntuランナー・Pagesを使用。課金サービスや常時稼働PCは不要です。スケジュールは遅延・欠落する可能性があります。60日活動がない公開リポジトリは定期実行が無効になる仕様があるため、長期に更新されないときはActions画面も確認してください。
既存PoCで表示されたActionsのNode.js非推奨警告は外部アクション由来です。本版では実績のあるPagesアクション版を維持しています。失敗扱いではありませんが、提供元の更新に合わせて今後見直します。

- [GitHub Pagesワークフロー](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub Actions料金](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [定期実行の仕様](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)

今回のローカル検証結果は `VERIFICATION.md`。全20サイト版のGitHub Actions・Inoreader確認は上書き配置後に行います。
