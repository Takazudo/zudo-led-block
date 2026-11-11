# A7 物理評価の準備と readiness

**未実施・製造リリースなし。** この文書は `scripts/a7_readiness.py` の生成物です。

レポート検証: VALID。発注適格性: **BLOCKED**。

## 共通記録 (Workflow F)

各実施は `run-templates/<手順ID>.json` をコピーし、unit、計器、条件、raw証跡（ファイルとSHA-256）、結果、次の行動を埋めて `records.json` の runs に追加します。雛形の identities と plan_sha256 は生成時点の値です。実施前に `python3 scripts/a7_readiness.py --check` が通ることを確認し、変わっていれば雛形を取り直します。失敗や再加工を上書きせず別 run として追加します。

受入値の確度: SOURCED = メーカー一次資料、MIRROR = 販売店掲載の写し、UNVERIFIED = 出典が未確認の記録、INFERRED = 推定、DESIGN = このプロジェクトの設計記録、ASSUMED = 仮定、UNRESOLVED = 未決（決める主体を記載）。値はすべて出典と照合済みで、照合できない値は生成時にエラーになります。

## 未実施の手順

### jack-continuity — PJ-324M 入荷時 TS/TRS 導通・端子対応

- 関連: Q2; #19
- 概要: 絶縁された未実装ジャック、TS/TRS プラグ、導通計。各挿抜状態で全端子対を測る。
- 根拠: `engineering/a7/electronics/README.md`
- 未決: 設計推定を採否判定する導通抵抗上限は未決。計器条件と判定値のレビューが必要。（区分: オーナーの判断）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- PJ-324M (C22355739) 未実装品を同一ロットから2個以上（入手元・ロット・数量を記録）
- TS (モノ) 3.5 mm プラグ 1本、TRS (ステレオ) 3.5 mm プラグ 1本（型番を記録）

計器・道具:

