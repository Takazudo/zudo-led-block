# 0.7–0.9 mm 基板の治具条件マトリクス — 計算記録（受入ではない）

**状態: 計算のみ。治具の受入・接触・荷重・位置決め・加工・発注のいずれの承認でもありません。**
生成物は [`condition-matrix.json`](condition-matrix.json)（`status` = `EXPERIMENTAL_CALCULATED_NOT_VALIDATED`）。
旧 1.6 mm 治具の PASS をこの基板へ移しません。`optical-support-study.md` に残る失敗値は撤回していません。
束縛先は採用された配線済み 0.8 mm コントローラ（PCB SHA-256 `d83691d6…`。2026-11-21 に同じ部品配置・外形の `710ed801…` から再束縛した。`710ed801…` は履歴）。

```sh
# 生成（最終基板へ再束縛するときもこの 1 コマンド）
python3 scripts/a7_fixture_matrix.py --rebind
# 検査（CI もこれを実行：identity・自己整合・レベル0の再計算）
python3 scripts/a7_fixture_matrix.py --check
# ソルバ検証（解析解・総当たり・2 ソルバ相互検証・スケーリング）
python3 -m unittest scripts/tests/test_a7_fixture_contact.py scripts/tests/test_a7_fixture_matrix.py
```

再束縛の前提: 新しい基板バイト列の native geometry 記録を取り直すこと。CI が保持した
artifact があれば `--from-zip`、開発機で固定イメージのゲートを回した場合は `--from-dir`
（記録は `provenance_class` = `LOCAL_PINNED_IMAGE_RUN`、`ci_retained_artifact` = false。
GitHub run id は無く、CI 保持 artifact と同等ではありません）。

```sh
# CI 保持 artifact（native-infrastructure-evidence の ZIP。VALID_PASS・run・attempt・基板/leaf ハッシュを照合）
python3 scripts/a7_fixture_geometry.py --from-zip <native.zip> \
  --expect-revision <CI の checkout SHA> --expect-run-id <run id> --expect-run-attempt <attempt> --write
# 開発機で固定イメージのゲートを回した場合
python3 scripts/a7_fixture_geometry.py --from-dir <a7-gate を含むディレクトリ> \
  --expect-revision <ゲートを回した checkout SHA> --write
python3 scripts/a7_fixture_geometry.py --check
```

現在の native geometry 記録は 0.8 mm コントローラ `d83691d6…` の **CI 保持 artifact** から取り込んだもの（2026-11-22、`--from-zip`、CI run 44981535275 attempt 1、artifact ZIP SHA-256 `11346c06…`、`provenance_class` = `CI_RETAINED_ARTIFACT`）。幾何の中身は 2026-11-21 の開発機実行（`--from-dir`、`LOCAL_PINNED_IMAGE_RUN`）とバイト単位で同一で、変わったのは出所の記録だけ。
記録と基板バイト列が食い違う間は `--check` が fail-closed で落ちます
（`pcb_identity.board_identity_bound`）。

## 方法（独立に検証できる形で）

| 項目 | 内容 |
|---|---|
| 板モデル | Kirchhoff 板、Bogner–Fox–Schmit 矩形 C1 要素（テンソル三次 Hermite、節点 4 自由度）。`scripts/a7_fixture_plate.py` |
| 領域 | 実基板外形 16.2 × 62.9 mm。穴・銅箔・部品補強・反りは入れない |
| 接触 | 剛体キャリア land に対する節点ごとの Signorini 条件（w ≥ 0, 反力 ≥ 0, w·反力 = 0）。land は押すだけで引けない。両側支持の結果は使わない |
| ソルバ1 | 可撓性形式の primal active set（`scripts/a7_fixture_contact.ContactModel`）。剛体モードのみ 3 点で拘束し、接触集合を active set で求める |
| ソルバ2 | 剛性形式の active set（`solve_reference`）。同一ケースを独立に解いて相互検証 |
| 収束確認 | 解の後に `K u − f` から接触条件・平衡残差・相補性を再計算し、満たさなければ戻さず例外にする |
| 荷重 | 一様圧の円形パッチ（プローブ先端 Ø0.5 mm、クランプピン Ø1.5 mm）。極座標積分で合力は厳密。点荷重は比較用に残す |
| 材料 | 曲げ弾性率 18000 MPa（**ASSUMED**: 基材未出典）、ポアソン比 0.3（**ASSUMED**）。出典のある FR-4 類似値は比較のみ |

