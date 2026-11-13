# A7 物理評価の準備 — 未実施、発注不可

Workflow F (`circuit/WORKFLOW.md`) の小さなプロジェクト専用記録です。現在、実機、測定、製造承認、発注はありません。

- `plan.json`: 手書きの手順と未決の判定基準。受入値は既存の部品 fact と設計記録からの引用だけで、新しい仮定は追加していません（引用元が仮定としている値は ASSUMED と表示します）。
- `records.json`: 実施記録の追記先。`runs` はまだ空です。`owner_prototype_route` にはオーナーの試作ルート承認（2026-11-12、HX 版は 2026-11-13 に再承認、#80 で `assembly-manifest.json` が変わった版も同日に再承認、`approvals/`）を識別付きで記録しています。識別のどれかが変わると readiness はこの承認を現在の版に効かないものとして止めます。試験結果を入力する前に根拠付き基準をレビューします。
- `run-template.json`: 未実施テンプレート。コピー先でunit/基板/実装/FW/設定、計器、条件、raw、結果と次の行動を埋めます。
- `readiness.json`, `procedures.md`, `run-templates/<手順ID>.json`, `doc/src/content/docs/project/order-checklist.mdx`: `python3 scripts/a7_readiness.py` の生成物。手編集しません。
- `plan.json` の各手順は inputs / tools / preconditions / steps / record / acceptance を持ちます。acceptance の値は `source`（部品 fact の `fact_id`、JSON の `pointer`、文書の `quote`）と一致しなければならず、確度は出典の記載を超えられません（部品 fact の provenance と verdict、JSON 記録で値の隣にある確度、引用行の ASSUMED / INFERRED）。出典は部品 fact（`fact_id` だけ）と設計記録（`engineering/a7/` の mechanical / study / electronics / verification と README、`engineering/a5/`）に限り、この計画や生成物は引用できません。`bound`（exact / min / min_exclusive / max / range / reference）は人が出典を読んで付けた比較の向きで、自動照合はしていません。ASSUMED / INFERRED は `confidence_trace` でその記載を示します。出典のない合否値は `UNRESOLVED` とし、`decided_by` に決める主体を書きます。外部の証跡待ちの手順では、さらに `supplied_by`（資料 / 測定 / 両方と、その中身）で何がその値を与えるかを書きます。
- 計算値は `derivation`（式、入力、丸め桁）を持ちます。各入力は出典の語（`token`、例 `68k`）と数値を持ち、生成時に出典の中にその語があること、語と数値が一致すること、式の再計算が値と一致することを検査します。式に使えるのは入力名、四則と累乗、min/max、単位換算の 1/2/10/100/1000 だけです。入力がすべて SOURCED か DESIGN なら確度は CALCULATED、推定を含む式（`assumption`）は INFERRED、弱い入力があればその確度になります。回路の定数はネットリストの部品値（`netlist_value`）から読みます。
- `PROPOSED` はレビュー用の提案値です。`rationale` と、出典が与える確度 `basis_confidence` を持ち、値と確度は他の項目と同じく照合します。提案値が残る手順は、`criterion_status` が REVIEWED でも基準ゲートが解除されません。採るときは確度を `basis_confidence` に戻し、レビュー記録を付けます。
- REVIEWED の手順は `criterion_accepted_by`（OWNER = オーナー本人、PROJECT_COORDINATOR_DELEGATED = オーナーが委ねた作業方針によるコーディネーター）と `criterion_acceptance_sha256`（受入値のダイジェスト）を持ちます。レビュー記録（`reviews/`）にも同じ `<手順ID> <ダイジェスト>` が書かれている必要があり、受入値を変えると基準ゲートは再び閉じます。
- 生成物のフラグを前提にする手順は、文中の `<フラグ>=true` と同じものを `precondition_states` に書きます。フラグは `state_flags` に登録し、`closed_by` にそのフラグを満たせる手順を書きます。自分（または自分を待つ手順）しか満たせないフラグを前提にすると生成時にエラーになります。治具の `digital_fixture_complete` は実機の基準 5 を含むので fixture-contact しか満たせず、fixture-contact は進捗表示の `digital_criteria_1_to_4_met` を前提にします。readiness はこのフラグを参考として表示するだけで、発注ゲートは `digital_fixture_complete` を読みます。
- `owner_decisions` は、オーナーの判断ゲートごとの質問・選択肢・各選択の結果・出典付きの推奨で、PCB 発注を先に止めるものから順に並べます（`stage`: PCB_ORDER → BENCH → RELEASE）。推奨は提案で、ゲートを解除しません。`evidence_requests` は資料・回答待ちのゲートごとに、入手の方法（オーナーのブラウザ保存 / クラウド取得 / 供給元の回答 / 日付付きの供給観測 / 実測）と URL を書きます。どちらも生成時に形と出典を検査し、現在のゲートに準備がないものは発注チェックリストに「準備がない」と表示します。
- `criterion_class` と `owner_actions` は、readiness の各ゲートを CLOUD_DIGITAL / OWNER_DECISION / ACCESS_EVIDENCE_HOLD / PHYSICAL_ONLY に分け、オーナーの作業と結び付けます。
- `supplier-questions.md`: 未送信の質問。送信や発注の承認ではありません。