- 抵抗計/導通計（型番・校正記録）
- 拡大鏡またはマクロ撮影できるカメラ

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 非通電で実施する（電源・信号を接続しない）
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 端子に図面の番号 1〜5 を付け、番号が読める向きで本体を撮影する（どの面から見た番号かも写す）。
2. 無挿入で全10端子対の抵抗を測り、表に記録する。
3. TS プラグを最後まで挿入し、全10端子対とプラグの Tip/Sleeve 対各端子を測る。
4. TRS プラグで同じ測定をする。プラグを抜き、無挿入の状態をもう一度測る。
5. 結果を下の推定対応・基板ネットと突き合わせる。1 か所でも違えば FAIL とし、基板を変えるかどうかは別のレビューで決める（ここで設計を変えない）。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `terminal_matrix` | 無挿入/TS/TRS/再無挿入 × 全端子対と、プラグ接点対端子の抵抗表（CSV、単位 Ω、開放は OL） |
| `ts_plug_identity` | TS プラグの型番・購入元・写真 |
| `trs_plug_identity` | TRS プラグの型番・購入元・写真 |
| `jack_lot` | ジャックの購入記録、ロット、数量、外観写真 |
| `contact_photos` | 端子番号付けの写真と、各挿入状態の写真 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| pin-function | 端子機能が推定対応と一致すること | `{"1": "SLEEVE", "2": "RING", "3": "RING normal", "4": "TIP", "5": "TIP normal"}` | NONE | INFERRED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-pin-function-inference` |
| board-nets | 基板のネット割当（この対応が前提） | `"1 SLEEVE→GND, 2 RING→GND, 3 RING normal→NC, 4 TIP→CV_THRU, 5 TIP normal→NC"` | NONE | DESIGN | `engineering/a7/electronics/README.md` 引用 |
| supplier-cad-conflict | 供給元 CAD の端子4/5の矛盾を実物で解消すること | `"Supplier symbol appears to assign direct tip spring to5 and normal branch to4, contrary to current inferred mapping."` | NONE | UNVERIFIED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-supplier-cad-conflict` |
| ts-sleeve | TS プラグの sleeve が CV_THRU 端子に触れないこと（安全側の必須条件） | `"A tip/ring swap would put CV_THRU on the contact that"` | NONE | DESIGN | `engineering/a7/README.md` 引用 |
| test-current | 測定電流は接点定格以下 | `"50 mA, 24 V DC"` | NONE | MIRROR | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-contact-rating` |
| threshold | 「導通」「開放」と判定する抵抗値 | — | ohm | UNRESOLVED | 部品資料に接触抵抗/絶縁抵抗の規定がない。計器条件とあわせてレビューで決める |

### jack-dimensions — ジャック軸・スロット・端子・ナット

- 関連: Q1/Q3/Q4; #8
- 概要: 未実装品と実基板を基準面を明示して寸法測定。ナット・ワッシャを含める。
- 根拠: `engineering/a7/open-questions.md`
- 未決: メーカー公差、穴・リード寸法、適合ナット/ワッシャ仕様が必要。（区分: 外部の証跡・アクセス待ち）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- PJ-324M 未実装品 2個以上（jack-continuity と同じロット）
- A7 rev2 の裸基板または実装基板（基板 SHA を記録）
- M6×0.5 ナット候補とワッシャ候補（型番を記録。C22355739 にナットが付属するかは未確認）
- 入手済みなら A7 前面 PMMA

計器・道具:

- ノギス（分解能 0.01 mm）
- ハイトゲージまたは測定顕微鏡
- ピンゲージ（ボア径 3.6 mm 付近）
- M6×0.5 ねじゲージ

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 非通電で実施する（電源・信号を接続しない）
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 本体の座面を定盤に置き、ボアにピンゲージを入れて上端高さを測る。軸高さ = 上端 − ピン径/2。
2. 本体高さ・幅、軸から両側の辺、バレル突出、端子の幅/厚さ/座面からの突出を測る。
3. 基板スロットの寸法を測り、未実装品が無理なく入るかを確認する（押し込み力が要る場合はその旨を記録）。
4. ナット（とワッシャ）を PMMA 相当の厚さ 2.0 mm 板に締め、露出ねじ長と噛み合い長を測る。
5. 値を下の基準と比べ、外れた値は FAIL として記録する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `axis_measurements` | 軸高さ・本体寸法の測定表（基準面を明記） |
| `slot_lead_measurements` | 端子寸法と基板スロット寸法、挿入可否 |
| `nut_washer_fit` | ナット/ワッシャの型番、締結後の露出ねじ長と噛み合い長、写真 |
| `instrument_identity` | 計器の型番・分解能・校正記録 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| axis-height | 軸高さ（図面に寸法なし。推定） | `"approximately 3 (visually scaled 2.9-3.0 from the front view; not dimensioned)"` | mm | INFERRED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-axis-height` |
| axis-band | 設計で許容した軸高さの範囲 | `[2.6, 3.4]` | mm | INFERRED | `engineering/a7/mechanical/layout.json` `/variants/3hp/jack_axis_height_used/band` |
| thread | ねじ | `"M6x0.5"` | NONE | MIRROR | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-thread` |
| axis-to-edge | 軸から端子 4/5 側の辺 | `5.4` | mm | MIRROR | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-axis-to-edge` |
| axis-to-far-edge | 軸から反対側の辺（計算値） | `6.1` | mm | MIRROR | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-axis-to-far-edge` |
| body-height | 本体高さ | `6.0` | mm | MIRROR | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-body-height` |
| slot-drill | 基板スロットのドリル（仮定） | `"1.6×0.8 mm ドリル"` | NONE | ASSUMED | `engineering/a7/electronics/README.md` 引用 |
| thread-engagement | ポケット付き最悪条件のねじ噛み合い（設計値） | `1.25` | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/z_stack/thread_engagement_selected/worst_engaged` |
| engagement-criterion | ねじ噛み合いの検討基準 | `"1.0 mm study criterion"` | NONE | DESIGN | `engineering/a7/README.md` 引用 |
| tolerances | 各寸法の合否公差 | — | mm | UNRESOLVED | メーカー公差・推奨穴寸法・適合ナット仕様（Q1/Q3/Q4、供給元への質問） |

### switch-fit — PCM13SMTR 真理値・ランド・設定アクセス

- 関連: Q10; #19
- 概要: 未実装品の全接点を測定後、基板ランドとペグを照合。モジュールを外して設定工具を確認。
- 根拠: `engineering/a7/electronics/README.md`
- 未決: ランド/本体位置公差、導通判定抵抗、設定工具と保持条件の採否値が未決。（区分: 外部の証跡・アクセス待ち）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- PCM13SMTR (C221842) 未実装品 2個以上（在庫 0 のため入手経路を記録）
- SW1 実装済みの A7 rev2 基板（試作ルートで入手した場合）

計器・道具:

- 抵抗計/導通計
- 測定顕微鏡
- 設定用の非導電スティック（形状を記録）

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 非通電で実施する（電源・信号を接続しない）
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 未実装品で 3 位置それぞれの全端子対（1〜4）の抵抗を測る。
2. 実装基板では非通電で、各位置の端子 3–1 と 3–4 の導通を基板上で測る。
3. ペグ穴への収まりと、ランドに対する本体のずれを顕微鏡で測る。
4. モジュールを組んだ状態で、ラックから外して下側 (+Y) から設定スティックで 3 位置を切り替えられるか確認し、表示 ON / PGM / CV と位置が合うか確認する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `contact_truth_table` | 3 位置 × 全端子対の抵抗表（未実装品と実装後） |
| `land_peg_measurements` | ペグ・本体位置の測定と写真 |
| `setup_access` | 設定アクセスの写真/動画と使った道具 |
| `switch_lot` | 購入記録・ロット・数量 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| function | 接点表（端子 3 が共通） | `{"POS.1": "1-3", "POS.2": "2-3", "POS.3": "3-4", "common": "3"}` | NONE | SOURCED | `.claude/skills/component-a7-pcm13smtr/facts.json` `fact-a7-pcm13smtr-function` |
| mode-map | モード符号（POS.1=ON、POS.2=PROGRAM、POS.3=CV） | `"POS.1 (1-3) で MODE_A=0,B=1 → ON"` | NONE | DESIGN | `engineering/a7/electronics/README.md` 引用 |
| contact-rating | 接点定格（測定電流はこれ以下） | `"0.3 A @ 6 VDC"` | NONE | SOURCED | `.claude/skills/component-a7-pcm13smtr/facts.json` `fact-a7-pcm13smtr-contact-rating` |
| travel | 1 位置あたりの移動量 | `1.5` | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/switch/actuator_travel_per_position` |
| peg-diameter | ペグ径 | `0.8` | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/switch/peg_diameter` |
| access | 設定アクセスの方向 | `"+Y (below the module), module out of the rack"` | NONE | DESIGN | `engineering/a7/mechanical/layout.json` `/switch/access_from` |
| fit-and-contact | 本体位置の許容ずれと導通判定抵抗 | — | NONE | UNRESOLVED | メーカーの本体-ペグ基準寸法と、3.3 V / 10 kΩ 負荷での接触判定値のレビュー |

### harness-depth — 完成ハーネスの全長経路・極性・奥行き

- 関連:  #8
- 概要: 完成 SH4 と電源ケーブルを全長収納し、全コネクタ・ラベル・IDC を含めて組む。
- 根拠: `engineering/a7/mechanical/layout.json`
- 未決: 現物ケーブル径、許容曲げ、自由長公差とラベル、完成品供給仕様が未確定。（区分: オーナーの判断）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 完成電源ケーブル（PicoBlade 3P、A1→B3 / A2→B2 / A3→B1）候補
- 完成 SH4 ケーブル 2本
- 16→10 pin IDC リボン
- 組立済みモジュール（PMMA・スパイン・キャップ・基板）

計器・道具:

- ノギス
- 導通計
- 曲げ半径ゲージまたは写真スケール
- 奥行き測定用のデプスゲージ

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 非通電で実施する（電源・信号を接続しない）
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 電源ケーブルの自由長をコネクタ嵌合面から嵌合面まで測る（測り方を記録）。
2. 各ケーブルのピン対応を導通で確かめ、`assembly-manifest.json` の pin_map と比べる。
3. モジュールに組み込み、全ケーブルの経路・曲げを写真に残し、最小曲げ半径を測る。
4. PMMA 裏面から最も奥の点（ケーブル・コネクタ含む）までの奥行きを測る。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `polarity_matrix` | 各ケーブルのピン対応導通表 |
| `full_length_routing` | 組込み状態の経路写真 |
| `bend_measurements` | 最小曲げ半径の測定 |
| `installed_depth` | PMMA 裏面からの奥行き測定 |
| `cable_identity` | ケーブルの型番・購入記録・ラベル |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| power-free-span | 電源ケーブルの自由長（公称） | `57.0` | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/power_cable_requirement/finished_free_span_nominal` |
| power-tolerance | 自由長の公差（仮定） | `3.0` | mm | ASSUMED | `engineering/a7/mechanical/layout.json` `/power_cable_requirement/tolerance` |
| power-band | 自由長の許容範囲 | `[54.0, 60.0]` | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/power_cable_requirement/band` |
| a5-cable | A5 の 50 ± 6 mm ケーブルは使えない | `false` | NONE | DESIGN | `engineering/a7/mechanical/layout.json` `/power_cable_requirement/a5_cable/fits` |
| sh4-length | コントローラー→左リーフ SH4 の長さ（モデル） | `50.0` | mm | DESIGN | `engineering/a7/mechanical/exports/3hp/verification.json` `/cables/0/layout_length_mm` |
| depth-target | 奥行き目標（PMMA 裏面から） | `30.0` | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/z_stack/installed_depth_target` |
| bend-radius | 許容最小曲げ半径 | — | mm | UNRESOLVED | ケーブル製造元の仕様（モデルの曲げ半径は製造元で未確認） |

