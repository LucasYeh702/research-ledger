# Research Ledger 與 Git：為什麼你可能需要兩者

> 「我已經用 Git 管理論文了，為什麼還需要 Research Ledger？」

這是合理的問題。Git 是極為優秀的版本控制系統，許多研究者已經用它管理論文原始碼和程式碼。這份文件不是要說服你放棄 Git，而是說明兩者解決的問題不同，以及在 AI 協作研究的場景下，它們如何互補。

---

## 設計目標差異

**Git** 是通用版本控制系統，設計用於追蹤檔案變更、支援分支合併、多人協作。它記錄的核心單位是 **commit**——一組檔案在某個時間點的整體狀態。Git 不關心你為什麼做出這些變更，也不區分人類寫的段落和 AI 產生的草稿。

**Research Ledger** 是研究語意記錄工具，設計用於記錄研究過程中的事件——命題（claim）、AI 輸出（ai_output）、來源查核（source_check）、人工裁決（adjudication）——並產生可驗證的審計軌跡（audit trail）。它記錄的核心單位是 **event**——一個帶有明確語意類型、密碼學簽章、內容快照的結構化記錄。

簡言之：Git 追蹤檔案的演進歷史；Research Ledger 追蹤研究決策的演進歷史。

---

## 功能對照表

| 功能 | Git | Research Ledger |
|:---|:---|:---|
| **版本追蹤** | File-level：每次 commit 是整個 repo 的快照 | Event-level：每次 record 是單一檔案的獨立快照 |
| **事件語意** | 自由文字 commit message，格式由團隊自訂 | 結構化 `event_type`（`claim`、`ai_output`、`source_check`、`adjudication`、`delete`、`rename`） |
| **AI 使用揭露** | 無內建支援；需手動整理 commit history | 內建 `export-disclosure`，一個指令產生揭露草稿（Markdown 或 JSON） |
| **密碼學簽章** | 選用：`git commit -S` 搭配 GPG/SSH key | 強制：每個 event 皆以 Ed25519 簽章，key binding 寫入 genesis 信任根 |
| **防篡改偵測** | Commit DAG 的 SHA hash chain；搭配 remote、signed commits/tags 時更容易發現歷史重寫，但本地歷史仍可被重寫 | 線性 hash chain + Merkle seal；append-only 設計，修改任一 event 會造成簽章、event hash 或鏈結檢查失敗 |
| **內容快照** | 整個 repo 的完整快照（透過 tree object） | 每個 event 獨立的 immutable snapshot，搭配 streaming SHA-256 hash |
| **多人協作** | 完整支援：remote repo、push/pull、PR review | 不支援：local-first only，v0.1 僅限單機單人 |
| **分支合併** | 完整支援：branch、merge、rebase | 不支援：append-only 線性記錄，無分支概念 |
| **工作筆記演進** | 追蹤所有變更差異（diff） | 記錄 event 時刻的快照；工作檔後續修改會在 verify 時產生 warning（非 failure） |
| **揭露報告自動化** | 無 | `export-disclosure` 自動產生事件摘要、類型統計、seal root、已知限制 |

---

## Research Ledger 內建而 Git 需要自行設計的事

### 1. 結構化事件語意

Git commit message 是自由文字。你可以寫「加了 AI 建議的段落」，也可以寫「fix typo」——Git 不會區分兩者。

Research Ledger 的 `event_type` 是結構化分類。當你用 `--type ai_output` 記錄一個事件，這個語意標籤會被寫入簽章範圍內的 event payload，無法事後偷改為 `claim`。這讓後續的揭露報告、審計查詢都能精確過濾。

### 2. 自動 AI 使用揭露報告

```bash
research-ledger export-disclosure --output disclosure.md
```

一個指令，Research Ledger 就會讀取本地 ledger，產生一份包含以下內容的揭露草稿：

- Ledger ID 與 schema 資訊
- Genesis hash 與 trusted key ID
- 驗證狀態（通過 / 警告 / 失敗）
- 各 event type 的數量統計
- 每個 event 的摘要（路徑、hash、時間戳）
- Seal root 摘要
- 明確列出的工具限制

這份草稿不是最終揭露文件——它是結構化的起點，讓研究者在此基礎上編輯、補充，再依照各自機構的要求提交。

### 3. 每事件獨立快照與內容雜湊

Git 的 commit 是整個 repo 的狀態快照。要驗證「這個 AI 輸出在當時確實是這個內容」，你需要 checkout 到那個 commit，再找到對應檔案，或自行建立約定好的檔案與 commit message 格式。

Research Ledger 的每個 event 都有獨立的 `snapshot_path` 和 `content_hash`（SHA-256）。快照是 immutable 的副本，存放在 `.research-ledger/snapshots/` 下。你可以不依賴 repo 的整體狀態，獨立驗證任何一筆記錄的內容完整性。

### 4. 工作筆記漂移偵測

研究筆記會持續演進——這是正常的。Research Ledger 明確區分兩種情況：

- **Warning**（exit code 1）：快照完好，但工作檔的內容已與快照不同。這代表筆記在記錄後被正常編輯。
- **Failure**（exit code 2）：快照本身被篡改、簽章不合法、或 hash chain 斷裂。這代表記錄的完整性被破壞。

Git 不會做這種區分——檔案要麼被追蹤，要麼不被追蹤。

