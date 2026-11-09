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

## 現在のローカル artifact identity

この表は上記 head に加えて存在するローカル生成物の記録であり、main への統合や製造承認を意味しません。入力が変わったら E3→E4→E5 の順で再生成して更新します。

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

## 統合検証（commit前）

40 preparation tests、17 readiness tests normal/-O、28 mechanical tests、125 native tests normal/-O、A5/circuit/catalog、generator freshness、CadQuery 2.7.0 carrier geometry は PASS。公開サイト build/check/site scan は PASS。ブラウザは当初pinned binary未導入で失敗し、導入後の再検証が必要。これらは完成治具/物理合格ではありません。

E1 CIログでは `ENABLED` は空でした（2026-11-09T09:35:50Z）。ただし設定APIは404、protected-policy accessを迂回せず、最終headのmerge条件は未確定のまま保留します。
