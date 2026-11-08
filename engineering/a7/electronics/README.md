# A7 コントローラー電子設計（R4, #19）

**状態: 回路図は独立電気レビュー済み（#24、head `1a2f31a`）。基板は配置・配線済みで、独立したレイアウト・電気レビュー済み（PR #30、head `e2a2219`、main へのマージ `eb8adeb`、基板 sha256 `ec810aec…74f2`）。** 権威ある A7 基板 `controller/controller.kicad_pcb` を `candidate` とする A7 リビジョンゲート（`engineering/a7/verification/native_gate.json`）は新規実行で `PASS` です。これはデジタル検証だけの結果で、物理評価・製造リリースではありません。

## 何が A5 から変わったか

`scripts/a7_electronics.py` は不変の A5 設計データ（`engineering/a5/electronics/design/design_data.py`）を読み取り専用で読み込み、次の 3 部品だけを差し替えます。他の 69 部品・全ネットは A5 のままです。

| Ref | A5 | A7 | ピン → ネット |
| --- | --- | --- | --- |
| J1 (CV IN) | PJ-3582-B (C500090) | SOFNG PJ-324M (C22355739) | 1 SLEEVE→GND, 2 RING→GND, 3 RING normal→NC, 4 TIP→CV_THRU, 5 TIP normal→NC |
| J2 (CV THRU) | 同上 | 同上 | 同上（J1.4 と J2.4 は同一 CV_THRU ネット） |
| SW1 (ON/PGM/CV) | 1MS3T1B1M2QES-5 (C908270) | C&K PCM13SMTR (C221842) | 3 COMMON→GND, 1→MODE_A, 4→MODE_B, 2→NC |

モード符号は不変です: POS.1 (1-3) で MODE_A=0,B=1 → ON、POS.2 (2-3, 端子 2 は未接続) で 1,1 → PROGRAM、POS.3 (3-4) で 1,0 → CV。0,0 には到達しません。R9/R10 のプルアップ、MCU ピン、CV 経路（C13→R7→U7、R24/R25、VADC=(100/133)*(VDD/2+CV/8)）、LED 左右ストリーム、電源ケーブルの極性は A5 と同一です（差分チェックで他の接続変化はゼロ）。

## 推定・ミラー由来で、確定していないもの

- **PJ-324M のピン機能は INFERRED**（R1 `pinmap-a7-pj-324m`）。メーカーのピン機能表はありません。入荷部品の導通試験（tip/ring/sleeve/normal をピンごと）が物理ゲートとして残ります。
- **PJ-324M の端子位置は MIRROR**（LCSC 掲載の SOFNG 図面）。across 方向の符号は部品面に対して未確認。**穴径は ASSUMED**（図面の向きに合わせた長穴: 1.6×0.8 mm ドリル、2.3×1.5 mm パッド。1 と 4 は軸に直交、2・3・5 は軸方向。1.2×0.40 mm ブレードに片側約 0.2 mm。図面に穴寸法なし、Q3）。軸から 5.4 mm の辺はピン 4/5 側、6.1 mm はピン 2/3 側（図面）。バレル突出は 3.5 mm。軸高さ約 3.0 mm は推定値のままで、確定寸法に昇格させていません。
- **PCM13SMTR のランドパターンは MIRROR**（C&K 文書の LCSC ミラー, sha256 `1c2ca483…`）。#24 の電気レビューの指摘で図面どおりに修正: 信号パッド 0.7×1.5 mm を x −3.0/−1.5/+1.5/+3.0（1.5/3.0/1.5 の寸法列、全幅 6.0）、ペグ線から 1.0〜2.5 mm。保持パッド 1.0×0.8 mm は内側スパン 9.3 mm・間隔 1.13 mm。Ø0.9 mm のペグ穴 5.0 mm ピッチ。本体のペグ線に対する位置は ASSUMED。JLC 在庫 0（Q10）。
- 寸法ごとの出典区分は `footprints/footprint_sources.json` にあります。

## ファイルと所有区分

すべて `scripts/a7_electronics.py generate` が書く **derived** ファイルです（`engineering/a7/verification/source_authority.json`）。手で編集しません。`generate --check` が最新であることを確認します。A5 の回路図ライタの移植は `reproduce-a5` で A5 回路図をバイト一致で再生成して証明しています。

