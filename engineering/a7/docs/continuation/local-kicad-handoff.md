# ローカル KiCad への引き継ぎ

2026-11-09。Cloud の実装対象は draft PR [#44](https://github.com/Takazudo/zudo-led-block/pull/44)。実装・テスト修正を含む固定入力は `1b53cae06ac2107e6ca54dc3015fc2c3f456cd69`。この文書を追加する後続コミットは設計入力を変更しません。実行対象の SHA と作業ツリー状態を最初に記録してください。

Cloud ローカルでは digest-pinned image 展開が32 GBディスクを満たし、native実行前にENOSPCとなりました。既存ActionsではE1 native PASS、統合headはPRのchecksを参照。Actions artifactのダウンロードもForbiddenだったため、治具に必要なfresh-native入力をローカルで取得・検査する段階へ引き継ぎます。Cloudでローカル機・desktop・remote executorへ切り替えてはいません。

## 固定入力

- controller revision 2: `engineering/a7/electronics/controller/controller.kicad_pcb`
- PCB SHA-256: `4453f818ede1e6d6c56e45ef43aa6faecb90990f3755f82c6d752258cd4d628e`
- canonical placement: `engineering/a7/electronics/controller/board_placement.json`
- profile/lock: `engineering/a7/verification/native_gate.json` / `native_gate.lock.json`
- KiCad: `kicad/kicad:10.0.8@sha256:3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34`
- Python 3.12、Node 24、pnpm 11.5.2、CadQuery 2.7.0。別バージョンのglobal KiCadで代用しない。

## ローカル実行

新しいcheckout/worktreeでrootのAGENTS.mdとcircuit/WORKFLOW.mdを読み、上記commitを取得します。以下は**引き継ぎ用**で、このCloudセッションで実行したローカル機の結果ではありません。ローカルのheavy-test policyがある場合は、そのguardでnative/CAD実行を包んでください。Docker storageには32 GBを超える展開余裕を実測で確認します。選択したPython 3.12環境にCadQuery 2.7.0を導入済みであることを確認します（例: 専用venvで `python3 -m pip install cadquery==2.7.0`）。

```bash
set -euo pipefail
git status --short
git rev-parse HEAD
sha256sum engineering/a7/electronics/controller/controller.kicad_pcb
python3 scripts/verify_seed.py --manifest provenance/seed-manifest.json --repo .
corepack pnpm install --frozen-lockfile
corepack pnpm circuit:check
python3 -c 'import cadquery; assert cadquery.__version__ == "2.7.0"'
python3 scripts/native_gate/runner.py lock --profile engineering/a7/verification/native_gate.json --check
python3 scripts/native_gate/runner.py lock --profile scripts/tests/fixtures/native/profile.json --check
# checkout外の新しい空directory。過去の失敗結果は上書きしない。
a7_verify_dir=$(mktemp -d /tmp/a7-local-verification.XXXXXX)
docker pull kicad/kicad:10.0.8@sha256:3f4a01786dfbe803a65f345c3342b765db9add913f5e9448f8356793714ddc34
python3 scripts/a7_electronics.py generate --check
python3 scripts/a7_schematic_check.py --out "$a7_verify_dir/schematic"
python3 scripts/native_gate/runner.py run --profile scripts/tests/fixtures/native/profile.json --out "$a7_verify_dir/infrastructure" --deadline-s 660
python3 scripts/native_gate/runner.py run --profile engineering/a7/verification/native_gate.json --out "$a7_verify_dir/candidate" --deadline-s 660
python3 scripts/native_gate/authority.py export-placement \
  --board engineering/a7/electronics/controller/controller.kicad_pcb \
  --facts "$a7_verify_dir/candidate/evidence/a7_controller/board_facts.json" \
  --geometry "$a7_verify_dir/candidate/evidence/a7_controller/board_geometry.json" \
  --out engineering/a7/electronics/controller/board_placement.json --check
python3 scripts/a7_mechanical_layout.py --check
python3 scripts/a7_fixture.py --check --cad-check
python3 scripts/verify_seed.py --manifest provenance/seed-manifest.json --repo .
git status --short
printf 'Retain verification directory: %s\n' "$a7_verify_dir"
```

`summary.json`のstatusだけでなくboard hash、DRC/zero-unconnected、refill、parity、regeneration、controls、cleanup、A5前後結果を確認します。`candidate/evidence/a7_controller/board_facts.json`と`board_geometry.json`、run summary/plan、正確なcommitとimage digestを保持します。失敗したrunも別の証跡として残します。

## その後の治具設計

現exportはpad中心/net/sideと基板geometryを拘束しますが、部品高さやはんだ包絡の完全なモデルではありません。fresh factsを取得するだけで完成治具になるとは扱いません。

1. 必要に応じnative extractorを別レビューで拡張し、同一PCB bytesから両面pad形状・寸法・回転・部品外形を取得する。部品高さ/はんだ包絡はexact資料または測定要求を別に結ぶ。既存exportのauthorityを増やさない。
2. INGUN資料の外径0.95/0.96 mm不一致、probe横遊び/同心度、board edge-to-pad/加工/位置決め公差を解決。Ø1 mm pad対Ø0.5 mm tipの公称半径予算0.25 mmは最悪余裕ではない。
3. PCB支持、逆挿し防止、全B面relief、荷重経路、travel stopを設計。PMMA・jack solderへ荷重を逃がさない。4.3 mm working stroke、公称5 Nを最大荷重と取り違えない。
4. 完成assembly STEP/寸法図をCadQuery 2.7.0で生成・干渉/公差レビューし、fixture→procurement→readinessを順に再生成。現carrier STEPを完成治具や発注図へ読み替えない。
5. 実測はowner-approved sample/prototype routeの後だけ。19手順はNOT_MEASUREDのまま、製造/注文承認を自動化しない。

A5不変、A6 #7/PR #14 hold、未送信supplier質問、merge/trackingのアクセスholdを維持します。元の物理Issueを準備成果だけで閉じません。
