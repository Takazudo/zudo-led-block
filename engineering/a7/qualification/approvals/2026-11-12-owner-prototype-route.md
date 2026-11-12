# オーナーの試作ルート承認（2026-11-12）

**承認者: オーナー（Takazudo）本人。** プロジェクトチャットでのオーナー自身の発言を、原文のまま記録します。これは試験目的の少数試作のルートの承認で、製造リリース・発注・供給元への連絡の承認ではありません。

## 質問（コーディネーター、2026-11-12T12:19:44Z、cmsg_01LWjimMEMhCfvWjnLbPbEF3W978it4DL1uHXAM8UDnine）

> 1. **Answer the decisions** on the order checklist (`/docs/project/order-checklist/`), starting with the prototype route, the panel route (I recommend our own panels) and the mode switch purchase. A reply here like "1 yes, 3 own panels" is enough.

発注チェックリストの最初の判断は `owner_prototype_route`（`engineering/a7/qualification/plan.json` の owner_decisions の先頭）: 「A7 r2（3HP / FR-4）の限定試作を承認しますか。」 推奨は `approve`（試験目的の少数試作を承認する）。

## オーナーの回答（2026-11-12T16:53:38Z、cmsg_01LWjimMEMhCfvWjnLbPbEF342cs4i3sQN6KykuG63UNbw）

> 1 OK

## この記録が承認として扱う範囲

- 読み方: 「1 OK」を、上の項目 1 の最初の判断 `owner_prototype_route` の `approve` への回答として記録します。この読み方はコーディネーターのもので、同じ回答が面付けの経路（`assembly:panel-route`）と切替スイッチの入手（`assembly:switch-supply`）も含むかは、オーナーに確認中です。それらはここでは承認として扱いません。
- 対象版: A7 r2（3HP / FR-4）。`records.json` の identities（基板・実装・回路図・FW・設定・機構・治具・台帳の SHA-256）に結び付けます。どれかが変わるとこの承認はその版には効かず、readiness は再び止まります。
- 数量: 2 台分（オーナーの判断 `order-quantity`、`engineering/a7/procurement/owner-decisions.json`）。コントローラー 2・LED リーフ 4・電源アダプタ 2 枚と、その部品・治具・ケーブル。
- 目的と範囲: `plan.json` の物理手順を実施するための試作品の入手。PJ-324M の端子 4/5 の確認（jack-continuity）は PCB 発注の前に行います。
- 実施者と試験前条件: この承認では指定していません。各手順の run に実施者を記録し、各手順の前提条件・安全条件（非通電の確認など）に従います。
- 制約: 製造リリースではありません（`manufacturing_release` は別の明示承認が必要で、未記録）。発注・購入・供給元への連絡は、この記録では行わず、オーナーが行います。実機の通電・書込み・試験は各手順の前提条件と安全条件に従います。readiness の他のゲート（判断・資料・実測）は解除しません。
