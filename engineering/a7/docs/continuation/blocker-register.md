# A7 発注準備の未解決記録

2026-11-09。判断は [decision-register.md](decision-register.md)、exact-head検証と成果identityは [checkpoint](order-preparation-checkpoint.md) を参照してください。以下は合格でも製品判断でもなく、未取得の証跡・未完実装・アクセス条件です。

| ID | 止まる範囲 / 状態 | 不足・解除条件 | 関連 |
|---|---|---|---|
| B1 | E1 merge: 保留 | リポジトリ変数APIはHTTP404。現在のmain mergeが無許可デプロイを起動しないことを、許可された方法で確認する必要。PR runのSKIPだけでは足りない | PR #44 |
| B2 | 新規子Issue: 親のhold | 最初の作成は中断され、未作成を確認済み。拒否/中断の理由が未特定。理由が明らかになるまで当該操作を再試行しない | #15、E1–E5下書き |
| B3 | ローカルnative取得/実行: ENOSPC失敗 | digest-pinned imageが32 GBを満たした。容量回復後もローカル成功とは記録しない。E1はexact-head CI native PASSで検証済み。新しいnative出力が必要な作業は対応可能なCloud実行環境が必要 | E1/E3 |
| B4 | E2残り資料: 未取得 | claim単位監査、独立レビュー修正、sync-states/selection/generation、公開site scanは完了。未取得一次資料と物理適用は残る。取得成功はfit/stock/service承認ではない | #9/#13/#19 |
| B5 | E3完成治具: BLOCKED | 2026-11-11 W8: 治具を分割構成に変更（固体 FR-4 のプローブ板 + 窓付き支持キャリア + ねじ止めばね押さえ板 + ベース）。JLCCNC 指針（未選定の参考、壁 1.0 mm・内角 R=H/10+0.5）を全プレートで満たし、基準 3（押さえ・ガイド・固定・絶縁・配線）と基準 4（組立 STEP 135 solid、干渉 0、重要隙間すべて正）をデジタルで閉じた。2026-11-12: J5 テール長の出典（`fact-530470310-tail-length`）を取り込み、基準 1 を満たした（`fresh_native_verified` true、`digital_criteria_1_to_4_met` true、`digital_fixture_complete` は基準 5 のため false）。全資材行に出典付きの金物候補を owner 承認待ちの提案として記録（`hardware_proposal_complete` true、選定ではない）。残り: 加工業者と提案金物の owner 承認、プローブ穴間 0.40 mm の穴あけ可否を加工業者が確認、物理試験（基準 5） | #19/#10 |
| B6 | 完成品調達: 未確定 | PJ-324M nut/washer、保証ケーブル構成と自由長、公差、PCM13SMTR供給/実装サービス、PMMA/PETG工程、fixture部材の確定。現行在庫/価格/MOQ/納期/包装は実取得分だけ有効 | #8/#9/#19 |
| B7 | ジャック/スイッチ適合: NOT_MEASURED | TS/TRS全端子導通、軸/端子/スロット/ナット、switch真理値/ランド/設定アクセスを実部品で確認しraw記録を残す | Q1–Q4/Q10、#8/#19 |
| B8 | 機構/ハーネス: NOT_MEASURED | PMMA公差・ポケット・締付/保持、PETG支持、完成ケーブル全長経路、M2×18 load path、挿抜/交換、全ケーブル込み30 mm奥行きの実測 | #8/#17 |
| B9 | 電気/FW/熱/光学: NOT_MEASURED | `qualification/procedures.md` の全手順とraw evidence kinds。電源/CV/THRU/校正、reset/rail-collapse/partial-rail/back-power/U7/LDO/load/容量、熱/光学、DATA_L結合ノイズを含む | #10 |
| B10 | LED timing判断: 未解決 | exact WS2812B-2020-V6 V1.4のT1L 580 ns–1 µsと継承FW 220–420 nsの不一致。メーカー訂正/新資料または購入ロット実測に基づく別レビュー。A5は変更しない | #13 |
| B11 | 試作入手: 未承認 | #10の現行release条件を保持したまま、限定sample/prototype routeのオーナー承認が必要。物理測定を捏造して依存関係を解消しない | #10 |
| B12 | 製造リリース/注文: なし | 必要な物理・供給・版別raw証跡と基準、レビュー済み製造ファイル、数量/注文条件、明示オーナー承認が必要。NOT-A-RELEASE出力を注文ファイルに改名しない | #10 |

`qualification/readiness.json` は（2026-11-09 時点で）49個の具体的な不足を機械可読で列挙します。資料または入力が変われば再生成が必要です。schema/reportのVALIDはこれらの解消を意味しません。

PET Q11/Q11a–fと2HPの0.8 mm再配線/公差課題は別案のブロッカーです。FR-4/3HPの必須ゲートに混ぜません。A6 #7/PR #14は引き続きON HOLDで、そのブランチ・記録を削除しません。

## 2026-11-09 の取得失敗