### pmma-supports — PMMA ポケット・締結・PETG 支持

- 関連: Q7/Q8/Q9; #8
- 概要: 製造ロットのPMMAと造形品を測る。段階的締結と保持を記録。
- 根拠: `engineering/a7/mechanical/README.md`
- 未決: 加工公差、締付トルク、割れ/クレージング、保持荷重、PETG工程条件の採否基準が未決。（区分: 外部の証跡・アクセス待ち）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- A7 前面 PMMA（加工先・材料ロットを記録）
- PETG で造形したスパイン・キャップ・ディフューザー（造形条件を記録）
- M2×18 ねじと M2 ナット、M6×0.5 ナット
- PJ-324M 実装基板

計器・道具:

- ノギス
- デプスゲージ（ポケット深さ）
- トルクドライバ（設定値を記録）
- プッシュプルゲージ

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 非通電で実施する（電源・信号を接続しない）
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. PMMA の板厚・穴径・後面ポケット深さと位置を測る。
2. 造形部品の寸法と造形条件（材料、ノズル温度、層厚、向き）を記録する。
3. M2×18 とジャックナットを段階的に締め、各段階で割れ・白化（クレージング）を確認し、トルクを記録する。
4. プッシュプルゲージでプラグ挿抜方向の荷重をかけ、保持とずれを記録する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `material_identity` | PMMA と PETG の材料・ロット |
| `pocket_tolerances` | 板厚・穴・ポケットの測定表 |
| `tightening_log` | 締付トルクと外観の記録 |
| `retention_load` | 荷重と変位/ずれの記録 |
| `print_settings` | 造形条件 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| panel-thickness | PMMA 板厚（公称） | `2.0` | mm | DESIGN | `engineering/a7/study/parameters.json` `/parameters/panel_thickness/nominal` |
| panel-thickness-tol | PMMA 板厚の公差（仮定） | `0.2` | mm | ASSUMED | `engineering/a7/study/parameters.json` `/parameters/panel_thickness/tol` |
| pocket-depth | 後面ポケット深さ | `0.5` | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/z_stack/rear_pocket_depth` |
| hole | ジャック穴 | `"6.2 mm hole for a 6.0 mm thread major diameter"` | NONE | DESIGN | `engineering/a7/study/parameters.json` 引用 |
| top-screw | 上キャップのねじ | `"M2x18"` | NONE | DESIGN | `engineering/a7/mechanical/layout.json` `/supports/top_cap_screw/designation` |
| plug-force | 保持が受けるプラグ挿抜力 | `"5.0-10.0 N inward and exiting"` | NONE | MIRROR | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-plug-force` |
| torque-retention | 締付トルクと保持荷重の合否 | — | N | UNRESOLVED | PMMA/PETG 加工先の公差・許容締付条件（供給元への質問）とレビュー |

### fixture-contact — SWD 治具の位置・接触・荷重

- 関連:  #19; #10
- 概要: 基板単体を支持した治具。PMMAとジャックは荷重経路に使わない。電源OFFで位置と短絡を検査後、承認された電源手順へ。
- 根拠: `engineering/a7/electronics/controller/board_placement.json`
- 未決: 完成治具の実位置公差、接触抵抗/繰返し回数、実挿入力と許容荷重が未決。（区分: クラウドで進められるデジタル作業）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 完成した SWD 治具（`engineering/a7/fixture/manifest.json` が digital_fixture_complete=true になった版）
- A7 rev2 実装基板

