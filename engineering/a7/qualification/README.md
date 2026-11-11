# A7 物理評価の準備 — 未実施、発注不可

Workflow F (`circuit/WORKFLOW.md`) の小さなプロジェクト専用記録です。現在、実機、測定、製造承認、発注はありません。

- `plan.json`: 手書きの手順と未決の判定基準。受入値は既存の部品 fact と設計記録からの引用だけで、新しい仮定は追加していません（引用元が仮定としている値は ASSUMED と表示します）。
- `records.json`: 実施記録の追記先。現在は空です。試験結果を入力する前に根拠付き基準をレビューします。
- `run-template.json`: 未実施テンプレート。コピー先でunit/基板/実装/FW/設定、計器、条件、raw、結果と次の行動を埋めます。
- `readiness.json`, `procedures.md`, `run-templates/<手順ID>.json`, `doc/src/content/docs/project/order-checklist.mdx`: `python3 scripts/a7_readiness.py` の生成物。手編集しません。
- `plan.json` の各手順は inputs / tools / preconditions / steps / record / acceptance を持ちます。acceptance の値は `source`（部品 fact の `fact_id`、JSON の `pointer`、文書の `quote`）と一致しなければならず、確度は出典の記載を超えられません（部品 fact の provenance と verdict、JSON 記録で値の隣にある確度、引用行の ASSUMED / INFERRED）。出典は部品 fact（`fact_id` だけ）と設計記録（`engineering/a7/` の mechanical / study / electronics / verification と README、`engineering/a5/`）に限り、この計画や生成物は引用できません。`bound`（exact / min / min_exclusive / max / range / reference）は人が出典を読んで付けた比較の向きで、自動照合はしていません。ASSUMED / INFERRED は `confidence_trace` でその記載を示します。出典のない合否値は `UNRESOLVED` とし、`decided_by` に決める主体を書きます。
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

`owner_prototype_route` はscope/quantity/constraints、identities、approval(path/hash)を記録します。`manufacturing_release` はidentities、approval(path/hash)、reviewed_order_files(path/hash)を必要とします。NOT-A-RELEASE のレビュー用Gerberや省略された `.gbrjob` を注文用に転用しません。

PETと2HPは別案です。FR-4/3HPの不足をPETだけの質問で増やしません。元の #8/#10/#13/#17/#19 と A6 #7/PR #14 の保留は維持します。

各runの `raw_evidence` は `{kind, path, sha256}` の配列です。`plan.json` の `required_evidence_kinds` を全て揃え、各種別を別ファイルで記録します。たとえばLED試験は左右波形、ロット、書込みreadback、stored configuration、時間軸setupが別々に必要です。一つの無関係なファイルを複数種別に付け替えて通すことはできません。判定基準をREVIEWEDにする際は、残る `missing_criterion` を実際に解消し空にして、レビュー証跡を付けます。

治具と組立台帳は各producerの `validate_report` で再計算して照合します。ハッシュを更新しただけの偽の完成フラグや省略された人口表は受け付けません。
