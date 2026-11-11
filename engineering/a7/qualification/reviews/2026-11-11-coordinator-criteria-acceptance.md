# A7 合否基準の採用記録（2026-11-11）

**採用者: プロジェクトのコーディネーター（オーナーが委ねた作業方針による）。オーナー本人の採用ではありません。**

- 日時: 2026-11-11T19:39Z（コーディネーターの判断の受領）
- 出典: プロジェクトスレッド https://claude.ai/code/project/chan_01LWjimMEMhCfvWjnLbPbEF3 でのコーディネーターの判断（W6 の合否基準）
- 条件: 独立レビューが導出を確認した基準だけを採用する（コーディネーターの指示）。
- 独立レビュー: このセッションで別に起動したレビューエージェントによる 2 回のレビュー（コミット 5869e0e と 0a764e4）。値の再計算、ネットリスト・FW・部品 fact との照合、抵抗コーナーの総当たりを含む。指摘の修正は 0a764e4 以降のコミットにある。
- これは基準の採用であり、測定・合格・製造承認・発注ではありません。すべての手順は NOT_MEASURED のままです。

## 採用した手順と受入値のダイジェスト

各行は `<手順ID> <acceptance の SHA-256>` です。readiness は、計画の受入値がこのダイジェストと一致するときだけ基準ゲートを解除します。値・単位・範囲・出典を変えると、新しい採用記録が必要になります。

power-current 5e29c26369e4904a769355f696e0a23c70be95a7bcd5b3f41aa14eb99fb43ac6
startup-reset 1b4ab27ce26ac587713cd432b5df862f3a6bc49704453de2ce0739544dfd805f
cv-thru-calibration e8597916ae9c3c860295c1aa8f6ae82f1181e8ec155419830721f41e0e48797e
rail-collapse 79f8442e4bbfd8059e2802b4d86f77fb28aa0f4bbe1d37158f4b38b8930eced0
load-short 197cb2fb3ec8c9d635656c65e478cb8db344923227488dcf50cae4e71b67ccc8
cv-noise ed52279e0344626b20103633bbb0da95af82cc01c16a90a757a216277cd0063b

## 採用しなかったもの

- u7-stress: 電源範囲と絶対最大の行は採用したが、R7 電流の上限 0.313 mA は CV_BUF の上限を推定に頼るため PROPOSED のまま。手順全体の基準ゲートは解除しない。
- jack-continuity: 独立レビューが確認しなかった（CV_THRU は下流のモジュールも駆動し、200 kΩ は接点品質の上限にならない）。PROPOSED のまま。
- thermal-optical: 85 °C が基板で最も低い温度上限であることを確認できない（14 種の部品に温度上限の fact がない。WS2812B を含む）。PROPOSED のまま。
- firmware-waveforms、harness-depth、service-envelope: コーディネーターの判断でオーナーに残す。

## レビューの注記

- cv-noise（50 mV）と cv-thru-calibration の残差（50 mV）はそれぞれ確認済み。ただし両方が上限近くなら合計は不感帯を超えうる。誤差予算の合算はオーナーの確認事項として残す。
