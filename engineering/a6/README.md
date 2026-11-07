# Light Block A6 — 制御基板のレイアウト版

A6 は A5 チェックポイントの上に作る **最小限の改訂** です。変更対象は制御基板の部品配置と 4 層配線だけで、
回路 (ネットリスト)・固定インターフェース・LED 基板・電源変換基板・機構・ファームウェアは A5 のままです。

> **製造リリースではありません。** A6 の制御基板は配線済みの候補で、実機・試作・物理評価は一切ありません。
> ネイティブ検証 (ERC / DRC / 回路との照合) が通っても、電子回路や製造の承認にはなりません。

## 何が権威 (source of truth) か

| 種別 | ファイル | 扱い |
|---|---|---|
| 権威 (authoritative) | `electronics/controller/controller.kicad_pcb` | 配線済みの制御基板。部品配置と銅箔の唯一の出典。どの生成コマンドもこのファイルを書きません |
| 派生 (derived) | `electronics/controller/controller.kicad_sch` | A5 の制御回路図そのもの。タイトル欄 (版・注記) だけを A6 に置換 |
| 派生 | `electronics/controller/controller.kicad_pro`, `LightBlock.kicad_sym`, `sym-lib-table` | A5 のバイト単位コピー (設計ルール・シンボルは無変更) |
| 派生 | `electronics/controller/fp-lib-table` | A5 のフットプリント `engineering/a5/electronics/footprints/LightBlock.pretty` を参照 |
| 派生 | `electronics/placement_and_connectivity.json` | 配線済み基板から抽出した配置と接続 (機構 CAD の入力。A5 と同じ形式) |
| 派生 | `manifest.json` | 継承した A5 入力と A6 ファイルのパス + SHA-256、所有区分、KiCad イメージのダイジェスト |
| 作成 (authored) | `electronics/routing_constraints.json` | 配線の根拠監査 (データシートのハッシュと該当箇所、適用内容、未解決事項) |
| 作成 | `verification/native_expectations.json` | ネイティブ検証の期待値と、許容する項目の理由 (生レポートは編集しない) |
| 作成 | `verification/residuals.md`, `verification/layout_rationale.md`, `verification/mechanical_impact.md` | 残る項目、配置変更の理由、機構への影響 |

A5 のファイルは `engineering/a5/` に置いたまま、パスとハッシュで参照します (コピーも編集もしません)。

## コマンド

```sh
# 派生ファイルとマニフェストが最新か (配線済み基板は書かない)
python3 scripts/a6_controller.py generate --check

# ネイティブ検証 (Docker と KiCad 10.0.8 イメージが必要。出力はリポジトリ外)
python3 scripts/a6_native_verify.py --repo . --out /tmp/a6-native

# 評価器のガードテスト (通常と -O の両方)
python3 -m unittest discover -s scripts/tests -p 'test_a6_*.py'
python3 -O -m unittest discover -s scripts/tests -p 'test_a6_*.py'

# 初期 (未配線) 基板の再生成は、リポジトリ外の空ディレクトリにだけ行う
python3 scripts/a6_controller.py init-board --out /tmp/a6-initial
```

配線済み基板を変更したら、ネイティブ検証の `raw/controller/board_facts.json` と `board_geometry.json` を使って
`python3 scripts/a6_controller.py generate --facts … --geometry …` を実行し、配置エクスポートとマニフェストを更新します。

## 状態の区別

- **A5 の履歴**: `engineering/a5/` の記録 (未配線の制御基板、130 未接続など) は A5 時点の結果として残します。
- **A6 の現状**: 配線済みの制御基板候補。残る DRC 項目は `verification/residuals.md` に個別に記載。
- **新たな検証**: CI の `a6-native` ジョブが、PR と main への push ごとに KiCad 10.0.8 で ERC・ネットリスト・回路照合・DRC・未接続・ゾーン再充填を実行します。
- **残る評価**: 実機の電気・温度・信号品質、ハーネスの装着適合、製造業者のスタックアップ確認、物理試作。
