# A7 調達・組立の準備台帳

自動生成。**製造承認・発注用ファイルではありません。** SW1 はオーナーの方針（動けばよい・安く・JLC 在庫あり）により 2026-11-12 に PCM13SMTR（C221842）から HX MSK13C02（C5149819）へ変更しました。PCM13SMTR は現在の実装部品ではなく、その観測は履歴として残すだけです。

実装する 30 型番すべてについて、2026-11-12 の JLC 掲載情報を保存しています（`engineering/a7/procurement/sourcing-projection.json`）。部品ページの記録（2026-11-12T10:35:07Z〜2026-11-12T19:56:55Z、SHA-256 のみ保存）と、その後の部品 API による価格点検（2026-11-12T19:09:52Z、行を再整形・raw なし）は別々の読み取りで、同時点のスナップショットではありません（在庫の数字が 25 型番で異なります）。Basic 14 / Extended 16。項目の意味と通貨（USD）はこちらの解釈です。**現在の在庫・見積・在庫確保・実装受入ではありません。** 納期・確定見積・在庫確保・実装受入はどの型番も未取得です。発注前に取り直してください。

台帳 SHA-256: `ea30c8a71c8a0d2f2d4eae0e6302881c6bb9067902d6d8b21254c5f4d1725755`。71 配置 / 81 実装点 / 台。

## 最初の発注数量: 2 台（オーナーの判断）

オーナーの言葉: 「JLCPCB accept at least 2 PCBA, so we will make 2 units first」（`engineering/a7/procurement/owner-decisions.json`）。JLC の PCBA 最小 2 枚は SOURCED（JLC の公開能力表で確認済み）。この数量は発注・試作ルート・製造リリースの承認ではありません。

必要枚数: controller 2 枚、led_leaf 4 枚、power_adapter 2 枚。必要数は実装点数 × 2 台で計 162 個（ロス分を含まない）。PCB 製造の最小枚数と JLC のロス分（attrition）の規則は未取得です。下の「購入数（推定）」は価格点検が API の項目（loss_number / least_patch_number / min_purchase、意味はこちらの解釈）から計算した値です。

オーナーの方針（原文）: 「basically I want to complete it on JLCPCB, external purchase from JLC parts lib is acceptable」。こちらの解釈（オーナー未確認）: JLC 在庫 → JLC 予約注文または Global Sourcing → それ以外は例外として行ごとに明示。

| LCSC | 型番 | 区分 | 必要数 | ページ在庫 | API 在庫 | 購入数（推定） | 単価（USD と推定） |
|---|---|---|---:|---:|---:|---:|---:|
| C122442 | 530470310 | EXTENDED | 4 | 21090 | 21090 | 6 | 0.1314 |
| C12891 | CL31A226KAHNNNE | BASIC | 4 | 2515861 | 2504817 | 8 | 0.1028 |
| C134375 | BAS70-04-7-F | EXTENDED | 2 | 247 | 247 | 7 | 0.0723 |
| C140331 | TPS2552DBVR-1 | EXTENDED | 2 | 2228 | 2218 | 2 | 0.8964 |
| C14663 | CC0603KRX7R9BB104 | BASIC | 32 | 36130749 | 36497856 | 47 | 0.006 |
| C15741 | SN74LVC2T45DCUR | EXTENDED | 2 | 85166 | 85126 | 5 | 0.2079 |
| C15850 | CL21A106KAYNNNE | BASIC | 6 | 8516270 | 8590360 | 20 | 0.0315 |
| C160404 | SM04B-SRSS-TB(LF)(SN) | EXTENDED | 10 | 9798 | 7443 | 10 | 0.2146 |
| C19666 | CL10A475KO8NNNC | BASIC | 6 | 3568082 | 3674763 | 20 | 0.015 |
| C20526 | MMBT3904(RANGE:100-300) | BASIC | 2 | 4183780 | 4184311 | 10 | 0.0103 |
| C2071056 | AP63205WU-7 | EXTENDED | 2 | 39904 | 39789 | 2 | 0.4629 |
| C21190 | 0603WAF1001T5E | BASIC | 6 | 28882373 | 28789506 | 20 | 0.0017 |
| C221351 | OPA197IDBVR | EXTENDED | 2 | 76873 | 76583 | 2 | 0.8424 |
| C22355739 | PJ-324M | EXTENDED | 4 | 5954 | 4454 | 4 | 0.2495 |
| C23138 | 0603WAF3300T5E | BASIC | 6 | 2416605 | 2413677 | 20 | 0.002 |
| C23162 | 0603WAF4701T5E | BASIC | 2 | 14660825 | 14582556 | 20 | 0.0028 |
| C23231 | 0603WAF6802T5E | BASIC | 2 | 787855 | 786565 | 20 | 0.0016 |
| C23254 | 0603WAF8202T5E | BASIC | 8 | 933289 | 934045 | 20 | 0.0027 |
| C25803 | 0603WAF1003T5E | BASIC | 12 | 15062647 | 15162637 | 22 | 0.0029 |
| C25804 | 0603WAF1002T5E | BASIC | 10 | 42898836 | 42847861 | 20 | 0.0022 |
| C398363 | TLV9001IDBVR | EXTENDED | 2 | 47115 | 47025 | 5 | 0.0792 |
| C404027 | TLV75533PDBVR | EXTENDED | 2 | 75642 | 75351 | 5 | 0.1216 |
| C50704 | PMEG4010CEJ,115 | EXTENDED | 4 | 12701 | 12689 | 6 | 0.3537 |
| C5149819 | HX MSK13C02 | EXTENDED | 2 | 4561 | 4561 | 2 | 0.1069 |
| C5270180 | STM32G031G8U6TR | EXTENDED | 2 | 4507 | 4507 | 2 | 1.7453 |
| C52917434 | WS2812B-2020-V6 | EXTENDED | 16 | 879804 | 876136 | 18 | 0.0859 |
| C5665 | 2.54-2*5P | EXTENDED | 2 | 131245 | 130239 | 2 | 0.1041 |
| C57112 | 0603B103K500NT | BASIC | 2 | 5337711 | 5396447 | 20 | 0.0103 |
| C694586 | SPM4020T-4R7M-LR | EXTENDED | 2 | 686 | 686 | 5 | 0.3798 |
| C7250 | 0603WAF1005T5E | BASIC | 4 | 795181 | 1022909 | 20 | 0.0022 |

