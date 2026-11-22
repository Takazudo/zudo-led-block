# A7 調達・組立の準備台帳

このディレクトリは [#87](https://github.com/Takazudo/zudo-led-block/issues/87) の **3HP / 0.8 mm controller / 0.8 mm rigid FR-4 leaf** へ製造入力を接続する工程準備台帳です。2HPは公差・組立の成立根拠を確保できず、0.8 mmの3HPを選定しました。両面maskは必要箇所以外を開口し、内層も広いGND面を設けません。透明PET/FPCは撤回しています。発注用BOM/CPL、製造承認、見積り、在庫予約ではありません。

旧1.6 mm controller / 0.6 mm leaf、`jlc-package/order/2026-11-13/`、当時の2台分の試作ルート承認は旧identityに限る履歴です。新設計の承認・製造releaseへ移し替えません。旧数量方針そのものを変更したという意味でもありません。現在の部品・PCBA受入と最終注文条件は別に照合します。板厚0.8 mmだけで実装サービス適合とは断定しません。露出銅の表面処理、局所mask/dam・via tentの製造条件も未確認項目として残します。

- `assembly-manifest.json`: 基板・入力ファイルの SHA-256、全実装リファレンス、DNP / テストパッド除外、外部部材、治具、サービス、未解決事項。
- `population.csv`: 人による実装点数確認用。**供給元へアップロードしないでください。**
- `ledger.md`: 点数と基板識別、部品ごとの日付付き観測の要約。
- `sourcing-projection.json`: 実装する 30 型番それぞれについて、最新の日付付き JLC 掲載観測（2026-11-22: `../jlc-package/sources.json` の `parts` に部品ページの受領記録、`price-audit/2026-11-22.json` に部品 API の行）と、それより古い観測（2026-11-12 の部品ページ・`price-audit/2026-11-12.json`・`supply-observations.json`）を `history` として分けて持ちます。各観測は取得時刻と受信バイトの SHA-256 を持ち、2026-11-22 分は匿名化した写しを非公開リポジトリ（`distributor-captures/jlcpcb-lcsc/zudo-led-block-a7-20261122/`、`provenance/private-resources.json`）に置きます。最新として示す観測は、履歴のどれよりも新しくなければ生成が失敗します。こちらの解釈（項目の意味・通貨・購入数の計算）と、どの型番も未取得の項目（納期・確定見積・在庫確保・実装受入）も記録します。部品ページと部品 API は別時刻の読み取りで、同時点のスナップショットではありません。掲載在庫が必要数を下回る型番は `listing_shortfall` に記録し、代替品は選びません。外した PCM13SMTR（C221842）は `retired` に履歴として残します。生成した `jlc-package/package.json` は入力にしません（この台帳を読むため循環になる）。
- `supplier-requests.json`: JLC 部品ライブラリ外の部材（完成電源ケーブル・SH4・IDC リボン・ねじ類・PMMA/PETG 部品・接着層・カバー・ラック金具）について、台帳の値から作った**未送信**の依頼内容。電源ケーブルは `mechanical/layout.json` の要求（現在 55 ± 3 mm、±3 は仮定、注文範囲 52–58 mm）をそのまま使います。供給元の回答・保証は記録していません（`supplier_answer` は null）。

手で書く入力（生成物ではありません）:

- `owner-decisions.json`: オーナーの判断と原文。発注数量（2 台）と調達の優先順（JLC 在庫 → JLC 予約注文または Global Sourcing → 例外）。推奨ではなく、オーナー自身の回答だけを記録します。部品選定のオーナーの方針（2026-11-12「basicallly choose JLC basic parts or have qty items. it's better」）: 部品を選ぶ・替えるときは、JLC の Basic 部品か、JLC が十分な在庫を持つ部品を優先する（`sourcing_preference.part_selection`）。方針であり、BOM や基板をそれだけで変えるものではありません。
- `supply-observations.json`: 日付付きの供給元掲載の観測（取得時刻・URL・raw の SHA-256・抜粋）。在庫確保・見積・実装受入ではありません。2026-11-12 の記録で、現在は履歴です。
- `price-audit/<日付>.json`: 日付ごとの部品 API 点検。最新は `scripts/a7_procurement.py` の `PRICE_AUDIT`、古いものは `PRICE_AUDIT_HISTORY` に並べ、書き換えません。

最初に挙げた 5 ファイル（`assembly-manifest.json`〜`supplier-requests.json`）は `python3 scripts/a7_procurement.py` が生成します。手編集せず、入力を修正して再生成してください。`--check` は現在入力との完全一致を確認し、古い識別、点数、二重計上や省略を拒否します。`python3 -m unittest scripts/tests/test_a7_procurement.py` が負の対照を実行します。

実装方式（SMD/THT）と面は、コントローラーが `fixture/native-geometry.json`（権威基板の SHA に結合した native export）のパッド属性、新leafがA7正本に結び付いたnative配置、変更しないadapterが不変A5配置のパッド属性から決まります。電源ケーブルと SH4 のピン対応は両端のネットリストから生成し、ネットが合わなければ失敗します。未解決事項は区分付き（`blockers[].class`）で、readiness がそれぞれを別のゲートとして扱います。

コントローラーは現在の A7 ネットリスト、カタログの A7 置換 3 点、実基板に結び付いた native 配置を照合します。新leafは `engineering/a7/electronics/led_leaf/` の正本・ネットリスト・native配置を参照し、旧A5 leafを現行製造入力として使いません。電源変換基板は1.6 mm・2層・zoneなしのA5正本を維持し、移動した機構配置はA7入力を参照します。リーフだけ 2 枚に掛け、71 配置を 81 実装点へ換算します。A5 の価格や在庫は現在値として転記しません。2026-11-12 の観測は現在の在庫や購入条件の保証ではなく、納期・確定見積・在庫確保・実装受入が揃うまでは調達未確定です。

機構部材は新PCBに結び付いた3HP FR-4機構検証の部品表から生成します。旧CAD結果を新identityへ付け替えず、再生成・照合が済むまでは未完了です。現行入力はadapter shift−4 mm（A5原点基準）、spacer4 mm、M2x20、電源cable55±3 mmです。トップキャップのボスと底キャップのフォークは一体形状なので別購入部品に数えません。ねじ・ナット・ワッシャーの形状包絡は注文型番ではありません。ジャック用 M6×0.5 ナットの同梱・適合、PMMA の公差とポケット、PETG、接着層、ラック締結部品は未確定です。電源ケーブルは `mechanical/layout.json` の要求をそのまま参照し、旧 A5 Molex 151340300 を代用品として載せません。

治具の材料は `fixture/materials.json` があれば取り込み、**モジュール 1 台当たりではなく治具 1 台当たり**として分離します。候補と採用品を混同しません。ソケット・ガイド・配線・支持材が未確定なら治具は未完のままです。

台帳の一致確認は native ERC / DRC、実装方向レビュー、現物の適合や電気・温度・光学評価を代替しません。A5 の配置は履歴データであり、新しい測定結果ではありません。書込みファームウェアの SHA は識別だけで、WS2812B-2020-V6 の T1L 問題 (#13) を解決しません。#8 / #10 / #13 の物理ゲートとオーナー承認が残ります。