計器・道具:

- 測定顕微鏡
- 抵抗計
- プッシュプルゲージ

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 非通電で実施する（電源・信号を接続しない）
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す
- 治具の manifest が digital_fixture_complete=true かつ fresh_native_verified=true

手順:

1. 基板を治具に置き、各プローブ先端と TP の位置ずれを顕微鏡で測る。
2. 非通電で TP 間・TP–隣接部品間の短絡がないことを全組合せで測る。
3. ストロークと押付け荷重を測り、基板の支持点でたわみがないか確認する。
4. 支持部と逆挿入防止の写真を残す。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `registration_measurements` | TP ごとの位置ずれ |
| `contact_short_matrix` | 全組合せの短絡/導通表 |
| `stroke_force` | ストロークと荷重 |
| `support_photos` | 支持・逆挿入防止の写真 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| tp1 | TP1 のネット（B 面） | `"/+3V3"` | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/52/pads/1/net` |
| tp2 | TP2 のネット | `"/GND"` | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/53/pads/1/net` |
| tp3 | TP3 のネット | `"/SWDIO"` | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/54/pads/1/net` |
| tp4 | TP4 のネット | `"/SWCLK"` | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/55/pads/1/net` |
| tp5 | TP5 のネット | `"/NRST"` | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/56/pads/1/net` |
| tp-side | テストパッドの面 | `"B"` | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/52/side` |
| registration | 許容位置ずれ・ストローク・荷重 | — | mm | UNRESOLVED | 完成治具の設計（manifest の最悪 registration margin と計算ストローク）とプローブの製造元仕様 |

### firmware-waveforms — 書込み識別とLED実ロット波形

- 関連:  #13; #10
- 概要: 承認済み電源/プログラマ構成、SWD readback、校正したオシロスコープで左右列を観測。
- 根拠: `engineering/a5/firmware/dist/timing.md`
- 未決: Worldsemi訂正/新資料または購入ロットの根拠に基づく別レビューのFW判断が必要。現FWタイミングを承認しない。（区分: オーナーの判断）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- A7 rev2 実装基板と FR-4 リーフ 2枚、SH4 ケーブル
- `light_block_A5.bin`（SHA を identities と照合）
- WS2812B-2020-V6 の購入ロット

計器・道具:

- SWD プローブ（型番記録）
- オシロスコープ（帯域 ≥ 100 MHz を推奨、型番記録）
- ±12 V の電流制限付き電源

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 書込み後に読み戻し、BIN の SHA と一致するか記録する。
2. 保存された設定（モード・校正値）を読み出して保存する。
3. 左右の DATA 線を LED の DI ピンで測り、T0H/T0L/T1H/T1L/リセットを各 100 ビット以上で統計する。
4. オシロの時間軸設定とプローブ接続を記録する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `programming_readback` | 書込みログと読み戻し SHA |
| `stored_configuration` | 保存設定の読み出し |
| `led_lot` | LED のロット |
| `left_waveform` | 左ストリームの波形と統計 |
| `right_waveform` | 右ストリームの波形と統計 |
| `timebase_setup` | 計器設定とプローブ |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| ds-timing | データシート V1.4 のビット時間 | `"T0H 220-380; T1H 580-1000; T0L 580-1000; T1L 580-1000"` | ns | SOURCED | `.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-bit-timing` |
| fw-t1l | 現行 FW の T1L 設計範囲 | `"220..420"` | NONE | DESIGN | `engineering/a5/firmware/dist/timing.md` 引用 |
| reset | リセット時間 | `280` | us | SOURCED | `.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-reset-time` |
| vih | 入力 High 閾値（VDD 比） | `0.55` | fraction of VDD | SOURCED | `.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-vih` |
| t1l-decision | T1L の合否（データシートと FW が矛盾） | — | ns | UNRESOLVED | #13 の判断: メーカー訂正/新資料、または購入ロット実測に基づく別レビュー |

### power-current — 電源・電流制限

- 関連:  #10
- 概要: 電流制限電源、全レール電圧/電流計測、左右LEDの規定負荷。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 試験電圧/負荷/持続時間と合否値のレビュー済み数表が未作成。（区分: クラウドで進められるデジタル作業）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール（リーフ 2枚、ケーブル込み）

計器・道具:

