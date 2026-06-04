# GPT-5.5 Pro 外部審查結果分流

日期：2026-06-03

來源：本地外部審查回覆（原始檔未納入公開 repo）

## 總體判讀

GPT-5.5 Pro 的結論是：Research Ledger 值得繼續、值得開源，也有足夠技術性與創新性；但若要以 provenance / tamper-evident 工具公開，公開前必須先補 P0 hardening。

這份審查有一個限制：reviewer 沒看到完整 repo，只根據審查包判斷。因此部分建議已經在目前 repo 中完成或部分完成，不能直接照單全收。

## P0 分流

| 項目 | reviewer 建議 | 目前 repo 狀態 | 分流 |
|---|---|---|---|
| P0-1 path containment | symlink / hardlink / junction / `.research-ledger/` 內部檔案安全邊界 | workspace 外路徑已拒絕；symlink 指向外部通常會因 `resolve()` 被拒；但 `.research-ledger/` 內部檔案與 non-regular file 還需要更硬 | 採納，優先做 |
| P0-2 signature / event hash contract | 明確 canonicalization、signature payload、event hash payload，並補 tamper matrix | `SPEC.md` 已描述主要規則；測試已有多種 tamper，但還沒有完整欄位矩陣 | 採納，補測試與規格摘要 |
| P0-3 security / provenance disclaimer | README、SECURITY、disclosure exporter 都要明確限制 | README / SECURITY 已有基本限制；disclosure exporter 還可更明確加入「非研究品質認證、非合規結論」 | 採納，補 disclosure disclaimer |
| P0-4 release gate / clean install smoke | ruff、pytest、build、wheel install、CLI smoke | 本地已跑過；CI 目前主要是 pytest，尚未把 build / wheel smoke / ruff 全部納入 | 採納，補 CI |
| P0-5 verify exit code semantics | 明確 warning/fail/usage/uninitialized/internal | `SPEC.md` 已有 exit code table；CLI 測試已有部分覆蓋；README 還不夠顯眼，且 reviewer 建議的語意和目前設計不同 | 部分採納：先補文件與測試，不立刻改 exit code contract |
| P0-6 atomic write / file locking | record/seal lock、atomic append、temp rename | snapshot 已用 pending file + replace；events append 尚未 lock；seal JSON 仍可改為 temp + replace | 採納，但可在 P0 第二波做 |

## P1 分流

| 項目 | 分流 |
|---|---|
| third-party audit bundle / verifier workflow | 採納。這會大幅強化 provenance 敘事，建議排在公開後第一個 feature。 |
| key loss / compromise recovery guide | 採納。文件成本低，安全價值高。 |
| README 3 分鐘 demo + tamper demo | 採納。公開前應補。 |
| disclosure templates | 採納但不必公開前完成；先補 disclaimer 與現有 exporter 品質。 |
| PyPI / GitHub release preparation | 採納。先補 release checklist 與 wheel smoke，不急著發 PyPI。 |
| dependency / supply-chain hygiene | 採納。CI 可加入 dependency audit，但不必阻塞第一個 public preview。 |

## P2 分流

| 項目 | 分流 |
|---|---|
| OpenTimestamps | 採納為長期方向，不做 v0.1 公開前 P0。 |
| Git signed tags integration | 採納為可選 integration，但文件必須避免把 signed tag 說成可信時間戳。 |
| Obsidian plugin | 採納為 adoption feature，不先於 core verifier hardening。 |
| multi-actor identity model | 採納為 v0.3+，目前 single-user local-first 先成立。 |
| hardware-backed key storage | 加分項，不列入近期。 |
| OpenAI API assisted event extraction | 加分項，且必須保持 core ledger 不依賴雲端。 |

## 建議下一步

先做「公開前 P0 第一波」：

1. `record` 禁止 `.research-ledger/` 內部檔案與 non-regular file。
2. 補 symlink / internal ledger / tamper matrix 測試。
3. disclosure Markdown / JSON 加強 disclaimer。
4. README 加 `What this proves / does not prove` 與 3 分鐘 demo。
5. GitHub Actions 加 ruff、build、wheel install smoke。

第二波再做：

1. event append lock。
2. seal temp write + atomic replace。
3. release checklist。
4. key loss / compromise guide。
5. sample audit bundle 或 export-bundle prototype。

## 完成狀態（2026-06-03）

已完成：

- `record` 禁止 `.research-ledger/` 內部檔案、symbolic link 與 non-regular file。
- 新增 write lock，保護 record / delete / rename / seal 的寫入流程。
- seal 改為 pending file + atomic replace。
- 新增 `verify --no-working-tree`，支援只驗證 immutable ledger/snapshot 的 archive 場景。
- 新增 `export-bundle --output ...`，輸出不含 `private_key.pem` 的第三方 audit ZIP。
- 新增 release checklist、key management guide、audit bundle guide、dependency policy。
- GitHub Actions 加入 ruff、pytest、build、wheel install smoke、export-bundle 解壓驗證。
- README / README.zh-Hant 補「能說明什麼／不能證明什麼」與三分鐘 demo。
- disclosure export 加入非研究品質認證、非合規結論的明確限制。

仍列為後續方向：

- disclosure templates。
- OpenTimestamps。
- Git signed tag integration。
- Obsidian plugin。
- multi-actor identity model。

## 不直接採納的地方

- 不立刻改目前 exit code contract。現有設計是 `0=pass`、`1=warnings`、`2=tamper/signature invalid`、`3=malformed/uninitialized`、`4=snapshot missing`，已在 `SPEC.md` 中成形。可先補文件與測試，之後若要支援 CI 可另加 `verify --strict`。
- 不把 OpenTimestamps、Git signed tags、Obsidian plugin、AI extraction 放進公開前 P0。這些能加分，但會分散目前最重要的 verifier hardening。
