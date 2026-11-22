# A7 調達・組立の準備台帳

自動生成。**製造承認・発注用ファイルではありません。** SW1 はオーナーの方針（動けばよい・安く・JLC 在庫あり）により 2026-11-12 に PCM13SMTR（C221842）から HX MSK13C02（C5149819）へ変更しました。PCM13SMTR は現在の実装部品ではなく、その観測は履歴として残すだけです。

実装する 30 型番すべてについて、2026-11-22 に JLC の部品ページと部品 API を匿名で読み直しました（`engineering/a7/procurement/sourcing-projection.json`）。部品ページ（2026-11-22T06:14:44Z〜2026-11-22T06:16:30Z）と部品 API（2026-11-22T06:14:42Z〜2026-11-22T06:16:28Z）は別々の読み取りで、取得時刻・受信バイトの SHA-256 をここに、匿名化した写しを非公開リポジトリに保存しています（在庫の数字が異なる型番 0）。Basic 14 / Extended 16。2026-11-12 の観測は履歴としてそのまま残し、最新としては扱いません。項目の意味と通貨（USD）はこちらの解釈です。**日付付きの掲載観測であり、現在の在庫・見積・在庫確保・実装受入ではありません。** 納期・確定見積・在庫確保・実装受入はどの型番も未取得です。発注前に取り直してください。

台帳 SHA-256: `b94ac5981de7eed846bf0c9eb0dae61c5cd1ea25d1fe4defb3b1369aada6c02d`。71 配置 / 81 実装点 / 台。

## 最初の発注数量: 2 台（オーナーの判断）

オーナーの言葉: 「JLCPCB accept at least 2 PCBA, so we will make 2 units first」（`engineering/a7/procurement/owner-decisions.json`）。JLC の PCBA 最小 2 枚は SOURCED（JLC の公開能力表で確認済み）。この数量は発注・試作ルート・製造リリースの承認ではありません。

必要枚数: controller 2 枚、led_leaf 4 枚、power_adapter 2 枚。必要数は実装点数 × 2 台で計 162 個（ロス分を含まない）。PCB 製造の最小枚数と JLC のロス分（attrition）の規則は未取得です。下の「購入数（推定）」は価格点検が API の項目（loss_number / least_patch_number / min_purchase、意味はこちらの解釈）から計算した値です。

オーナーの方針（原文）: 「basically I want to complete it on JLCPCB, external purchase from JLC parts lib is acceptable」。こちらの解釈（オーナー未確認）: JLC 在庫 → JLC 予約注文または Global Sourcing → それ以外は例外として行ごとに明示。