- ±12 V の電流制限付きベンチ電源
- 電流計（各レール）
- オシロスコープ
- 電子負荷（VLED 負荷試験用）

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 電流制限を低く設定して ±12 V を投入し、+5 V・+3V3・VLED を測る。
2. 全消灯・通常点灯・全点灯（51/255 上限）の各状態で ±12 V 電流を記録する。
3. VLED に段階負荷をかけ、TPS2552 の電流制限と FAULT を観察する。
4. 各条件のレール波形を保存する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `supply_setup` | 電源設定と配線 |
| `rail_waveforms` | 各レールの波形 |
| `current_log` | 状態ごとの電流 |
| `load_matrix` | 負荷条件の表 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| ilim-formula | TPS2552 の電流制限式（最大側） | `"IOSmax(mA) = 22980 V / RILIM^0.94 kohm"` | mA | SOURCED | `.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-ilim-formula-max` |
| rilim | RILIM (R11) | `68000` | ohm | UNVERIFIED | `.claude/skills/component-0603waf6802t5e/facts.json` `fact-0603waf6802t5e-resistance` |
| u4-iout | TPS2552 の推奨出力電流 | `1.2` | A | SOURCED | `.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-roc-iout` |
| ldo-iout | TLV75533 の推奨出力電流 | `500` | mA | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-roc-iout` |
| buck-limit | AP63205 のピーク電流制限 | `"2.5 to 3.1 (typ 2.8)"` | A | SOURCED | `.claude/skills/component-ap63205wu-7/facts.json` `fact-ap63205wu-7-peak-current-limit` |
| channel-cap | FW の LED 上限 | `"51u"` | NONE | DESIGN | `engineering/a5/firmware/include/lb_config.h` 引用 |
| table | 条件ごとの許容電流・電圧の数表 | — | mA | UNRESOLVED | 上記の部品値から条件付き数表を作りレビューする（クラウドで作れる） |

### cv-thru-calibration — CV/受動THRU/校正

- 関連:  #10
- 概要: 校正したCV源と計測器、IN/THRU/ADCを同時測定。
- 根拠: `engineering/a7/electronics/README.md`
- 未決: 誤差/直線性/校正残差の採否値と測定不確かさが未決。（区分: クラウドで進められるデジタル作業）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール
- CV 源（−5〜+5 V を出せる校正済み電源または DAC）

計器・道具:

- 6½ 桁 DMM
- SWD プローブ（ADC 値の読み出し）

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. CV IN に段階電圧を入れ、各点で CV THRU 端の電圧、VDD、ADC 生値を記録する。
2. 上昇・下降の両方向で掃引する。
3. 校正係数を求め、残差を表にする。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `cv_sweep` | 入力電圧と ADC 値の表 |
| `vdd_adc_thru_data` | VDD・THRU 電圧 |
| `calibration_coefficients` | 校正係数 |
| `residuals` | 残差の表 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| transfer | ADC 入力の伝達式 | `"VADC=(100/133)*(VDD/2+CV/8)"` | NONE | DESIGN | `engineering/a7/electronics/README.md` 引用 |
| vdd-accuracy | VDD (3.3 V LDO) の出力精度 | `1` | % | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-output-accuracy` |
| residual | 許容誤差・直線性・残差 | — | V | UNRESOLVED | 抵抗公差と VDD 精度からの誤差予算をクラウドで作り、オーナーが許容値を決める |

### startup-reset — 起動・リセット・fault復帰

- 関連:  #10
- 概要: 規定の電源立上り/リセット/FAULT条件を一つずつ印加し全レールとLED enableを観測。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: ランプ/パルス条件、観測窓、復帰合否表をレビューする必要。（区分: クラウドで進められるデジタル作業）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール

計器・道具:

- オシロスコープ 4ch
- ±12 V 電源（立上り時間を変えられるもの）

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 速い/遅い立上りで ±12 V を投入し、+5 V、+3V3、NRST、LED_EN_N、LED_FAULT_N を同時に記録する。
2. 起動後の設定を読み出し、正しいモードで動くか確認する。
3. 短い瞬断を入れ、復帰を記録する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `reset_fault_enable_waveforms` | NRST・EN・FAULT の波形 |
| `rail_waveforms` | 各レールの波形 |
| `configuration_readback` | 起動後の設定読み出し |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| latch | TPS2552-1 はラッチオフ（過電流後は EN を戻すまで復帰しない） | `"TPS2552DxVx-1: enable active low; overcurrent fault response latch off; no quick output discharge"` | NONE | SOURCED | `.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-variant-latch` |
| ldo-vin | TLV75533 の推奨入力範囲 | `"1.45 to 5.5"` | V | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-roc-vin` |
| window | 立上り条件・観測窓・復帰の合否表 | — | NONE | UNRESOLVED | A5 の startup/fault 動作の記述から条件表を作ってレビューする |

### rail-collapse — 急速レール崩壊

- 関連:  #10
- 概要: 承認された負荷/電源遮断条件でレール低下と制御を同時観測。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 崩壊率、最悪負荷、5 V valid monitorの必要性を判断する合否基準が未決。（区分: オーナーの判断）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール

計器・道具:

- オシロスコープ
- 電子負荷
- ±12 V 電源

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. +12 V だけを段階的に落とし、+5 V・+3V3・MCU の状態を記録する。
2. LED 全点灯の最悪負荷で同じ試験をする。
3. 設定・校正値が失われないか読み出す。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `rail_enable_waveforms` | 崩壊時のレールと EN の波形 |
| `collapse_load_conditions` | 負荷と崩壊速度の条件 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| ldo-vin | TLV75533 の推奨入力範囲 | `"1.45 to 5.5"` | V | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-roc-vin` |
| criteria | 崩壊速度・最悪負荷・5 V 監視の要否の合否基準 | — | NONE | UNRESOLVED | オーナーの判断（5 V valid 監視を追加するかは設計判断） |

### partial-rails — 部分電源・逆給電・無電源CV

- 関連:  #10
- 概要: 許可された全レール組合せと無電源CV入力を電流制限下で試す。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 最大印加値、注入電流制限、順序、許容逆流値を部品資料から承認する必要。（区分: クラウドで進められるデジタル作業）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール

計器・道具:

- 独立した 3 系統の電源（+12 V、−12 V、5 V）
- 電流計
- オシロスコープ

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す
- 各入力ピンに流す電流は下の絶対最大定格を超えない

手順:

