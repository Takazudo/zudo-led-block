# A7 SWD 治具 — 未完成のキャリア検討

**BLOCKED / 加工・購入・使用の承認ではありません。** E3 の完成治具ではなく、正確な部品資料、現行基板に拘束した接点表、再生成可能な FR-4 キャリア単体の検討です。STEP を生成・検査済みでも、支持・位置決め・ストッパ・接触性能を検証したことにはなりません。

- `sources.json`: INGUN 一次資料の実取得バイトの SHA-256、11/26_GB、ページ位置。原本は記載のローカルキャッシュ。再取得時はハッシュを比較する。
- `materials.json`: 治具1台分の候補。モジュール1台分の BOM と別。未選定材料・価格を埋めない。
- `manifest.json`: 現行 revision 2 の PCB/placement/geometry identity、B面変換、TP接続、計算と未解決事項。
- `carrier-study.step` / `carrier-study.svg`: キャリア**単体**。組立図・完成治具モデルではない。

## 再生成と検査

```sh
python3 scripts/a7_fixture.py --cad
python3 scripts/a7_fixture.py --check --cad-check
python3 -m unittest scripts/tests/test_a7_fixture.py scripts/tests/test_a7_fixture_relief.py
```

STEP は CadQuery **2.7.0** で生成し、再読込して1 solid、体積4604.289782 mm³（下記の逃げを含む。CadQuery の boolean 結果を矩形和集合の体積で照合。逃げ導出そのものの検証ではない）、25×40×5 mm、形状妥当性を検査する。STEP の時刻ヘッダではなく形状を検査する。JSON/SVG は通常生成で一致検査する。PCB または canonical placement が変わると明示的 identity lock により失敗し、レビューなしの追随を防ぐ。E1の canonical/copy/PCB 検査を使用するが、これは fresh-native の独立検証の代替ではない。

## Native CI の証拠範囲