- `src-pmeg4010cej-115-ds`: https://assets.nexperia.com/documents/data-sheet/PMEG4010CEJ.pdf、2026-11-09T09:19:18.570819+00:00、HTTP 403、資料bytes未取得。別の公式配布先またはオーナー提供の原本を取得し、hash/適用型番/ページを検証する。変更のない再試行はしない。
- `src-sm04b-srss-tb-lf-sn-sh-catalog`: https://www.jst-mfg.com/product/pdf/eng/eSH.pdf、2026-11-09T09:19:19.369040+00:00、HTTP 403、資料bytes未取得。別の公式配布先またはオーナー提供の原本を取得し、hash/適用型番/ページを検証する。変更のない再試行はしない。
- `src-a7-pj-324m-sofng-site`: https://www.sofng.com/、2026-11-09T09:19:23.249215+00:00、HTTP 502、資料bytes未取得。別の公式配布先またはオーナー提供の原本を取得し、hash/適用型番/ページを検証する。変更のない再試行はしない。
- E1 CI artifact `native-infrastructure-evidence`（run 42594178172）のダウンロードは通常/許可された昇格とも Forbidden。CIログのPASSは確認したが、fixtureのfresh-native geometry未取得を解消しない。

## 2026-11-11 更新

- B1: 解除。main push run 43051871789 の deploy-gate で `CLOUDFLARE_DEPLOY_ENABLED` は空、Production deploy は SKIPPED。workflow は値が厳密に `true` のときだけ deploy する。変数 API 404 は保護規則の証拠として扱わない。
- B3: Cloud VM の native 実行は引き続き行わず、既存 Actions を使う。CI artifact は 2026-11-11 に取得可能だったが、A7 候補の facts/geometry を保存していない。保存範囲の修正は別 PR。
- B2: 維持（子 Issue は作らない）。B4–B12: 変更なし。

## 2026-11-11 W3 更新

`qualification/readiness.json` の `gates` が不足を 57 個のゲートに分け、解除手段で区分します（CLOUD_DIGITAL 5、OWNER_DECISION 16、ACCESS_EVIDENCE_HOLD 16、PHYSICAL_ONLY 20）。上の「49個」は区分前の数で、現在は 58 理由です。B6–B12 の内容は変わりません。B7–B9 の各手順は、実施に必要な準備物・手順・受入値を `qualification/procedures.md` に持つようになりましたが、実機での実施が必要な点は同じです。オーナーの作業は `/docs/project/order-checklist/` にまとめています。

同じ日に他の作業が明らかにした未解決事項（readiness では fixture と jack-continuity のゲートに含まれる）:

- 治具（#47）: 壁厚が検討用の最小 0.5 mm を下回る箇所がある（R7/R9 付近のプローブ穴で 6 か所、ポケット間で 15 か所）。最小値自体に出典はない。
- 治具: B 面のはんだフィレット高さに出典がない（貫通窓のため隙間は依存しない）。J5 のテール長は 2026-11-12 に出典化し、突出は基板厚に依存しない上限 2.8 mm で検査している。
- PJ-324M: SOFNG の supplier symbol は、推定対応（端子 4 = TIP）と矛盾する。symbol の読みだけでは欠陥と言えないため、ピン対応と銅箔は変えない（coordinator 判断）。**PCB を発注する前に**実物の PJ-324M で端子 4/5 のどちらが tip 接点でどちらが normal かを導通試験で確定する（jack-continuity 手順 5、オーナーチェックリスト O0）。
- 部品証跡（#48 の後も残るもの）: PMEG4010CEJ の `,115` 包装の型番はデータシートで確定しない。SM04B-SRSS-TB の回路番号は No.1 端以外が印刷されていない。PJ-324M の推奨穴寸法・軸高さ・ナット付属は出典なし。台帳の `exact-part-evidence`（外部の証跡待ち）。

## 2026-11-11 W6 更新

合否基準の作業（W6）で区分が変わりました。50 ゲート / 63 理由（CLOUD_DIGITAL 2、OWNER_DECISION 12、ACCESS_EVIDENCE_HOLD 16、PHYSICAL_ONLY 20）。提案値が残る基準ゲートには「PROPOSED または UNRESOLVED が残る」という理由が付きます。7 手順の基準をコーディネーターが採用したため、その基準ゲートは解除されました（`qualification/reviews/2026-11-11-coordinator-criteria-acceptance.md`、オーナー本人の採用ではない）。

- power-current、startup-reset、u7-stress: 受入値を部品資料・ネットリスト・FW 定数から導出し、生成時に再計算で照合するようにした。power-current と startup-reset はコーディネーターが採用。u7-stress は R7 電流の上限が推定に頼るため PROPOSED が残り、基準ゲートは閉じたまま。
- コーディネーターが採用: power-current、startup-reset、cv-thru-calibration、rail-collapse、load-short、cv-noise、jack-continuity（独立レビューが導出を確認したものだけ）。jack-continuity は、端子対応の閾値（200 kΩ / 20 MΩ）と接点品質（SOFNG 掲載図面の初期接触抵抗 50 mΩ、未監査の抜粋なので UNVERIFIED）に分けてから採用した。thermal-optical は 85 °C が最低の温度上限だと確認できない（14 種の部品に温度 fact がない）ため採用していない。
- オーナー判断の 9 手順: 出典付きの提案値（PROPOSED、21 件）を用意。採否前なのでゲートは解除しない。service-envelope の繰返し回数と thermal-optical の材料温度・見え方は提案できる出典がなく、UNRESOLVED のまま。
- 外部証跡待ちの 7 手順: 未決の値ごとに、何の資料または測定で決まるかを `supplied_by` に記録。
- CLOUD_DIGITAL に残る 2 ゲート（`artifact:fixture`、`assembly:fixture-materials`）は治具の作業（W5）が持つ。