1. +12 V のみ、−12 V のみ、片側欠けの組合せで投入し、各レールと逆流電流を測る。
2. CV 入力に電圧をかけたまま電源を切り、注入電流を測る。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `rail_combination_matrix` | 組合せごとのレール電圧 |
| `injection_reverse_current` | 注入・逆流電流 |
| `rail_waveforms` | 波形 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| u6-input | OPA197 入力の絶対最大 | `"(V-) - 0.5 to (V+) + 0.5"` | V | SOURCED | `.claude/skills/component-opa197idbvr/facts.json` `fact-opa197idbvr-abs-max-input-voltage` |
| u6-current | OPA197 入力電流の絶対最大 | `10` | mA | SOURCED | `.claude/skills/component-opa197idbvr/facts.json` `fact-opa197idbvr-abs-max-input-current` |
| u7-input | TLV9001 入力の絶対最大 | `"(V-) - 0.5 to (V+) + 0.5"` | V | SOURCED | `.claude/skills/component-tlv9001idbvr/facts.json` `fact-tlv9001idbvr-abs-max-input-voltage` |
| u5-vi | SN74LVC2T45 入力の絶対最大 | `6.5` | V | SOURCED | `.claude/skills/component-sn74lvc2t45dcur/facts.json` `fact-sn74lvc2t45dcur-abs-max-vi` |
| led-vi | WS2812B 入力の絶対最大 | `"-0.3 to VDD+0.7"` | V | SOURCED | `.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-input-abs-max` |
| limits | 許容印加値・注入電流・順序の数表 | — | mA | UNRESOLVED | 上記の部品値から条件表を作ってレビューする（STM32 の注入電流はカタログで未取得） |

### u7-stress — U7 差動ストレス

- 関連:  #10
- 概要: CVと電源遷移中のU7両入力/電源を差動プローブで測る。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 安全な印加条件とプローブ帯域、部品限界の条件付き数表が未作成。（区分: クラウドで進められるデジタル作業）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール

計器・道具:

- オシロスコープ（帯域を記録）
- 差動プローブまたは 2ch 差分

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. CV 入力の最大/最小、電源投入・遮断時に U7 の入力ピンと電源ピンを同時に測る。
2. 入力と電源の差を計算し、絶対最大と比べる。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `input_supply_waveforms` | U7 入力と電源の波形 |
| `differential_stress_calculation` | 差の計算表 |
| `probe_identity` | プローブの型番と帯域 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| supply | TLV9001 電源の絶対最大 | `7` | V | SOURCED | `.claude/skills/component-tlv9001idbvr/facts.json` `fact-tlv9001idbvr-ratings` |
| input | TLV9001 入力の絶対最大 | `"(V-) - 0.5 to (V+) + 0.5"` | V | SOURCED | `.claude/skills/component-tlv9001idbvr/facts.json` `fact-tlv9001idbvr-abs-max-input-voltage` |
| current | TLV9001 入力電流の絶対最大 | `10` | mA | SOURCED | `.claude/skills/component-tlv9001idbvr/facts.json` `fact-tlv9001idbvr-abs-max-input-current` |
| conditions | 安全な印加条件と必要なプローブ帯域 | — | NONE | UNRESOLVED | 上記の値から条件表を作ってレビューする |

### ldo-reverse — LDO 逆電流

- 関連:  #10
- 概要: 入力/出力レール遷移を承認済み制限下で独立に制御。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 印加順序/上限と許容逆電流/時間のexact-part根拠が必要。（区分: 外部の証跡・アクセス待ち）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール

計器・道具:

- 電源 2 系統
- 電流計
- 温度計

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す
- +3V3 に外部電圧をかける試験は、許容逆電流が決まるまで実施しない

手順:

1. +5 V を切った状態で +3V3 側に SWD プローブ等から電圧がかかる場合の電流を測る。
2. 順序と時間を変えて記録する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `rail_waveforms` | 波形 |
| `reverse_current` | 逆電流 |
| `temperature` | U3 の温度 |
| `sequence_conditions` | 順序と時間 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| vin-max | TLV75533 VIN の絶対最大 | `6.0` | V | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-ratings` |
| en-max | TLV75533 EN の絶対最大 | `6.0` | V | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-abs-max-en` |
| reverse | 許容逆電流と時間 | — | mA | UNRESOLVED | TLV75533 の逆電流の記述をメーカー資料から取得する（カタログ未記録） |

### load-short — 負荷・短絡・保護

- 関連:  #10
- 概要: 制限電源と規定短絡負荷を使い、回復と温度を観測。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 短絡場所、時間、繰返しと復帰/最大温度基準の承認が必要。（区分: オーナーの判断）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール（交換用の予備を用意）

計器・道具:

- 短絡治具（場所ごと）
- 電流計
- サーモカメラまたは熱電対
- オシロスコープ

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す
- 破損の可能性がある試験なので、どのユニットを使うかを owner_prototype_route の範囲に含める

手順:

