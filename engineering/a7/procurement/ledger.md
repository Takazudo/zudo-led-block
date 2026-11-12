# A7 調達・組立の準備台帳

自動生成。**製造承認・発注用ファイルではありません。** SW1 はオーナーの方針（動けばよい・安く・JLC 在庫あり）により 2026-11-12 に PCM13SMTR（C221842、JLC 在庫 0）から HX MSK13C02（C5149819）へ変更しました。C5149819 は 2026-11-12T19:35:14Z の JLC 観測で在庫 4561（Extended）・最小購入 1・包装数 3000、1〜49 個の段階価格 0.1069（通貨の項目なし）です（項目の意味はこちらの解釈）。確保済み在庫ではなく、納期・実装受入は未取得です。他の部品の現在の商取引条件も未取得で、過去の A5 価格を現在値として再掲しません。

台帳 SHA-256: `3f418594564fca0f747c03b9d72e935b4f3f9b34c85108ca209509f64f6090fa`。71 配置 / 81 実装点 / 台。

## 最初の発注数量: 2 台（オーナーの判断）

オーナーの言葉: 「JLCPCB accept at least 2 PCBA, so we will make 2 units first」（`engineering/a7/procurement/owner-decisions.json`）。JLC の PCBA 最小 2 枚は SOURCED（JLC の公開能力表で確認済み）。この数量は発注・試作ルート・製造リリースの承認ではありません。

必要枚数: controller 2 枚、led_leaf 4 枚、power_adapter 2 枚。PCB 製造の最小枚数と JLC のロス分（attrition）は未取得で、下の数に上乗せしていません。

オーナーの方針（原文）: 「basically I want to complete it on JLCPCB, external purchase from JLC parts lib is acceptable」。こちらの解釈（オーナー未確認）: JLC 在庫 → JLC 予約注文または Global Sourcing → それ以外は例外として行ごとに明示。

| LCSC | 型番 | 必要数 | 最小購入 | 購入数 | 経路 |
|---|---|---:|---:|---:|---|
| C5149819 | HX MSK13C02 | 2 | 1 | 2 | JLC_STOCK |

ほかの 29 型番は JLC 在庫を第一候補とし、在庫と最小購入数は未観測です（行ごとの必要数は `assembly-manifest.json` の `order_plan.lines`）。

| 基板 | 枚数/台 | 実装点/枚 | SMD F/B | THT F/B | PCB SHA-256 |
|---|---:|---:|---|---|---|
| controller | 1 | 59 | 31/25 | 3/0 | `89310d539b3c28096775cee821e46c14fdba42a87809c82f1fd7f0751704e727` |
| led_leaf | 2 | 10 | 10/0 | 0/0 | `6244280cec3efe00ca31d9c5c8878f3ed6eb59a1c6bd4e933beffedd49511df3` |
| power_adapter | 1 | 2 | 0/0 | 2/0 | `b0f071f2730afdfd3d29de2176b1cce5f90b0c0726d14fd15501e27f90d95187` |

実装する型番は 30 種類。SMD / THT の区別はコントローラーが native geometry のパッド属性、リーフとアダプタが不変 A5 の配置データのパッド属性から生成しています。コントローラーは両面 SMD と F 面 THT の組合せで、実装サービスの受入は未確認です。

## 未解決事項

| ID | 区分 | 内容 |
|---|---|---|
| supply-observations | ACCESS_EVIDENCE_HOLD | Order quantity is 2 modules (owner decision). JLC stock, price, minimum, packaging, lead time and assembly applicability at that quantity are not observed for any line except the C5149819 switch (stock 4561 at 2026-11-12); JLC attrition is not sourced; stock never reserved. |
| jack-switch-qualification | PHYSICAL_ONLY | PJ-324M pin function (which of terminals 4/5 is the tip contact; the supplier symbol contradicts the inferred 4 = tip) is not confirmed: the owner waived the pre-order continuity test on 2026-11-12 and accepted the risk, so it is a first-article check on the assembled boards. Slot, axis height and nut fit, and the HX MSK13C02 truth table and land/peg fit, also need received parts (jack-continuity, jack-dimensions, switch-fit). |
| exact-part-evidence | ACCESS_EVIDENCE_HOLD | Exact-part gaps after the 2026-11-11 source recovery (the PMEG4010CEJ ,115 packing is since sourced: SOD323F on a 7-inch reel, fact-pmeg4010cej-115-orderable): SM04B-SRSS-TB per-circuit numbering not printed beyond the No. 1 end; PJ-324M recommended hole/slot sizes, axis height and whether a nut ships with C22355739 not sourced. |
| mechanical-materials | ACCESS_EVIDENCE_HOLD | PMMA sheet and pocket tolerances, PETG process and orderable fastener part numbers are not sourced; the model carries designations (M2x18, M1.6x4) and envelopes only. |
| rack-hardware | OWNER_DECISION | The owner accepted naming the case (2026-11-12, accept all recommendations); the case model, and so the rail/thread interface and fasteners, is not given yet. |
| fixture-materials | OWNER_DECISION | Fixture digital criteria 1-4 met; the owner approved the proposed hardware on 2026-11-12 (accept all recommendations). The fabricator for the four FR-4 plates is not chosen. Physical contact/load tests (criterion 5) follow. |
| prototype-and-release | OWNER_DECISION | No reviewed manufacturing package and no manufacturing release approval. A prototype route, when the owner approves one, is recorded in engineering/a7/qualification/records.json and is not a release. |

外部部材・ケーブル・治具・サービスの詳細は `assembly-manifest.json` を参照してください。TP1–TP5 は購入部品に数えません。治具数量は台数に掛けません。B面・角度・位置は元の KiCad 出力とハッシュに追跡できますが、この台帳だけでは新規 native 検証や実装方向の承認になりません。
