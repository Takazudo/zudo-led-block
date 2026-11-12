# A7 調達・組立の準備台帳

自動生成。**製造承認・発注用ファイルではありません。** C221842 は 2026-11-09T09:18:55Z の JLC 観測で在庫 0・予約可能数 0・MOQ 3・包装数 3500。2026-11-12T08:57:07Z の JLC 掲載では購入可（Extended）・予約注文の最小 3・予約可能数 0（項目の意味はこちらの解釈）で、JLC 在庫の数値は掲載データにありませんでした。価格は通貨不明の段階価格だけです。確保済み在庫ではなく、納期・実装受入は未取得です。他の部品の現在の商取引条件も未取得で、過去の A5 価格を現在値として再掲しません。

台帳 SHA-256: `626d595caebbfbc064492d3ec1823c1fe74bdee26151db9214d0e08e9dc6a329`。71 配置 / 81 実装点 / 台。

## 最初の発注数量: 2 台（オーナーの判断）

オーナーの言葉: 「JLCPCB accept at least 2 PCBA, so we will make 2 units first」（`engineering/a7/procurement/owner-decisions.json`）。JLC の PCBA 最小 2 枚は SOURCED（JLC の公開能力表で確認済み）。この数量は発注・試作ルート・製造リリースの承認ではありません。

必要枚数: controller 2 枚、led_leaf 4 枚、power_adapter 2 枚。PCB 製造の最小枚数と JLC のロス分（attrition）は未取得で、下の数に上乗せしていません。

オーナーの方針（原文）: 「basically I want to complete it on JLCPCB, external purchase from JLC parts lib is acceptable」。こちらの解釈（オーナー未確認）: JLC 在庫 → JLC 予約注文または Global Sourcing → それ以外は例外として行ごとに明示。

| LCSC | 型番 | 必要数 | 最小購入 | 購入数 | 経路 |
|---|---|---:|---:|---:|---|
| C221842 | PCM13SMTR | 2 | 3 | 3 | JLC_PREORDER_OR_GLOBAL_SOURCING |

ほかの 29 型番は JLC 在庫を第一候補とし、在庫と最小購入数は未観測です（行ごとの必要数は `assembly-manifest.json` の `order_plan.lines`）。

| 基板 | 枚数/台 | 実装点/枚 | SMD F/B | THT F/B | PCB SHA-256 |
|---|---:|---:|---|---|---|
| controller | 1 | 59 | 31/25 | 3/0 | `4453f818ede1e6d6c56e45ef43aa6faecb90990f3755f82c6d752258cd4d628e` |
| led_leaf | 2 | 10 | 10/0 | 0/0 | `6244280cec3efe00ca31d9c5c8878f3ed6eb59a1c6bd4e933beffedd49511df3` |
| power_adapter | 1 | 2 | 0/0 | 2/0 | `b0f071f2730afdfd3d29de2176b1cce5f90b0c0726d14fd15501e27f90d95187` |

実装する型番は 30 種類。SMD / THT の区別はコントローラーが native geometry のパッド属性、リーフとアダプタが不変 A5 の配置データのパッド属性から生成しています。コントローラーは両面 SMD と F 面 THT の組合せで、実装サービスの受入は未確認です。

## 未解決事項

| ID | 区分 | 内容 |
|---|---|---|
| supply-observations | ACCESS_EVIDENCE_HOLD | Order quantity is 2 modules (owner decision). JLC stock, price, minimum, packaging, lead time and assembly applicability at that quantity are not observed for any line except C221842 (switch-supply); JLC attrition is not sourced; stock never reserved. |
| switch-supply | OWNER_DECISION | PCM13SMTR (C221842): 2 needed for 2 modules. JLC stock 0 at 2026-11-09; at 2026-11-12 JLC lists it buyable (Extended) with pre-order minimum 3 and presale 0 (field meanings inferred), tier prices without currency, no lead time. The owner wants to complete on JLC: on our reading, a pre-order (presale 0 may mean none can be placed now; fill depends on LCSC stock, not observed) or a Global Sourcing quote; otherwise wait, or accept a reviewed alternate with its own contact table and fit review. |
| panel-route | OWNER_DECISION | None of the three boards meets JLC single-board PCBA size; the panel route is not chosen. Panel by JLCPCB puts 10 controllers, 8 leaves or 2 adapters on each panel (20 PCM13SMTR for a 2-panel minimum if the PCBA quantity counts panels, not sourced); a repo-built panel holding 1 controller, 2 leaves or 1 adapter gives exactly 2 modules but is not built. Comparison in engineering/a7/jlc-package/package.json. |
| jack-switch-qualification | PHYSICAL_ONLY | PJ-324M pin function (which of terminals 4/5 is the tip contact and which its normal; the supplier symbol contradicts the inferred 4 = tip, so this continuity test must precede any PCB order), slot, axis height and nut fit, and PCM13SMTR truth table and land fit, need received parts (jack-continuity, jack-dimensions, switch-fit). |
| exact-part-evidence | ACCESS_EVIDENCE_HOLD | Exact-part gaps after the 2026-11-11 source recovery: PMEG4010CEJ ,115 packing variant not established by the datasheet; SM04B-SRSS-TB per-circuit numbering not printed beyond the No. 1 end; PJ-324M recommended hole/slot sizes, axis height and whether a nut ships with C22355739 not sourced. |
| finished-cables | OWNER_DECISION | Finished A7 power cable (57 mm, +/-3 ASSUMED), SH4 cables and IDC ribbon not selected; supplier answers and the owner choice of assembly are needed before physical routing checks. |
| mechanical-materials | ACCESS_EVIDENCE_HOLD | PMMA sheet and pocket tolerances, PETG process and orderable fastener part numbers are not sourced; the model carries designations (M2x18, M1.6x4) and envelopes only. |
| rack-hardware | OWNER_DECISION | Owner rack rail/thread interface and fasteners not specified. |
| fixture-materials | OWNER_DECISION | Fixture digital criteria 1-4 met and a sourced hardware proposal recorded; the fabricator choice and approval of the proposed hardware are owner decisions. Physical contact/load tests (criterion 5) follow. |
| prototype-and-release | OWNER_DECISION | No owner-approved prototype route, no reviewed manufacturing package and no release approval. |

外部部材・ケーブル・治具・サービスの詳細は `assembly-manifest.json` を参照してください。TP1–TP5 は購入部品に数えません。治具数量は台数に掛けません。B面・角度・位置は元の KiCad 出力とハッシュに追跡できますが、この台帳だけでは新規 native 検証や実装方向の承認になりません。