1. VLED、+5 V、+3V3 の各点で短絡を入れ、電流・温度・復帰を記録する。
2. TPS2552 のラッチ後、EN の再投入で復帰するか確認する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `short_recovery_waveforms` | 短絡と復帰の波形 |
| `current_temperature` | 電流と温度 |
| `fault_log` | FAULT の記録 |
| `load_conditions` | 場所・時間・回数 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| latch | TPS2552-1 のラッチオフ動作 | `"TPS2552DxVx-1: enable active low; overcurrent fault response latch off; no quick output discharge"` | NONE | SOURCED | `.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-variant-latch` |
| ldo-limit | TLV75533 の電流制限（最小） | `560` | mA | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-current-limit` |
| buck-limit | AP63205 のピーク電流制限 | `"2.5 to 3.1 (typ 2.8)"` | A | SOURCED | `.claude/skills/component-ap63205wu-7/facts.json` `fact-ap63205wu-7-peak-current-limit` |
| criteria | 短絡の場所・時間・回数と、復帰/最大温度の合否 | — | NONE | UNRESOLVED | オーナーの承認（破損を許す範囲）とレビュー |

### effective-capacitance — MLCC 実効容量

- 関連:  #10
- 概要: 実装型番/ロットのDCバイアスと温度条件を記録して容量/リップルを測る。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 必要容量下限と測定法を部品曲線と回路レビューで決める。（区分: 外部の証跡・アクセス待ち）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 実装と同じロットの MLCC 単品
- 組立済みモジュール

計器・道具:

- LCR メータ（DC バイアス付き）
- 恒温槽または温度計
- オシロスコープ

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 各 MLCC 型番を実際の DC 電圧で測る（単品）。
2. 回路のリップルを測る（通電試験は POWER の条件に従う）。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `component_lot` | ロット |
| `bias_temperature` | バイアスと温度の条件 |
| `capacitance` | 容量測定値 |
| `ripple_waveforms` | リップル波形 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| c10u | CL21A106KAYNNNE 定格電圧 | `25` | V | SOURCED | `.claude/skills/component-cl21a106kaynnne/facts.json` `fact-cl21a106kaynnne-ratings` |
| c22u | CL31A226KAHNNNE 定格電圧 | `25` | V | SOURCED | `.claude/skills/component-cl31a226kahnnne/facts.json` `fact-cl31a226kahnnne-ratings` |
| c4u7 | CL10A475KO8NNNC 定格電圧 | `16` | V | SOURCED | `.claude/skills/component-cl10a475ko8nnnc/facts.json` `fact-cl10a475ko8nnnc-ratings` |
| dc-bias | 動作点での実効容量 | `"effective capacitance at the A5 DC operating point not established"` | NONE | UNVERIFIED | `.claude/skills/component-cl21a106kaynnne/facts.json` `fact-cl21a106kaynnne-dc-bias` |
| minimum | 必要容量の下限 | — | NONE | UNRESOLVED | メーカーの DC バイアス曲線（未取得）と回路レビュー |

### thermal-optical — 温度・光学・Kumiko照明

- 関連:  #10
- 概要: 最悪負荷/周囲条件でインダクタ、ホットスポット、PETG、PMMAを測定し左右照明を撮影。
- 根拠: `engineering/a7/mechanical/README.md`
- 未決: 周囲条件/安定判定、部品/材料温度限界と見え方のオーナー採否が未決。（区分: オーナーの判断）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール（PMMA・PETG ディフューザー込み）

計器・道具:

- 熱電対または IR カメラ（放射率補正を記録）
- 室温計
- カメラ（露出固定）

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 室温を記録し、全点灯（上限 51/255）で温度が安定するまで記録する。
2. LED 付近、U2、U4、PETG、PMMA の温度を測る。
3. 露出固定で点灯の見え方を撮影する（暗所と通常照明）。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `temperature_series` | 温度の時系列 |
| `ir_corrections` | 放射率補正 |
| `material_lot` | PETG/PMMA のロット |
| `optical_photos` | 点灯写真 |
| `ambient_conditions` | 周囲条件 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| channel-cap | FW の LED 上限 | `"51u"` | NONE | DESIGN | `engineering/a5/firmware/include/lb_config.h` 引用 |
| switch-temp | PCM13SMTR の動作温度 | `"-40 to +85"` | C | SOURCED | `.claude/skills/component-a7-pcm13smtr/facts.json` `fact-a7-pcm13smtr-operating-temperature` |
| mlcc-temp | X7R MLCC の動作温度 | `"-55 to +125"` | degC | SOURCED | `.claude/skills/component-cc0603krx7r9bb104/facts.json` `fact-cc0603krx7r9bb104-operating-temperature` |
| limits | PETG/PMMA の温度限界、安定判定、見え方の合否 | — | degC | UNRESOLVED | オーナーの判断（見え方）と材料資料（未取得） |

### cv-noise — CV ノイズと DATA_L 結合

- 関連:  #10
- 概要: 静的CVを印加しDATA_L/左右ストリームのパターンを切替、ADC/THRUを同期観測。
- 根拠: `engineering/a7/verification/interface_review.md`
- 未決: 帯域、ノイズ統計と許容誤差の採否値が未決。（区分: オーナーの判断）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール

計器・道具:

- オシロスコープ（同期トリガ）
- CV 源

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- 通電は owner_prototype_route が許す範囲だけ。初回通電の電流制限値は未決なので、試験前にレビューで決めて conditions に記録する
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. LED データ送信中に CV_THRU と ADC 値を同期して記録する。
2. データパターン（全消灯/全点灯/交互）を変えて統計を取る。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `synchronous_waveforms` | 同期波形 |
| `noise_statistics` | ノイズ統計 |
| `probe_wiring` | プローブ配線 |
| `data_patterns` | データパターン |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| layout | 同層での CV と DATA の間隔（設計） | `"No CV node runs within 0.6 mm of DATA_L/R or ±12V_PROT on the same layer."` | NONE | DESIGN | `engineering/a7/verification/interface_review.md` 引用 |
| limit | 許容ノイズと帯域 | — | V | UNRESOLVED | cv-thru-calibration の誤差予算とオーナーの許容値 |

### service-envelope — 挿抜・交換・組立外形

- 関連:  #8; #10
- 概要: 全ケーブルと完成部品で挿抜、側板交換、スイッチ設定、再組立を実施。
- 根拠: `engineering/a7/mechanical/layout.json`
- 未決: 繰返し回数、許容力/損傷、組立ばらつきと合否基準が未決。（区分: オーナーの判断）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

準備するもの:

- 組立済みモジュール
- ユーロラック試験ケース

計器・道具:

- ノギス
- プッシュプルゲージ
- カメラ

実施前の条件:

- `records.json` の owner_prototype_route（対象版・数量・範囲・承認）が記録済み
- `readiness.json` の identities（基板/実装/回路図/FW/設定/機構/治具/台帳の SHA-256）を run にそのまま写す

手順:

1. 幅・高さ・奥行きを測る。
2. ラックへの挿抜とジャックの挿抜を決めた回数繰り返し、力と損傷を記録する。
3. 設定スイッチの切替えとケーブル交換を行い、前後の写真を残す。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `envelope_dimensions` | 外形寸法 |
| `insertion_extraction_force` | 挿抜力 |
| `replacement_record` | 交換記録 |
| `before_after_photos` | 前後の写真 |
| `part_identity` | 部品の型番 |

受入値:

| ID | 基準 | 値 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|
| width | 前面幅 (3HP) | `14.9` | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/variants/3hp/panel_width` |
| height | 前面高さ | `128.5` | mm | DESIGN | `engineering/a7/mechanical/exports/3hp/verification.json` `/parts/0/bbox_max/1` |
| depth | 奥行き目標 | `30.0` | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/z_stack/installed_depth_target` |
| plug-force | プラグ挿抜力 | `"5.0-10.0 N inward and exiting"` | NONE | MIRROR | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-plug-force` |
| switch-life | 設定スイッチの寿命 | `10000` | cycles | SOURCED | `.claude/skills/component-a7-pcm13smtr/facts.json` `fact-a7-pcm13smtr-life` |
| cycles | 繰返し回数と許容損傷 | — | NONE | UNRESOLVED | オーナーの判断 |

