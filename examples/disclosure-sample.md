# AI 使用揭露草稿範例

這是 `research-ledger export-disclosure` 的輸出用途示例。實際內容會依照本地
`.research-ledger` 的事件、seal 與驗證狀態產生。

```bash
research-ledger export-disclosure --output disclosure.md
research-ledger export-disclosure --format json --output disclosure.json
```

報告會包含：

- ledger id
- verification status
- event type counts
- recorded event summaries
- seal roots
- Research Ledger 的限制
