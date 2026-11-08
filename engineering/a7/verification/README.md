# A7 ネイティブ検証の基盤 (R3, #18)

A7 の制御基板はまだありません。このディレクトリは、A7 基板が入ったときに適用する検証の **定義** と、
検証機構そのものを確かめる仕組みを置く場所です。

> **ここにある結果は A7 基板の合格ではありません。** CI の `native-infrastructure` ジョブは
> `scripts/tests/fixtures/native/` の配線済みフィクスチャで検証機構を動かし、最良でも
> `INFRASTRUCTURE_PASS` (検出すべきものを検出できた) しか出しません。A7 プロファイル `native_gate.json` は
> `candidate: null` のため、実行すると `NO_CANDIDATE` で失敗します。電子回路・製造の承認でもありません。

## ファイル

| ファイル | 区分 | 内容 |
|---|---|---|
| `native_gate.json` | authored | A7 リビジョン用ゲートプロファイル (候補基板なし) |
| `native_gate.lock.json` | derived | `python3 scripts/native_gate/runner.py lock --profile engineering/a7/verification/native_gate.json` |
| `authorized_delta.json` | authored | A5 基準ネットリストに対する A7 の許可済み差分 (未レビュー、エントリなし) |
| `interface_roles/a5_reference.json` | authored | A5 のピン割り当てを役割として表したもの (陽性対照) |
| `interface_roles/a7_controller.json` | authored | A7 の役割表。ジャック/スイッチは R1 #16 の部品根拠待ちで `unresolved` |
| `interface_review.md` | authored | A5 のインターフェース検査を A7 にどう引き継いだか |
| `source_authority.json` | authored | 所有区分と再生成ルール |

## ルール

- `engineering/a5/` は不変。ゲートは実行前後に `scripts/verify_seed.py` とツリーハッシュで確認します。
- 権威 (authoritative) 基板 `engineering/a7/electronics/controller/controller.kicad_pcb` は予約のみ。基板と、
  それを `candidate` とする完全なゲートは同じ PR で入れます (R4 #19)。未配線の初期基板はドラフトブランチに留め、
  ゲートは失敗のままにします。
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
```