`w` は上向き正（F 面側）。マージンの判定量は **プローブパッド中心の変位**（プローブ圧縮量を直接変える量）と、
**land からの浮き上がり**（着座が崩れる量）です。浮き上がりは接触モデルでしか表せず、旧 1D ストリップモデルには
存在しませんでした。基板全体の上下限は Bézier 制御網の凸包から保守的に取ります。

## 判定限界

| 量 | 限界 | 根拠 |
|---|---|---|
| プローブパッド変位 | 0.1 mm | PROJECT-CHOICE（`a7_fixture_relief.RULES`）。作動ストローク 4.3 mm と最大 6.35 mm の差 2.05 mm に対して小さい |
| land からの浮き | 0.1 mm | PROJECT-CHOICE、同値。基板は land と基準ピンに着座するため、浮きは圧縮と位置決めの両方の損失 |
| クランプ合計力 | ≥ 12.7 N | 最大ストローク時プローブ合計 6.35 N の 2 倍（`clamp_force_margin_factor`） |
| 圧縮量 | > 0 かつ ≤ 1.3 mm | ストローク 1.5 mm からストローク端余裕 0.2 mm |
| メッシュ収束 | 最終ステップの相対変化 ≤ 5 % | 記録した要求。レベルは 20×78 → 40×156 → 60×234 |

力のバンドは変位制御のまま：公称圧縮 1.05 mm、積み上げ公差 ±0.25 mm（基板厚 0.1、ストップ長 0.05、設定 0.1）、
押さえ板たわみ 0.009 mm、さらに **同一接触モデルで解いた基板のたわみ** を最小側から引き、カタログ直線に ±20 %
の受入帯をかけます。たわみを旧ストリップ値（0.40 mm）ではなく接触モデル値（0.002–0.007 mm）で引くため、
力のバンドは旧記録より広くなります。これはモデルの差であり、測定でも承認でもありません。

## 結果の要点

- **現候補（`optical_stepped_tip`、ピン (1.2, 20.8) と (15.325, 26.375)）**: 位置とプランジャ（KIPP K0318.04）は
  そのままで、2 本目の POM ピンの基板接触端だけを Ø1.2 mm × 長さ 0.5 mm の段付き先端にする案です。接触径で
  板端余裕は最悪 0.175 mm（1 本目は Ø1.5 mm のまま 0.150 mm）となり、記録した要求 0.15 mm を **変えずに**
  満たします。0.7/0.8/0.9 mm の全板厚・全力コーナーで荷重限界も満たします（`adopted_candidate`）。
  - 接触圧は最大プランジャ力 ÷ 接触面積の平均値で確認します。許容値 20 MPa は **ASSUMED**（無充填 POM の
    約 1 % ひずみ時の圧縮応力の一般的な値。出典なし、ピンのグレード不明）で、出典付きの値か押込み試験に
    置き換えるまで受入根拠にはなりません。
  - 段付き先端は購入品の追加工で、**PROPOSED**（未調達・未選定・owner 承認待ち）。Ø1.5 mm の軸部は基板に
    触れず、平面視では最悪でも基板内（余裕 0.025 mm）に残ります。先端の摩耗・クリープ・レジスト面の傷・
    実際の接触面は実機確認の対象です。
  - 検討した 3 案は `adopted_candidate.options_considered` に残します。(b) 長円形フット（1.2 × 1.8 mm）は数値は
    通りますが、スプリングプランジャのピンは回転自由で向きを保てないため不採用。(c) 3 本目の押さえは、
    平面規則を満たす位置がプローブ重心より先に無く、基板が 0.576 mm 浮くため不成立。