| LCSC | 型番 | 区分 | 必要数 | ページ在庫 | API 在庫 | 最小購入 | 購入数（推定） | 単価（USD と推定） | 在庫 2026-11-12（履歴） | 経路 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| C122442 | 530470310 | EXTENDED | 4 | 17167 | 17167 | 1 | 6 | 0.1314 | 21090 | JLC_STOCK |
| C12891 | CL31A226KAHNNNE | BASIC | 4 | 2568477 | 2568477 | 1 | 8 | 0.1028 | 2504817 | JLC_STOCK |
| C134375 | BAS70-04-7-F | EXTENDED | 2 | 1 **不足** | 1 | 1 | 7 | 0.0724 | 247 | JLC_PREORDER_OR_GLOBAL_SOURCING |
| C140331 | TPS2552DBVR-1 | EXTENDED | 2 | 2003 | 2003 | 1 | 2 | 0.8966 | 2218 | JLC_STOCK |
| C14663 | CC0603KRX7R9BB104 | BASIC | 32 | 53154123 | 53154123 | 1 | 47 | 0.0052 | 36497856 | JLC_STOCK |
| C15741 | SN74LVC2T45DCUR | EXTENDED | 2 | 53962 | 53962 | 1 | 5 | 0.2055 | 85126 | JLC_STOCK |
| C15850 | CL21A106KAYNNNE | BASIC | 6 | 9314861 | 9314861 | 1 | 20 | 0.0311 | 8590360 | JLC_STOCK |
| C160404 | SM04B-SRSS-TB(LF)(SN) | EXTENDED | 10 | 4643 | 4643 | 43 | 43 | 0.2147 | 7443 | JLC_STOCK |
| C19666 | CL10A475KO8NNNC | BASIC | 6 | 3144424 | 3144424 | 1 | 20 | 0.0144 | 3674763 | JLC_STOCK |
| C20526 | MMBT3904(RANGE:100-300) | BASIC | 2 | 4176944 | 4176944 | 1 | 10 | 0.0103 | 4184311 | JLC_STOCK |
| C2071056 | AP63205WU-7 | EXTENDED | 2 | 57435 | 57435 | 1 | 2 | 0.4631 | 39789 | JLC_STOCK |
| C21190 | 0603WAF1001T5E | BASIC | 6 | 40500481 | 40500481 | 1 | 20 | 0.0016 | 28789506 | JLC_STOCK |
| C221351 | OPA197IDBVR | EXTENDED | 2 | 71013 | 71013 | 1 | 2 | 0.7445 | 76583 | JLC_STOCK |
| C22355739 | PJ-324M | EXTENDED | 4 | 4113 | 4113 | 1 | 4 | 0.2496 | 4454 | JLC_STOCK |
| C23138 | 0603WAF3300T5E | BASIC | 6 | 2611842 | 2611842 | 1 | 20 | 0.0015 | 2413677 | JLC_STOCK |
| C23162 | 0603WAF4701T5E | BASIC | 2 | 19300585 | 19300585 | 1 | 20 | 0.0028 | 14582556 | JLC_STOCK |
| C23231 | 0603WAF6802T5E | BASIC | 2 | 673837 | 673837 | 1 | 20 | 0.0016 | 786565 | JLC_STOCK |
| C23254 | 0603WAF8202T5E | BASIC | 8 | 850956 | 850956 | 1 | 20 | 0.0027 | 934045 | JLC_STOCK |
| C25803 | 0603WAF1003T5E | BASIC | 12 | 13030961 | 13030961 | 1 | 22 | 0.0029 | 15162637 | JLC_STOCK |
| C25804 | 0603WAF1002T5E | BASIC | 10 | 42489966 | 42489966 | 1 | 20 | 0.0017 | 42847861 | JLC_STOCK |
| C398363 | TLV9001IDBVR | EXTENDED | 2 | 12316 | 12316 | 1 | 5 | 0.0794 | 47025 | JLC_STOCK |
| C404027 | TLV75533PDBVR | EXTENDED | 2 | 98097 | 98097 | 1 | 5 | 0.1218 | 75351 | JLC_STOCK |
| C50704 | PMEG4010CEJ,115 | EXTENDED | 4 | 11091 | 11091 | 1 | 6 | 0.3538 | 12689 | JLC_STOCK |
| C5149819 | HX MSK13C02 | EXTENDED | 2 | 3511 | 3511 | 1 | 2 | 0.1069 | 4561 | JLC_STOCK |
| C5270180 | STM32G031G8U6TR | EXTENDED | 2 | 3891 | 3891 | 1 | 2 | 1.7457 | 4507 | JLC_STOCK |
| C52917434 | WS2812B-2020-V6 | EXTENDED | 16 | 708163 | 708163 | 1 | 18 | 0.0915 | 876136 | JLC_STOCK |
| C5665 | 2.54-2*5P | EXTENDED | 2 | 179329 | 179329 | 1 | 2 | 0.1033 | 130239 | JLC_STOCK |
| C57112 | 0603B103K500NT | BASIC | 2 | 4617494 | 4617494 | 1 | 20 | 0.0044 | 5396447 | JLC_STOCK |
| C694586 | SPM4020T-4R7M-LR | EXTENDED | 2 | 686 | 686 | 1 | 5 | 0.3799 | 686 | JLC_STOCK |
| C7250 | 0603WAF1005T5E | BASIC | 4 | 882386 | 882386 | 1 | 20 | 0.0022 | 1022909 | JLC_STOCK |

**掲載在庫が 2 台分に足りない型番**: BAS70-04-7-F（C134375）在庫 1 / 必要 2。代替品は選んでいません（オーナー方針の優先順で、JLC 予約注文・Global Sourcing・待つ・別途レビューした代替のいずれか）。

最小購入数が必要数を上回る型番: C160404（購入数の推定に反映）。

