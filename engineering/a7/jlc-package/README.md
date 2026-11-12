# JLCPCB 発注パッケージの予行（未リリース）

**アップロード・発注しないでください。** readiness の発注ゲートは BLOCKED で、ここにあるのは JLC の注文画面が何を求めるかを確かめる予行です。オーナーの判断（2 台）の数量で作っています。

- `sources.json`（手で記録）: 2026-11-12 に匿名で読んだ JLC のページの受領記録（URL・取得時刻・SHA-256・引用）と、30 型番の部品ページの観測（Basic / Extended・在庫・予約可能数）。raw はコミットしていません。項目の意味はこちらの解釈です。
- `*_BOM_DRYRUN.csv` / `*_CPL_DRYRUN.csv`（生成）: JLC の列名（BOM: Comment / Designator / Footprint / JLCPCB Part #、CPL: Designator / Mid X / Mid Y / Rotation / Layer、mm）。数量・型番は調達台帳、位置・回転・面は凍結した基板ファイルから。
- `package.json`（生成）: 基板ごとの注文値、PCBA の区分（Economic / Standard）、部品の区分と経路、止めている項目（名前付き）。
- `export-receipt.json`: 最後の予行エクスポートのファイル名一覧。
- `panels/`: リポジトリ面付けの準備（`scripts/a7_panel.py`、未リリース）。詳細は `panels/README.md`。

`python3 scripts/a7_jlc_package.py` が生成し、`--check` が一致を確かめます。基板ファイルは書きません。`python3 scripts/a7_jlc_package.py export --out <リポジトリ外の空ディレクトリ>` はピン留めの KiCad 10.0.8 イメージで Gerber・drill・位置ファイルを出し、基板ごとの zip を作り、CPL が KiCad 自身の位置出力と一致するか（位置・回転・面）を確かめます。

オーナー向けの手順は `doc/src/content/docs/project/jlc-order-package.mdx`（生成）にあります。
