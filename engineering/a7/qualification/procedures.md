# A7 物理評価の準備と readiness

**未実施・製造リリースなし。** この文書は `scripts/a7_readiness.py` の生成物です。

レポート検証: VALID。発注適格性: **BLOCKED**。

## 共通記録 (Workflow F)

各実施は `run-templates/<手順ID>.json` をコピーし、unit、計器、条件、raw証跡（ファイルとSHA-256）、結果、次の行動を埋めて `records.json` の runs に追加します。雛形の identities と plan_sha256 は生成時点の値です。実施前に `python3 scripts/a7_readiness.py --check` が通ることを確認し、変わっていれば雛形を取り直します。失敗や再加工を上書きせず別 run として追加します。

受入値の確度: SOURCED = メーカー一次資料、MIRROR = 販売店掲載の写し、UNVERIFIED = 出典が未確認の記録、INFERRED = 推定、DESIGN = このプロジェクトの設計記録、ASSUMED = 仮定、CALCULATED = 一次資料と設計記録だけを入力にした計算、PROPOSED = レビュー用の提案（採否前。ゲートを解除しない）、UNRESOLVED = 未決（決める主体と入手先を記載）。計算値は生成時に入力の出典を照合して再計算し、計算値の確度は最も弱い入力に合わせます。各値は出典の値と一致すること、確度が出典の記載（部品 fact の provenance、記録に並ぶ確度、引用行の ASSUMED / INFERRED）を超えないことを生成時に検査します。出典は部品 fact と設計記録だけで、この計画や生成物は引用できません。範囲（min/max 等）の向きは人が出典を読んで付けたもので、自動照合していません。

## 状態フラグ

手順の前提と発注ゲートが読む生成物のフラグです。「ゲート」は readiness が発注ゲートで読むもの、「参考のみ」は進捗の表示でゲートを解除しません。どの手順も、自分（または自分を待つ手順）しか満たせないフラグを前提にできません（生成時に検査）。

| 生成物 | フラグ | 現在値 | 役割 | 満たす手順 | 説明 |
|---|---|---|---|---|---|
| fixture | `digital_fixture_complete` | `false` | ゲート | fixture-contact | README の完了基準 1–5 がすべて満たされたこと。基準 5（接触・荷重・位置決め・ストローク・損傷の実機試験）は fixture-contact の観測でしか満たせないので、どの手順の前提にもできない。 |
| fixture | `fresh_native_verified` | `false` | ゲート | —（デジタル生成物） | 治具形状の native 検証。B 面の全突起の高さに出典があることを含み、資料の入手で満たす（手順の観測では満たさない）。 |
| fixture | `digital_criteria_1_to_4_met` | `false` | 参考のみ | —（デジタル生成物） | README の基準 1–4 がデジタルで満たされ、デジタルのブロッカーがないこと（fresh_native_verified を含む）。進捗の表示で、完了フラグでも発注適格性でもない。fixture-contact を始める前提。 |
| fixture | `hardware_proposal_complete` | `true` | 参考のみ | —（デジタル生成物） | 治具の各金物要求（materials.json）に出典付きの候補（hardware_proposal）が 1 つずつあること。オーナー承認待ちの提案で、選定でも承認でもない。true かつ基準 1–4 が満たされると、調達の assembly:fixture-materials はオーナーの判断（加工先の選択と金物の承認）に移る。 |

## 未実施の手順

### jack-continuity — PJ-324M 入荷時 TS/TRS 導通・端子対応

- 関連: Q2; #19
- 概要: 絶縁された未実装ジャック、TS/TRS プラグ、導通計とミリオーム計。各挿抜状態で全端子対を測り、閉じた接点の接触抵抗を測る。
- 根拠: `engineering/a7/electronics/README.md`
- 基準: 採用済み（プロジェクトのコーディネーター（オーナーが委ねた作業方針による）、記録 `engineering/a7/qualification/reviews/2026-11-11-coordinator-criteria-acceptance.md`）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 基準はコーディネーターが採用済み（オーナー本人ではない）。PCB を発注する前に実物の PJ-324M で手順を実施し、端子 4/5 を確定する（O0）。

準備するもの:

- PJ-324M (C22355739) 未実装品を同一ロットから2個以上（入手元・ロット・数量を記録）
- TS (モノ) 3.5 mm プラグ 1本、TRS (ステレオ) 3.5 mm プラグ 1本（型番を記録）

計器・道具:

