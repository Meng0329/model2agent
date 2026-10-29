# Model2Agent V0.3 — P0 Pilot 结果（真实数据）

> 由 `scripts/summarize_pilot.py` 从 `results/logs/pilot_runs.jsonl`（296 条记录）自动生成。
> 2 模型 Pilot 仅报告**描述性结果**，不宣称跨模型泛化（对齐 Paper2Agent 统计规范）。

## 1. 端到端 Agentification（方法 M）

| 模型 | 成功 | 能力验证率(可验证) |
|---|---|---|
| cnn_digits | True | 1.0 |
| xgb_tabular | True | 1.0 |

## 2. 任务准确率（正确/运行次数）

| 模型 | 方法 | tutorial | novel | 合计 |
|---|---|---|---|---|
| cnn_digits | B0 | 12/15 | 14/15 | 26/30 |
| cnn_digits | B2 | 12/15 | 13/15 | 25/30 |
| cnn_digits | M | 12/15 | 12/15 | 24/30 |
| xgb_tabular | B0 | 25/30 | 26/30 | 51/60 |
| xgb_tabular | B2 | 15/30 | 8/30 | 23/60 |
| xgb_tabular | M | 29/30 | 27/30 | 56/60 |

## 3. 工具/能力验证率（通过/验证次数）

| 方法 | 通过率 |
|---|---|
| B0 | 6/8 = 0.750 |
| B2 | 7/8 = 0.875 |
| M | 7/8 = 0.875 |

## 4. 成本（任务运行累计，USD）

- B0: $0.0404
- B2: $0.0314
- M: $0.0875

## 5. 配对统计（M vs 基线）

| 对比 | 均值差 | paired-t | p(t) | Cohen dz | 聚类Bootstrap 95%CI |
|---|---|---|---|---|---|
| M vs B0 | -0.08333333333333333 | -0.560611910581388 | 0.5862993069206738 | -0.16183471874253738 | [-0.16666666666666674, 0.0] |
| M vs B2 | 0.16666666666666666 | 0.8043996665398436 | 0.43820589933765797 | 0.23221018200641194 | [-0.33333333333333337, 0.6666666666666667] |

> 仅 2 个模型，聚类 Bootstrap 的 n_models=2，置信区间极宽，**不得据此下跨模型结论**。

## 6. 鲁棒性（6 类故障注入，方法 M）

| 模型 | 故障 | 检出 | 自动修复 | 修复后一致 | 不安全修复拒绝 |
|---|---|---|---|---|---|
| cnn_digits | missing_dependency | True | False | True | False |
| cnn_digits | broken_path | True | False | True | False |
| cnn_digits | deprecated_api | True | False | True | False |
| cnn_digits | invalid_input_schema | True | False | True | False |
| cnn_digits | preprocessing_drift | True | False | True | True |
| cnn_digits | weight_config_mismatch | True | False | True | True |
| xgb_tabular | missing_dependency | True | False | True | False |
| xgb_tabular | broken_path | True | False | True | False |
| xgb_tabular | deprecated_api | True | False | True | False |
| xgb_tabular | invalid_input_schema | True | False | True | False |
| xgb_tabular | preprocessing_drift | True | False | True | True |
| xgb_tabular | weight_config_mismatch | True | False | True | True |

- **故障检测率：12/12 = 1.000**
- **不安全修复拒绝率：4/4 = 1.000**
- **自动修复成功率：0**（检测到故障但未实现自动修复，列为 P1 工作）
- 修复后一致性仅在转换被判 success 时检验；本次全部故障均判失败，故该项不代表修复效果。

> 结论：检测能力 100%，但缺少自动修复；不得将“检测到”当作“已修复”。

## 7. 诚实声明

- 本 Pilot 只跑了 2 个模型；B1/B3、消融 A1-A5、100 模型、未见家族均**未执行**。
- 任何未跑完的 split 在原始 JSONL 中如实缺省，未补造数值。
- 结果用于技术可行性验证，不作性能优越性宣称。