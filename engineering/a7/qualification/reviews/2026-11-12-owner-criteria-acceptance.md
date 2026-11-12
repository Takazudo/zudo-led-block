# A7 合否基準の採用記録（2026-11-12、オーナー本人）

**採用者: オーナー本人。** プロジェクトのコーディネーターによる採用（2026-11-11 の記録）とは区別します。

- 日時: 2026-11-12T18:45:15Z（オーナーのメッセージ）
- オーナーの原文: 「5 accept all」（発注チェックリストに残っていた判断について、推奨をすべて受け入れる）
- 記録: `engineering/a7/procurement/owner-decisions.json` の accept-all-recommendations。オーナーが決めた値は `engineering/a7/qualification/owner-criteria.json` にあります。
- これは基準の採用であり、測定・合格・製造承認・発注ではありません。すべての手順は NOT_MEASURED のままです。

## 採用した手順と受入値のダイジェスト

各行は `<手順ID> <acceptance の SHA-256>` です。readiness は、計画の受入値がこのダイジェストと一致するときだけ基準ゲートを解除します。値・単位・範囲・出典を変えると、新しい採用記録が必要になります。

harness-depth 886e5fd6948d5d2c939b8ab37e668749db83307b2c78f972892713ef46071943
u7-stress bcfdaa1b30cbf474bb7b951d87563a0cbca39e9c002293ae9a3b060b24c3d30d
service-envelope cdde947562ab8dfe327d7067bd01de8e6aa4f4e5668b49af3fd163773e5b92e5
ldo-reverse 0df9272f616326f663ecaa1ccda4866a9e00d371c0b78d5614ea51734bc5ad7a

## 採用した内容

- harness-depth（推奨 adopt）: 電源ケーブル自由長の注文範囲 54–60 mm（57 ± 3 mm。±3 は仮定のまま ASSUMED）と最小曲げ半径 2.0 mm（3HP の経路モデルの設計値）。ケーブル業者がより狭い公差を保証すれば、新しい採用記録で置き換える。
- u7-stress（推奨 adopt）: R7 を流れる電流の上限 0.313 mA。CV_BUF が U6 の電源を超えないという推定を含む計算（INFERRED）のまま採る。
- service-envelope（推奨 100）: ジャック挿抜 100 回で割れ・ずれ・緩みがないこと、挿抜力 10.0 N（販売店掲載の写し、MIRROR）。ジャックの寿命試験ではない。
- ldo-reverse（推奨 prohibit）: +5 V を切った状態で +3V3 に外部から電圧をかけない（0 mA）。試験は電源投入・遮断の順序と、遮断時に VOUT ≤ VIN + 0.3 V が保たれるかの確認だけ。

## 基準ゲートを解除しないもの（方針だけ採用）

- thermal-optical（推奨 75）: 部品温度の上限を 75 °C（PJ-324M の保存温度の上限）に改めた。PETG/PMMA の温度限界と見え方の合否が未決なので、手順全体の基準ゲートは開いたまま。
- firmware-waveforms（推奨 maker-written）: Worldsemi の公式窓口の書面確認が届くまで、T1L の提案値は採らず、基準ゲートは開いたまま。
- effective-capacitance（推奨 bench）: U2 入力リップルと出力の安定の合否値は、測定の前にレビューで決める。それまで基準ゲートは開いたまま。