- 抵抗計/導通計（型番・校正記録）
- ミリオーム計（4 端子法、測定電流 50 mA 以下に設定できるもの。型番・測定電流・校正記録）
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
5. TS と TRS プラグを挿入した状態で、閉じている各接点（プラグ tip–tip 端子、sleeve–sleeve 端子、TRS の ring–ring 端子）の抵抗をミリオーム計で測る。4 端子法で、測定電流は 50 mA 以下。2 端子法しか使えない場合は、測定リードとプラグを短絡して読んだ値を差し引き、その値も記録する。
6. 端子 4 と 5 のどちらが tip 接点（プラグの tip と導通）で、どちらがその normal（無挿入で tip 接点と導通し、挿入で開放）かを判定し、terminal_matrix に「tip=端子N、tip normal=端子M」と明記する。供給元 symbol は端子 5 を tip としており、現在の推定（端子 4 = tip）と矛盾する。この判定は PCB を発注する前に必須。
7. 結果を下の推定対応・基板ネットと突き合わせる。1 か所でも違えば FAIL とし、基板を変えるかどうかは別のレビューで決める（ここで設計を変えない）。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `terminal_matrix` | 無挿入/TS/TRS/再無挿入 × 全端子対と、プラグ接点対端子の抵抗表（CSV、単位 Ω、開放は OL）。閉じた接点の接触抵抗（mΩ、測定法・測定電流・差し引いたリード抵抗）を別の列に記録 |
| `ts_plug_identity` | TS プラグの型番・購入元・写真 |
| `trs_plug_identity` | TRS プラグの型番・購入元・写真 |
| `jack_lot` | ジャックの購入記録、ロット、数量、外観写真 |
| `contact_photos` | 端子番号付けの写真と、各挿入状態の写真 |

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| pin-function | 端子機能が推定対応と一致すること | `{"1": "SLEEVE", "2": "RING", "3": "RING normal", "4": "TIP", "5": "TIP normal"}` | exact | NONE | INFERRED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-pin-function-inference` |
| board-nets | 基板のネット割当（この対応が前提） | `"1 SLEEVE→GND, 2 RING→GND, 3 RING normal→NC, 4 TIP→CV_THRU, 5 TIP normal→NC"` | reference | NONE | DESIGN | `engineering/a7/electronics/README.md` 引用 |
| supplier-cad-conflict | 供給元 CAD の端子4/5の矛盾を実物で解消すること | `"Supplier symbol appears to assign direct tip spring to5 and normal branch to4, contrary to current inferred mapping."` | reference | NONE | UNVERIFIED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-supplier-cad-conflict` |
| ts-sleeve | TS / TRS プラグでの入荷時導通試験が必須（tip/ring が入れ替わると TS プラグの sleeve が CV_THRU に触れるため） | `"an incoming-part continuity test with TS and TRS plugs is required"` | reference | NONE | DESIGN | `engineering/a7/README.md` 引用 |
| test-current | 測定電流は接点定格以下 | `"50 mA, 24 V DC"` | max | NONE | SOURCED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-contact-rating` |
| mapping-closed-max | 端子対応の判定で「導通」とみなす抵抗の上限（どの端子が tip / normal かを見分けるためだけの閾値） | `200000` | max | ohm | CALCULATED | 計算 `(R1 + R2) * DB / FS`（内訳は下） |
| mapping-open-min | 端子対応の判定で「開放」とみなす抵抗の下限 | `20000000` | min | ohm | CALCULATED | 計算 `R1 + R2`（内訳は下） |
| contact-max | 閉じた接点 1 つあたりの接触抵抗の上限（新品の初期値）。4 端子法、または 2 端子法で、測定リードとプラグを短絡して読んだ値を差し引く（リード抵抗の扱いを記録）。測定電流は接点定格 50 mA 以下 | `50` | max | mohm | UNVERIFIED | 計算 `Rc`（内訳は下） |

計算の内訳:

- `mapping-closed-max`: `(R1 + R2) * DB / FS` = `200000` ohm（小数 0 桁に丸め）
  - `R1` = 10000000.0（`10M`、`engineering/a7/verification/schematic/netlist.xml` R1 の値、の value）
  - `R2` = 10000000.0（`10M`、`engineering/a7/verification/schematic/netlist.xml` R2 の値、の value）
  - `DB` = 50.0（`50`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_CV_DEADBAND_MV            50」）
  - `FS` = 5000.0（`5000`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_CV_FULL_SCALE_MV          5000」）
- `mapping-open-min`: `R1 + R2` = `20000000` ohm（小数 0 桁に丸め）
  - `R1` = 10000000.0（`10M`、`engineering/a7/verification/schematic/netlist.xml` R1 の値、の value）
  - `R2` = 10000000.0（`10M`、`engineering/a7/verification/schematic/netlist.xml` R2 の値、の value）
- `contact-max`: `Rc` = `50` mohm（小数 0 桁に丸め）
  - `Rc` = 50.0（`50`、`.claude/skills/component-a7-pj-324m/sources.json` `src-a7-pj-324m-sofng-site` の抜粋（未監査）、「50 mOhm max」）

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
4. 厚さ 2.0 mm で後面に深さ 0.5 mm のポケットを設けた板（設計どおりの rear-pocket 構成、前面ワッシャなし）にナットを締め、露出ねじ長と噛み合い長を測る。平板（plain）構成も測る場合は別の結果として記録する。
5. 値を下の基準と比べ、外れた値は FAIL として記録する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `axis_measurements` | 軸高さ・本体寸法の測定表（基準面を明記） |
| `slot_lead_measurements` | 端子寸法と基板スロット寸法、挿入可否 |
| `nut_washer_fit` | ナット/ワッシャの型番、締結後の露出ねじ長と噛み合い長、写真 |
| `instrument_identity` | 計器の型番・分解能・校正記録 |

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| axis-height | 軸高さ（図面に寸法なし。推定） | `"approximately 3 (visually scaled 2.9-3.0 from the front view; not dimensioned)"` | reference | mm | INFERRED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-axis-height` |
| axis-band | 設計で許容した軸高さの範囲 | `[2.6, 3.4]` | range | mm | INFERRED | `engineering/a7/mechanical/layout.json` `/variants/3hp/jack_axis_height_used/band` |
| thread | ねじ | `"M6x0.5"` | exact | NONE | SOURCED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-thread` |
| axis-to-edge | 軸から端子 4/5 側の辺 | `5.4` | reference | mm | SOURCED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-axis-to-edge` |
| axis-to-far-edge | 軸から反対側の辺（計算値） | `6.1` | reference | mm | UNVERIFIED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-axis-to-far-edge` |
| body-height | 本体高さ | `6.0` | reference | mm | SOURCED | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-body-height` |
| slot-drill | 基板スロットのドリル（仮定） | `"1.6×0.8 mm ドリル"` | reference | NONE | ASSUMED | `engineering/a7/electronics/README.md` 引用 |
| thread-engagement | rear-pocket 構成の最悪条件のねじ噛み合い（設計値） | `1.25` | reference | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/z_stack/thread_engagement_selected/worst_engaged` |
| thread-engagement-plain | 平板構成の最悪条件のねじ噛み合い（設計値、基準未達で UNRESOLVED の案） | `0.85` | reference | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/z_stack/thread_engagement_alternate/worst_engaged` |
| engagement-criterion | ねじ噛み合いの検討基準 | `"1.0 mm study criterion"` | min | NONE | DESIGN | `engineering/a7/README.md` 引用 |
| tolerances | 各寸法の合否公差 | — | — | mm | UNRESOLVED | メーカー公差・推奨穴寸法・適合ナット仕様（Q1/Q3/Q4、供給元への質問）。入手先（資料と測定）: SOFNG の公差付き図面・推奨穴寸法・適合ナット仕様（供給元への質問 Q1/Q3/Q4）。得られなければ購入ロットの実測で公差を決める |

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| function | 接点表（端子 3 が共通） | `{"POS.1": "1-3", "POS.2": "2-3", "POS.3": "3-4", "common": "3"}` | exact | NONE | SOURCED | `.claude/skills/component-a7-pcm13smtr/facts.json` `fact-a7-pcm13smtr-function` |
| mode-map | モード符号（POS.1=ON、POS.2=PROGRAM、POS.3=CV） | `"POS.1 (1-3) で MODE_A=0,B=1 → ON"` | exact | NONE | DESIGN | `engineering/a7/electronics/README.md` 引用 |
| contact-rating | 接点定格（測定電流はこれ以下） | `"0.3 A @ 6 VDC"` | max | NONE | SOURCED | `.claude/skills/component-a7-pcm13smtr/facts.json` `fact-a7-pcm13smtr-contact-rating` |
| travel | 1 位置あたりの移動量 | `1.5` | reference | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/switch/actuator_travel_per_position` |
| peg-diameter | ペグ径 | `0.8` | reference | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/switch/peg_diameter` |
| access | 設定アクセスの方向 | `"+Y (below the module), module out of the rack"` | exact | NONE | DESIGN | `engineering/a7/mechanical/layout.json` `/switch/access_from` |
| fit-and-contact | 本体位置の許容ずれと導通判定抵抗 | — | — | NONE | UNRESOLVED | メーカーの本体-ペグ基準寸法と、3.3 V / 10 kΩ 負荷での接触判定値のレビュー。入手先（資料と測定）: C&K の本体とペグの基準寸法の公差（図面）と、実部品での 3.3 V / 10 kΩ 負荷の接触抵抗の測定 |

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| power-free-span | 電源ケーブルの自由長（公称） | `57.0` | reference | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/power_cable_requirement/finished_free_span_nominal` |
| power-tolerance | 自由長の公差（仮定） | `3.0` | reference | mm | ASSUMED | `engineering/a7/mechanical/layout.json` `/power_cable_requirement/tolerance` |
| power-band | 自由長の許容範囲（公差が仮定なので範囲も仮定） | `[54.0, 60.0]` | range | mm | ASSUMED | `engineering/a7/mechanical/layout.json` `/power_cable_requirement/band` |
| a5-cable | A5 の 50 ± 6 mm ケーブルは使えない | `false` | exact | NONE | DESIGN | `engineering/a7/mechanical/layout.json` `/power_cable_requirement/a5_cable/fits` |
| sh4-length | コントローラー→左リーフ SH4 の長さ（モデル） | `50.0` | reference | mm | DESIGN | `engineering/a7/mechanical/exports/3hp/verification.json` `/cables/0/layout_length_mm` |
| depth-target | 奥行き目標（PMMA 裏面から） | `30.0` | max | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/z_stack/installed_depth_target` |
| bend-radius | 許容最小曲げ半径 | `2.0` | min | mm | PROPOSED（根拠 DESIGN） | `engineering/a7/mechanical/layout.json` `/variants/3hp/routes/adapter_to_controller_power/end_bend_room` |
| power-band-order | 電源ケーブル自由長の注文範囲 | `[54.0, 60.0]` | range | mm | PROPOSED（根拠 ASSUMED） | `engineering/a7/mechanical/layout.json` `/power_cable_requirement/band` |

提案の理由（PROPOSED は採否前で、この手順の基準ゲートを解除しません）:

- `bend-radius`: 3HP の経路モデルが電源ケーブル端の曲げに残した余裕 2.0 mm（2HP では 0.9 mm で「推奨未満」とされた値）。ケーブル製造元の最小曲げ半径が分かればそちらを優先する。
- `power-band-order`: 仮定の 57 ± 3 mm をそのまま完成ケーブルの注文仕様にする案。供給元が保証できる公差が分かれば置き換える。

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| panel-thickness | PMMA 板厚（公称） | `2.0` | reference | mm | DESIGN | `engineering/a7/study/parameters.json` `/parameters/panel_thickness/nominal` |
| panel-thickness-tol | PMMA 板厚の公差（仮定） | `0.2` | reference | mm | ASSUMED | `engineering/a7/study/parameters.json` `/parameters/panel_thickness/tol` |
| pocket-depth | 後面ポケット深さ | `0.5` | reference | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/z_stack/rear_pocket_depth` |
| hole | ジャック穴 | `"6.2 mm hole for a 6.0 mm thread major diameter"` | reference | NONE | DESIGN | `engineering/a7/study/parameters.json` 引用 |
| top-screw | 上キャップのねじ | `"M2x18"` | exact | NONE | DESIGN | `engineering/a7/mechanical/layout.json` `/supports/top_cap_screw/designation` |
| plug-force | 保持が受けるプラグ挿抜力 | `"5.0-10.0 N inward and exiting"` | range | NONE | MIRROR | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-plug-force` |
| torque-retention | 締付トルクと保持荷重の合否 | — | — | N | UNRESOLVED | PMMA/PETG 加工先の公差・許容締付条件（供給元への質問）とレビュー。入手先（資料）: PMMA/PETG 加工先の加工公差と許容締付トルク（供給元への質問の回答） |

### fixture-contact — SWD 治具の位置・接触・荷重

- 関連:  #19; #10
- 概要: 基板単体を支持した治具。PMMAとジャックは荷重経路に使わない。電源OFFで位置と短絡を検査後、承認された電源手順へ。
- 根拠: `engineering/a7/electronics/controller/board_placement.json`
- 未決: 完成治具の実位置公差、接触抵抗/繰返し回数、実挿入力と許容荷重が未決。（区分: 外部の証跡・アクセス待ち）
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
- 治具の manifest が digital_criteria_1_to_4_met=true（README 基準 1–4 のデジタル進捗。治具の完了フラグではない）

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| tp1 | TP1 のネット（B 面） | `"/+3V3"` | exact | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/52/pads/1/net` |
| tp2 | TP2 のネット | `"/GND"` | exact | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/53/pads/1/net` |
| tp3 | TP3 のネット | `"/SWDIO"` | exact | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/54/pads/1/net` |
| tp4 | TP4 のネット | `"/SWCLK"` | exact | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/55/pads/1/net` |
| tp5 | TP5 のネット | `"/NRST"` | exact | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/56/pads/1/net` |
| tp-side | テストパッドの面 | `"B"` | exact | NONE | DESIGN | `engineering/a7/electronics/controller/board_placement.json` `/components/52/side` |
| registration | 許容位置ずれ・ストローク・荷重 | — | — | mm | UNRESOLVED | 完成治具の設計（manifest の最悪 registration margin と計算ストローク）とプローブの製造元仕様。入手先（資料と測定）: 採用するプローブの製造元仕様（ストローク・荷重・横方向の遊び）と、完成治具の位置の実測 |

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| ds-timing | データシート V1.4 のビット時間 | `"T0H 220-380; T1H 580-1000; T0L 580-1000; T1L 580-1000"` | range | ns | SOURCED | `.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-bit-timing` |
| fw-t1l | 現行 FW の T1L 設計範囲 | `"220..420"` | reference | NONE | DESIGN | `engineering/a5/firmware/dist/timing.md` 引用 |
| reset | リセット時間 | `280` | min_exclusive | us | SOURCED | `.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-reset-time` |
| vih | 入力 High 閾値（VDD 比） | `0.55` | min | fraction of VDD | SOURCED | `.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-vih` |
| t1l-min | T1L の下限 | `580` | min | ns | PROPOSED（根拠 CALCULATED） | 計算 `T`（内訳は下） |
| t1l-max | T1L の上限 | `1000` | max | ns | PROPOSED（根拠 CALCULATED） | 計算 `T`（内訳は下） |

計算の内訳:

- `t1l-min`: `T` = `580` ns（小数 0 桁に丸め）
  - `T` = 580.0（`580`、`.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-bit-timing`、「T1L 580-1000」）
- `t1l-max`: `T` = `1000` ns（小数 0 桁に丸め）
  - `T` = 1000.0（`1000`、`.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-bit-timing`、「T1L 580-1000」）

提案の理由（PROPOSED は採否前で、この手順の基準ゲートを解除しません）:

- `t1l-min`: T1L はメーカーの現行資料 V1.4（V1.0 も同じ）の値。FW の 220–420 ns はこれを満たさないので、この案を採ると現行 FW は不合格になる。メーカー訂正や購入ロットの実測で別の値にするかは #13 の判断。
- `t1l-max`: T1L はメーカーの現行資料 V1.4（V1.0 も同じ）の値。FW の 220–420 ns はこれを満たさないので、この案を採ると現行 FW は不合格になる。メーカー訂正や購入ロットの実測で別の値にするかは #13 の判断。

### power-current — 電源・電流制限

- 関連:  #10
- 概要: 電流制限電源、全レール電圧/電流計測、左右LEDの規定負荷。
- 根拠: `engineering/a5/integration/independent_review`
- 基準: 採用済み（プロジェクトのコーディネーター（オーナーが委ねた作業方針による）、記録 `engineering/a7/qualification/reviews/2026-11-11-coordinator-criteria-acceptance.md`）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 基準はコーディネーターが採用済み（オーナー本人ではない）。実機で手順を実施して記録する。

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| ilim-formula | TPS2552 の電流制限式（最大側） | `"IOSmax(mA) = 22980 V / RILIM^0.94 kohm"` | reference | mA | SOURCED | `.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-ilim-formula-max` |
| u4-iout | TPS2552 の推奨出力電流 | `1.2` | max | A | SOURCED | `.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-roc-iout` |
| ldo-iout | TLV75533 の推奨出力電流 | `500` | max | mA | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-roc-iout` |
| buck-limit | AP63205 のピーク電流制限 | `"2.5 to 3.1 (typ 2.8)"` | range | A | SOURCED | `.claude/skills/component-ap63205wu-7/facts.json` `fact-ap63205wu-7-peak-current-limit` |
| channel-cap | FW の LED 上限 | `"51u"` | max | NONE | DESIGN | `engineering/a5/firmware/include/lb_config.h` 引用 |
| rilim | RILIM (R11) の部品値（A7 ネットリスト） | `"68k"` | reference | ohm | DESIGN | `engineering/a7/verification/schematic/netlist.xml` R11 の値 |
| ilim-min | VLED の電流制限が働く電流の下限（式 3、R11 が +1 % の最悪側）。段階負荷で制限/FAULT に入る電流はこれ以上。R11 の温度係数 100 ppm/°C は含まない | `343.3` | min | mA | CALCULATED | 計算 `A / (R * (1 + tol / 100) / 1000) ** k`（内訳は下） |
| ilim-max | VLED の電流制限が働く電流の上限（式 1、R11 が −1 % の最悪側）。段階負荷で制限/FAULT に入る電流はこれ以下。R11 の温度係数 100 ppm/°C は含まない | `439.4` | max | mA | CALCULATED | 計算 `B / (R * (1 - tol / 100) / 1000) ** m`（内訳は下） |
| no-trip | 全点灯（51/255 上限）の定常 VLED 電流は ilim-min 未満（通常点灯で制限に入らない） | `343.3` | max | mA | CALCULATED | 計算 `A / (R * (1 + tol / 100) / 1000) ** k`（内訳は下） |
| v3v3-min | +3V3 の下限（出力精度 ±1 %。規定条件は VIN = 3.8 V・IOUT = 1 mA・TJ ≤ 85 °C で、基板の VIN = 5 V との入力変動と負荷変動は含まない。負荷時の値は別に記録） | `3.267` | min | V | CALCULATED | 計算 `V * (1 - acc / 100)`（内訳は下） |
| v3v3-max | +3V3 の上限（同条件） | `3.333` | max | V | CALCULATED | 計算 `V * (1 + acc / 100)`（内訳は下） |
| v5 | +5 V（AP63205 の CCM 時 FB 精度） | `"4.95 to 5.05 (typ 5.00)"` | range | V | SOURCED | `.claude/skills/component-ap63205wu-7/facts.json` `fact-ap63205wu-7-vout` |