## ゲートの区分

| 区分 | ゲート数 |
|---|---:|
| CLOUD_DIGITAL（クラウドで進められるデジタル作業） | 8 |
| OWNER_DECISION（オーナーの判断） | 15 |
| ACCESS_EVIDENCE_HOLD（外部の証跡・アクセス待ち） | 13 |
| PHYSICAL_ONLY（実機が必要） | 20 |

## 現在のブロッカー

- fixture digital design incomplete or unverified
- fixture: unresolved preparation blockers
- assembly_manifest: supply-observations: Current stock, price, MOQ, packaging, lead time and assembly applicability not obtained for any line except the dated C221842 zero-stock observation; stock never reserved.
- assembly_manifest: order-quantity: No agreed order quantity; 1/10/100 are comparison scenarios only, so no supply observation can be judged available for a proposed order.
- assembly_manifest: switch-supply: PCM13SMTR (C221842) had JLC stock 0 / presale 0 at 2026-11-09; wait, buy elsewhere, or accept a reviewed alternate with its own contact table and fit review.
- assembly_manifest: jack-switch-qualification: PJ-324M pin function, slot, axis height and nut fit, and PCM13SMTR truth table and land fit, need received parts (jack-continuity, jack-dimensions, switch-fit).
- assembly_manifest: finished-cables: Finished A7 power cable (57 mm, +/-3 ASSUMED), SH4 cables and IDC ribbon not selected; supplier answers and the owner choice of assembly are needed before physical routing checks.
- assembly_manifest: mechanical-materials: PMMA sheet and pocket tolerances, PETG process and orderable fastener part numbers are not sourced; the model carries designations (M2x18, M1.6x4) and envelopes only.
- assembly_manifest: rack-hardware: Owner rack rail/thread interface and fasteners not specified.
- assembly_manifest: fixture-materials: Fixture design and materials incomplete (see fixture manifest); physical contact/load tests follow.
- assembly_manifest: prototype-and-release: No owner-approved prototype route, no reviewed manufacturing package and no release approval.
- jack-continuity: criterion unresolved or review receipt missing
- jack-continuity: NOT_MEASURED: no run
- jack-dimensions: criterion unresolved or review receipt missing
- jack-dimensions: NOT_MEASURED: no run
- switch-fit: criterion unresolved or review receipt missing
- switch-fit: NOT_MEASURED: no run
- harness-depth: criterion unresolved or review receipt missing
- harness-depth: NOT_MEASURED: no run
- pmma-supports: criterion unresolved or review receipt missing
- pmma-supports: NOT_MEASURED: no run
- fixture-contact: criterion unresolved or review receipt missing
- fixture-contact: NOT_MEASURED: no run
- firmware-waveforms: criterion unresolved or review receipt missing
- firmware-waveforms: NOT_MEASURED: no run
- power-current: criterion unresolved or review receipt missing
- power-current: NOT_MEASURED: no run
- cv-thru-calibration: criterion unresolved or review receipt missing
- cv-thru-calibration: NOT_MEASURED: no run
- startup-reset: criterion unresolved or review receipt missing
- startup-reset: NOT_MEASURED: no run
- rail-collapse: criterion unresolved or review receipt missing
- rail-collapse: NOT_MEASURED: no run
- partial-rails: criterion unresolved or review receipt missing
- partial-rails: NOT_MEASURED: no run
- u7-stress: criterion unresolved or review receipt missing
- u7-stress: NOT_MEASURED: no run
- ldo-reverse: criterion unresolved or review receipt missing
- ldo-reverse: NOT_MEASURED: no run
- load-short: criterion unresolved or review receipt missing
- load-short: NOT_MEASURED: no run
- effective-capacitance: criterion unresolved or review receipt missing
- effective-capacitance: NOT_MEASURED: no run
- thermal-optical: criterion unresolved or review receipt missing
- thermal-optical: NOT_MEASURED: no run
- cv-noise: criterion unresolved or review receipt missing
- cv-noise: NOT_MEASURED: no run
- service-envelope: criterion unresolved or review receipt missing
- service-envelope: NOT_MEASURED: no run
- material assembly_service: missing or ambiguous dated observation
- material finished_cables: missing or ambiguous dated observation
- material fixture: missing or ambiguous dated observation
- material jack: missing or ambiguous dated observation
- material pmma_petg_hardware: missing or ambiguous dated observation
- material switch: missing or ambiguous dated observation
- owner-approved sample/prototype route absent for this revision and quantity
- reviewed manufacturing files and explicit revision-bound owner release absent

## 別案

- PET: Q11/Q11a–f: process, copper/vias/coverlay, lamination, force and optical tests remain separate. Reuse pet-fpc.md questions 1–9; not sent.
- 2HP: Parked: Q1/Q6 evidence, owner choice, 0.8 mm controller and new routing required.
