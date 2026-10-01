# Codex Token Usage Summary

## 1. 文件信息

- 公开统计文件：`codex_usage_summary.json`
- 原始来源：`codex_usage.json` JSON Lines 事件日志
- 公开处理：原始事件日志包含完整 Codex event payload，已移入本地归档目录，不进入公开仓库。
- 统计对象：`payload.type = token_count` 的事件记录

## 2. 统计口径

本文件中的 token 用量记录包含两种常见视角：

- `last_token_usage`：当前这一次请求的增量 token 用量
- `total_token_usage`：截至当前记录位置的累计 token 用量快照

本次总量统计采用 `last_token_usage` 累加，原因是它更适合表示整份日志中每次请求实际消耗的 token 总和。

## 3. 总体结果

- `token_count` 事件数：`412`
- 统计时间范围：`2026-05-26T15:03:33.016Z` 到 `2026-05-30T05:44:38.662Z`

按 `last_token_usage` 增量累加后的总 token 用量如下：

| 指标 | 数值 |
|---|---:|
| Input Tokens | 128,628,799 |
| Cached Input Tokens | 96,417,792 |
| Effective Input Tokens（Input - Cached） | 32,211,007 |
| Output Tokens | 268,907 |
| Reasoning Output Tokens | 19,643 |
| Total Tokens | 129,737,247 |

## 4. 最后一条累计快照

文件最后一条 `token_count` 记录中的 `total_token_usage` 为：

| 指标 | 数值 |
|---|---:|
| Input Tokens | 127,629,852 |
| Cached Input Tokens | 96,309,120 |
| Output Tokens | 267,767 |
| Reasoning Output Tokens | 19,440 |
| Total Tokens | 127,897,619 |

## 5. 说明

- `Cached Input Tokens` 是输入 token 中命中缓存的部分，通常可单独观察，不建议简单与 `Output Tokens` 直接比较成本贡献。
- `Effective Input Tokens` 为 `Input Tokens - Cached Input Tokens`，可用来近似理解未命中缓存的输入规模。
- `Total Tokens` 来自日志原始字段，保留原始统计口径。
- 若后续需要进一步按日期、任务、会话或目录拆分，需要源日志中存在可关联的任务标识字段，并额外做分组分析。
