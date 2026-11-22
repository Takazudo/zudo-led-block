# JLCPCB 発注パッケージ（生成器の基準セット・製造リリースではない）

このディレクトリ直下のファイルは、JLC の注文画面が何を求めるかを確かめるための生成器の基準セットで、**ここから直接アップロードしません。** 数量はオーナーの判断（2 台）です。

ファイルの段階:

1. 直下の `*_DRYRUN.csv` と `package.json`: 単基板の基準（参照のみ）。
2. `panels/`: オーナーが選んだリポジトリ面付けの基準セット（`scripts/a7_panel.py`）。
3. 日付付きセット: どれが現行かは `package-sets.json`（手で記録・生成器が検証）が決めます。生成器は各セットの `SHA256SUMS` と基板の識別を確かめ、現在の基板と一致しないセットを現行にできません。
   - `order/2026-11-13/`: **履歴（HISTORICAL_SUPERSEDED）。アップロードしません。** PR #88 より前の旧基板（controller 1.6 mm 4 層 `89310d53…e727`、LED leaf 0.6 mm 2 層の A5 ファイル `6244280c…1df3`）から `db0ca95` で出したもので、2026-11-12/13 のオーナーの試作ルート承認もこの旧識別に限ります。バイトと承認記録はそのまま残します。
   - 現在の基板（controller `d83691d6…db2b` 0.8 mm 4 層、LED leaf `bcf2e35d…94cf9` 0.8 mm 2 層、power adapter は A5 のまま `b0f071f2…5187`）のセットは `package-sets.json` の `current` が指します。状態が REVIEW_ONLY_NOT_FOR_ORDER の間はレビュー専用で、アップロードしません。現在の識別に対するオーナーの試作ルート承認と注文画面の確認の後にだけ、アップロードの対象になります。

どの段階も製造リリースではなく、readiness の発注ゲートは BLOCKED のままです（製造リリースまでの全条件を数えているため）。発注・アップロード・支払いはオーナーが行い、リポジトリには発注記録がありません。部品ごとの日付付きの観測と未取得の項目は `../procurement/sourcing-projection.json` にあります。

- `sources.json`（手で記録）: 2026-11-12 に匿名で読んだ JLC のページの受領記録（URL・取得時刻・SHA-256・引用）と、30 型番の部品ページの観測（Basic / Extended・在庫・予約可能数）。raw はコミットしていません。項目の意味はこちらの解釈です。
- `*_BOM_DRYRUN.csv` / `*_CPL_DRYRUN.csv`（生成）: JLC の列名（BOM: Comment / Designator / Footprint / JLCPCB Part #、CPL: Designator / Mid X / Mid Y / Rotation / Layer、mm）。数量・型番は調達台帳、位置・回転・面は凍結した基板ファイルから。
- `package.json`（生成）: 基板ごとの注文値、PCBA の区分（Economic / Standard）、部品の区分と経路、止めている項目（名前付き）。
- `export-receipt.json`: 最後の予行エクスポートのファイル名一覧。
- `panels/`: リポジトリ面付けの準備（`scripts/a7_panel.py`、未リリース）。詳細は `panels/README.md`。

`python3 scripts/a7_jlc_package.py` が生成し、`--check` が一致を確かめます。基板ファイルは書きません。`python3 scripts/a7_jlc_package.py export --out <リポジトリ外の空ディレクトリ>` はピン留めの KiCad 10.0.8 イメージで Gerber・drill・位置ファイルを出し、基板ごとの zip を作り、CPL が KiCad 自身の位置出力と一致するか（位置・回転・面）を確かめます。

オーナー向けの手順は `doc/src/content/docs/project/jlc-order-package.mdx`（生成）にあります。
