# A7 発注準備の判断記録

2026-11-09。証跡不足は別の [blocker-register.md](blocker-register.md) で扱います。作業状態は [checkpoint](order-preparation-checkpoint.md) を参照してください。

| ID | 判断 / 状態 | 根拠・影響 |
|---|---|---|
| D1 | 3HP、1.6 mm controller、FR-4 leaf を維持（既存の作業候補） | 前面14.9×128.5 mm、透明2 mm PMMA、30 mm奥行き目標を維持。2HPを自動的に再開しない |
| D2 | 実PCBを唯一の銅箔権威とする | canonical exportと機構コピーは派生物。E1はこの結合を検証し、generatorが権威基板を上書きしない |
| D3 | E3を完成治具と呼ばない | carrier-only CADと候補probe/receptacleの資料は有用な準備成果。公差・支持・travel stop未解決のためfixture completion=falseを維持 |
| D4 | VALID/BLOCKEDレポートと発注適格性を分離 | E5の生成・schema検証はBLOCKEDでも成功し、発注/release gateは不足証跡で失敗する。合格の実測を作らない |
| D5 | E1 mergeを保留 | PR CIでproductionがSKIPPEDでもmain merge時の設定は証明されない。リポジトリ変数404を迂回せず、非デプロイ条件の確認を待つ |
| D6 | 子Issue作成を保留 | 中断した最初のIssueは親が未作成と確認。原因不明の拒否/中断操作を繰り返さず、許可された独立ローカル作業を進める |

2026-11-11: D5 は解除。owner が通常の merge 完了を依頼し、main push の deploy-gate で deploy 変数が空・Production deploy SKIPPED を確認した（[checkpoint](order-preparation-checkpoint.md) の 2026-11-11 節）。

## オーナーの判断が必要なもの

- **限定された評価用サンプル/統合試作ルート:** 2026-11-12 にオーナーが承認（`qualification/approvals/2026-11-12-owner-prototype-route.md`、`records.json` の owner_prototype_route）。以下は承認前の記述として残します。実物がないまま #10 の物理ゲートを満たせません。対象版・数量・入手部材・許可工程・実施者・未解決事項・試験前条件を明示した限定承認が必要です。既存リリース条件の例外が必要ならオーナーが明示してレビューします。推奨は、まず必要なサンプルと評価範囲を限定して決め、通常の製造リリースと発注承認を分けることです。量産承認を省略する判断ではありません。
- **基準が未決の物理試験:** `qualification/plan.json` の `missing_criterion` に挙げる出典または採否判断が必要です。エージェントは数値を創作しません。
- **2HP/PET:** 将来選択するなら別途判断と必要な設計/評価を行います。現在のFR-4準備を止めるための前提にはしません。

#11 hosting、#12 agentページ公開の判断、A6 #7/PR #14 のholdは、この作業で変更しません。

2026-11-11 W3: 「基準が未決の物理試験」は、手順ごとに `criterion_class` で、クラウドで作れる条件表（power-current、startup-reset、u7-stress）、オーナーの判断（cv-thru-calibration の許容誤差を含む）、外部の証跡待ち（partial-rails の STM32 注入電流、fixture-contact のプローブ仕様など）に分けました。オーナーが決める項目は `/docs/project/order-checklist/` の O1–O10 です。エージェントは数値を創作せず、出典のない合否値は UNRESOLVED のままです。

2026-11-11 W6: クラウドで作れる 3 手順（power-current、startup-reset、u7-stress）の受入値を、部品 fact・A7 ネットリスト・FW 定数からの計算として記録しました。計算は生成時に再実行して照合します。TPS2552 の電流制限 343.3–439.4 mA は A5 の履歴計算（`engineering/a5/electronics/reports/electrical_margins.json`）と一致します。u7-stress の R7 電流上限 0.313 mA は「CV_BUF が U6 の電源 ±20 V を超えない」という推定を含むので PROPOSED のままです。オーナーから判断を委ねられたコーディネーターが、独立レビューで導出が確認された 7 手順（power-current、startup-reset、cv-thru-calibration、rail-collapse、load-short、cv-noise、jack-continuity）の基準を採用しました。オーナー本人の採用とは区別して記録しています（`criterion_accepted_by`）。オーナー判断の 9 手順には PROPOSED の提案値を付けました。提案はゲートを解除しません。チェックリストはオーナーの作業を 1 つの順序付きリストにしました。