計算の内訳:

- `ilim-min`: `A / (R * (1 + tol / 100) / 1000) ** k` = `343.3` mA（小数 1 桁に丸め）
  - `A` = 25230.0（`25230`、`.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-ilim-formula-nom-min`、「IOSmin(mA) = 25230 V / RILIM^1.016」）
  - `k` = 1.016（`1.016`、`.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-ilim-formula-nom-min`、「IOSmin(mA) = 25230 V / RILIM^1.016」）
  - `R` = 68000.0（`68k`、`engineering/a7/verification/schematic/netlist.xml` R11 の値、の value）
  - `tol` = 1.0（`1%`、`engineering/a7/verification/schematic/netlist.xml` R11 の値、の tolerance）
- `ilim-max`: `B / (R * (1 - tol / 100) / 1000) ** m` = `439.4` mA（小数 1 桁に丸め）
  - `B` = 22980.0（`22980`、`.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-ilim-formula-max`、「IOSmax(mA) = 22980 V / RILIM^0.94」）
  - `m` = 0.94（`0.94`、`.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-ilim-formula-max`、「IOSmax(mA) = 22980 V / RILIM^0.94」）
  - `R` = 68000.0（`68k`、`engineering/a7/verification/schematic/netlist.xml` R11 の値、の value）
  - `tol` = 1.0（`1%`、`engineering/a7/verification/schematic/netlist.xml` R11 の値、の tolerance）
- `no-trip`: `A / (R * (1 + tol / 100) / 1000) ** k` = `343.3` mA（小数 1 桁に丸め）
  - `A` = 25230.0（`25230`、`.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-ilim-formula-nom-min`、「IOSmin(mA) = 25230 V / RILIM^1.016」）
  - `k` = 1.016（`1.016`、`.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-ilim-formula-nom-min`、「IOSmin(mA) = 25230 V / RILIM^1.016」）
  - `R` = 68000.0（`68k`、`engineering/a7/verification/schematic/netlist.xml` R11 の値、の value）
  - `tol` = 1.0（`1%`、`engineering/a7/verification/schematic/netlist.xml` R11 の値、の tolerance）
- `v3v3-min`: `V * (1 - acc / 100)` = `3.267` V（小数 3 桁に丸め）
  - `V` = 3.3（`3.3`、`.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-vout-nominal`）
  - `acc` = 1.0（`1`、`.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-output-accuracy`）
- `v3v3-max`: `V * (1 + acc / 100)` = `3.333` V（小数 3 桁に丸め）
  - `V` = 3.3（`3.3`、`.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-vout-nominal`）
  - `acc` = 1.0（`1`、`.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-output-accuracy`）

### cv-thru-calibration — CV/受動THRU/校正

- 関連:  #10
- 概要: 校正したCV源と計測器、IN/THRU/ADCを同時測定。
- 根拠: `engineering/a7/electronics/README.md`
- 基準: 採用済み（プロジェクトのコーディネーター（オーナーが委ねた作業方針による）、記録 `engineering/a7/qualification/reviews/2026-11-11-coordinator-criteria-acceptance.md`）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 基準はコーディネーターが採用済み（オーナー本人ではない）。実機で手順を実施して記録する。

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| transfer | ADC 入力の伝達式 | `"VADC=(100/133)*(VDD/2+CV/8)"` | reference | NONE | DESIGN | `engineering/a7/electronics/README.md` 引用 |
| vdd-accuracy | VDD (3.3 V LDO) の出力精度 | `1` | max | % | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-output-accuracy` |
| adc-m5-min | CV = -5 V での未校正 V(CV_ADC) の下限 | `0.634` | min | V | CALCULATED | 計算 `V`（内訳は下） |
| adc-m5-max | CV = -5 V での未校正 V(CV_ADC) の上限 | `0.911` | max | V | CALCULATED | 計算 `V`（内訳は下） |
| adc-0-min | CV = 0 V での未校正 V(CV_ADC) の下限 | `1.111` | min | V | CALCULATED | 計算 `V`（内訳は下） |
| adc-0-max | CV = 0 V での未校正 V(CV_ADC) の上限 | `1.374` | max | V | CALCULATED | 計算 `V`（内訳は下） |
| adc-p5-min | CV = 5 V での未校正 V(CV_ADC) の下限 | `1.577` | min | V | CALCULATED | 計算 `V`（内訳は下） |
| adc-p5-max | CV = 5 V での未校正 V(CV_ADC) の上限 | `1.846` | max | V | CALCULATED | 計算 `V`（内訳は下） |
| residual-max | 校正後の CV 残差の上限 | `50` | max | mV | CALCULATED | 計算 `DB`（内訳は下） |

計算の内訳:

- `adc-m5-min`: `V` = `0.634` V（小数 3 桁に丸め）
  - `V` = 0.6339931421446384（`0.6339931421446384`、`engineering/a5/electronics/reports/electrical_margins.json` `/cv_transfer/results/-5/ADC_V_min`）
- `adc-m5-max`: `V` = `0.911` V（小数 3 桁に丸め）
  - `V` = 0.9108190880526671（`0.9108190880526671`、`engineering/a5/electronics/reports/electrical_margins.json` `/cv_transfer/results/-5/ADC_V_max`）
- `adc-0-min`: `V` = `1.111` V（小数 3 桁に丸め）
  - `V` = 1.1109725685785536（`1.1109725685785536`、`engineering/a5/electronics/reports/electrical_margins.json` `/cv_transfer/results/0/ADC_V_min`）
- `adc-0-max`: `V` = `1.374` V（小数 3 桁に丸め）
  - `V` = 1.3736664921074289（`1.3736664921074289`、`engineering/a5/electronics/reports/electrical_margins.json` `/cv_transfer/results/0/ADC_V_max`）
- `adc-p5-min`: `V` = `1.577` V（小数 3 桁に丸め）
  - `V` = 1.5771344252434243（`1.5771344252434243`、`engineering/a5/electronics/reports/electrical_margins.json` `/cv_transfer/results/5/ADC_V_min`）
- `adc-p5-max`: `V` = `1.846` V（小数 3 桁に丸め）
  - `V` = 1.846172835232828（`1.846172835232828`、`engineering/a5/electronics/reports/electrical_margins.json` `/cv_transfer/results/5/ADC_V_max`）
- `residual-max`: `DB` = `50` mV（小数 0 桁に丸め）
  - `DB` = 50.0（`50`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_CV_DEADBAND_MV            50」）

### startup-reset — 起動・リセット・fault復帰

- 関連:  #10
- 概要: 規定の電源立上り/リセット/FAULT条件を一つずつ印加し全レールとLED enableを観測。
- 根拠: `engineering/a5/integration/independent_review`
- 基準: 採用済み（プロジェクトのコーディネーター（オーナーが委ねた作業方針による）、記録 `engineering/a7/qualification/reviews/2026-11-11-coordinator-criteria-acceptance.md`）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 基準はコーディネーターが採用済み（オーナー本人ではない）。実機で手順を実施して記録する。

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| latch | TPS2552-1 はラッチオフ（過電流後は EN を戻すまで復帰しない） | `"TPS2552DxVx-1: enable active low; overcurrent fault response latch off; no quick output discharge"` | reference | NONE | SOURCED | `.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-variant-latch` |
| ldo-vin | TLV75533 の推奨入力範囲 | `"1.45 to 5.5"` | range | V | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-roc-vin` |
| en-off | LED を無効にしている間（電源投入から FW の有効化まで、FAULT 後）の LED_EN_N。U4 の EN VIH 最小以上（active low なのでオフ） | `1.1` | min | V | CALCULATED | 計算 `VIH`（内訳は下） |
| en-on | FW が有効化した後の LED_EN_N。EN VIL 最大以下 | `0.66` | max | V | CALCULATED | 計算 `VIL`（内訳は下） |
| nrst-tau | NRST の RC 時定数 R21 × C14（立上り波形の参照値。STM32 内部のプルアップは含まない） | `1.0` | reference | ms | CALCULATED | 計算 `R * C * 1000`（内訳は下） |
| settle | FW 初期化から LED を有効化するまでの最短時間 | `100` | min | ms | CALCULATED | 計算 `T`（内訳は下） |
| adc-timeout | この時間内に ADC 値が得られなければ FAULT（有効化しない） | `250` | reference | ms | CALCULATED | 計算 `T`（内訳は下） |
| power-settle | 有効化から最初の黒フレーム送信までの最短時間 | `5` | min | ms | CALCULATED | 計算 `T`（内訳は下） |
| vdda-min | VDDA がこれ未満なら、その取り込み（1 ms ごと）で ADC FAULT（有効化しない、有効なら停止） | `3000` | reference | mV | CALCULATED | 計算 `V`（内訳は下） |
| vdda-max | VDDA がこれを超えれば、その取り込み（1 ms ごと）で ADC FAULT | `3600` | reference | mV | CALCULATED | 計算 `V`（内訳は下） |
| no-retry | FAULT 後は電源を入れ直すまで再有効化しない（FW） | `"No enable or retry path exists in this routine."` | exact | NONE | DESIGN | `engineering/a5/firmware/src/light_block.c` 引用 |
| lockout | 電源投入リセットで保持マーカーが空のときだけ通常起動する。外部リセット・ウォッチドッグ・バックアップ領域が残る BOR では消灯のまま（全電源の崩壊は電源再投入と区別できず再起動しうる。firmware/docs/reset_policy.md） | `"return LB_BOOT_LOCKED_RETAINED;"` | exact | NONE | DESIGN | `engineering/a5/firmware/src/light_block.c` 引用 |
| window | 観測窓（FW 初期化から）の最短長 = ADC 待ち上限 + 電源待ち + 黒フレーム転送の上限。SW1 が有効な位置にあること（無効位置では有効化を待ち続ける） | `260` | min | ms | CALCULATED | 計算 `A + W + T`（内訳は下） |

