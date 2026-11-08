# 配線記録（R4, #19）

`route_proposal_seed0.json` は `scripts/a7_route.py --seed 0` が出力した配線案です。権威基板 `engineering/a7/electronics/controller/controller.kicad_pcb` の配線とビアは、この配線案をそのまま `a7_board.py apply` で書き込んだものです。

## CI での再現性チェック

`python3 scripts/a7_route_check.py --out <リポジトリ外の空ディレクトリ> [--review-aid]` を CI の native ジョブで毎回実行します。

1. ピン留めの KiCad 10.0.8 イメージで `a7_board.py build` を実行し、コミット済みの配置と回路図ネットリストから未配線のステージング基板とパッド形状を作ります。
2. その形状に `a7_route.py --seed 0` を実行し、結果が `route_proposal_seed0.json` とバイト単位で一致することを確かめます。numpy は `scripts/requirements-router.txt` でバージョンとハッシュを固定しています。
3. 権威基板の配線とビアが、配線案と完全に一致することを確かめます。KiCad の内部単位（1 nm）で、多重集合として比較します。配線案に失敗ネットがある場合、基板または配線案に配線やビアが 1 本もない場合も失敗にします（空どうしの一致で合格させないため）。

結果の `summary.json` は CI のアーティファクト `native-infrastructure-evidence` にゲートの要約と一緒に残します。

`PASS` は、記録した配線が再現でき、基板がその配線を持っていることだけを示します。基板の結果はネイティブゲート（`native_gate.json`）が出します。

## レビュー補助（リリース出力ではありません）

`--review-aid` を付けると、コミット済み基板の Gerber、ドリル、部品位置ファイルを書き出します。CI のアーティファクト `a7-controller-review-aid-NOT-A-RELEASE` にも入ります。これはレビュアーが DFM を事前に確認するための補助です。

- リリース出力ではありません。追跡もしていません。これを使って発注しないでください。
- Gerber ジョブファイル（.gbrjob）は意図的に削除しています。基板メーカーのサイトにそのまま一括で読み込めないようにするためです。
- どの基板メーカーの DFM にも通していません。製造注記、層構成図、面付けも含みません。
- A7 は製造用にリリースしていません。#19 の物理ゲート（PJ-324M の導通・穴・軸高さ、PCM13SMTR の適合、在庫、ポゴピン治具）が残っています。
