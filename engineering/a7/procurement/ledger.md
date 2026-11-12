# A7 調達・組立の準備台帳

自動生成。**製造承認・発注用ファイルではありません。** C221842 は 2026-11-09T09:18:55Z の JLC 観測で在庫 0・予約可能数 0・MOQ 3・包装数 3500。確保済み在庫ではなく、価格・納期・実装受入は未取得です。他の部品の現在の商取引条件も未取得で、過去の A5 価格を現在値として再掲しません。

台帳 SHA-256: `c2646fda776a98640bce80d5609582f0fa29a49f0258f26c1767ea742b26088f`。71 配置 / 81 実装点 / 台。数量 1・10・100 は比較条件だけです。

| 基板 | 枚数/台 | 実装点/枚 | SMD F/B | THT F/B | PCB SHA-256 |
|---|---:|---:|---|---|---|
| controller | 1 | 59 | 31/25 | 3/0 | `4453f818ede1e6d6c56e45ef43aa6faecb90990f3755f82c6d752258cd4d628e` |
| led_leaf | 2 | 10 | 10/0 | 0/0 | `6244280cec3efe00ca31d9c5c8878f3ed6eb59a1c6bd4e933beffedd49511df3` |
| power_adapter | 1 | 2 | 0/0 | 2/0 | `b0f071f2730afdfd3d29de2176b1cce5f90b0c0726d14fd15501e27f90d95187` |

実装する型番は 30 種類。SMD / THT の区別はコントローラーが native geometry のパッド属性、リーフとアダプタが不変 A5 の配置データのパッド属性から生成しています。コントローラーは両面 SMD と F 面 THT の組合せで、実装サービスの受入は未確認です。

## 未解決事項

| ID | 区分 | 内容 |
|---|---|---|
| supply-observations | ACCESS_EVIDENCE_HOLD | Current stock, price, MOQ, packaging, lead time and assembly applicability not obtained for any line except the dated C221842 zero-stock observation; stock never reserved. |
| order-quantity | OWNER_DECISION | No agreed order quantity; 1/10/100 are comparison scenarios only, so no supply observation can be judged available for a proposed order. |
| switch-supply | OWNER_DECISION | PCM13SMTR (C221842) had JLC stock 0 / presale 0 at 2026-11-09; wait, buy elsewhere, or accept a reviewed alternate with its own contact table and fit review. |
| jack-switch-qualification | PHYSICAL_ONLY | PJ-324M pin function (which of terminals 4/5 is the tip contact and which its normal; the supplier symbol contradicts the inferred 4 = tip, so this continuity test must precede any PCB order), slot, axis height and nut fit, and PCM13SMTR truth table and land fit, need received parts (jack-continuity, jack-dimensions, switch-fit). |
| exact-part-evidence | ACCESS_EVIDENCE_HOLD | Exact-part gaps after the 2026-11-11 source recovery: PMEG4010CEJ ,115 packing variant not established by the datasheet; SM04B-SRSS-TB per-circuit numbering not printed beyond the No. 1 end; PJ-324M recommended hole/slot sizes, axis height and whether a nut ships with C22355739 not sourced. |
| finished-cables | OWNER_DECISION | Finished A7 power cable (57 mm, +/-3 ASSUMED), SH4 cables and IDC ribbon not selected; supplier answers and the owner choice of assembly are needed before physical routing checks. |
| mechanical-materials | ACCESS_EVIDENCE_HOLD | PMMA sheet and pocket tolerances, PETG process and orderable fastener part numbers are not sourced; the model carries designations (M2x18, M1.6x4) and envelopes only. |
| rack-hardware | OWNER_DECISION | Owner rack rail/thread interface and fasteners not specified. |
| fixture-materials | CLOUD_DIGITAL | Fixture design and materials incomplete (fixture manifest: digital_criteria_1_to_4_met not true, hardware_proposal_complete not true); physical contact/load tests follow. |
| prototype-and-release | OWNER_DECISION | No owner-approved prototype route, no reviewed manufacturing package and no release approval. |

外部部材・ケーブル・治具・サービスの詳細は `assembly-manifest.json` を参照してください。TP1–TP5 は購入部品に数えません。治具数量は台数に掛けません。B面・角度・位置は元の KiCad 出力とハッシュに追跡できますが、この台帳だけでは新規 native 検証や実装方向の承認になりません。
