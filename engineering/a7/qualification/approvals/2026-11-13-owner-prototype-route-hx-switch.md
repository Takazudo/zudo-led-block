# オーナーの試作ルート再承認（2026-11-13、SW1 を HX MSK13C02 にした版）

**承認者: オーナー（Takazudo）本人。** スレッドの判断カードへのオーナー自身のタップを記録します。これは試験目的の少数試作のルートの承認で、製造リリース・発注・供給元への連絡の承認ではありません。

## 経緯

- 2026-11-12T16:53:38Z、オーナーは「1 OK」（cmsg_01LWjimMEMhCfvWjnLbPbEF342cs4i3sQN6KykuG63UNbw）で A7 r2 の限定試作を承認しました（`2026-11-12-owner-prototype-route.md`）。その承認は当時の基板・回路図・機構・台帳などの SHA-256 に結び付いていました。
- 2026-11-12 に SW1 を C&K PCM13SMTR（C221842）から hanxia HX MSK13C02（C5149819）に変えました（PR #78、#77）。変わったのは SW1 の部品欄とその記録で、銅パターンと配置は同じですが、ハッシュが変わったので前の承認はこの版に効かなくなりました。

## 質問（判断カード、2026-11-12、cmsg_01LWjimMEMhCfvWjnLbPbEF3Lk5T81pRxYpsU65QPfEcEV）

> Approve the test prototype again for the new-switch version?

選択肢: 「Yes, approve this version」（推奨。前の 1 OK をスイッチ変更後の基板について記録し直す。発注・製造リリースではない）/「Not yet」。

## オーナーの回答（2026-11-13T02:38:51Z）

> Chose "Yes, approve this version" on the decision card asking "Approve the test prototype again for the new-switch version?"

これはカードへのオーナーのタップを、プラットフォームが記録した文面です（オーナーが入力した文ではありません）。

## この記録が承認として扱う範囲

- 対象版: A7 r2（3HP / FR-4）、SW1 = HX MSK13C02。`records.json` の owner_prototype_route の identities（2026-11-13 時点の readiness.json の値）に結び付けます。どれかが変わるとこの承認はその版には効かず、readiness は再び止まります。
- 数量・目的・制約は前の承認と同じです（2 台分、物理手順の実施のための試作。製造リリース・発注・供給元への連絡ではない）。
- SW1 のランド上の端子番号の向きは部品 CAD だけが根拠で、組立後の最初の確認項目です（switch-fit）。この承認はその確認の代わりになりません。