部品代の計算値（推定、USD と推定）: 29.86。段取り料金・PCB 製造・送料・税などは含みません。外された PCM13SMTR（C221842）は `retired` に履歴として残し、必要数に含めません。

| 基板 | 枚数/台 | 実装点/枚 | SMD F/B | THT F/B | PCB SHA-256 |
|---|---:|---:|---|---|---|
| controller | 1 | 59 | 31/25 | 3/0 | `d83691d6590e013b2a66957b61d76ba2f68bedaaec04789326e1215b2d1bdb2b` |
| led_leaf | 2 | 10 | 10/0 | 0/0 | `bcf2e35d767221f5a9db0cd16769a2e503a672f522fd4f32f78012cdeb494cf9` |
| power_adapter | 1 | 2 | 0/0 | 2/0 | `b0f071f2730afdfd3d29de2176b1cce5f90b0c0726d14fd15501e27f90d95187` |

実装する型番は 30 種類。SMD / THT の区別はコントローラーが native geometry のパッド属性、リーフが採用した A7 PCB のパッド属性、アダプタが不変 A5 の配置データのパッド属性から生成しています。コントローラーは両面 SMD と F 面 THT の組合せで、実装サービスの受入は未確認です。

## 未解決事項

| ID | 区分 | 内容 |
|---|---|---|
| supply-observations | ACCESS_EVIDENCE_HOLD | Order quantity is 2 modules (owner decision), 162 fitted pieces before attrition. 30 of 30 fitted identities have dated 2026-11-22 JLC listing observations from both the rendered part pages and the parts API (separate reads, field meanings and currency inferred; 2026-11-12 reads kept as history; engineering/a7/procurement/sourcing-projection.json). Listed JLC stock below the 2-module need at 2026-11-22: BAS70-04-7-F (C134375) stock 1 for 2 (no substitute chosen). Listed minimum purchase above the need: C160404. Not obtained for any line: lead time, confirmed quote, stock reservation and assembly acceptance. JLC attrition is not sourced as a rule; the audit's buy quantities are our inference. Refresh before ordering. |
| jack-switch-qualification | PHYSICAL_ONLY | PJ-324M pin function (which of terminals 4/5 is the tip contact; the supplier symbol contradicts the inferred 4 = tip) is not confirmed: the owner waived the pre-order continuity test on 2026-11-12 and accepted the risk, so it is a first-article check on the assembled boards. Slot, axis height and nut fit, and the HX MSK13C02 truth table and land/peg fit, also need received parts (jack-continuity, jack-dimensions, switch-fit). |
| exact-part-evidence | ACCESS_EVIDENCE_HOLD | Exact-part gaps after the 2026-11-11 source recovery (the PMEG4010CEJ ,115 packing is since sourced: SOD323F on a 7-inch reel, fact-pmeg4010cej-115-orderable): SM04B-SRSS-TB per-circuit numbering not printed beyond the No. 1 end; PJ-324M recommended hole/slot sizes, axis height and whether a nut ships with C22355739 not sourced. |
| mechanical-materials | ACCESS_EVIDENCE_HOLD | PMMA sheet and pocket tolerances, PETG process and orderable fastener part numbers are not sourced; the model carries designations from the current mechanical layout and envelopes only; exact orderable hardware and assembly fit remain unqualified. |
| rack-hardware | OWNER_DECISION | The owner accepted naming the case (2026-11-12, accept all recommendations); the case model, and so the rail/thread interface and fasteners, is not given yet. |
| fixture-materials | CLOUD_DIGITAL | Fixture design and materials incomplete (fixture manifest: digital_criteria_1_to_4_met not true, hardware_proposal_complete not true); physical contact/load tests follow. |
| prototype-and-release | OWNER_DECISION | No reviewed manufacturing package and no manufacturing release approval. A prototype route, when the owner approves one, is recorded in engineering/a7/qualification/records.json and is not a release. |

外部部材・ケーブル・治具・サービスの詳細は `assembly-manifest.json` を参照してください。TP1–TP5 は購入部品に数えません。治具数量は台数に掛けません。B面・角度・位置は元の KiCad 出力とハッシュに追跡できますが、この台帳だけでは新規 native 検証や実装方向の承認になりません。
