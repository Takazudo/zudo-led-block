# A5 部品在庫・価格 XLSX

`build_parts_workbook.mjs` は、プロジェクト直下の `procurement_rows.json` から `deliverables/light_block_A5_parts.xlsx` を再生成します。成果物は 3 シートです。

- **部品表**: JLC PCBA 部品 30 行・実装81点/台。黄色の試作・比較台数と各行の個数/台を変更すると、必要数、価格帯、単価、金額が再計算されます。
- **価格帯**: 部品ごとの数量帯、USD 単価、在庫、先行購入上限、Library、実装区分、確認日時、URL、未完の設計事項。
- **外部品**: 別調達する既製ケーブル、前面板、PETG 部材、金具。未確認単価をゼロと扱いません。

価格帯は部品ごとの昇順の範囲を `VLOOKUP(...,TRUE)` で参照します。入力データに存在する数量境界と単価を保持します。価格帯の最終 `max_qty` の空欄は上限なしの取得値です。部品の試算は実装数量に基づき、MOQ、調達ロス、実装費、治具、送料、税は加算しません。100 台は比較シナリオであり、発注指示ではありません。

`InStock` と `AvailableOrderQty` は別々の値です。後者がゼロでも PCBA 不可とは扱いません。在庫予約、部品価格の固定、回路/機構/実装のリリース完了を示す表ではありません。Standard 実装では Basic もフィーダー費の対象である旨と、確認した料金ページの URL を記載しています。

## 再生成

Artifact Tool を使える Codex primary Node runtime が必要です。プロジェクト直下から、実行ファイルと依存関係を OS の一時ディレクトリへ置き、次の形で実行します。

```bash
lb_project_dir="$PWD"
lb_xlsx_workdir=$(mktemp -d /tmp/light_block_A5_xlsx.XXXXXX)
cp "$lb_project_dir/spreadsheet/build_parts_workbook.mjs" "$lb_xlsx_workdir/"
ln -s "$CODEX_PRIMARY_RUNTIME_NODE_MODULES" "$lb_xlsx_workdir/node_modules"
cd "$lb_xlsx_workdir"
LB_PROJECT_DIR="$lb_project_dir" "$CODEX_PRIMARY_RUNTIME_NODE" build_parts_workbook.mjs "$lb_project_dir/procurement_rows.json"
```

必要なら `LB_PROJECT_DIR`、`LB_OUTPUT_DIR`、`LB_QA_DIR` を指定できます。入力 JSON のパスは第一引数でも指定できます。日本語の表示確認には Noto Sans JP を使用しています。

## 検証

ビルダーは実際のワークブックを再計算し、0/1/10/100 台、空欄、価格帯の境界、個数/台の変更、元データの費用統制値を検証します。数量 0 と未入力を区別し、先行購入上限 0 も保持します。外部品の価格と数量も独立した計算で照合します。

`../spreadsheet_qa/` に再計算結果、数式検査、エラー検索、全シートの表示確認用 PNG を保存します。納品 XLSX の ZIP/XML も読み取り検証します。検証には Artifact Tool を使用し、Excel デスクトップアプリ自体は起動していません。

元データの確認日時以降に在庫・価格は変化し得ます。価格・在庫の再取得はビルダーに含まれません。
