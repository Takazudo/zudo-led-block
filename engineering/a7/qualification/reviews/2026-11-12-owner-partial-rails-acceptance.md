# A7 partial-rails 合否基準の採用記録（2026-11-12、オーナー本人）

**採用者: オーナー本人。**

- 日時: 2026-11-12T19:15:57Z（判断カードでの選択）
- オーナーの選択: 「Yes, maker's maximum is the line」（質問「Fail the partial-power test if any chip goes past its maker's maximum?」）。説明はスレッドのメッセージ cmsg_01LWjimMEMhCfvWjnLbPbEF3275UCBrNq6bpyEMHqSmtHr。
- 記録: `engineering/a7/procurement/owner-decisions.json` の partial-rails-criterion。
- 「accept all」（18:45Z）の後に出た判断なので、まとめての受け入れには含めず、別に尋ねた。
- これは基準の採用であり、測定・合格・製造承認・発注ではありません。手順は NOT_MEASURED のままです。

## 採用した手順と受入値のダイジェスト

partial-rails 4cd52a8a77ed13aa6357c0636263ce016e36608d85670c7eefa09f3e69f910ba

## 採用した内容

部分電源・無電源 CV の試験で、どのピンも部品の絶対最大定格（STM32 の注入電流 −5 mA/ピン・合計 25 mA、FT 入力 VDD + 4.0 V（ADC に使う PA0 は 4 V）、VDD −0.3〜4.0 V、OPA197 と TLV9001 の入力は電源の 0.5 V 外まで、OPA197 の入力電流 10 mA、SN74LVC2T45 6.5 V、WS2812B VDD + 0.7 V）を超えないことを合否とする。値はすべて部品資料の SOURCED の fact。絶対最大はストレス限界なので、超えなくても余裕は保証されない。初回通電の電流制限値は試験前のレビューで決める。逆電流（U3）は ldo-reverse で別に決めた。
