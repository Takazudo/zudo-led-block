# 0.8 mm FR-4 機構判断・電源adapter保持の根拠

2026-11-17 JST owner変更、子Issue #87。デジタル設計入力の独立検討記録であり、実物の嵌合・光学性能・製造releaseではありません。計算正本は `design-inputs.json` と `../study/parameters.json`、生成結果は `layout.json` です。

## 幅とleaf

0.8 ±0.1 mmで既存の有限offset sweepを再計算。2HPのnominal適合候補offset0.6 mmはworst端子側−0.35 mm、本体側−0.15 mm、ナット0.00 mm。最良worst値を与えるoffset0.7 mmでも−0.25/−0.25/−0.10 mmです。軸高さ・trim・加工公差の未確定があるため、2HPが物理的に不可能と断定せず、今回の試作には許可された3HPを選びます。3HP中央・0.8 mm・未trimはworst +0.10/+3.00/+3.15 mm。板厚を1.6 mmへ戻す選択はしません。

leafは0.8 mm×2＋bond0.10 mm＝1.70 mm。bond±0.05 mmとfinished slot±0.05 mmは未確認の製造・組立受入要求です。板厚公差込みの積層1.45–1.95 mmに対しcap溝2.15 mmは最悪片側0.075 mmの隙間。旧1.60 mm溝は公称でも片側0.05 mm干渉します。controller溝は1.10 mm、同じslot公差なら最大0.90 mm基板との最悪片側隙間0.075 mmです。実物の保持・接着・ガタ・組立は未評価です。

## adapterは1.6 mm・2層を保持し、取付位置を変更

`engineering/a5/electronics/native/power_adapter/power_adapter.kicad_pcb`を読取確認：外形8.8×30.0 mm、板厚1.6 mm、F.Cu/B.Cuの2層、zoneなし。A5の基板・mask・配線・部品を編集しません。今回の主対象leaf/controllerの0.8 mm方針から、このadapterを変更する必要性は直接光路の位置関係では認めません。

座標の原点を取り違えないこと：A5のadapter前面Zは17.4 mmです。旧A7のshift−2.0はZ15.4–17.0。新入力のshift−4.0は**A5の17.4に加算**するためZ13.4–15.0です。旧A7位置から−4.0をさらに引く操作ではありません。

3HPでadapterのX範囲は3.05–11.85、Y18–48。新leafの直接左右放射corridorはZ19.4–28.4なので、adapter PCBとは公称4.4 mm離れます。IDC tailのモデル上限Z16.0、PicoBlade tail Z15.7も、このcorridorに入りません。controller上端Y48.5とのadapter基板のnominal Y隙間は0.5 mm、adapter PicoBlade本体上限Y47.85との隙間は0.65 mmです。0.8 mm controllerではcomponent face X4.45を維持し、solder faceだけX3.65へ移動するので、このadapterのnominal配置条件を悪化させません。

これは全方向の光学影響がないという意味ではありません。adapterは前面から見たY18–48の領域に従来の不透明な基板・コネクタの影を残します。散乱・反射・周囲光透過・実際の明るさは未測定であり、直接側方corridorの非交差だけで光学PASSにしません。IDC socketは参照品、ribbonは条件付きscenarioという既存の限定も維持します。

## SHハーネスの公差予算

旧Z15.4–17.0の位置では、JLCの1.6 mm±10%を入れるだけでZ18.2・radius1.0のハーネスとの最悪隙間が0.04 mmになり、組立余裕を確保できませんでした。adapterを前へ移すことで基板を薄くせずに解消します。

- adapter板厚1.6±0.16 mm（JLC公開条件、最終注文条件は要照合）＋取付Z±0.10 mm（仮定）→rear最大15.26 mm。
- leaf前端Z19.4±0.10 mm（取付の仮定）→front最小19.30 mm。
- SH gap-run中心Z17.9±0.10 mm、bundle最大radius1.10 mm（ともに未測定の受入要求）→Z16.70–19.10 mm。
- adapter側最悪1.44 mm、leaf側最悪0.20 mm。generatorは0.20 mm未満を拒否します。

この区間計算は、ハーネスの全swept path、部品間干渉、connector insertion、工具アクセスの代用ではありません。新しいCADで全経路を検証し、実ケーブル外径・曲げ半径・位置保持・加工公差を物理工程で確認します。PMMA rear Z0に対して移動後の参照socket前端はZ3.6、IDC本体前端はZ4.5で、公称の前方空間は残ります。

adapter移動に伴いcap spacerは4.0 mm（Z15–19）、top-cap screwはM2x20（旧M2x18）、nut先端からの公称突出2.2 mmを維持。これらの荷重・材料・実部品は未検証です。generatorのpower cable自由長は55±3 mm（52–58 mm）、両幅のstowage許容区間49.037–76.053 mmへ変わります。製造manifestと完成ケーブル仕様はこの新入力へ接続する必要があります。

## 根拠と未完

- JLCPCB Capabilities: https://jlcpcb.com/capabilities/Capabilities のThickness Tolerance行。2026-11-16 UTC閲覧、1.0 mm未満±0.1 mm、1.0 mm以上±10%。
- 不変のA5 `mechanical/geometry.json` と `mechanical/README.md`：adapter、C5665最大包絡、PicoBlade寸法、参照socket・ribbonの限定。
- 新しいnative PCB、CAD、fixture、Gerber、previewと同一identityでの最終照合が必要。旧dated order・旧fixture PASS・旧製造承認の適用範囲は変更しません。

## CADで検出したleaf／M1.6ナット干渉への修正

新しい0.8 mm leafの実形状CADで、旧中心offset±2.4 mmのM1.6ナットがleafに干渉しました。±2.7 mmへの移動だけでは製造・取付公差込みの余裕を確保できません。

採用3HPは中心offset±3.4 mmに変更します。ナットAF3.2±0.1 mm（公差は仮定）の最大外接半径1.9053 mmを使い、回転方向固定による小さい包絡に依存しません。穴/pocket位置±0.10 mm、nut/pocket内移動±0.10 mm、leaf中心±0.05 mm（いずれも仮定した受入要求）と最大leaf半厚0.975 mmを加えると、最悪leaf隙間は0.2697 mm。cap外縁の±0.10 mmも含めた外側余裕は1.5447 mmです。基準はleaf隙間0.15 mm、外側0.30 mm以上で、採用variantが下回るとgeneratorを停止します。±2.7 mmへ戻すnegative testを追加しました。

2HPは旧offset±2.4 mmを履歴比較として表示しますが、この公差予算を満たさず未採用です。3HP用offsetを2HPへ無条件でコピーすると外側余裕も不足します。

hardware-to-leaf隙間の成立はcap強度の証明ではありません。nut pocketとleaf slotがZ28.2–28.6で近接するため、薄い局所lipを構造webとみなさず、CAD側では必要な逃げと残存する中央rear bridgeを別途検討します。ナット保持・印刷品質・組立荷重・基板接着の物理評価は未実施です。
