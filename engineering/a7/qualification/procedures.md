# A7 物理評価の準備と readiness

**未実施・製造リリースなし。** この文書は `scripts/a7_readiness.py` の生成物です。

レポート検証: VALID。発注適格性: **BLOCKED**。

## 共通記録 (Workflow F)

各実施は `run-template.json` のコピーを使い、unit、基板/実装/FW/設定ハッシュ、計器、条件、期待基準、raw証跡、結果、次の行動を記録します。失敗や再加工を上書きせず別 run として追加します。

## 未実施の手順

### jack-continuity — PJ-324M 入荷時 TS/TRS 導通・端子対応

- 関連: Q2; #19
- セットアップ/操作: 絶縁された未実装ジャック、TS/TRS プラグ、導通計。各挿抜状態で全端子対を測る。
- 期待基準: J1/J2: 1=sleeve→GND, 2=ring→GND, 4=tip→CV_THRU, 3/5=NC は設計上の推定。実物対応と normal 接点を確認し、TS sleeve に CV が短絡しないこと。
- 根拠: `engineering/a7/electronics/README.md`
- 未決: 設計推定を採否判定する導通抵抗上限は未決。計器条件と判定値のレビューが必要。
- 必須raw証跡: 全端子対の導通表、プラグ型番、写真、ジャックロット
- 機械検証する証跡種別: terminal_matrix, ts_plug_identity, trs_plug_identity, jack_lot, contact_photos
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### jack-dimensions — ジャック軸・スロット・端子・ナット

- 関連: Q1/Q3/Q4; #8
- セットアップ/操作: 未実装品と実基板を基準面を明示して寸法測定。ナット・ワッシャを含める。
- 期待基準: 3HP/1.6 mm の現行寸法と比較。軸高さは INFERRED、基板スロットは ASSUMED、ナット同梱と適合は未確認。
- 根拠: `engineering/a7/open-questions.md`
- 未決: メーカー公差、穴・リード寸法、適合ナット/ワッシャ仕様が必要。
- 必須raw証跡: 寸法図付き測定、座面写真、ロット、ゲージ情報
- 機械検証する証跡種別: axis_measurements, slot_lead_measurements, nut_washer_fit, instrument_identity
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### switch-fit — PCM13SMTR 真理値・ランド・設定アクセス

- 関連: Q10; #19
- セットアップ/操作: 未実装品の全接点を測定後、基板ランドとペグを照合。モジュールを外して設定工具を確認。
- 期待基準: 端子3共通GND、1→MODE_A、4→MODE_B、2→NC。1–3/2–3/3–4→ON/PROGRAM/CV。0/0はinvalid/dark。
- 根拠: `engineering/a7/electronics/README.md`
- 未決: ランド/本体位置公差、導通判定抵抗、設定工具と保持条件の採否値が未決。
- 必須raw証跡: 接点表、寸法、実装写真、アクセス動画
- 機械検証する証跡種別: contact_truth_table, land_peg_measurements, setup_access, switch_lot
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### harness-depth — 完成ハーネスの全長経路・極性・奥行き

- 関連:  #8
- セットアップ/操作: 完成 SH4 と電源ケーブルを全長収納し、全コネクタ・ラベル・IDC を含めて組む。
- 期待基準: PMMA 裏面から30 mm以内が目標。電源自由長は mechanical/layout.json の power_cable_requirement（現時点57±3 mm、±3 ASSUMED）。A5 50±6 mmは流用不可。
- 根拠: `engineering/a7/mechanical/layout.json`
- 未決: 現物ケーブル径、許容曲げ、自由長公差とラベル、完成品供給仕様が未確定。
- 必須raw証跡: 配線極性表、全長/曲げ/奥行き測定、各方向写真
- 機械検証する証跡種別: polarity_matrix, full_length_routing, bend_measurements, installed_depth, cable_identity
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### pmma-supports — PMMA ポケット・締結・PETG 支持

- 関連: Q7/Q8/Q9; #8
- セットアップ/操作: 製造ロットのPMMAと造形品を測る。段階的締結と保持を記録。
- 期待基準: 透明2 mm PMMA、裏面フロスト/表面平滑。0.5 mm後面ポケットは設計選択。M2×18上部ねじ、ボスとフォークを含む。
- 根拠: `engineering/a7/mechanical/README.md`
- 未決: 加工公差、締付トルク、割れ/クレージング、保持荷重、PETG工程条件の採否基準が未決。
- 必須raw証跡: 加工測定、締付ログ、保持試験、写真、材料/造形設定
- 機械検証する証跡種別: material_identity, pocket_tolerances, tightening_log, retention_load, print_settings
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### fixture-contact — SWD 治具の位置・接触・荷重