2026-11-09 に E1 の pinned native CI [run 42594178172](https://github.com/Takazudo/zudo-led-block/actions/runs/42594178172) が head `4894a6f6f21b30419d039bd6427e89553f8dee55`、同一PCB SHA-256 `4453f818ede1e6d6c56e45ef43aa6faecb90990f3755f82c6d752258cd4d628e` で PASS と確認された。この結果はその E1 head の証拠であり、未コミットの統合変更や治具形状を検証したものではない。artifact download は escalation 後も Forbidden で、raw native facts は未取得。治具が新しい外形データを消費・検査していないため、`fresh_native_verified` は **false** のままとする。

2026-11-11 更新: PR #44 の準備 head `f0b1d8aa37f3967ccc8c9a6bd6ca0e7b7fc7b3a0`（base `af523f9`）の CI [run 42596523199](https://github.com/Takazudo/zudo-led-block/actions/runs/42596523199) も同一PCBで native gate PASS。同 run の `native-infrastructure-evidence` artifact（ID 13663737750、ZIP SHA-256 `33f3d9121164f364b0325540b161e9546ddf73c8b723c9166fdcd8a19867cf0e`）は今回ダウンロードできたが、A7 候補については `a7-gate/summary.json` しか保存されておらず、`board_facts.json` / `board_geometry.json` は含まれない。上の 2026-11-09 の Forbidden は当時の観測として残す。現在の不足はアクセス拒否ではなく artifact の保存範囲であり、`fresh_native_verified` は引き続き **false**。

2026-11-11 追記（PR #46）: native gate が同一PCBから治具用の `fixture_geometry.json`（pad の形状・寸法・銅箔 bbox・回転・有効層・net、footprint の原点・面・courtyard/外形 bbox）を出力し、CI artifact に保存するようになった。[run 43077448786](https://github.com/Takazudo/zudo-led-block/actions/runs/43077448786)（head `01bc3812202c6e72f772d2568148ae5df4915be7`、artifact ZIP SHA-256 `db6d6fe101641a4176d0fad83a7fd453ee4ae09173e7fb36d26dd444284b74c4`）の artifact は VALID_PASS と分類され、`scripts/a7_fixture_geometry.py --from-zip` が `native-geometry.json` に記録した（64 footprints、変換・面・net・位置を canonical placement と照合、未知 extents 0）。`manifest.json` の `native_geometry` はこの記録で TP1–TP5 の5パッド（B面、丸 1 mm、B.Cu/B.Mask、位置、net）を照合した結果である。部品本体高さ・はんだ包絡は native facts に含まれず、キャリア検討は courtyard/外形 bbox をまだ支持・逃げ設計に使っていないため、`fresh_native_verified` と `digital_fixture_complete` は **false** のまま。記録は `python3 scripts/a7_fixture_geometry.py --check`（CI でも実行）で PCB/placement の陳腐化、pad 数、内部不整合を検査する。member hash まで再計算した改変の出所は `--check` では判定できず、`--from-zip` による作成時の検証と差分レビューで担保する。

## B面の逃げと支持（2026-11-11）

`scripts/a7_fixture_relief.py` が `native-geometry.json` から B面の逃げを導き、`manifest.json` の `b_side_relief` と STEP/SVG に反映する。

- 0603 抵抗（B面、キャリア範囲内の13個と、範囲端に 0.175 mm だけ掛かる R12 の計14ポケット）: native の pad 銅箔 box と、資料の最大本体外形（UNI-ROYAL SMD-SP-001 V.11、物理 page index 3、0603 行 L 1.60±0.15 / W 0.80±0.10 / H 0.45±0.10 mm、SHA-256 `d27e4cdc…20d3`）の和に 0.2 mm を加えたポケット。深さは最大本体高 0.55 mm + 0.25 mm = 0.80 mm。高さは **SOURCE_DERIVED**（測定値ではない）。はんだフィレット高さの出典はなく `null`。
- THT（J1/J2 の PJ-324M、J5 の PicoBlade）: native の pad 銅箔 box + 0.3 mm の貫通逃げ。はんだは銅箔にのみ濡れるため横方向は銅箔で抑える。貫通なので高さに依存しないが、PJ-324M の突出（端子突出 3.2±0.2 mm、ミラー資料、板厚公差は未出典）と J5 のテール長（出典なし、`null`）はキャリア下側の設計で未解決。
- SW1 の NPTH ピン（0.5 mm、メーカー一次資料）は 1.6 mm 板を貫通しないため逃げ不要。
- プローブ穴と逃げの最小肉厚: 研究値 0.5 mm（出典のある最小値はない）に対し、TP1/TP2/TP3/TP4/TP5 と R7/R9 の間で 0.255–0.420 mm の6組が不足。blocker として manifest に残す。基板変更は範囲外。
- 逃げ同士・逃げとキャリア端の壁: 0.5 mm 未満の壁（R6/R7、R16/R17、R16/R18、R24/R25 など）も blocker として列挙する。
- 基板外形より外側のキャリア張り出し部: J1/J2 の F面 courtyard が掛かるが、本体は F面側で B面より上にあるとみなし、検査していない（manifest の `overhang_not_checked`）。
- 支持: キャリア上面が B面に接する面積の幾何計算のみ（ランド率 0.80、各プローブ半径 3 mm 内 0.54–0.72）。荷重経路・たわみ・押さえは未解析。

クリアランス・最小肉厚・支持半径は PROJECT-CHOICE の検討値であり、加工公差や適合結果ではない。`fresh_native_verified` は、フィレット高さ・J5 テール・PJ-324M の一次資料/板厚公差が未出典のため **false**。`digital_fixture_complete` は下記「完成に必要な証拠」2–5 が未達のため **false**。

## 現時点の数値と限界


GKS-050 214 050 A 1000 は先端 Ø0.5 mm、推奨ストローク4.3 mmで公称1 N、最大6.35 mm、初期荷重0.44 N。5本では公称5 N、初期2.2 N。公差は資料にないため最大荷重とは呼ばない。実PCBの露出B面丸パッド Ø1 mmとの差から、**公称**半径予算は0.25 mm。基板端→パッド、位置決め、穴位置、接触子の横遊び・同心度の最悪値が未確定なので最悪登録余裕は `null`。数値を推定して合格にしない。

KS-050 E08 V-30 の一次資料は FR-4/CEM1穴 Ø0.98–1.00 mm。検討穴 Ø0.99 mm は加工要求であり、製造実績ではない。樹脂印刷穴へ転用しない。外径は図0.96 mmと表0.95 mmが不一致。資料の互換シリーズはKS-050だが、寸法差・圧入高さ・実ストロークを解決してから選定する。

現行最小ピッチ1.4 mm、メーカー公称グリッド1.27 mm、カラー外径1.04 mmから公称カラー間隔0.36 mm。隣接部品の高さ・工具アクセス・圧入荷重の承認ではない。キャリアZは局所モデル座標のみで、接触高さを規定していない。

## SWD 配線の検討（未実施）

| Pad | 信号 | 接続意図 |
|---|---|---|
| TP1 | +3V3 | programmer の VTref **入力**。ターゲット給電出力に接続しない |
| TP2 | GND | 共通GND |
| TP3 | SWDIO | SWDIO |
| TP4 | SWCLK | SWCLK |
| TP5 | NRST | reset |

全レセプタクルは緑線なので両端にTP識別を付ける必要がある。programmer型式・コネクタpin番号・電圧仕様は未選定。外部電源は既存の正規入力経路、極性、電流制限、rail/back-power手順を別途確定する。TP1による逆給電やprogrammerとの二重給電を承認しない。

最終モジュール組立前のコントローラ単体を対象とする案。電源OFFで方向/identity/配線を照合し、支持部へ設置、ストッパまで押し込み、接触確認後に規定の電源投入、認識/書込/照合、電源OFF、解除という手順を**設計してから**実施する。現時点で実施可能な手順ではない。

## 完成に必要な証拠

1. 同一PCBのfresh-native F/B pad・component外形、高さ、はんだ包絡から、局所支持と全逃げを決定。PMMAやジャックはんだ部へ荷重を逃がさない。
2. 非対称な実形状で逆挿しを阻止する位置決めと支持経路を設計し、上記0.25 mm予算内の最悪公差を出典または明示した受入測定要求で閉じる。基板の矩形外形だけでは逆向きを防げない。
3. 実装高さ・ストローク・最大荷重を解決し、調整法と独立した機械ストッパ、ガイド、固定具、絶縁と配線保持を設計。
4. 完成組立STEP/寸法図を再生成・干渉検査。現ファイルを完成品として流用しない。
5. owner承認の試作ルートにより、治具/基板unit ID、測定器、raw画像・測定値付きで接触、実荷重、位置決め、ストローク、損傷を試験。観測はすべて NOT_MEASURED。

関連の #8 / #10 / #19 の物理受入は未完了。部品への発注・質問送信は行っていない。
