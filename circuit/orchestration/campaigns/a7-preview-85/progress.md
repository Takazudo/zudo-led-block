# A7 preview/status — issue 85

Manager: Codex Cloud delegated from parent thread `6afb1f7f-4754-8191-a429-d7231953e0ee`; no incumbent preview task found. Selected VM only. Session model routing not independently observable. Single writer/integrator, one local heavy job; no compute fan-out or manual Actions dispatch. Shared account quota/peer occupancy unknown; ordinary repository PR/main CI only.

Initial: fresh clone `/workspace/zudo-led-block`, clean `main` at `0c19fea8afe356fc993570e969742e774b7a9914`; one worktree, no prior local branches/work. Remote pre-existing branches retained, notably A6 `claude/project-thread-391rx3` / draft PR 14 at `7e96380be4fbea2bfcc4a5bd1d5721272a5a141f`. Only open PR 14. Open issues 7–13 and 15. Task branch `codex/a7-assembly-preview-85`.

Environment startup: host workspace instructions supplied portable paths; explicit loader verified snapshot `d49195e0…6661`, source `67f64089…4317`. Runtime restoration skipped; native registration not claimed. Loader stdout recovered in chunks after truncation. Node 24.19.0, Corepack pnpm 11.5.2 (shell fallback 11.19.0 not used), frozen lock installed, Playwright 1.63.0. Corepack default cache missing; task cache `/tmp/a7-corepack`. No HOME/CODEX_HOME changes. Referenced css-wisdom absent from bundled/project skills; no substitute skill claimed.

Resources observed: cgroup RAM 16 GiB, initial current 1.1 GiB; CPU quota 4; 30 GiB disk free; no swap. Budget: one heavy run, 900 seconds each, target <4 GiB plus >8 GiB reserve; one transient retry only when diagnosed. Heavy/browser guards from installed portable profile use shared VM directories `/tmp/agent-guard/heavy` and `/tmp/agent-guard/playwright` (native home directory unavailable); no other launched worker processes. Evidence in local ignored `test-results/`, temporary logs `/tmp/a7-*`; browser CI artifacts use existing retention 3 days.

Baseline circuit:check PASS: manual inventory 33 lines / 74 declared placements unverified; CAD disabled, pin-asset SKIP. Baseline CI run 43569596410 passed on main; production skipped. Current-head results required separately.

Implementation: source GLBs untouched, 3HP hash `b6718dbdcc0eb8c50cb0e452331a2972f2cfd6adb3626d4783a634ac24c006d4`, 1,662,464 bytes. Separate A7 selection and generated manifest; publication producer extended, no A5 page/seed changes. Three.js 0.180.0 / esbuild 0.28.2 pinned, licence copied locally, no runtime CDN. GLB mm coordinates + export rotation explicitly handled. Native iframe requires no message protocol; renderer lazy, close/pagehide disposes. #15 corrected with dated post-#82 status; readback verified.

First focused test caught an erroneous expected asset count (10 actual, corrected); first build caught CSS-spelled style requirement (`border-radius`, corrected). Neither failure is a baseline or infrastructure failure.

Hosting: existing PR/main workflow inspected. Deployment condition requires main push/dispatch, successful checks and CLOUDFLARE_DEPLOY_ENABLED=true. `gh variable list` returned HTTP 403 Resource not accessible by integration; setting not changed or retried. Latest observed main production job skipped. Existing automatic effects disclosed; no separate deploy or hosting activation authorized/performed. Physical/order/manufacturing work excluded.

Remaining: rendered acceptance/screenshots, full checks, independent review, current-head CI, policy-eligible merge, post-merge outcome and terminal cleanup audit. Issue 85 alone may close on verified integration. All existing held/hardware/publication issues remain open.