計算の内訳:

- `en-off`: `VIH` = `1.1` V（小数 2 桁に丸め）
  - `VIH` = 1.1（`1.1`、`.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-roc-vin`、conditions、「EN VIH min 1.1 V」）
- `en-on`: `VIL` = `0.66` V（小数 2 桁に丸め）
  - `VIL` = 0.66（`0.66`、`.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-roc-vin`、conditions、「VIL max 0.66 V」）
- `nrst-tau`: `R * C * 1000` = `1.0` ms（小数 3 桁に丸め）
  - `R` = 10000.0（`10k`、`engineering/a7/verification/schematic/netlist.xml` R21 の値、の value）
  - `C` = 1.0000000000000001e-07（`100n`、`engineering/a7/verification/schematic/netlist.xml` C14 の値、の value）
- `settle`: `T` = `100` ms（小数 0 桁に丸め）
  - `T` = 100.0（`100u`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_STARTUP_SETTLE_MS          100u」）
- `adc-timeout`: `T` = `250` ms（小数 0 桁に丸め）
  - `T` = 250.0（`250u`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_STARTUP_ADC_TIMEOUT_MS    250u」）
- `power-settle`: `T` = `5` ms（小数 0 桁に丸め）
  - `T` = 5.0（`5u`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_LED_POWER_SETTLE_MS       5u」）
- `vdda-min`: `V` = `3000` mV（小数 0 桁に丸め）
  - `V` = 3000.0（`3000u`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_VDDA_MIN_MV               3000u」）
- `vdda-max`: `V` = `3600` mV（小数 0 桁に丸め）
  - `V` = 3600.0（`3600u`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_VDDA_MAX_MV               3600u」）
- `window`: `A + W + T` = `260` ms（小数 0 桁に丸め）
  - `A` = 250.0（`250u`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_STARTUP_ADC_TIMEOUT_MS    250u」）
  - `W` = 5.0（`5u`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_LED_POWER_SETTLE_MS       5u」）
  - `T` = 5.0（`5u`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_TRANSFER_TIMEOUT_MS       5u」）

### rail-collapse — 急速レール崩壊

