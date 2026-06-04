# AGY Opus 4.6 開源前審查摘要

日期：2026-06-04

本文件是外部 AGY / Opus 4.6 審查結果的公開版摘要與處理紀錄。原始 agent transcript 含本機路徑與執行細節，不納入公開倉庫。

## 結論

外部審查結論：Research Ledger 可以朝 public preview 前進，但正式公開前應先修正本地檔案權限、CLI malformed ledger 行為與公開倉庫衛生問題。不建議在未完成這些項目前推送 PyPI 或大規模推廣。

## Findings 與處理狀態

### P0 Blocking

無 P0 blocking findings。

### P1-1 私鑰建立時存在權限時間差

狀態：已修正。

處理：
- 私鑰改用 `os.open(..., mode=0o600)` 建立，避免先寫入再 `chmod` 的時間差。
- 新增 POSIX 權限測試，確認 `private_key.pem` 為 `0600`。

### P1-2 `.research-ledger` 與 snapshot/seal 權限過大

狀態：已修正。

處理：
- `.research-ledger/`、`snapshots/`、`seals/` 建立或重開時強制為 `0700`。
- snapshot 與 seal 檔案建立時強制為 `0600`。
- 新增 POSIX 權限測試，確認目錄與產物檔權限。

### P1-3 CLI verify exit code 依賴錯誤字串比對

狀態：已修正。

處理：
- `VerificationResult` 新增 `issue_codes`。
- CLI `verify` 改用結構化 issue code 決定 exit code。
- 新增測試固定 `snapshot_missing` 與 `malformed` 的 exit code 行為。

### P1-4 Pydantic `ValidationError` 未被 CLI 捕捉

狀態：已修正。

處理：
- CLI 將 `ValidationError` 納入 malformed ledger 類錯誤。
- malformed `ledger.json`、`events.jsonl`、`scope.json` 會以 exit code 3 結束，且不輸出 Python Traceback。
- 新增對 `verify`、`report`、`export-disclosure` 的 malformed 測試。

### P1-5 原始 agent log 不適合公開

狀態：已修正。

處理：
- 本文件已替換原始 transcript。
- 公開版本只保留審查結論、風險摘要與處理狀態，不包含本機路徑、artifact 路徑或逐步 agent 執行紀錄。

### P2-1 測試名稱與斷言語意不一致

狀態：已修正。

處理：
- 將行尾變更測試更名為 warning 語意，符合實際模型：搬遷後 working file drift 是 warning，不是 ledger integrity failure。

### P2-2 stale write lock 可能需要人工清除

狀態：待後續版本。

理由：
- 目前鎖定檔在正常流程會自動移除。
- 若程序被 `SIGKILL`，可能留下 stale lock，使用者需手動刪除或等待 timeout 後處理。
- 自動清除 stale PID lock 需要跨平台程序存在性判斷，應另以測試驅動方式實作。

### P2-3 datetime 標準化不一致

狀態：已修正。

處理：
- timezone-aware metadata datetime 會轉為 UTC 並以 `Z` 結尾。
- naive datetime 保持 ISO 8601 原始語意。

## 上線前必跑檢查

- `uv run --extra dev pytest -q`
- `uvx ruff check .`
- `uv build`
- `uvx pip-audit`
- 掃描公開倉庫候選內容，確認無私鑰、本機路徑、cache、`.DS_Store`、`.pyc` 或未整理 agent transcript。

## Public Preview 判斷

完成 P1 修補與公開倉庫掃描後，可進入 public preview。第一次正式公開前仍應完成 initial commit，並再次對 release checklist 逐項確認。