`python3 scripts/a7_readiness.py --check` は、正しく BLOCKED を報告する生成物でも成功します。
`python3 scripts/a7_readiness.py --gate` は、必要な証跡、現在版への結合、資料/実施レビュー、供給観測、オーナー承認が不足する間は失敗します。
検証成功は証跡の真正性を保証しません。記録された承認を実際の権限者が確認する必要があります。このコマンドは発注を行いません。

実施時には `readiness.json` の identities の全 SHA-256 を run に記録します。設定はビルド時の `lb_config.h` と実測時の stored/calibration configuration の両方が必要です。後者は `conditions` と raw readback に保存します。実装差分/reworkも記録し、別runを追加します。実施日時が最新のrunがFAIL/INCONCLUSIVEなら過去のPASSで隠せません（配列の並べ替えでは変わりません）。同一手順で同じ実施日時が複数ある場合は曖昧として止めます。前の失敗とrawデータを削除しないでください。

供給記録は material 種別ごとに、`observed_on`、`valid_until`（供給元の有効期間またはレビューされた再確認期限）、`available_for_proposed_order`、全identities、`source` のpath/hashを必要とします。古い価格の再出力は更新ではありません。在庫は予約されていません。

## 試作品がない依存関係

#10 は配線・適合・物理評価後に製造ファイルをレビューする条件を維持しています。一方、その評価に実物が必要です。現在のループを、このツールで解消したことにはしません。

オーナーが明示する必要があるのは、**評価用サンプル/統合試作を入手する限定ルート**です。対象版と数量、入手する部品/基板/治具、許す工程、未解決事項、実施者、試験前安全条件、製造リリースとは異なる承認範囲を記録してください。既存 #10 の条件に例外が必要なら、オーナーが明示してレビューする必要があり、現在のコードは例外を推定しません。承認後も通常の製造リリース・発注には別の明示承認が必要です。

2026-11-12 にオーナーがこのルートを承認し、SW1 を HX MSK13C02 にした版を 2026-11-13 に再承認しました（`approvals/2026-11-13-owner-prototype-route-hx-switch.md`、PR #79）。#80 で調達台帳が変わった版（`557d5e48…`）も同日に再承認しています（`approvals/2026-11-13-owner-prototype-route-sourcing-manifest.md`）。試作のための日付付き注文ファイルは `../jlc-package/order/2026-11-13/` にあります（CI のレビュー補助 Gerber とは別に、`a7_panel.py build` で作り照合したもの）。どちらも発注・製造リリースではありません。

`owner_prototype_route` はscope/quantity/constraints、identities、approval(path/hash)を記録します。`manufacturing_release` はidentities、approval(path/hash)、reviewed_order_files(path/hash)を必要とします。NOT-A-RELEASE のレビュー用Gerberや省略された `.gbrjob` を注文用に転用しません。

PETと2HPは別案です。FR-4/3HPの不足をPETだけの質問で増やしません。元の #8/#10/#13 と A6 #7/PR #14 の保留は維持します（#17/#19 はデジタルの範囲を終えて閉じた）。

各runの `raw_evidence` は `{kind, path, sha256}` の配列です。`plan.json` の `required_evidence_kinds` を全て揃え、各種別を別ファイルで記録します。たとえばLED試験は左右波形、ロット、書込みreadback、stored configuration、時間軸setupが別々に必要です。一つの無関係なファイルを複数種別に付け替えて通すことはできません。判定基準をREVIEWEDにする際は、残る `missing_criterion` を実際に解消し空にして、レビュー証跡を付けます。

治具と組立台帳は各producerの `validate_report` で再計算して照合します。ハッシュを更新しただけの偽の完成フラグや省略された人口表は受け付けません。