- 関連:  #10
- 概要: 承認された負荷/電源遮断条件でレール低下と制御を同時観測。
- 根拠: `engineering/a5/integration/independent_review`
- 基準: 採用済み（プロジェクトのコーディネーター（オーナーが委ねた作業方針による）、記録 `engineering/a7/qualification/reviews/2026-11-11-coordinator-criteria-acceptance.md`）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 基準はコーディネーターが採用済み（オーナー本人ではない）。実機で手順を実施して記録する。

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| ldo-vin | TLV75533 の推奨入力範囲 | `"1.45 to 5.5"` | range | V | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-roc-vin` |
| collapse-en-off | +3V3 が vdda 下限未満になっている間の LED_EN_N（U4 オフ） | `1.1` | min | V | CALCULATED | 計算 `VIH`（内訳は下） |
| collapse-threshold | 上の条件を見る +3V3 の電圧 | `3000` | reference | mV | CALCULATED | 計算 `V`（内訳は下） |
| collapse-recovery | 復帰後、バックアップ領域が残っていれば有効化しない（RESET_LOCKOUT） | `"return LB_BOOT_LOCKED_RETAINED;"` | exact | NONE | DESIGN | `engineering/a5/firmware/src/light_block.c` 引用 |

計算の内訳:

- `collapse-en-off`: `VIH` = `1.1` V（小数 2 桁に丸め）
  - `VIH` = 1.1（`1.1`、`.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-roc-vin`、conditions、「EN VIH min 1.1 V」）
- `collapse-threshold`: `V` = `3000` mV（小数 0 桁に丸め）
  - `V` = 3000.0（`3000u`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_VDDA_MIN_MV               3000u」）

### partial-rails — 部分電源・逆給電・無電源CV

- 関連:  #10
- 概要: 許可された全レール組合せと無電源CV入力を電流制限下で試す。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 最大印加値、注入電流制限、順序、許容逆流値を部品資料から承認する必要。（区分: 外部の証跡・アクセス待ち）
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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| u6-input | OPA197 入力の絶対最大 | `"(V-) - 0.5 to (V+) + 0.5"` | range | V | SOURCED | `.claude/skills/component-opa197idbvr/facts.json` `fact-opa197idbvr-abs-max-input-voltage` |
| u6-current | OPA197 入力電流の絶対最大 | `10` | max | mA | SOURCED | `.claude/skills/component-opa197idbvr/facts.json` `fact-opa197idbvr-abs-max-input-current` |
| u7-input | TLV9001 入力の絶対最大 | `"(V-) - 0.5 to (V+) + 0.5"` | range | V | SOURCED | `.claude/skills/component-tlv9001idbvr/facts.json` `fact-tlv9001idbvr-abs-max-input-voltage` |
| u5-vi | SN74LVC2T45 入力の絶対最大 | `6.5` | max | V | SOURCED | `.claude/skills/component-sn74lvc2t45dcur/facts.json` `fact-sn74lvc2t45dcur-abs-max-vi` |
| led-vi | WS2812B 入力の絶対最大 | `"-0.3 to VDD+0.7"` | range | V | SOURCED | `.claude/skills/component-ws2812b-2020-v6/facts.json` `fact-ws2812b-2020-v6-input-abs-max` |
| limits | 許容印加値・注入電流・順序の数表 | — | — | mA | UNRESOLVED | 上記の部品値から条件表を作ってレビューする（STM32 の注入電流はカタログで未取得）。入手先（資料）: STM32G031 データシートの I/O 注入電流と絶対最大（カタログに fact がない） |

### u7-stress — U7 差動ストレス

- 関連:  #10
- 概要: CVと電源遷移中のU7両入力/電源を差動プローブで測る。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 受入値は部品資料・ネットリスト・FW 定数から導出し、生成時に再計算で照合している。採用のレビュー記録（criterion_review）がまだない。（区分: オーナーの判断）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 導出した受入値をレビューして採否を記録する（コーディネーターかオーナー）。その後に実機で手順を実施する。

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| supply | TLV9001 電源の絶対最大 | `7` | max | V | SOURCED | `.claude/skills/component-tlv9001idbvr/facts.json` `fact-tlv9001idbvr-ratings` |
| input | TLV9001 入力の絶対最大 | `"(V-) - 0.5 to (V+) + 0.5"` | range | V | SOURCED | `.claude/skills/component-tlv9001idbvr/facts.json` `fact-tlv9001idbvr-abs-max-input-voltage` |
| current | TLV9001 入力電流の絶対最大 | `10` | max | mA | SOURCED | `.claude/skills/component-tlv9001idbvr/facts.json` `fact-tlv9001idbvr-abs-max-input-current` |
| supply-roc | U7 電源 (+3V3) の推奨範囲 | `"1.8 to 5.5"` | range | V | SOURCED | `.claude/skills/component-tlv9001idbvr/facts.json` `fact-tlv9001idbvr-roc-vs` |
| in-current-bound | R7 を流れる電流（U7 IN+ と D3 の合計）の上限（計算）。CV_AFFINE の全抵抗（R3–R6）と +3V3 の上限を含む節点計算。測定した R7 の電圧から求めた電流はこれ以下で、U7 入力の絶対最大 10 mA より小さい | `0.313` | max | mA | PROPOSED（根拠 INFERRED） | 計算 `(V / (R3 * (1 - t3 / 100)) + (V3 * (1 + acc / 100)) / (R4 * (1 - t4 / 100)) + (V3 * (1 + acc / 100)) / (R5 * (1 - t5 / 100))) / (1 / (R3 * (1 - t3 / 100)) + 1 / (R4 * (1 - t4 / 100)) + 1 / (R5 * (1 - t5 / 100)) + 1 / (R6 * (1 + t6 / 100)) + 1 / (R7 * (1 - t7 / 100))) / (R7 * (1 - t7 / 100)) * 1000`（内訳は下） |

計算の内訳:

- `in-current-bound`: `(V / (R3 * (1 - t3 / 100)) + (V3 * (1 + acc / 100)) / (R4 * (1 - t4 / 100)) + (V3 * (1 + acc / 100)) / (R5 * (1 - t5 / 100))) / (1 / (R3 * (1 - t3 / 100)) + 1 / (R4 * (1 - t4 / 100)) + 1 / (R5 * (1 - t5 / 100)) + 1 / (R6 * (1 + t6 / 100)) + 1 / (R7 * (1 - t7 / 100))) / (R7 * (1 - t7 / 100)) * 1000` = `0.313` mA（小数 3 桁に丸め）
  - `V` = 20.0（`20`、`.claude/skills/component-opa197idbvr/facts.json` `fact-opa197idbvr-ratings`、conditions、「(+/-20 V dual supply)」）
  - `V3` = 3.3（`3.3`、`.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-vout-nominal`）
  - `acc` = 1.0（`1`、`.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-output-accuracy`）
  - `R3` = 82000.0（`82k`、`engineering/a7/verification/schematic/netlist.xml` R3 の値、の value）
  - `t3` = 1.0（`1%`、`engineering/a7/verification/schematic/netlist.xml` R3 の値、の tolerance）
  - `R4` = 82000.0（`82k`、`engineering/a7/verification/schematic/netlist.xml` R4 の値、の value）
  - `t4` = 1.0（`1%`、`engineering/a7/verification/schematic/netlist.xml` R4 の値、の tolerance）
  - `R5` = 82000.0（`82k`、`engineering/a7/verification/schematic/netlist.xml` R5 の値、の value）
  - `t5` = 1.0（`1%`、`engineering/a7/verification/schematic/netlist.xml` R5 の値、の tolerance）
  - `R6` = 82000.0（`82k`、`engineering/a7/verification/schematic/netlist.xml` R6 の値、の value）
  - `t6` = 1.0（`1%`、`engineering/a7/verification/schematic/netlist.xml` R6 の値、の tolerance）
  - `R7` = 1000.0（`1k`、`engineering/a7/verification/schematic/netlist.xml` R7 の値、の value）
  - `t7` = 1.0（`1%`、`engineering/a7/verification/schematic/netlist.xml` R7 の値、の tolerance）
  - 推定: CV_BUF (U6 出力) は U6 の電源を超えず、U6 の電源は絶対最大の ±20 V 以内とする推定。CV_FILTER を 0 V に固定して R7 の電流を大きく見積もる

提案の理由（PROPOSED は採否前で、この手順の基準ゲートを解除しません）:

- `in-current-bound`: U6 (OPA197) の出力はレールまで最大 25 mV（無負荷、25 °C）まで近づけると資料にある（fact-opa197idbvr-output-swing）。これはレールを超えない保証ではなく、絶対最大にも出力ピンの行はないが、CV_BUF は U6 の電源 +12V_PROT / −12V_PROT を超えないと推定する（資料からの推論で、資料の値ではない）。その電源の上限はモジュールの外（ラック電源）で決まり、Doepfer A-100 の技術資料は ±12 V の公称値だけで許容差も上限も示さない。D3 (BAS70-04) と U7 内部ダイオードの電流分担はどちらの資料にもない（BAS70 の VF は 1 mA で最大 410 mV、25 °C だけ。TLV9001 は電源を 0.5 V 超える入力を 10 mA 以下に制限することだけを求める）が、R7 を流れる合計がこの上限以下なら分担に関係なく U7 の 10 mA を下回る。±20 V は資料の値ではなく設計上の推定で、同じ節点計算では CV_BUF が約 845 V にならないと 10 mA に届かない。推定を外せる資料（ラック電源の上限）が得られるまで提案のまま。

### ldo-reverse — LDO 逆電流

- 関連:  #10
- 概要: 入力/出力レール遷移を承認済み制限下で独立に制御。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: TLV755P は許容逆電流・時間を規定しない（§7.1.4 が挙げる 3 つの逆電流条件はいずれも絶対最大（VOUT > VIN + 0.3 V）を超えるとし、必要なら外付けショットキーを推奨）。+3V3 への外部印加を試験で許すか、許すならどの上限で行うかはオーナーのリスク判断。（区分: オーナーの判断）
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
- +3V3 に外部電圧をかける試験は、オーナー判断 criterion:ldo-reverse で bounded が選ばれ、上限と時間が記録されるまで実施しない

手順:

1. 電源投入・遮断の順序を変えて +5V と +3V3 の波形を記録し、遮断時に VOUT ≤ VIN + 0.3 V が保たれるかを確かめる。
2. （bounded が選ばれた場合のみ）+5 V を切った状態で +3V3 側に SWD プローブ等から記録済みの上限内で電圧をかけ、電流と時間を測る。
3. 順序と時間を変えて記録する。

記録する raw 証跡（種別ごとに別ファイル）:

| 種別 | 内容 |
|---|---|
| `rail_waveforms` | 波形 |
| `reverse_current` | 逆電流 |
| `temperature` | U3 の温度 |
| `sequence_conditions` | 順序と時間 |

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| vin-max | TLV75533 VIN の絶対最大 | `6.0` | max | V | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-ratings` |
| en-max | TLV75533 EN の絶対最大 | `6.0` | max | V | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-abs-max-en` |
| reverse-spec | TLV75533 の逆電流に関するメーカー記述 | `"no allowed reverse current specified; VOUT must not exceed VIN + 0.3 V or 6.0 V, whichever is smaller"` | reference | NONE | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-reverse-current` |
| reverse | 試験で許す逆電流と時間 | — | — | mA | UNRESOLVED | オーナー判断（メーカーは許容値を規定しないので、試験で許すかどうかと上限はプロジェクトのリスク判断） |