部品代の計算値（推定、USD と推定）: 23.08。段取り料金・PCB 製造・送料・税などは含みません。外された PCM13SMTR（C221842）は `retired` に履歴として残し、必要数に含めません。

| 基板 | 枚数/台 | 実装点/枚 | SMD F/B | THT F/B | PCB SHA-256 |
|---|---:|---:|---|---|---|
| controller | 1 | 59 | 31/25 | 3/0 | `89310d539b3c28096775cee821e46c14fdba42a87809c82f1fd7f0751704e727` |
| led_leaf | 2 | 10 | 10/0 | 0/0 | `6244280cec3efe00ca31d9c5c8878f3ed6eb59a1c6bd4e933beffedd49511df3` |
| power_adapter | 1 | 2 | 0/0 | 2/0 | `b0f071f2730afdfd3d29de2176b1cce5f90b0c0726d14fd15501e27f90d95187` |

実装する型番は 30 種類。SMD / THT の区別はコントローラーが native geometry のパッド属性、リーフとアダプタが不変 A5 の配置データのパッド属性から生成しています。コントローラーは両面 SMD と F 面 THT の組合せで、実装サービスの受入は未確認です。

## 未解決事項

| ID | 区分 | 内容 |
|---|---|---|
| supply-observations | ACCESS_EVIDENCE_HOLD | Order quantity is 2 modules (owner decision), 162 fitted pieces before attrition. 30 of 30 fitted identities have dated 2026-11-12 JLC listing observations from both the rendered part pages and the later parts-API audit (separate reads, raw bytes not committed, field meanings and currency inferred; engineering/a7/procurement/sourcing-projection.json). Not obtained for any line: lead time, confirmed quote, stock reservation and assembly acceptance. JLC attrition is not sourced as a rule; the audit's buy quantities are our inference. Refresh before ordering. |
| jack-switch-qualification | PHYSICAL_ONLY | PJ-324M pin function (which of terminals 4/5 is the tip contact; the supplier symbol contradicts the inferred 4 = tip) is not confirmed: the owner waived the pre-order continuity test on 2026-11-12 and accepted the risk, so it is a first-article check on the assembled boards. Slot, axis height and nut fit, and the HX MSK13C02 truth table and land/peg fit, also need received parts (jack-continuity, jack-dimensions, switch-fit). |
| exact-part-evidence | ACCESS_EVIDENCE_HOLD | Exact-part gaps after the 2026-11-11 source recovery (the PMEG4010CEJ ,115 packing is since sourced: SOD323F on a 7-inch reel, fact-pmeg4010cej-115-orderable): SM04B-SRSS-TB per-circuit numbering not printed beyond the No. 1 end; PJ-324M recommended hole/slot sizes, axis height and whether a nut ships with C22355739 not sourced. |
| mechanical-materials | ACCESS_EVIDENCE_HOLD | PMMA sheet and pocket tolerances, PETG process and orderable fastener part numbers are not sourced; the model carries designations (M2x18, M1.6x4) and envelopes only. |
| rack-hardware | OWNER_DECISION | The owner accepted naming the case (2026-11-12, accept all recommendations); the case model, and so the rail/thread interface and fasteners, is not given yet. |
| fixture-materials | OWNER_DECISION | Fixture digital criteria 1-4 met; the owner approved the proposed hardware on 2026-11-12 (accept all recommendations). The fabricator for the four FR-4 plates is not chosen. Physical contact/load tests (criterion 5) follow. |
| prototype-and-release | OWNER_DECISION | No reviewed manufacturing package and no manufacturing release approval. A prototype route, when the owner approves one, is recorded in engineering/a7/qualification/records.json and is not a release. |

外部部材・ケーブル・治具・サービスの詳細は `assembly-manifest.json` を参照してください。TP1–TP5 は購入部品に数えません。治具数量は台数に掛けません。B面・角度・位置は元の KiCad 出力とハッシュに追跡できますが、この台帳だけでは新規 native 検証や実装方向の承認になりません。
