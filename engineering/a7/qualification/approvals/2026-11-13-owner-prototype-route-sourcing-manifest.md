# オーナーの試作ルート再承認（2026-11-13、#80 で調達台帳が変わった版）

**承認者: オーナー（Takazudo）本人。** プロジェクトチャットでのオーナー自身の返信を記録します。これは試験目的の少数試作のルートの承認で、製造リリース・発注・供給元への連絡の承認ではありません。

## 経緯

- 2026-11-12 の「1 OK」（`2026-11-12-owner-prototype-route.md`）と、2026-11-13T02:38:51Z の HX 版の再承認（`2026-11-13-owner-prototype-route-hx-switch.md`、PR #79）は、そのときの識別に結び付いていました。両方とも履歴としてそのまま残します。
- PR #81（#80）で、調達の観測を日付付きの根拠から投影し直したため、`engineering/a7/procurement/assembly-manifest.json` が `c12c964ac3ea0c012bb03fbd11f1fac22d0f769a5cacdf2daf1b289f1493e865` から `557d5e48045b60bb4a8f91dc55f9fae2988d4494082c42532679032da2c8502c` に変わりました。変わったのは調達欄（order_plan の行の欄、attrition、population の調達ポインタ、供給ブロッカーの文、inputs_sha256）だけで、部品・数量・基板・配置・面付けファイル・日付付きの注文ファイルは同じです。ハッシュが変わったので前の承認はこの版に効かなくなり、readiness は `owner_prototype_route` を再び出していました。

## 質問（プロジェクトチャット、2026-11-13T19:36:48Z、cmsg_01LWjimMEMhCfvWjnLbPbEF33nbxEvZN42AMVjrN8YUuPL）

> **Re-approve the prototype route.** The fix had to change the parts manifest that your prototype approval was tied to, so the approval no longer counts and the order gate is blocked again. No part, quantity, board or order file changed. Reply "yes" to approve the new version.

## オーナーの回答（2026-11-13T19:44:23Z、cmsg_01LWjimMEMhCfvWjnLbPbEF35HegRmywRMtKRc3TMNp83s、上の質問への返信）

> approve

## この記録が承認として扱う範囲

- 対象版: A7 r2（3HP / FR-4）、SW1 = HX MSK13C02、調達台帳 `557d5e48…502c`。`records.json` の owner_prototype_route の identities（この記録の時点の readiness.json の値）に結び付けます。どれかが変わるとこの承認はその版には効かず、readiness は再び止まります。
- 数量・目的・制約は前の承認と同じです（2 台分、物理手順の実施のための試作。製造リリース・発注・供給元への連絡ではない）。
- 日付付きの注文ファイルの注文フォーム確認（DRYRUN 名、power_adapter の材質、表面処理、位置と回転）と、SW1 の端子向きの組立後確認（switch-fit）は残ります。この承認はそれらの代わりになりません。
