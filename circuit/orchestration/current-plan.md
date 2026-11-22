# zudo-led-block 現行オーケストレーション

## #87: 0.8 mm rigid FR-4 optical redesign

2026-11-17 JSTのowner指示を、親 [#15](https://github.com/Takazudo/zudo-led-block/issues/15) と子 [#87](https://github.com/Takazudo/zudo-led-block/issues/87) で追跡します。透明PET/FPCは撤回し、LED leaf/controllerを0.8 mm rigid FR-4、両面必要箇所以外mask開口、全層の広いGND面なしへ変更します。2HPを優先評価し、根拠不足なら3HPへ進みます。3HPでも0.8 mmを維持します。

今回の設計変更・Issue/PR運用・条件を満たしたmain統合は依頼済みです。旧「新規欠陥がなければ再設計しない」「2HP保留」「3HPの最も厚い成立板」「PET任意検討」は今回には適用しません。A5はimmutable、A6 #7 / draft PR #14は保留を維持します。

| 担当範囲 | 完了に必要な証跡 |
| --- | --- |
| 単一統合担当 | live Issue/PR/branch/sessionと資源監査、単一作業branch/統合PR、最終revisionの整合、current-head CIとreview後のmerge |
| 電気設計 | A5外の新leaf正本、controllerの実stackup/GND return/mask、電源アダプタの要否判断、全銅層・表裏mask Gerber、native ERC/parity/DRC/未接続/refill/再生成保護とrouting再現 |
| 機構・治具 | 0.8±0.1 mmとbond公差、2HP/3HP判断、支持・端子・工具・ハーネス・奥行、CAD実生成、新板厚での治具計算 |
| 製造入力・表示 | BOM/CPL/JLC/panel/readinessの新正本参照、全層銅遮光と未測定のFR-4半透明表現を分けるpreview、生成所有ページのgenerator更新 |
| 独立レビュー | 電気と機構の別レビュー、上記成果物の同一revision/hash、negative controls維持、未実測事項の明示 |

[継続手順](../../engineering/a7/docs/continuation/continue-here.md)、[根拠索引](../../engineering/a7/docs/continuation/evidence-index.md)、[WORKFLOW.md](../WORKFLOW.md)、[ORCHESTRATION.md](../ORCHESTRATION.md) を使用します。現在のpin/profile/CIを読み直し、実測したCloud資源と有限予算でnative/CADを実行します。共有Actions枠の重複実行を避け、存在しないworkerや別環境GUIを仮定しません。旧PASSや注文承認を新PCBへ移し替えません。物理評価・発注・supplier連絡・実機書込み/通電・別deploy・hosting/security設定変更は今回行いません。

## 履歴: 2026-11-12の初期対応表（#87以前）

以下は以前の方針・導入時環境の記録です。「現在」「未起動」「完了」は当時を指し、今回の候補や実行結果ではありません。


方針日: 2026-11-12。確認した main: `af523f9abb74e206c27aaaa076b3b68a5c474940`。これは初期の作業・環境・モデル対応表であり、実行記録ではありません。セッション、資源予約、計算は起動していません。[WORKFLOW.md](../WORKFLOW.md)、[ORCHESTRATION.md](../ORCHESTRATION.md)、[AGENTS.md](../../AGENTS.md) と現在の owner decision を優先してください。

## 最初に確認する正本と、変更しない境界

[A7 の継続手順](../../engineering/a7/docs/continuation/continue-here.md)、[根拠資料索引](../../engineering/a7/docs/continuation/evidence-index.md)、[A7 の概要](../../engineering/a7/README.md)、[現在の次作業](../../doc/src/content/docs/project/next-actions.mdx) と epic [#15](https://github.com/Takazudo/zudo-led-block/issues/15) の最新コメントを読んでください。古い README の A5 状態を A7 の現状に置き換えて解釈しないでください。

- `engineering/a5/` は immutable な輸入チェックポイントです。A7 の都合で編集・再生成・整形・修復しません。seed manifest、30 identities / 71 placements / 81 pieces の照合条件を維持します。A5 の生成ページと publication assets は既存 generator が所有します。
- A6 は PR #14 / issue #7 の held work です。今回の方針で再開・採用・クローズしません。固有の資料と依存を確認してから個別に扱います。
- A7 の継続記録では、controller revision 2 の配線、native gate、独立した再レビュー、配置を参照するデジタル機構検証が完了しています。新しい理由がなければ配線を最初からやり直しません。デジタル完了は実機・製造承認ではありません。
- 3HP が現在の working candidate、2HP は保留です。FR-4 leaf が既定・fallback であり、透明 PET FPC の条件付き検討を採用済みとしません。PET の未解決事項を FR-4 全体の停止理由に広げません。
- native engineering は記録された KiCad 10.0.8 の gate を確認します。framework の 9.0.9 preview renderer と同一視せず、OSC の 10.0.6 も移植しません。実行時は現在の pin と wrapper を読み直します。
- 日本語優先のサイトを維持します。`CLOUDFLARE_DEPLOY_ENABLED`、資格情報、hosting 設定は変更しません。製造ファイル、発注、業者への送信、実機書込み・通電は既存の個別承認境界を維持します。

## 提案する作業単位（すべて未起動）

| Key / 成果物 | 環境・モデル | 依存関係・完了条件 |
| --- | --- | --- |
| B-0: 現在の issue/PR、資料、owner decision、既存セッションと共有資源の確認 | Cloud manager、小型の読み取り担当 | 最初に実施。#15 と既存 R1–R5 を再利用し、完了済みの限定作業を重複しない |
| B-1: 未取得部品資料・physical gate・owner question の整理 | Cloud。固定照合は小型モデル、難しい設計判断は Fable/Astra | #9、A7 open-questions と関連 owner bundle。メーカー一次資料・ミラー・推測を混同せず、業者への送信や部品選定を暗黙実行しない |
| B-2: 承認された新しいソフトウェア／検証ツールの欠陥修正 | 独立した cloud child、Sonnet 等の適切なモデル | `scripts/` と許可された A7 範囲。A5 は不変。既存の gate/negative controls を弱めない。新規欠陥がなければ作業を作らない |
| B-3: 必要な差分だけの native／routing再現／CAD 検証 | 既存 Actions または計測済み cloud VM。小型調整担当とプログラム | 現在の `scripts/native_gate/`、`scripts/a7_route_check.py` と CI を再利用。入力・版・候補・完全な結果を固定し、重い処理を無制限に並列化しない |
| B-4: 独立レビュー、単一統合担当、継続資料更新 | Cloud reviewer/integrator。機構／電気的な新判断は Fable/Astra | 変更した board と R2 機構の適用性を再確認。既存 generator で更新し、日本語の公開状態と証拠索引を整合させる |
| B-HOLD: 部品・試作機・測定・owner decision が必要な残作業 | 承認された local / physical 環境のみ | #8/#10/#13、jack の pin/slot/axis、switch、寸法・光学・熱・firmware実機検証等。cloud の結果で代用しない |

継続記録の「planned digital work is done」を尊重し、実行可能な独立作業がなければ正確な blocker と必要な入力を報告してください。モデルや VM が余っていることは再設計・再配線の理由になりません。

## 実行前に記録する内容

`campaigns/<campaign-id>/` に manager/dispatcher、task/issue/branch/session 対応、使用モデル、正確な入力と工具、所有パス、共有アカウント枠と CI reserve、VM 実測、有限の時間・メモリ・再試行予算、許可された artifact 保存先、次の安全な再開操作を残します。現時点ではすべて未割当です。OSC/PD/lamp と同じ Actions アカウントの全枠を各自で占有しないでください。

既存チェック: `pnpm circuit:check`、`pnpm a5:check`、seed/catalog verifier、関連する A7 source/host tests、native gate、`pnpm check`、build/site/browser 等から変更に適用するものを選びます。firmware release generator は A5 内で実行せず、書込みがある再現は disposable copy を使います。`.github/workflows/ci.yml` の既存責務を確認し、OSC 用の workflow を存在すると仮定しません。

今回の既知 DNS 障害と同じ署名に限り、ORCHESTRATION の方針で調査・再試行・badge 待ちを後回しにして独立作業を続けます。この repo の障害を確認したという意味でも、native／physical gate を免除する意味でもありません。

## 今回の文書導入の検証境界

運用 Markdown と agent 入口のみを変更します。A5/A7、manifest、CAD、firmware、生成ページ、CI、工具 pin は変更しません。既存 AGENTS/CLAUDE の同一 blob を確認して本文を保持し、追記・リンク・差分を確認しました。導入用環境には pnpm がなく Node は22、直接 GitHub への DNS が利用できないため、完全な package/native/build 検証は NOT RUN です。文書確認を工学的 PASS として扱いません。