- `controller/` — 回路図、シンボルライブラリ、プロジェクト、ライブラリテーブル。A5 フットプリントは `engineering/a5/electronics/footprints/LightBlock.pretty` を読み取り専用で参照します。
- `footprints/LightBlockA7.pretty/` — PJ324M と PCM13SMTR のみ。

## 検証（新規実行、ピン留め KiCad 10.0.8 イメージ）

`python3 scripts/a7_schematic_check.py --out <リポジトリ外の空ディレクトリ>` が実行します。結果は `engineering/a7/verification/schematic/` にあります。

- ERC: 0 件（全重大度）
- 回路図→PCB パリティ: 0 件（`a7_electronics.py init-board` がリポジトリ外の空ディレクトリに生成した未配線のステージング基板に対して。ステージング基板の DRC/未接続数は基板結果ではありません）
- 振る舞いアサーション: 51 件すべて合格（レビュー記録済み）。差し替え部品（J1/J2/SW1）は全ピンが役割に割り当てられていること、未使用ピンがネットリストに実在することも確認します
- 承認差分チェック: 合格。観測差分 12 件（J1/J2/SW1 のフィールド）すべて component_replaced エントリでカバー。他部品の接続変化はゼロ

状態は `SCHEMATIC_REVIEWED` です。これは回路図フェーズの結果であり、基板・配線・物理ゲートの承認ではありません。レビュー記録（`authorized_delta.json` / `interface_roles/a7_controller.json` の `review`）は未解決の物理ゲートを列挙しています: PJ-324M のピン機能（TS/TRS 導通試験）、across 方向の符号、穴寸法（Q3）、軸高さ（Q1）、PCM13SMTR の本体センタリング、在庫（Q10）。

## 基板（配置・配線）

- **外形と座標**: R2 の外形 16.2×62.9 mm、board_x = 組立 Z − 0.2、board_y = 組立 Y − 48.5。F 面が部品面、B 面ははんだ面で 0.6 mm の低背領域（R0603 とテストパッドだけ）。
- **層構成**: 4 層 1.6 mm。In1.Cu は GND のベタ、F・In2・B にも GND の塗りつぶし。信号層は F・In2・B。
- **配置**: `scripts/a7_board.py place` が R2 の `placement-envelopes.json` のキープアウトに対して配置を検査し、`controller/placement.json` に書きます。J1/J2/J3/J5/SW1 は R2 が決めた位置に固定（J3 は MP パッドの基板端クリアランスのため x 12.6）。
- **配線**: `scripts/a7_board.py build` がリポジトリ外の空ディレクトリに未配線の基板とパッド形状を作り、`scripts/a7_route.py`（0.1 mm 格子の negotiated-congestion ルーター、seed 0）が配線案を作り、`a7_board.py apply` が配線・ビア・GND の塗りつぶしを加えて充填します。結果を確認してから権威基板にコピーしました。配線案は `engineering/a7/verification/routing/route_proposal_seed0.json` に記録し、現在の配置から同じ結果が再現します。通常の再生成は権威基板を書きません。
- **設計ルール差分**: ビアを 0.6/0.3 mm から 0.5/0.2 mm に変更（`min_via_diameter`、`min_through_hole_diameter`、ネットクラスのビア）。U1 周辺の配線を通すために必要でした。JLCPCB の公開能力（多層 0.15/0.25 mm 以上、推奨最小穴 0.2 mm）に基づき、`native_gate.json` の `design_rule_delta` に理由と証拠（`engineering/a7/verification/fab/jlcpcb_capabilities.json`、URL・取得ハッシュ・該当行）を記録しています。アニュラーリング 0.15 mm、配線幅・クリアランス・層数は A5 のままです。
- **ゲート結果**（ピン留め KiCad 10.0.8、新規実行）: ERC 0、パリティ 0、DRC 0、未接続 0、ゾーン再充填が一致、再生成で基板が変わらない、配置エクスポート `controller/board_placement.json` が最新。負の対照（配線切断・誤接続・充填ずれ・タイムアウト・A5 期待失敗・合成対照）はすべて検出。

## 残っている作業

1. レビューで挙がった軽微な改善（C11 と U6.5 の距離、C17/U7.2 付近の GND ビア追加、U4.1 近くの +5 V コンデンサ、CV_FILTER と VLED の並走 約 0.9 mm）。
2. 物理ゲート: PJ-324M のピン導通・穴寸法・軸高さの実測、PCM13SMTR の位置ごとの導通とランド適合、在庫（Q10）。
