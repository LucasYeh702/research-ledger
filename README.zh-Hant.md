# Research Ledger

Research Ledger 是一個本地優先的研究留痕工具，用來把 AI 協作研究過程轉成
可驗證、可簽章、可偵測篡改的紀錄。

它不證明命題為真，不保證來源可靠，也不保證作者完整記錄所有步驟。它只在
明確信任假設下，偵測已記錄事件與引用檔案是否在記錄後被改動。

## 它能幫助說明什麼

- 已記錄的 snapshot 在記錄後是否保持不變。
- 事件是否依 hash chain 依序連接。
- 事件是否由 ledger 綁定的本地 Ed25519 key 簽署。
- 本地 Merkle seal 是否能摘要已記錄事件 hash。
- 工作筆記可以繼續演進；內容漂移會以 warning 呈現。

## 它不能證明什麼

Research Ledger 不證明命題為真，不保證來源可靠，不保證作者完整記錄所有研究
步驟，不保證 AI 使用已完整揭露，也不代表任何法律、學校或期刊規範的證據能力
或合規結論。

在沒有外部錨定時，若某人同時控制私鑰與所有本地檔案，他可以重寫一份內部一致
的新 ledger。

它適合：

- 使用 Obsidian 寫論文或研究筆記的人
- 需要揭露 AI 使用過程的研究者
- 想保留命題、來源查核、AI 輸出、人類採否理由的人
- 想示範 responsible AI research workflow 的開源專案

## 三分鐘示範

```bash
mkdir rl-demo
cd rl-demo
research-ledger init \
  --scope-title "AI 協作法學論文研究" \
  --scope-description "本 ledger 涵蓋本論文的研究命題、來源查核、AI 輸出、人類裁判、草稿與 AI 使用揭露。" \
  --include .

cat > claim.md <<'EOF'
# 命題
AI 輔助法學研究需要記錄研究過程，而不只是最後引用。
EOF

research-ledger record claim.md --type claim
research-ledger verify

printf "\n來源查核後修正。\n" >> claim.md
research-ledger verify

research-ledger record claim.md --type claim
research-ledger seal --label demo
research-ledger report
research-ledger export-disclosure --output disclosure.md
```

若在本 repo 內開發，請在指令前加上 `uv run`。

## 第一次啟動的研究範圍宣告

`research-ledger init` 會建立已簽署的 `.research-ledger/scope.json`。這是
第一次啟動時對研究筆記邊界與範圍的宣告，應先於任何研究事件記錄。

這份宣告應說明：

- 這條 ledger 對應哪一個研究計畫、論文題目或研究線。
- 哪些資料夾或筆記屬於研究範圍。
- 哪些資料夾或資料明確排除在外。
- 第三方 reviewer 應如何理解「有記錄」與「未記錄」的界線。

範圍宣告會被簽章、驗證，並放入 audit bundle。它不是完整記錄保證；它只定義
eligible research-note boundary，讓後續事件、揭露與第三方審查有可解釋的上下文。

建議以「一個研究案一個 ledger root」作為預設做法。若整個 Obsidian vault 裡
有些筆記有留痕、有些沒有，應把 ledger 範圍限縮到該研究案資料夾，並用
`--include` / `--exclude` 明確宣告。否則 reviewer 可能無法判斷未留痕筆記是
範圍外資料、暫存資料，還是選擇性遺漏。

## PDF 與附件

PDF 是正常研究來源，尤其在法學與學術寫作中，不應被視為禁止留存的資料。
Research Ledger 可以直接記錄 PDF，但 `record` 會保存完整 snapshot；若同一份
PDF 被反覆記錄，ledger 會依檔案大小線性成長。

一般文獻 PDF 建議保存在研究案資料夾中，並建立 `source_check` 或 manifest 卡，
記錄引用資訊、本機路徑、來源 URL / DOI、取得日期、檔案大小與 checksum。只有在
審計上需要保留該份 PDF 的精確本機副本時，才直接 record PDF 本體。

`export-bundle` 目前會包含所有已記錄的 snapshots；如果 snapshot 是授權文獻、
私人資料或指導教授限制分享的 PDF，審查包也會包含該 PDF。對外分享前必須先確認
是否有權分享。詳見 [docs/storage-policy.md](docs/storage-policy.md)。

## 第一版功能

- `research-ledger init`：初始化本地 ledger，產生 Ed25519 金鑰與研究範圍宣告
- `research-ledger record PATH --type claim`：記錄一份研究事件
- `research-ledger seal`：把目前事件封裝成 Merkle root
- `research-ledger verify`：驗證 hash chain、簽章與內容 hash
- `research-ledger report`：輸出簡短狀態報告
- `research-ledger export-disclosure`：輸出 AI 使用揭露草稿
- `research-ledger delete PATH --reason ...`：記錄筆記已被刪除
- `research-ledger rename OLD NEW --reason ...`：記錄筆記已被改名

`record` 只接受 ledger workspace 內的一般檔案；不會把工作區外的本機檔案複製進
snapshot。

工作筆記可以繼續演進。`record` 會保留當下 snapshot；後續修改 live note 只會讓
`verify` 產生 warning。若筆記是刻意刪除或改名，請用 `delete` / `rename`
留下 lifecycle event，避免舊路徑永久警告。

## 安裝與測試

```bash
uv sync --extra dev
uv run pytest
uv run research-ledger --help
```

## AI 使用揭露輸出

`export-disclosure` 會把目前 ledger 轉成揭露草稿，內容包含事件類型統計、
研究範圍宣告、紀錄檔案、驗證狀態、seal root 與工具限制。

```bash
uv run research-ledger export-disclosure
uv run research-ledger export-disclosure --format json --output disclosure.json
```

這份報告不是研究品質認證，也不是法律證據；它只是協助研究者整理 AI 協作與
人類採否流程的可檢查紀錄。

## 重要邊界

Research Ledger 是 **tamper-evident，可偵測篡改**，不是絕對防篡改。
它可以偵測事件被修改、順序被調換、snapshot 被改動。工作筆記可以繼續演進；
如果目前筆記和當時 snapshot 不同，`verify` 會回報 warning，而不是 fail。
本地 ledger 不能單獨阻止持有私鑰的人重寫整條歷史。後續版本可加入
OpenTimestamps 作為外部時間錨定，並加入 Git signed tags 作為公開里程碑與
身分簽章輔助；其中 Git signed tags 本身不等於可信時間戳。

公開使用前請先看：

- [SPEC.md](SPEC.md)
- [docs/threat-model.md](docs/threat-model.md)
- [SECURITY.md](SECURITY.md)
- [docs/migration.md](docs/migration.md)
- [docs/audit-bundle.md](docs/audit-bundle.md)
- [docs/key-management.md](docs/key-management.md)
- [docs/scope-declaration.md](docs/scope-declaration.md)
- [docs/storage-policy.md](docs/storage-policy.md)
- [docs/publish-runbook.md](docs/publish-runbook.md)