此外，若筆記是刻意刪除或改名，可用 `delete` / `rename` lifecycle event 明確記錄，抑制舊路徑的假警報，同時保留原始 snapshot 歷史。

### 5. Merkle 封印

```bash
research-ledger seal --label "投稿前里程碑"
```

Seal 會對目前所有 event hash 計算 Merkle root，產生一份摘要指紋。Merkle tree 使用 domain-separated hashing，奇數 leaf 向上提升而非複製，避免 last-leaf duplication 攻擊。

這提供一個本地里程碑的完整性指紋——即使後續新增更多 event，seal 的 Merkle root 仍可重新計算驗證。若要讓它成為更強的外部時間錨定，仍需要 OpenTimestamps、Git signed tag 搭配公開 remote，或其他第三方發布紀錄。

### 6. 生命週期事件

`delete` 和 `rename` event 明確記錄筆記路徑的刻意變更。它們產生 immutable 的 synthetic snapshot（包含 lifecycle action 的 canonical JSON），抑制舊路徑的 drift warning，但不會刪除或修改歷史 snapshot。

Git 的 `git rm` 和 `git mv` 也能記錄刪除和改名，commit message 也可以說明原因；差別在於 Git 沒有內建 `delete` / `rename` 事件 schema，也不會把 `reason` 當作可驗證事件欄位處理。

---

## Git 做了什麼 Research Ledger 做不到的事

Research Ledger 不是 Git 的替代品。以下是 Git 的核心能力，v0.1 的 Research Ledger 完全不具備：

### 1. 分支與合併

Git 的 branch/merge/rebase 支援平行開發線，讓你同時探索不同方向，再合併成果。Research Ledger 是 append-only 的線性記錄，沒有分支概念。

### 2. 遠端同步

Git 的 remote repository 讓你在多台電腦、多人之間同步工作。Research Ledger v0.1 是 local-first only，ledger 資料僅存在於本機。

### 3. 差異比較（diff）

`git diff` 提供逐行變更追蹤，讓你精確看到每次修改了什麼。Research Ledger 只記錄事件時刻的完整快照，不提供兩次快照之間的差異比較。

### 4. 大型專案管理

Git 能高效追蹤數千個檔案的變更歷史，包括二進位檔案（搭配 Git LFS）。Research Ledger 是事件級記錄工具，不適合大量檔案的批量追蹤。

### 5. 生態系統

Git 擁有龐大的生態系統——GitHub、GitLab、CI/CD pipeline、PR review、IDE 整合、自動化測試。Research Ledger 是一個小型命令列工具，沒有這些整合。

---

## 建議的互補使用方式

以下是一個實際的工作流程，展示兩者如何搭配使用：

### 步驟 1：用 Git 管理論文原始碼和程式碼

```bash
git init my-paper
cd my-paper
git add paper.tex analysis.py data/
git commit -m "初始論文架構"
```

Git 負責檔案版本控制、分支管理、與共同作者的協作。

### 步驟 2：用 Research Ledger 記錄研究過程中的 AI 互動和人工決策

```bash
research-ledger init
research-ledger record notes/hypothesis.md --type claim
research-ledger record notes/gpt-summary.md --type ai_output
research-ledger record notes/source-verification.md --type source_check
research-ledger record notes/decision.md --type adjudication
```

Research Ledger 負責記錄你的研究過程——哪些是你自己的命題、哪些是 AI 產出、你怎麼查核來源、最終怎麼判斷取捨。

### 步驟 3：在提交論文前產生揭露草稿

```bash
research-ledger export-disclosure --output disclosure.md
```

檢視產生的草稿，補充機構要求的額外資訊，編輯後作為正式揭露文件提交。

### 步驟 4：管理 `.research-ledger/` 與 Git 的關係

你有兩個選擇：

- **排除**：在 `.gitignore` 中加入 `.research-ledger/`，ledger 僅保留在本機。適合 ledger 包含敏感 AI 對話的情況。
- **選擇性提交**：提交 `ledger.json`、`genesis.json`、`events.jsonl`、`seals/`，以及在內容可公開時提交 `snapshots/`。若不提交 snapshots，第三方仍可檢查事件鏈與簽章，但無法完整驗證每筆 `content_hash` 對應的原始內容。無論哪種方式，都必須確保 `private_key.pem` 始終被排除（Research Ledger 已在 `.research-ledger/.gitignore` 中自動排除私鑰）。

### 步驟 5：用 Git signed tags + Research Ledger seals 雙重標記里程碑

```bash
# Research Ledger 封印
research-ledger seal --label "v1-submission"

# Git 簽署標籤
git tag -s v1-submission -m "投稿版本，seal root: $(jq -r .merkle_root .research-ledger/seals/*.json | tail -1)"
git push origin v1-submission
```

這樣你同時有 Git signed tag 提供身分簽章與公開發布線索，和 Research Ledger seal 提供事件級的 Merkle root 完整性指紋。請注意：Git signed tag 本身不等於可信時間戳；若要更強的時間證明，應加入 OpenTimestamps 或其他外部 timestamping 機制。

---

## 一句話總結

> Git 記錄你**改了什麼**；Research Ledger 記錄你**為什麼這樣做**、**AI 說了什麼**、**你怎麼判斷的**。

兩者不衝突。Git 管理你的檔案歷史；Research Ledger 管理你的研究決策歷史。在 AI 深度參與學術研究的今天，後者正在成為負責任研究實踐的一部分。