### load-short — 負荷・短絡・保護

- 関連:  #10
- 概要: 制限電源と規定短絡負荷を使い、回復と温度を観測。
- 根拠: `engineering/a5/integration/independent_review`
- 基準: 採用済み（プロジェクトのコーディネーター（オーナーが委ねた作業方針による）、記録 `engineering/a7/qualification/reviews/2026-11-11-coordinator-criteria-acceptance.md`）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 基準はコーディネーターが採用済み（オーナー本人ではない）。実機で手順を実施して記録する。

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| latch | TPS2552-1 のラッチオフ動作 | `"TPS2552DxVx-1: enable active low; overcurrent fault response latch off; no quick output discharge"` | reference | NONE | SOURCED | `.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-variant-latch` |
| ldo-limit | TLV75533 の電流制限（最小） | `560` | min | mA | SOURCED | `.claude/skills/component-tlv75533pdbvr/facts.json` `fact-tlv75533pdbvr-current-limit` |
| buck-limit | AP63205 のピーク電流制限 | `"2.5 to 3.1 (typ 2.8)"` | range | A | SOURCED | `.claude/skills/component-ap63205wu-7/facts.json` `fact-ap63205wu-7-peak-current-limit` |
| vled-short | VLED (J3) 短絡で U4 がラッチオフし、外しても電源再投入まで復帰しない | `"TPS255x-1 latch-off: on overcurrent it asserts FAULT after the deglitch period and turns off; stays off even after the overload is removed until enable is toggled or power is cycled"` | exact | NONE | SOURCED | `.claude/skills/component-tps2552dbvr-1/facts.json` `fact-tps2552dbvr-1-latch-behaviour` |
| short-no-retry | 短絡後 FW は再有効化しない | `"No enable or retry path exists in this routine."` | exact | NONE | DESIGN | `engineering/a5/firmware/src/light_block.c` 引用 |

### effective-capacitance — MLCC 実効容量

- 関連:  #10
- 概要: 実装型番/ロットのDCバイアスと温度条件を記録して容量/リップルを測る。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 部品ごとの典型 DC バイアス曲線は記録済み（Samsung 製品ページ、typical data）。必要容量の下限は、レギュレータ・負荷スイッチ資料の入出力容量要件と曲線から回路レビューで決める（クラウドで実施できる）。（区分: クラウドで進められるデジタル作業）
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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| c10u | CL21A106KAYNNNE 定格電圧 | `25` | max | V | SOURCED | `.claude/skills/component-cl21a106kaynnne/facts.json` `fact-cl21a106kaynnne-ratings` |
| c22u | CL31A226KAHNNNE 定格電圧 | `25` | max | V | SOURCED | `.claude/skills/component-cl31a226kahnnne/facts.json` `fact-cl31a226kahnnne-ratings` |
| c4u7 | CL10A475KO8NNNC 定格電圧 | `16` | max | V | SOURCED | `.claude/skills/component-cl10a475ko8nnnc/facts.json` `fact-cl10a475ko8nnnc-ratings` |
| dc-bias | 動作点での実効容量 | `"effective capacitance at the A5 DC operating point not established"` | reference | NONE | UNVERIFIED | `.claude/skills/component-cl21a106kaynnne/facts.json` `fact-cl21a106kaynnne-dc-bias` |
| dc-bias-c10u | CL21A106KAYNNNE の典型 DC バイアス特性（保証値ではない） | `"-50.31 % at 5.0 V; -81.6 % at 12.208 V"` | reference | % | SOURCED | `.claude/skills/component-cl21a106kaynnne/facts.json` `fact-cl21a106kaynnne-dc-bias-curve` |
| dc-bias-c22u | CL31A226KAHNNNE の典型 DC バイアス特性（保証値ではない） | `"-37.96 % at 5.0 V"` | reference | % | SOURCED | `.claude/skills/component-cl31a226kahnnne/facts.json` `fact-cl31a226kahnnne-dc-bias-curve` |
| dc-bias-c4u7 | CL10A475KO8NNNC の典型 DC バイアス特性（保証値ではない） | `"-30.44 % at 3.3 V; -49.92 % at 5.0 V"` | reference | % | SOURCED | `.claude/skills/component-cl10a475ko8nnnc/facts.json` `fact-cl10a475ko8nnnc-dc-bias-curve` |
| minimum | 必要容量の下限 | — | — | NONE | UNRESOLVED | 回路レビュー（レギュレータ・負荷スイッチ資料の入出力容量要件と、記録済みの典型 DC バイアス曲線・許容差・温度特性から決める）。入手先（資料）: AP63205 / TLV755P / TPS2552 データシートの入出力容量要件（クラウドで取得できる） |

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| channel-cap | FW の LED 上限 | `"51u"` | max | NONE | DESIGN | `engineering/a5/firmware/include/lb_config.h` 引用 |
| switch-temp | PCM13SMTR の動作温度 | `"-40 to +85"` | range | C | SOURCED | `.claude/skills/component-a7-pcm13smtr/facts.json` `fact-a7-pcm13smtr-operating-temperature` |
| mlcc-temp | X7R MLCC の動作温度 | `"-55 to +125"` | range | degC | SOURCED | `.claude/skills/component-cc0603krx7r9bb104/facts.json` `fact-cc0603krx7r9bb104-operating-temperature` |
| part-temp-max | 安定後の部品表面温度の上限 | `85` | max | degC | PROPOSED（根拠 CALCULATED） | 計算 `T`（内訳は下） |
| materials-appearance | PETG/PMMA の温度限界と見え方の合否 | — | — | degC | UNRESOLVED | 材料の温度限界は資料（未取得）、見え方はオーナーの判断。入手先（資料）: 使う PETG フィラメントと PMMA 板の製造元の熱変形温度（資料未取得） |

計算の内訳:

- `part-temp-max`: `T` = `85` degC（小数 0 桁に丸め）
  - `T` = 85.0（`+85`、`.claude/skills/component-a7-pcm13smtr/facts.json` `fact-a7-pcm13smtr-operating-temperature`、「-40 to +85」）

提案の理由（PROPOSED は採否前で、この手順の基準ゲートを解除しません）:

- `part-temp-max`: カタログの部品 fact で動作温度の上限が分かるもののうち最も低いのは +85 °C で、複数の部品が同じ値になる（WS2812B-2020 の Topt、AP63205 と SN74LVC2T45 の周囲温度 TA、STM32G031 の温度コード 6、PCM13SMTR、SM04B（通電による温度上昇を含む）、Samsung X5R の温度特性範囲）。TPS2552 と TLV755P の上限は接合部温度（どちらも +125 °C。TPS2552 は IOUT ≤ 1.5 A なら +105 °C）。PJ-324M は保存温度が −25〜+75 °C で、動作温度の欄は資料で空欄（fact は UNSOURCED）なので、+75 °C を基板の上限とみなすかも採否で決める。温度の fact がない部品は 530470310、BOOMELE C5665、PJ-3582-B（ミラー資料だけ）。1MS3T1B1M2QES-5 はミラー資料による −40〜85 °C の fact だけで UNSOURCED。表面温度は接合部より低いので、余裕をどれだけ取るかも採否で決める。

### cv-noise — CV ノイズと DATA_L 結合

- 関連:  #10
- 概要: 静的CVを印加しDATA_L/左右ストリームのパターンを切替、ADC/THRUを同期観測。
- 根拠: `engineering/a7/verification/interface_review.md`
- 基準: 採用済み（プロジェクトのコーディネーター（オーナーが委ねた作業方針による）、記録 `engineering/a7/qualification/reviews/2026-11-11-coordinator-criteria-acceptance.md`）
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 基準はコーディネーターが採用済み（オーナー本人ではない）。実機で手順を実施して記録する。

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| layout | 同層での CV と DATA の間隔（設計） | `"No CV node runs within 0.6 mm of DATA_L/R or ±12V_PROT on the same layer."` | reference | NONE | DESIGN | `engineering/a7/verification/interface_review.md` 引用 |
| noise-max | LED データ送信中の CV 換算ノイズ（ピーク・ツー・ピーク）の上限 | `50` | max | mV | CALCULATED | 計算 `DB`（内訳は下） |

