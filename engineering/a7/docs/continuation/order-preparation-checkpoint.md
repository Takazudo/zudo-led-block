# A7 発注準備の作業記録 — 2026-11-09

## E1 の PR 検証は成功、main への統合は保留

- 基準 main: `af523f9abb74e206c27aaaa076b3b68a5c474940`。このセッションで merge はしていません。
- 作業ブランチ: `codex/a7-order-preparation-20261109`。
- E1 の [draft PR #44](https://github.com/Takazudo/zudo-led-block/pull/44) の検証対象 head: `4894a6f6f21b30419d039bd6427e89553f8dee55`。
- [CI run 42594178172](https://github.com/Takazudo/zudo-led-block/actions/runs/42594178172) は、この head で全検証が PASS。native gate を含み、production deploy は SKIPPED。この PR 実行での SKIP は、将来の main merge での非デプロイを保証しません。
- リポジトリ変数の読み取りは HTTP 404。merge が本番デプロイを起動しないことは未確認のため、merge は保留。設定を変更したり、アクセス拒否を迂回したりしません。
- 制御基板 revision 2 SHA-256: `4453f818ede1e6d6c56e45ef43aa6faecb90990f3755f82c6d752258cd4d628e`。銅箔は変更していません。
- 最初の子 Issue 作成は結果が返る前に中断。親セッションが全 Issue を確認し、未作成と確認しました。拒否・中断の理由が判明するまで、その作成を再試行しないという親の hold を維持します。
- 独立したローカル実装・検証は続行可能。E2–E5 のローカル成果は、上記 E1 head の CI 結果に含めて合格扱いにしません。
- A6 #7 / PR #14 は ON HOLD。発注・供給元への送信・製造承認・印刷・書込み・本番公開は行っていません。

判断は [decision-register.md](decision-register.md)、未解決の証跡・環境・アクセスは [blocker-register.md](blocker-register.md) に分離しています。物理証跡の欠落は、設計判断や合格ではありません。

## 作業単位と次の行動

各作業は #15 に属する予定の E1–E5 です。子 Issue は未作成のため番号を割り当てません。元の #8/#10/#13/#17/#19/#20 は完了として閉じません。

| 作業 | worker | 現在の成果 / 状態 | 次の行動 |
|---|---|---|---|
| E1 基板 identity の結合 | e1_binding | PR #44、上記 exact head の CI/native PASS。機構コピーと canonical export、実基板 identity を結合。独立した fresh-native export check を維持 | merge の非デプロイ条件を正当に確認できるまで保留。追加変更後は新しい head で再検証 |
| E2 exact-part 証跡 | e2_research、親の統合 | 一次資料と supplier CAD を取得・検査。独立レビュー指摘を修正、4 focused tests と circuit/catalog PASS | 統合CIを新headで検証。locatorの表記を修正し、build/check/site scan PASS |
| E3 SWD 治具 | e3_fixture | `fixture/manifest.json` は BLOCKED。CadQuery 2.7.0 の carrier-only STEP/寸法図と候補部材はあるが、完成治具ではない | 登録公差、fresh-native 部品 extents、支持・逆挿入防止・load path/travel stop を解決してから完全設計を検証 |
| E4 調達・組立台帳 | e4_ledger | `procurement/assembly-manifest.json`、71 unique fitted placements / 81 pieces。12 focused tests と生成チェック PASS、独立レビュー済み。工程用準備資料のみ | E2/E3 入力変更後に再生成。供給/完成ケーブル/実装サービスの未確定を残す |
| E5 readiness・物理手順 | e5_readiness | 19 未実施手順、17 tests（normal/-O）PASS、独立レビュー済み。`--check` は VALID/BLOCKED、`--gate` は exit 1 | 最終 E2/E3/E4 入力で再生成。現在49 blocker、観測は全て NOT_MEASURED |

## 2026-11-09 時点の artifact identity（履歴）

現行値は末尾の 2026-11-11 節を参照。この表は上記 head に加えて存在するローカル生成物の記録であり、main への統合や製造承認を意味しません。入力が変わったら E3→E4→E5 の順で再生成して更新します。

| 成果 | SHA-256 |
|---|---|
| A5 firmware BIN（継承、書込みなし） | `0446cb0acfa7efe86a5f6c02beb7afa482daa419ecfce204fe9169487599765e` |
| `engineering/a7/fixture/manifest.json` | `9109acd79096d832bfc31b1a44e389c4cbed6028dd86a3072b8f1b412169ff69` |
| `engineering/a7/procurement/assembly-manifest.json` | `69033523efa1ec2da53093c6814c3522ef0264adbc084f1fac3c3980c86e3967` |
| `engineering/a7/qualification/readiness.json` | `5617a908a44cc499b0bacb8cdfabdb739f6a3ac9366782287e21a876b3290d0f` |

物理手順は `engineering/a7/qualification/procedures.md`、未実施テンプレートは `run-template.json`、未送信の質問は `supplier-questions.md`。治具の STEP は carrier の形状検討であり、完成 jig の納品ではありません。

## 開始時の確認と環境上の限界

A5 seed は 786 ファイル / 83,093,114 bytes で PASS。circuit check は PASS（32 lines / 74 declared placements）。manual inventory のため回路図・配置の照合はせず、CAD pin-asset check は SKIP。
Node 24.19.0 / Python 3.12.14 / Corepack の pnpm 11.5.2 を使用。初回は環境の既定 pnpm 11.19.0 だったため、11.5.2 で再確認。native lock は current。
main の既存 CI 42508822486 は基準 SHA での履歴証跡です。新しい E1 の証跡は上記 PR CI を参照します。

ローカルの digest-pinned KiCad image 取得は32 GBディスクを満たし、native 実行は ENOSPC で失敗しました。取得したimageを除去して容量を回復しましたが、このローカル実行は PASS ではありません。E1 exact head の native 検証は既存 GitHub Actions で成功しました。これは物理測定や E3 の未取得形状を代替しません。

## 子 Issue の下書き（未作成）

各項目の親は #15。元の物理評価 Issue を閉じるものではない。

### E1: Bind mechanical verification to current authoritative PCB

対象: mechanical layout、native facts/export producer、機構入力・レポートと回帰テスト。関連 #17 / #19。
依存: 現在の main と baseline。
完了条件: actual PCB → fresh native facts → canonical export → mechanical report を結び、欠落・不正・古い identity、古いコピー、両 JSON の同時改変を適切な検証段階で拒否。既存の外形・固定部品・keep-out・裏面・厚さ検査を維持。
検証: 変更前の再現、負のテスト、native gate/controls、再生成で銅箔不変、A5 seed。物理適合は未評価。

### E2: Recover exact-part sources and actionable supply evidence

対象: PCM13SMTR、PJ-324M、現行実装の部品証跡、WS2812B-2020-V6。関連 #9 / #13 / #19。
依存: 正確な型番と共有カタログの直列更新。
完了条件: 実際の資料 bytes/hash/revision/page、図面検査、supported facts のみ更新。文書権威・接点・適合・在庫・実装サービスを区別し、取得失敗も記録。
検証: sync-states/selection/generation、circuit/catalog と必要な native/electrical/mechanical review。実機・ロットの合格は主張しない。

### E3: Design revision-bound digital SWD pogo fixture

対象: fixture source、STEP、寸法図、probe/receptacle/materials、配線。関連 #19 / #10。
依存: E1 の正しく結ばれた export と exact primary probe data。
完了条件: B 面 TP1–TP5 の現在座標、座標変換、逆挿入防止、裏面部品 relief、PCB 支持、travel stop、stroke/force、最悪登録誤差を数値で示す。
検証: CadQuery 2.7.0 で実生成・形状確認・identity/clearance tests・独立レビュー。造形・接触・実荷重は未評価。

### E4: Generate active A7 procurement and assembly ledger

対象: controller、FR-4 leaf ×2、adapter、完成ケーブル、PMMA/PETG、M2×18、fixture。関連 #8 / #9 / #10。
依存: 現在の design/identity と E3 materials。
完了条件: 全 fitted ref を一度ずつ照合、DNP/test pads を区別、2 枚乗数、obsolete parts/重複/欠落/stale identity を検出。power cable は layout.json から取得。未取得の価格・在庫は unknown。
検証: 再現生成と mutation tests、A5 seed。承認済み supplier upload ではない。

### E5: Prepare revision-bound readiness and physical procedures

対象: Workflow F に沿う小さい readiness 検査、空の物理手順、未送信の質問、継続資料。関連 #8 / #10 / #13 / #17 / #19 / #20。
依存: E1–E4 の成果と #10 の release gates。
完了条件: BLOCKED report の schema pass と order/release eligibility を分離。board/population/firmware/config/raw evidence を結び、missing/stale/negative/unapproved を拒否。観測は NOT_MEASURED、PET/2HP は別。prototype を得るための owner-approved route を明記。
検証: wrong revision/firmware、stale material、raw evidence 欠落、false completion の負のテスト、docs/site/browser。物理結果を作らず、release gate を緩めない。

## 統合検証

40 preparation tests、17 readiness tests normal/-O、28 mechanical tests、125 native tests normal/-O、A5/circuit/catalog、generator freshness、CadQuery 2.7.0 carrier geometry は PASS。公開サイト build/check/site scan は PASS。ブラウザは当初pinned binary未導入で失敗したが、導入後のauthored-site checksとframework 16 viewport/theme navigationsはPASS（viewer機能は対象なしでSKIP）。これらは完成治具/物理合格ではありません。

E1 CIログでは `ENABLED` は空でした（2026-11-09T09:35:50Z）。ただし設定APIは404、protected-policy accessを迂回せず、最終headのmerge条件は未確定のまま保留します。

統合commit `ec75bdd40dadaaae2f8193a30b78fc1c89d92082` のCI 42595823301で、R1の古い2テストがPCM一次資料未取得を固定期待していたことを検出。ローカルでも再現し、実取得hash/authorityとidentityの期待値に更新。物理coverage OPENの負の検査は維持。最終headの結果はPR #44のchecksを参照。

## 2026-11-11 統合（PR #44）

- 作業: Claude Code Cloud Project の単一 manager が PR #44 を引き継ぎ、main `33457b01c5722d91b9ab5b25e8e73c097b32236b`（orchestration 文書のみ追加）を merge。E1–E5 を作り直さず、全差分を独立レビュー。
- レビュー指摘の修正: readiness で 1 つの保持ファイルが複数の承認役割（基準レビュー、実施レビュー、材料出典、試作承認、製造リリース承認、レビュー済み発注ファイル）や複数手順の raw evidence を兼ねることを、解決後のファイルと内容 hash の両方で拒否（`receipt reused across roles`）。fixture manifest が `carrier-study.step` の bytes を `study_step_sha256` で結合し、STEP の差し替えを `--check` で検出。PCM13SMTR の記述の空白欠落を修正。上の「uncommitted」表現と E1 のみの記述を producer から更新。
- 未修正として残すもの: 材料観測の `valid_until` に上限期間がない（期間の方針は未決のため数値を創作しない）。E2 で記録した資料 hash は ignored cache の bytes に依存し、CI では再計算できない。
- native CI: 準備 head `f0b1d8aa37f3967ccc8c9a6bd6ca0e7b7fc7b3a0`（base `af523f9`、synthetic merge `f3232a4`）の [run 42596523199](https://github.com/Takazudo/zudo-led-block/actions/runs/42596523199) は全 job PASS。統合 head の結果は PR #44 の checks を参照。
- artifact: 2026-11-09 の Forbidden は当時の観測。2026-11-11 に run 42596523199 の `native-infrastructure-evidence`（ID 13663737750、ZIP SHA-256 `33f3d9121164f364b0325540b161e9546ddf73c8b723c9166fdcd8a19867cf0e`、43 members）を取得できた。A7 候補は `a7-gate/summary.json` のみで、summary が hash を記録する `board_facts.json` / `board_geometry.json` は含まれない。これは保存範囲の不足で、別の CI 修正で扱う。`fresh_native_verified` は false のまま。
- merge と deploy（B1/D5 の再確認）: 変数 API の 404 自体は保護規則の証拠ではない。main push の [run 43051871789](https://github.com/Takazudo/zudo-led-block/actions/runs/43051871789)（2026-11-11T15:59Z）の deploy-gate ログで `ENABLED` は空、Production deploy は SKIPPED。workflow は `CLOUDFLARE_DEPLOY_ENABLED == 'true'` の場合だけ deploy する。したがって owner が依頼した通常の merge は deploy を起動しない。hosting 設定は変更していない。
- 子 Issue 作成の hold（B2/D6）は維持。この作業は #15 と既存 Issue を使う。

| 成果（2026-11-11 統合時） | SHA-256 |
|---|---|
| `engineering/a7/fixture/manifest.json` | `52266a19a09d0f3c282da2297a4000f904044a4c0f0cb402c2822f1525a2f808` |
| `engineering/a7/procurement/assembly-manifest.json` | `69033523efa1ec2da53093c6814c3522ef0264adbc084f1fac3c3980c86e3967` |
| `engineering/a7/qualification/readiness.json` | `7bb5f9d8af782a5e07a81ef7d371c4afc829fee3e7a986393ee45d30f0e206df` |

2026-11-11 追記: PR #45 で CI artifact が A7 候補の `plan.json` / `board_facts.json` / `board_geometry.json` を保持し、`scripts/a7_native_artifact.py` が検証するようになった（上の保存範囲の不足は解消）。PR #46 で治具用 native geometry を `fixture/native-geometry.json` に記録し、fixture manifest が TP1–TP5 を照合する。`fresh_native_verified` と `digital_fixture_complete` は false、order gate は BLOCKED のまま。この時点の fixture manifest は `38dde81d2bcce1b61cc66763f3bd3f0f5bb470f4b3c08bdeedcb0c6995df81f5`、readiness は `418ad365a774635427339019bcd05d27e001ca730e85d9df559d0c1b1b941ba2`（procurement は不変）。

## 2026-11-11 W3: 発注パッケージの監査と物理手順の実行準備

- 基準 main: `eccbae4`（PR #46 の merge）。作業ブランチ `claude/project-thread-eroz5e`。権威基板 `4453f818…628e` は変更していません。
- **監査で直したもの（producer 経由）:**
  - 実装方式と面: 台帳はコントローラーの SMD/THT と面を native geometry（`fixture/native-geometry.json`、権威基板の SHA に結合）のパッド属性から、リーフとアダプタは不変 A5 の配置データのパッド属性から取るようにした。コントローラーは F 面 SMD 31・B 面 SMD 25・F 面 THT 3（J1、J2、J5）。以前の「SMT と THT」という記述は、B 面にも SMD があることを示していなかった。
  - ケーブルのピン対応: 電源ケーブル（A1→B3 / A2→B2 / A3→B1）と SH4（コントローラー J3 → 左リーフ J1）を手書きの文字列ではなくネットリストから生成し、ネットが合わなければ失敗するようにした。手書きの記述は正しかったが、検証されていなかった。
  - 未解決事項を 9 件に分け、何で解除できるかの区分を付けた。
  - 実装する型番数 30 を台帳に記録。71 配置 / 81 実装点、基板と MPN/LCSC は native board・ネットリスト・カタログと一致（不一致なし）。
- **照合して一致したもの:** 64 footprint の ref・面・footprint・MPN/LCSC が権威基板と台帳で一致。TP1–TP5 は基板で exclude_from_bom/pos。電源ケーブルの自由長 57 ± 3 mm（±3 は ASSUMED）、M2×18、FR-4 リーフ ×2 は現行の機構記録どおり。
- **物理手順:** 19 手順に準備物、計器、実施前の条件、手順、raw 証跡の記録項目、受入値を追加。受入値は部品 fact・設計記録・引用と照合し、確度（SOURCED / MIRROR / UNVERIFIED / INFERRED / DESIGN / ASSUMED / UNRESOLVED）が出典と違えば生成が失敗する。`qualification/run-templates/` に手順ごとの記録雛形を生成。すべて NOT_MEASURED のまま。
- **オーナーのチェックリスト:** `doc/src/content/docs/project/order-checklist.mdx`（生成物）に、オーナーにしかできない 10 項目と、それぞれが解除するゲートを記載。
- readiness は 57 ゲート / 58 理由（以前は区分なしの 49 理由。増えたのは台帳の未解決事項を 1 件から 10 件に分けたため）。W1（#47）と W2（#48）を取り込んで fixture → procurement → readiness の順で再生成。W2 で PJ-324M の寸法・定格が一次資料で確認され、受入値の確度は検査により MIRROR から SOURCED に変わった。order gate は BLOCKED のまま。
- 独立レビューの指摘を修正: 出典は部品 fact（fact_id のみ）と設計記録に限定し計画・生成物は引用不可、記録が値の隣に書く確度はすべて強制、引用行の ASSUMED/INFERRED も強制、引用値は語単位で一致、比較の向き `bound` を必須化、電源ケーブル範囲 54–60 mm を ASSUMED に訂正、ねじ噛み合い手順を rear-pocket 構成に合わせた、cv-thru-calibration をオーナー判断・partial-rails と fixture-contact を外部証跡待ちに再分類、リーフ間 SH4 のピン対応もネットリストから生成。

## 2026-11-11 W6: 合否基準

- 基準 main: `5b9db66`（PR #49 の merge）。作業ブランチ `claude/project-thread-eroz5e`（main から作り直し）。権威基板は変更していません。
- **導出した受入値:** power-current（VLED 電流制限 343.3–439.4 mA、通常点灯はその下限未満、+3V3 3.267–3.333 V、+5 V 4.95–5.05 V）、startup-reset（LED_EN_N ≥ 1.1 V で無効、≤ 0.66 V で有効、有効化は初期化から 100 ms 以降、黒フレームまで 5 ms 以上、ADC 待ち 250 ms、VDDA 3000–3600 mV、観測窓 260 ms 以上（SW1 が有効位置のとき）、FAULT 後の再有効化なし、保持マーカーが残るリセットでは起動しない）、u7-stress（電源 1.8–5.5 V、入力 ±0.5 V / 10 mA の絶対最大、R7 電流の計算上限 0.313 mA は PROPOSED）。すべて NOT_MEASURED。
- **提案値と採用:** オーナー判断の手順に PROPOSED を用意し、独立レビューが確認したものをコーディネーターが採用（7 手順。オーナー本人ではない）。残る提案は 7 件。採用は受入値のダイジェストに結び付き、値を変えると基準ゲートが再び閉じる。
- **外部証跡待ち:** 7 手順の未決値に、決め手になる資料または測定を記録。
- **チェックリスト:** オーナーの作業を 1 つの順序付きリスト（11 項目）にし、提案値の一覧を追加。
- readiness は 50 ゲート / 63 理由（CLOUD_DIGITAL 2、OWNER_DECISION 12、ACCESS_EVIDENCE_HOLD 16、PHYSICAL_ONLY 20）。order gate は BLOCKED のまま。
