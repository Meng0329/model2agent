# Model2Agent V0.3 — 失败报告（P0 2 模型 Pilot）

> 自动生成。仅报告真实执行结果；未执行的实验（100 模型 / 消融 / 未见家族）不在此声称完成。

原始记录：`/data/mzb/paper2agent/results/logs/pilot_runs.jsonl`（296 条）。

## 1. 端到端 Agentification（M）

| 模型 | Agent 化成功 | 能力验证(通过/可验证) |
|---|---|---|
| cnn_digits | True | 10/12 |
| xgb_tabular | True | 10/12 |

失败转换计入成功率分母（分母=全部尝试模型）。

## 2. 任务准确率（正确/总运行）

| 模型 | 方法 | tutorial | novel |
|---|---|---|---|
| cnn_digits | B0 | 12/15 | 14/15 |
| cnn_digits | B2 | 12/15 | 13/15 |
| cnn_digits | M | 12/15 | 12/15 |
| xgb_tabular | B0 | 25/30 | 26/30 |
| xgb_tabular | B2 | 15/30 | 8/30 |
| xgb_tabular | M | 29/30 | 27/30 |

## 3. 失败模式

- [M] x4: RuntimeError: shape '[-1, 1, 8, 8]' is invalid for input of 
- [M] x4: routing_parse
- [B0] x1: RateLimitError: Error code: 429 - {'error': {'message': 'Ups
- [B2] x1:   File "/tmp/tmpyxnz5w2y.py", line 1
    predict(features) -
- [M] x1: RateLimitError: Error code: 429 - {'error': {'message': 'Ups
- [B2] x1:   File "/tmp/tmpbwjw0tw_.py", line 1
    hey YG. pasted mode
- [B2] x1:   File "/tmp/tmp3n_8etvy.py", line 1
    hey YG. pasted mode
- [B2] x1:   File "/tmp/tmpycm15u_l.py", line 39
    features = [0.0, 4
- [M] x1: RateLimitError: Error code: 429 - {'error': {'message': 'gro
- [B0] x1:   File "/tmp/tmpg9dgypwf.py", line 2
    // Build: (none — d
- [B2] x1:   File "/tmp/tmp7xmltdyj.py", line 1
    0  0  0  3 15 13  1
- [B2] x1: Traceback (most recent call last):
  File "/tmp/tmptvm9a6de.
- [B2] x1: Traceback (most recent call last):
  File "/tmp/tmpksgojoz4.
- [B2] x1:   File "/tmp/tmp30yjh5ov.py", line 1
    yo YG. pasted model
- [B0] x1:   File "/tmp/tmpztde5y1q.py", line 1
    // Runtime | Python

## 4. 未执行 / 未完成项（诚实标注）

- 100 模型大规模集：**未执行**（P3）。
- 未见任务家族测试：**未执行**（P3）。
- A1–A5 消融：**未执行**（P1/P2）。
- B1 / B3 基线：**未执行**（代码接口预留）。
- 开放式（open-ended）任务与双人评分：**未执行**（仅结构预留）。
- 鲁棒性 6 类故障注入：代码就绪，**待运行**（`scripts/run_robustness.py`）。
- 本次 Pilot 若因 LLM 延迟出现部分 split 未跑完，已在记录中如实反映（不补造）。