計算の内訳:

- `noise-max`: `DB` = `50` mV（小数 0 桁に丸め）
  - `DB` = 50.0（`50`、`engineering/a5/firmware/include/lb_config.h` 引用、「LB_CV_DEADBAND_MV            50」）

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

受入値（範囲: exact = 一致、min / max = 下限 / 上限、min_exclusive = この値を超える、range = 範囲内、reference = 比較の参照値）:

| ID | 基準 | 値 | 範囲 | 単位 | 確度 | 出典 / 決める主体 |
|---|---|---|---|---|---|---|
| width | 前面幅 (3HP) | `14.9` | max | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/variants/3hp/panel_width` |
| height | 前面高さ | `128.5` | max | mm | DESIGN | `engineering/a7/mechanical/exports/3hp/verification.json` `/parts/0/bbox_max/1` |
| depth | 奥行き目標 | `30.0` | max | mm | DESIGN | `engineering/a7/mechanical/layout.json` `/z_stack/installed_depth_target` |
| plug-force | プラグ挿抜力 | `"5.0-10.0 N inward and exiting"` | range | NONE | MIRROR | `.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-plug-force` |
| switch-life | 設定スイッチの寿命 | `10000` | reference | cycles | SOURCED | `.claude/skills/component-a7-pcm13smtr/facts.json` `fact-a7-pcm13smtr-life` |
| cycles | 繰返し回数と許容損傷 | — | — | NONE | UNRESOLVED | オーナーの判断 |
| retention-force | ジャック保持がずれ・割れなく受ける挿抜力 | `10.0` | min | N | PROPOSED（根拠 MIRROR） | 計算 `F`（内訳は下） |

計算の内訳:

- `retention-force`: `F` = `10.0` N（小数 1 桁に丸め）
  - `F` = 10.0（`10.0`、`.claude/skills/component-a7-pj-324m/facts.json` `fact-a7-pj-324m-plug-force`、「5.0-10.0 N inward」）

提案の理由（PROPOSED は採否前で、この手順の基準ゲートを解除しません）:

- `retention-force`: PJ-324M の挿抜力の上限 10.0 N（販売店掲載の写し）。回数はオーナーが決める（cycles）。

## ゲートの区分

| 区分 | ゲート数 |
|---|---:|
| CLOUD_DIGITAL（クラウドで進められるデジタル作業） | 3 |
| OWNER_DECISION（オーナーの判断） | 12 |
| ACCESS_EVIDENCE_HOLD（外部の証跡・アクセス待ち） | 14 |
| PHYSICAL_ONLY（実機が必要） | 20 |

## 現在のブロッカー

- fixture: unresolved preparation blockers
- fixture digital design incomplete or unverified
- assembly_manifest: supply-observations: Order quantity is 2 modules (owner decision). JLC stock, price, minimum, packaging, lead time and assembly applicability at that quantity are not observed for any line except C221842 (switch-supply); JLC attrition is not sourced; stock never reserved.
- assembly_manifest: switch-supply: PCM13SMTR (C221842): 2 needed for 2 modules. JLC stock 0 at 2026-11-09; at 2026-11-12 JLC lists it buyable (Extended) with pre-order minimum 3 and presale 0 (field meanings inferred), tier prices without currency, no lead time. The owner wants to complete on JLC: on our reading, a pre-order (presale 0 may mean none can be placed now; fill depends on LCSC stock, not observed) or a Global Sourcing quote; otherwise wait, or accept a reviewed alternate with its own contact table and fit review.
- assembly_manifest: jack-switch-qualification: PJ-324M pin function (which of terminals 4/5 is the tip contact and which its normal; the supplier symbol contradicts the inferred 4 = tip, so this continuity test must precede any PCB order), slot, axis height and nut fit, and PCM13SMTR truth table and land fit, need received parts (jack-continuity, jack-dimensions, switch-fit).
- assembly_manifest: exact-part-evidence: Exact-part gaps after the 2026-11-11 source recovery: PMEG4010CEJ ,115 packing variant not established by the datasheet; SM04B-SRSS-TB per-circuit numbering not printed beyond the No. 1 end; PJ-324M recommended hole/slot sizes, axis height and whether a nut ships with C22355739 not sourced.
- assembly_manifest: finished-cables: Finished A7 power cable (57 mm, +/-3 ASSUMED), SH4 cables and IDC ribbon not selected; supplier answers and the owner choice of assembly are needed before physical routing checks.
- assembly_manifest: mechanical-materials: PMMA sheet and pocket tolerances, PETG process and orderable fastener part numbers are not sourced; the model carries designations (M2x18, M1.6x4) and envelopes only.
- assembly_manifest: rack-hardware: Owner rack rail/thread interface and fasteners not specified.
- assembly_manifest: fixture-materials: Fixture design and materials incomplete (fixture manifest: digital_criteria_1_to_4_met not true); physical contact/load tests follow.
- assembly_manifest: prototype-and-release: No owner-approved prototype route, no reviewed manufacturing package and no release approval.
- jack-continuity: NOT_MEASURED: no run
- jack-dimensions: criterion unresolved or review receipt missing
- jack-dimensions: criterion has PROPOSED or UNRESOLVED acceptance values: tolerances
- jack-dimensions: NOT_MEASURED: no run
- switch-fit: criterion unresolved or review receipt missing
- switch-fit: criterion has PROPOSED or UNRESOLVED acceptance values: fit-and-contact
- switch-fit: NOT_MEASURED: no run
- harness-depth: criterion unresolved or review receipt missing
- harness-depth: criterion has PROPOSED or UNRESOLVED acceptance values: bend-radius, power-band-order
- harness-depth: NOT_MEASURED: no run
- pmma-supports: criterion unresolved or review receipt missing
- pmma-supports: criterion has PROPOSED or UNRESOLVED acceptance values: torque-retention
- pmma-supports: NOT_MEASURED: no run
- fixture-contact: criterion unresolved or review receipt missing
- fixture-contact: criterion has PROPOSED or UNRESOLVED acceptance values: registration
- fixture-contact: NOT_MEASURED: no run
- firmware-waveforms: criterion unresolved or review receipt missing
- firmware-waveforms: criterion has PROPOSED or UNRESOLVED acceptance values: t1l-min, t1l-max
- firmware-waveforms: NOT_MEASURED: no run
- power-current: NOT_MEASURED: no run
- cv-thru-calibration: NOT_MEASURED: no run
- startup-reset: NOT_MEASURED: no run
- rail-collapse: NOT_MEASURED: no run
- partial-rails: criterion unresolved or review receipt missing
- partial-rails: criterion has PROPOSED or UNRESOLVED acceptance values: limits
- partial-rails: NOT_MEASURED: no run
- u7-stress: criterion unresolved or review receipt missing
- u7-stress: criterion has PROPOSED or UNRESOLVED acceptance values: in-current-bound
- u7-stress: NOT_MEASURED: no run
- ldo-reverse: criterion unresolved or review receipt missing
- ldo-reverse: criterion has PROPOSED or UNRESOLVED acceptance values: reverse
- ldo-reverse: NOT_MEASURED: no run
- load-short: NOT_MEASURED: no run
- effective-capacitance: criterion unresolved or review receipt missing
- effective-capacitance: criterion has PROPOSED or UNRESOLVED acceptance values: minimum
- effective-capacitance: NOT_MEASURED: no run
- thermal-optical: criterion unresolved or review receipt missing
- thermal-optical: criterion has PROPOSED or UNRESOLVED acceptance values: part-temp-max, materials-appearance
- thermal-optical: NOT_MEASURED: no run
- cv-noise: NOT_MEASURED: no run
- service-envelope: criterion unresolved or review receipt missing
- service-envelope: criterion has PROPOSED or UNRESOLVED acceptance values: cycles, retention-force
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
