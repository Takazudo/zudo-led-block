# A7 ネイティブ検証 (R3 #18, R4 #19)

このディレクトリは A7 制御基板に適用する検証の **定義** と、検証機構そのものを確かめる仕組みを置く場所です。

> A7 プロファイル `native_gate.json` は権威基板 `a7_controller` を `candidate` とし、CI で毎回新規に実行して
> `PASS` を要求します (ERC・パリティ・DRC・未接続 0・ゾーン再充填・再生成保存・負の対照)。CI の
> フィクスチャ実行は最良でも `INFRASTRUCTURE_PASS` で、A7 基板の結果ではありません。どちらもデジタル検証で、
> 電子回路の物理評価・製造の承認ではありません。

## ファイル

| ファイル | 区分 | 内容 |
|---|---|---|
| `native_gate.json` | authored | A7 リビジョン用ゲートプロファイル (`candidate: a7_controller`、`design_rule_delta` でビア 0.5/0.2 mm と、厳しくする方向だけのカスタムルール PTH–トラック 0.35 mm、`placement` でコートヤード比較を KiCad の内部単位 1 nm で行う) |
| `native_gate.lock.json` | derived | `python3 scripts/native_gate/runner.py lock --profile engineering/a7/verification/native_gate.json` |
| `authorized_delta.json` | authored | A5 基準ネットリストに対する A7 の許可済み差分 (J1/J2/SW1 の部品置換、同じ PR #24 レビューで承認済み) |
| `interface_roles/a5_reference.json` | authored | A5 のピン割り当てを役割として表したもの (陽性対照) |
| `interface_roles/a7_controller.json` | authored | A7 の役割表 (`status: reviewed`)。ジャック/スイッチのピン割り当ては R1 #16 の部品根拠から記入し、独立した電気レビュー ([PR #24 review 5818088400](https://github.com/Takazudo/zudo-led-block/pull/24#pullrequestreview-5818088400)、head `1a2f31a`) で承認済み。PJ-324M のピン機能は導通試験まで INFERRED のまま |
| `interface_review.md` | authored | A5 のインターフェース検査を A7 にどう引き継いだか |
| `source_authority.json` | authored | 所有区分と再生成ルール |
| `fab/jlcpcb_capabilities.json` | authored | ルール差分の根拠となる JLCPCB の公開能力 (URL・取得ハッシュ・該当行) |
| `routing/route_proposal_seed0.json` | authored | 権威基板の配線を作ったルーター出力の記録 (基板が正、これから基板は再生成しない) |

## ルール

- `engineering/a5/` は不変。ゲートは実行前後に `scripts/verify_seed.py` とツリーハッシュで確認します。
- 権威 (authoritative) 基板 `engineering/a7/electronics/controller/controller.kicad_pcb` と、それを `candidate` と
  する完全なゲートは同じ PR (R4 #19) で入れました。
- 通常の再生成は権威基板を書きません (`scripts/native_gate/authority.py` が拒否し、ゲートが前後のハッシュを比較)。
- 初期基板の生成は、リポジトリ外の空ディレクトリにのみ書きます (`authority.py init-board`, `make_fixture.py`)。
- 配置・接続のエクスポートは、権威基板の新しいネイティブ結果からのみ作ります (`authority.py export-placement`)。
- A5 との完全一致は要求しません。代わりに (1) レビュー済み基準、(2) 許可済み差分の記録、(3) 新しい回路図–基板の
  ピン/ネット照合、(4) 挙動アサーション (パッシブ THRU、モード符号化、電源、CV、左右 LED ストリーム) を要求します。
- 未配線を許すモード、`continue-on-error`、成功ラッパー、広い除外は使いません。

## コマンド

```sh
python3 -m unittest discover -s scripts/tests -p 'test_native_*.py'      # 通常
python3 -O -m unittest discover -s scripts/tests -p 'test_native_*.py'   # -O
python3 scripts/native_gate/runner.py lock --profile scripts/tests/fixtures/native/profile.json --check
python3 scripts/native_gate/runner.py run  --profile scripts/tests/fixtures/native/profile.json --out /tmp/native   # Docker が必要
python3 scripts/native_gate/runner.py run  --profile engineering/a7/verification/native_gate.json --out /tmp/a7-gate  # A7 基板、PASS を要求
```