- 関連:  #19; #10
- セットアップ/操作: 基板単体を支持した治具。PMMAとジャックは荷重経路に使わない。電源OFFで位置と短絡を検査後、承認された電源手順へ。
- 期待基準: 現行基板のB面TP1 +3V3（電圧参照）、TP2 GND、TP3 SWDIO、TP4 SWCLK、TP5 NRST。治具の計算ストロークと荷重に照合。
- 根拠: `engineering/a7/electronics/controller/board_placement.json`
- 未決: 完成治具の実位置公差、接触抵抗/繰返し回数、実挿入力と許容荷重が未決。
- 必須raw証跡: 位置測定、荷重/ストローク、短絡/接触ログ、写真
- 機械検証する証跡種別: registration_measurements, contact_short_matrix, stroke_force, support_photos
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### firmware-waveforms — 書込み識別とLED実ロット波形

- 関連:  #13; #10
- セットアップ/操作: 承認済み電源/プログラマ構成、SWD readback、校正したオシロスコープで左右列を観測。
- 期待基準: 現行A5イメージのハッシュと設定を照合。WS2812B-2020-V6 V1.4 T1L 580 ns–1 µs 対FW 220–420 nsは未解決。
- 根拠: `engineering/a5/firmware/dist/timing.md`
- 未決: Worldsemi訂正/新資料または購入ロットの根拠に基づく別レビューのFW判断が必要。現FWタイミングを承認しない。
- 必須raw証跡: 書込み/readbackハッシュ、設定、ロット、両列のraw波形と時間軸
- 機械検証する証跡種別: programming_readback, stored_configuration, led_lot, left_waveform, right_waveform, timebase_setup
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### power-current — 電源・電流制限

- 関連:  #10
- セットアップ/操作: 電流制限電源、全レール電圧/電流計測、左右LEDの規定負荷。
- 期待基準: 各部品の推奨条件と電流制限の依存関係を exact component 証跡から試験条件ごとにレビュー。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 試験電圧/負荷/持続時間と合否値のレビュー済み数表が未作成。
- 必須raw証跡: 電源設定、全レール波形、電流ログ、負荷表
- 機械検証する証跡種別: supply_setup, rail_waveforms, current_log, load_matrix
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### cv-thru-calibration — CV/受動THRU/校正

- 関連:  #10
- セットアップ/操作: 校正したCV源と計測器、IN/THRU/ADCを同時測定。
- 期待基準: VADC=(100/133)*(VDD/2+CV/8)、C13→R7→U7、R24/R25、受動THRUを維持。
- 根拠: `engineering/a7/electronics/README.md`
- 未決: 誤差/直線性/校正残差の採否値と測定不確かさが未決。
- 必須raw証跡: 入力掃引、VDD/ADC/THRU記録、校正係数と残差
- 機械検証する証跡種別: cv_sweep, vdd_adc_thru_data, calibration_coefficients, residuals
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### startup-reset — 起動・リセット・fault復帰

- 関連:  #10
- セットアップ/操作: 規定の電源立上り/リセット/FAULT条件を一つずつ印加し全レールとLED enableを観測。
- 期待基準: 既存startup/fault動作を維持。保持reset禁止は全ての部分電源喪失を保証しない。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: ランプ/パルス条件、観測窓、復帰合否表をレビューする必要。
- 必須raw証跡: リセット/FAULT/enable/全レールraw波形、設定
- 機械検証する証跡種別: reset_fault_enable_waveforms, rail_waveforms, configuration_readback
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### rail-collapse — 急速レール崩壊

- 関連:  #10
- セットアップ/操作: 承認された負荷/電源遮断条件でレール低下と制御を同時観測。
- 期待基準: 5 V-only sagとバックアップ状態喪失の未解決を評価する。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 崩壊率、最悪負荷、5 V valid monitorの必要性を判断する合否基準が未決。
- 必須raw証跡: 全レール/enable/MCU信号raw波形、負荷と遮断条件
- 機械検証する証跡種別: rail_enable_waveforms, collapse_load_conditions
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### partial-rails — 部分電源・逆給電・無電源CV

- 関連:  #10
- セットアップ/操作: 許可された全レール組合せと無電源CV入力を電流制限下で試す。
- 期待基準: 部分電源/バックパワーを未確認として扱う。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 最大印加値、注入電流制限、順序、許容逆流値を部品資料から承認する必要。
- 必須raw証跡: 組合せ表、電圧/注入/逆流記録、raw波形
- 機械検証する証跡種別: rail_combination_matrix, injection_reverse_current, rail_waveforms
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### u7-stress — U7 差動ストレス

