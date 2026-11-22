# JLC 注文画面チェックリスト（A7 試作）

自動生成（`scripts/a7_jlc_package.py`）。**発注・製造リリース・工場受入ではありません。** 発注ゲート: BLOCKED。

## コントローラー（`controller`）

- 基板: 4 層 / 0.8 mm（±0.1 mm） / 積層 JLC04081H-3313 / 表面処理 ENIG / レジスト色 green (the recorded 0.10 mm via web uses the green 1 oz bridge row; black/white need 0.13 mm)
- 面付け: 1 枚入り 70 × 76.9 mm、PCBA 数量 2 シート → 実装 2 枚（必要 2）、Panel by JLCPCB は No
- PCB 数量（基板の製造枚数）: 未確認。JLC の最小数は取得していない（`pcb-fabrication-quantity-not-sourced`）。PCBA 数量とは別に、注文画面で提示される最小数を入れる
- PCBA: STANDARD、実装面 Bottom + Top
- ビア: Tented (not ink-plugged: plugging needs 0.35 mm to openings; our web is 0.10 mm)。レジスト: use the Gerber mask openings as drawn (minimal mask: F.Mask and B.Mask graphics are openings, not retained mask)
- J1: 基板 CPL (-0.7, -35.8) 90° Top、面付け CPL (9.75, -42.8) 90°、原点とパッド中心の差 7.358 mm → 配置プレビューで確認
- J2: 基板 CPL (-0.7, -50.8) 90° Top、面付け CPL (9.75, -57.8) 90°、原点とパッド中心の差 7.358 mm → 配置プレビューで確認
- J5: 基板 CPL (7.24, -27.5) 0° Top、面付け CPL (17.69, -34.5) 0°、原点とパッド中心の差 1.25 mm → 配置プレビューで確認
- SW1: 基板 CPL (6.8, -60.1) 0° Top、面付け CPL (17.25, -67.1) 0°、原点とパッド中心の差 0.568 mm → 配置プレビューで確認
- B 面 25 点（R1 0°, R2 0°, R3 0°, R4 90°, R5 90°, R6 0°, R7 90°, R8 90°, R9 90°, R10 90°, R11 0°, R12 0°, R13 0°, R14 0°, R15 0°, R16 0°, R17 90°, R18 90°, R19 90°, R20 90°, R21 90°, R22 0°, R23 0°, R24 0°, R25 90°）→ B 面プレビューで向きを確認
- 向きを確認する極性部品: D1, D2, D3, J1, J2, J3, J5, L1, Q1, SW1, U1, U2, U3, U4, U5, U6, U7

## LED リーフ（`led_leaf`）

- 基板: 2 層 / 0.8 mm（±0.1 mm） / 積層 none published for 2-layer 0.8 mm / 表面処理 ENIG / レジスト色 green (the recorded 0.10 mm via web uses the green 1 oz bridge row; black/white need 0.13 mm)
- 面付け: 2 枚入り 70 × 96.5 mm、PCBA 数量 2 シート → 実装 4 枚（必要 4）、Panel by JLCPCB は No
- PCB 数量（基板の製造枚数）: 未確認。JLC の最小数は取得していない（`pcb-fabrication-quantity-not-sourced`）。PCBA 数量とは別に、注文画面で提示される最小数を入れる
- PCBA: STANDARD、実装面 Top
- ビア: Tented (not ink-plugged: plugging needs 0.35 mm to openings; our web is 0.10 mm)。レジスト: use the Gerber mask openings as drawn (minimal mask: F.Mask and B.Mask graphics are openings, not retained mask)
- 向きを確認する極性部品: D1, D2, D3, D4, J1, J2

## 電源アダプタ（`power_adapter`）

- 基板: 2 層 / 1.6 mm（±10%） / 表面処理 HOLD: not recorded (power-adapter-a5-settings-unspecified) / レジスト色 HOLD: not recorded
- 面付け: 1 枚入り 22.8 × 44 mm、PCBA 数量 2 シート → 実装 2 枚（必要 2）、Panel by JLCPCB は No
- PCB 数量（基板の製造枚数）: 未確認。JLC の最小数は取得していない（`pcb-fabrication-quantity-not-sourced`）。PCBA 数量とは別に、注文画面で提示される最小数を入れる
- PCBA: ECONOMIC、実装面 Top
- J1: 基板 CPL (3.13, -10.32) 0° Top、面付け CPL (10.13, -17.32) 0°、原点とパッド中心の差 5.236 mm → 配置プレビューで確認
- J2: 基板 CPL (3.15, -28.7) 0° Top、面付け CPL (10.15, -35.7) 0°、原点とパッド中心の差 1.25 mm → 配置プレビューで確認
- 向きを確認する極性部品: J1, J2

## 工場に確認すること（未回答）

- `controller-4l-jlc04081h-3313`（controller）: Confirm the order form lets JLC04081H-3313 be chosen for this 4-layer 0.8 mm order without impedance-controlled traces, and that the fabricated build follows it.
- `leaf-2l-construction`（led_leaf）: Which core and copper construction JLC uses for a 2-layer 0.8 mm FR-4 board (needed for the optical/translucency assumption, not for orderability).
- `enig-exposed-copper`（controller, led_leaf）: Whether JLC CAM/DFM accepts the large mask openings that expose ENIG copper around pads, and confirmation that no trace is left uncovered (else the 0.25/0.25 mm uncovered-trace rule applies). Not checked against the Gerbers by this review.
- `mask-dam-and-openings`（controller, led_leaf）: Whether the custom openings and local dams are kept as drawn (for the 2-layer leaf, the "Do not modify original solder mask size" option; for the 4-layer controller, 1:1 LDI), and whether a 0.10 mm web between a tented via and an opening is held (the published 0.10 mm row is pad spacing, not a tented-via rule).
- `via-tenting`（controller, led_leaf）: Whether tenting holds over the 0.10 mm web to the nearest opening on 0.8 mm boards; thin mask on the annular ring is a stated normal appearance.
- `pcba-0p8-thin-board`（controller, led_leaf）: Thin-board acceptance: whether 0.8 mm customer panels of this size need extra support, a carrier or wider rails, and whether double-sided reflow of the 0.8 mm controller is accepted as is.
- `customer-panels`（controller, led_leaf, power_adapter）: PCBA quantity unit for a customer panel (panels or boards) and acceptance of these panels; the owner closed this from their own knowledge (jlc-questions, owner-stated, not supplier-confirmed).

## 保留

- `power-adapter-a5-settings-unspecified`: Surface finish, mask colour and base material of the unchanged A5 1.6 mm 2-layer adapter are not recorded; an order-form choice, not a design change. Holds until the owner names them.

未取得: quote、lead time、stock reservation、factory DFM acceptance、assembly acceptance。
