# A7 発注準備の判断記録

## 現行方針: 0.8 mm rigid FR-4 への設計変更（2026-11-17 JST）

親 [#15](https://github.com/Takazudo/zudo-led-block/issues/15) の新しい変更を [#87](https://github.com/Takazudo/zudo-led-block/issues/87) で追跡します。透明PCBをrigid FR-4の代替と考えていましたが、実際は薄いflex PCBだったため、透明PET/FPC案は撤回しました。普通のrigid FR-4基材のくすんだ半透明性を試します。透過率、拡散、実物の見え方は未測定です。

- LED leafとcontrollerは公称 **0.8 mm**。完成板厚の評価範囲は **0.7–0.9 mm**。両面maskは必要箇所以外を開口し、内層も含め広いGND面を撤去します。必要な配線、pad、via、局所銅とmaskの位置・理由を記録し、全銅層と表裏maskのGerberを確認します。
- **2HP（9.8 mm）を優先**して公差・配線・組立条件を評価し、成立根拠を確保できなければ **3HP（14.9 mm）**へ進みます。3HPでも0.8 mm、最小mask、広いGND面なしを維持します。旧「最も厚い成立板」の規則は適用しません。
- 8 RGB LED、左右各4個の独立2stream、共通電流制限VLED、passive CV IN→THRU、MCUのpin/伝達関数/既存mode、前面128.5 mm・cast PMMA 2 mm・奥行30 mm目標、工場実装と完成ケーブルを維持します。
- 新leafの正本はA5外に設けます。旧leaf 0.6 mm、新leaf 0.8 mm、旧controller 1.6 mmを混同しません。leaf積層は0.8×2＋bond 0.1＝**1.70 mm nominal**で、公差・支持・治具・機構・製造入力・プレビューを再検証します。
- この指示は設計方針の承認です。旧PCBのnative PASS、治具PASS、試作ルート承認、`order/2026-11-13/`は旧identityに限る履歴で、新設計に付け替えません。新設計の統合検証と製造releaseは未完了です。

PET供給元への質問は履歴として保管し、現行FR-4案の前提条件・次作業から外します。実機の透過性・熱・電気動作・組立・治具接触・収まりは別の物理作業です。A5は不変、A6 #7 / draft PR #14は保留。発注、supplier連絡、書込み・通電、別deploy、hosting/security設定変更は行いません。

D87: 上記オーナー方針がD1の1.6 mm/3HP固定と、2HP/PETを将来の再承認待ちとする方針を更新します。旧子Issue作成holdは今回には適用せず、#87を確立済みです。以下は旧設計での判断履歴です。

## 旧設計の判断記録


2026-11-09。証跡不足は別の [blocker-register.md](blocker-register.md) で扱います。作業状態は [checkpoint](order-preparation-checkpoint.md) を参照してください。

| ID | 判断 / 状態 | 根拠・影響 |
|---|---|---|
| D1 | 3HP、1.6 mm controller、FR-4 leaf を維持（既存の作業候補） | 前面14.9×128.5 mm、透明2 mm PMMA、30 mm奥行き目標を維持。2HPを自動的に再開しない |
| D2 | 実PCBを唯一の銅箔権威とする | canonical exportと機構コピーは派生物。E1はこの結合を検証し、generatorが権威基板を上書きしない |
| D3 | E3を完成治具と呼ばない | carrier-only CADと候補probe/receptacleの資料は有用な準備成果。公差・支持・travel stop未解決のためfixture completion=falseを維持 |
| D4 | VALID/BLOCKEDレポートと発注適格性を分離 | E5の生成・schema検証はBLOCKEDでも成功し、発注/release gateは不足証跡で失敗する。合格の実測を作らない |
| D5 | E1 mergeを保留 | PR CIでproductionがSKIPPEDでもmain merge時の設定は証明されない。リポジトリ変数404を迂回せず、非デプロイ条件の確認を待つ |
| D6 | 子Issue作成を保留 | 中断した最初のIssueは親が未作成と確認。原因不明の拒否/中断操作を繰り返さず、許可された独立ローカル作業を進める |

2026-11-13: D3 の「完成治具と呼ばない」は維持（物理の基準 5 が未実施）。ただし carrier-only の段階は過ぎ、4 枚プレートの設計がデジタル基準 1–4 と native の新規検証を満たし、金物はオーナーが承認済み、加工業者は未選定。現在の試作ルート承認は `qualification/approvals/2026-11-13-owner-prototype-route-sourcing-manifest.md`（基板 `89310d53…e727`、調達台帳 `557d5e48…502c`）で、#80 の台帳変更の後にオーナーが再承認した。HX 版の承認（`2026-11-13-owner-prototype-route-hx-switch.md`）は履歴として残す（[continue-here.md](continue-here.md) の冒頭）。

2026-11-11: D5 は解除。owner が通常の merge 完了を依頼し、main push の deploy-gate で deploy 変数が空・Production deploy SKIPPED を確認した（[checkpoint](order-preparation-checkpoint.md) の 2026-11-11 節）。

## オーナーの判断が必要なもの

- **限定された評価用サンプル/統合試作ルート:** 2026-11-12 にオーナーが承認（`qualification/approvals/2026-11-12-owner-prototype-route.md`、`records.json` の owner_prototype_route）。以下は承認前の記述として残します。実物がないまま #10 の物理ゲートを満たせません。対象版・数量・入手部材・許可工程・実施者・未解決事項・試験前条件を明示した限定承認が必要です。既存リリース条件の例外が必要ならオーナーが明示してレビューします。推奨は、まず必要なサンプルと評価範囲を限定して決め、通常の製造リリースと発注承認を分けることです。量産承認を省略する判断ではありません。
- **基準が未決の物理試験:** `qualification/plan.json` の `missing_criterion` に挙げる出典または採否判断が必要です。エージェントは数値を創作しません。
- **2HP/PET:** 将来選択するなら別途判断と必要な設計/評価を行います。現在のFR-4準備を止めるための前提にはしません。

#11 hosting、#12 agentページ公開の判断、A6 #7/PR #14 のholdは、この作業で変更しません。

2026-11-11 W3: 「基準が未決の物理試験」は、手順ごとに `criterion_class` で、クラウドで作れる条件表（power-current、startup-reset、u7-stress）、オーナーの判断（cv-thru-calibration の許容誤差を含む）、外部の証跡待ち（partial-rails の STM32 注入電流、fixture-contact のプローブ仕様など）に分けました。オーナーが決める項目は `/docs/project/order-checklist/` の O1–O10 です。エージェントは数値を創作せず、出典のない合否値は UNRESOLVED のままです。

2026-11-11 W6: クラウドで作れる 3 手順（power-current、startup-reset、u7-stress）の受入値を、部品 fact・A7 ネットリスト・FW 定数からの計算として記録しました。計算は生成時に再実行して照合します。TPS2552 の電流制限 343.3–439.4 mA は A5 の履歴計算（`engineering/a5/electronics/reports/electrical_margins.json`）と一致します。u7-stress の R7 電流上限 0.313 mA は「CV_BUF が U6 の電源 ±20 V を超えない」という推定を含むので PROPOSED のままです。オーナーから判断を委ねられたコーディネーターが、独立レビューで導出が確認された 7 手順（power-current、startup-reset、cv-thru-calibration、rail-collapse、load-short、cv-noise、jack-continuity）の基準を採用しました。オーナー本人の採用とは区別して記録しています（`criterion_accepted_by`）。オーナー判断の 9 手順には PROPOSED の提案値を付けました。提案はゲートを解除しません。チェックリストはオーナーの作業を 1 つの順序付きリストにしました。