- **前候補（`optical_full_pin`、Ø1.5 mm ピンそのまま）** も記録に残します。荷重限界は満たしますが、2 本目の
  ピンの板端余裕が 0.025 mm で要求 0.15 mm を下回ります（下の「幾何学的不足」）。
- **旧配置（`historical_plunger_pair`）は依然 FAIL**。接触モデルでもプローブ変位が 0.1 mm を超え、基板が land から
  0.8 mm 以上浮きます。`a7_fixture_relief` の `REJECTED_INSUFFICIENT_FORCE` も記録に残します。
- **候補の CAD（2026-11-22）**: 段付き先端・ピンスリーブ・J5 ノッチ・押さえ板を CadQuery で組み、保持中の形状とは別に [`candidate-assembly.step`](candidate-assembly.step) と [`candidate-assembly-interference.json`](candidate-assembly-interference.json)、[`candidate-drawing.svg`](candidate-drawing.svg) に記録しました（`python3 scripts/a7_fixture.py --cad`）。0.7/0.8/0.9 mm の各板厚で干渉 0、このマトリクスの値（ピン位置・接触径・先端長・ノッチ・押し込み範囲）と一致することを `--check` が照合します。ただし押さえ板は Ø3.4 の通し穴の M3 ねじだけで位置が決まり最大 0.4 mm ずれ得るため、上の端余裕（記録した許容差 0.10 mm 前提）はその位置決めが 無いと成立しません（同記録の `registration`）。**受入ではありません**。
- **全径ピンの幾何学的不足（段付き先端で回避、位置移動では未解決）**: 全径ピンの 2 本目は板端まで最悪
  0.025 mm しか残らず、記録した要求 0.15 mm を下回ります。平面規則を満たす全ペアを走査しても、押さえ板の web 規則が候補位置を y ≤ 22.3 mm に閉じ込め、
  プローブ列（y 22.4–28.2 mm）を挟めるペアが存在しません。そのため代替ペアはいずれも基板を 0.42 mm 以上
  浮かせます。閉じるには計算では出せない入力が必要です（より小径の出典付きプランジャ本体、J5 ノッチの縮小、
  押さえ板の拡大、または小さい端余裕をゲージ受入要求として owner が受け入れる判断）。
- 数値そのものは `condition-matrix.json` の `layouts.*.verdict` / `force_band_per_thickness` / `cases` /
  `convergence` / `alternative_clamp_sites` を参照。ここに数値を手書きしません（ドリフトを防ぐため）。

## 仮定（記録の `assumptions` と同じ）

完成板厚 0.8 ±0.1 mm は JLCPCB 公開公差（1.0 mm 未満）であり発注も実測もしていない／曲げ弾性率とポアソン比は
ASSUMED／キャリア land は剛体平面と扱い、平面度・積み上げ・ピン先端の同一平面性は受入要求／反り・歪みは
未モデル（初期隙間ゼロ）／プランジャ力はカタログ直線に ±20 % 帯（カタログに公差なし）／プローブ力は資料の
直線、最大ストローク値はグラフ読み／穴・銅箔・レジスト・部品補強は板モデルに入れていない（銅箔の省略は
常に保守側ではない）／部品高さ・はんだ包絡・押さえ板の CAD 干渉はこの記録の外（候補の CAD 検査は `candidate-assembly-interference.json`）。

## 残っている作業

実機の接触・荷重検証（プランジャ力の両端実測、プローブ力、ストローク、基準ピンへの着座、位置決め、損傷確認を
治具・基板の unit ID、測定器、生データ付きで：治具基準 5）／発注基板の実測板厚と基材曲げ特性／反りの受入と
接触集合への影響／押さえ板の位置決め（CAD は干渉 0 だが通し穴だけでは端余裕が閉じない）／このモデルと入力の独立レビュー（初回の再導出は `README.md` の「独立レビュー」）／
プレート加工業者の選定と加工可否。