- 関連:  #10
- セットアップ/操作: CVと電源遷移中のU7両入力/電源を差動プローブで測る。
- 期待基準: exact U7 の許容入力差動条件に条件ごと照合。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 安全な印加条件とプローブ帯域、部品限界の条件付き数表が未作成。
- 必須raw証跡: 両入力と電源のraw波形、最大差分計算、プローブ情報
- 機械検証する証跡種別: input_supply_waveforms, differential_stress_calculation, probe_identity
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### ldo-reverse — LDO 逆電流

- 関連:  #10
- セットアップ/操作: 入力/出力レール遷移を承認済み制限下で独立に制御。
- 期待基準: TLV75533PDBVR の逆電流未確認を評価。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 印加順序/上限と許容逆電流/時間のexact-part根拠が必要。
- 必須raw証跡: 両レール波形、逆電流、温度、回路条件
- 機械検証する証跡種別: rail_waveforms, reverse_current, temperature, sequence_conditions
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### load-short — 負荷・短絡・保護

- 関連:  #10
- セットアップ/操作: 制限電源と規定短絡負荷を使い、回復と温度を観測。
- 期待基準: 現行電源保護の実動作を検証する。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 短絡場所、時間、繰返しと復帰/最大温度基準の承認が必要。
- 必須raw証跡: 短絡/解除波形、電流/温度/FAULTログ
- 機械検証する証跡種別: short_recovery_waveforms, current_temperature, fault_log, load_conditions
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### effective-capacitance — MLCC 実効容量

- 関連:  #10
- セットアップ/操作: 実装型番/ロットのDCバイアスと温度条件を記録して容量/リップルを測る。
- 期待基準: 各exact MLCCの条件付き有効容量と回路要求の照合。
- 根拠: `engineering/a5/integration/independent_review`
- 未決: 必要容量下限と測定法を部品曲線と回路レビューで決める。
- 必須raw証跡: 型番/ロット、バイアス/温度、容量とリップルraw記録
- 機械検証する証跡種別: component_lot, bias_temperature, capacitance, ripple_waveforms
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### thermal-optical — 温度・光学・Kumiko照明

- 関連:  #10
- セットアップ/操作: 最悪負荷/周囲条件でインダクタ、ホットスポット、PETG、PMMAを測定し左右照明を撮影。
- 期待基準: 51/255 capは温度承認ではない。約2% D2遮光はモデル推定のみ。
- 根拠: `engineering/a7/mechanical/README.md`
- 未決: 周囲条件/安定判定、部品/材料温度限界と見え方のオーナー採否が未決。
- 必須raw証跡: 温度時系列、IR補正、材料ロット、露出固定写真、周囲条件
- 機械検証する証跡種別: temperature_series, ir_corrections, material_lot, optical_photos, ambient_conditions
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### cv-noise — CV ノイズと DATA_L 結合

- 関連:  #10
- セットアップ/操作: 静的CVを印加しDATA_L/左右ストリームのパターンを切替、ADC/THRUを同期観測。
- 期待基準: 記録されたCV_THRU対DATA_L_3V3/SWDIO、CV_ADC対SWCLKの結合懸念を評価。
- 根拠: `engineering/a7/verification/interface_review.md`
- 未決: 帯域、ノイズ統計と許容誤差の採否値が未決。
- 必須raw証跡: 同期波形、スペクトル/統計、配線/プローブ位置、パターン
- 機械検証する証跡種別: synchronous_waveforms, noise_statistics, probe_wiring, data_patterns
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

### service-envelope — 挿抜・交換・組立外形

- 関連:  #8; #10
- セットアップ/操作: 全ケーブルと完成部品で挿抜、側板交換、スイッチ設定、再組立を実施。
- 期待基準: PMMA裏面を基準に30 mm目標、3HP前幅14.9 mm、高さ128.5 mm。
- 根拠: `engineering/a7/mechanical/layout.json`
- 未決: 繰返し回数、許容力/損傷、組立ばらつきと合否基準が未決。
- 必須raw証跡: 寸法、挿抜力、交換動画、前後写真、部品識別
- 機械検証する証跡種別: envelope_dimensions, insertion_extraction_force, replacement_record, before_after_photos, part_identity
- 観測: NOT_MEASURED。結果: NOT_RUN。
- 次: 不足する基準をレビューし、オーナー承認の試作ルート確定後に実物で実施。

## 現在のブロッカー

- fixture digital design incomplete or unverified
- fixture: unresolved preparation blockers
- assembly_manifest: unresolved preparation blockers
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
