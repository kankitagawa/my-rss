# 個人用RSS — ANA 翼の王国 PoC

このフォルダーの中身をGitHubリポジトリのルートに置くと、ANA「翼の王国」の公開新着一覧を1日1回取得し、RSSをGitHub Pagesで配信できます。**今回動くのはANAのみです。** 他サイトの対象一覧は `TARGETS.md` に残しています。

## 最短の始め方（PCへのPython導入不要）

1. ZIPをダウンロードしてWindowsで「すべて展開」します。
2. [GitHubで新規リポジトリを作成](https://github.com/new)します。名前は `my-rss`、公開範囲は **Public**、READMEを追加して作成します。この無料構成ではコード・取得履歴・RSSが公開されます。公開してよい新着メタデータのみを扱います。
3. リポジトリの **Add file → Upload files** を開き、展開した `my-rss` の**中身**をドラッグしてアップロードします。`my-rss` フォルダーごと置かず、直下に `update.py` と `config`、`tests`、`.github` などが並ぶ形にしてください。ZIPそのもののアップロードでは動きません。
4. **Commit changes** で保存します。GitHub上に `.github/workflows/update.yml` があることを確認してください。ブラウザのアップロードでこのフォルダーが抜けた場合は、**Add file → Create new file** でファイル名に `.github/workflows/update.yml` を指定し、同梱ファイルの内容を貼って保存します。
5. **Settings → Pages → Build and deployment → Source** を **GitHub Actions** にします。提案される別のワークフローを新規作成する必要はありません。
6. **Actions → Update RSS → Run workflow → Run workflow** を押します。既定ブランチ（通常 `main`）で実行してください。Actionsの有効化画面が出たら有効にします。
7. 実行が緑色になるまで待ちます。`build` と `deploy` の両方が成功すると公開完了です。初回は数分かかる場合があります。
8. **Settings → Pages** の公開URLを開き、「ANA 翼の王国・新着記事（非公式）」のリンク先をコピーしてInoreaderのフィード追加欄に貼り付けます。

通常のRSS URLは `https://あなたのGitHubユーザー名.github.io/my-rss/feeds/ana.xml` です。リポジトリ名や独自ドメインで変わるので、Pagesの公開画面から確認するのが確実です。

アカウント名・URLをコードへ手入力する必要はありません。公開URLはGitHub側の設定から自動で取得します。パスワード、APIキー、Personal Access Tokenも不要です。

## 動作の説明

- 毎日日本時間06:17頃に1回起動。GitHubの混雑で遅延・実行欠落が起きる可能性があり、正確な時刻は保証されません。
- 通常のHTTPで新着欄だけを取得。記事本文や画像は配信せず、公開タイトル・リンク・日付だけをRSS化します。
- 記事URLを固定IDとして使用。既知記事はタイトルを修正してもIDと公開日を保持し、新規記事として作り直しません。Inoreaderでの表示・既読挙動は登録後に実測します。
- 初回は新着欄に掲載されている記事を取り込みます。過去全記事の収集ではありません。RSSは最大100件、URLとメタデータの履歴は `state/ana.json` に蓄積します。
- 新着欄から消えた記事も履歴に残します。ただし、巡回間に掲載されて消えた記事は拾えません。現段階ではANA先頭の新着欄だけが対象です。
- 0件、日付欠損、不正なリンク、前回比で半分未満の件数ではエラー停止。公開済みRSSは更新されません。
- 履歴をGitHubへ保存してから公開します。公開だけが失敗した場合も次回は履歴から全RSSを作り直せます。
- `last_checked` を実行ごとに履歴へ保存します。履歴ファイルを消すと新規判定がリセットされるため、通常は削除しません。
- 1サイトのPoCなので専用HTML解析処理です。今後、サイト別アダプターやCSSセレクター設定へ拡張します。

## エラーが出たら

**Actions → 失敗した実行 → build または deploy → 赤いステップ** を開き、エラー部分をこのチャットに送ってください。

| エラーの場所 | 確認すること |
|---|---|
| Configure Pages | Settings → PagesのSourceがGitHub Actionsか |
| Save history（403） | Settings → Actions → GeneralのWorkflow permissions、組織の制限、既定ブランチへの書込み制限。個人用の新規リポジトリを想定。ブランチ保護を一律解除せず、エラーを共有してください |
| Generate RSS（HTTP 403等） | この実行環境からのアクセスが拒否された可能性。ログを共有してください |
| Generate RSS（件数低下等） | サイト構造変更や一時的な取得異常。自動で前回結果を消しません |
| Deploy | Pagesとgithub-pages環境の設定、実行の権限を確認 |

再実行は **Run workflow** で行えます。修正ファイルをアップロードしただけでは実行しない設計です。
Actionsの失敗通知はGitHubアカウントの通知設定に依存します。独自のメール送信は実装していません。
公開リポジトリでは60日間活動がないと定期実行が無効になる仕様があります。長期間更新されない場合はActions画面で有効状態を確認し、必要に応じて再有効化してください。

## 任意：Windowsで先に確認

Python 3.11以上がある場合、展開フォルダー `my-rss` でPowerShellを開きます。

```powershell
py -3 -m unittest discover -s tests -v
py -3 update.py
py -3 update.py
```

追加ライブラリのインストールは不要です。1回目の `new` は取得記事数、変化がなければ2回目は `new=0` になります。出力は `public/feeds/ana.xml`。ローカルの確認結果をGitHubへアップロードする必要はありません。GitHubへ配置するのは同梱のプログラム・設定・テストです。

## 無料運用の前提と参考

GitHub Freeの公開リポジトリ、標準Ubuntuランナー、GitHub Pagesを使用します。有料ランナーや独自サーバーは使いません。サービス仕様変更時には再確認が必要です。

- [Pagesの公開範囲・公式ワークフロー](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Actionsの料金](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [定期実行の制約](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [取得元：ANA 翼の王国](https://tsubasa.ana.co.jp/)

GitHub Actionsでの本番実行、Pages公開、Inoreaderでの購読はユーザーのリポジトリへ配置後に確認します。
