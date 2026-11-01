# Model2ScientistBench — S1 报告（自动生成，来自真实 run ledger）

> 数据源：`results/logs/scientist_runs.jsonl`（追加式，不可改写历史）。
> 未运行的方法/任务一律标注 **NOT_TESTED**，失败标注 **FAILED**，不补造数字。
> 本轮 `reps=1`；仅作描述性报告，不做显著性宣称。

## 1. 逐任务结果

| 任务 | 域 | 方法 | n | SISR | oracle | SEV | 模型调用 | oracle 查询 | 修订 | 成本($) | 时延(s) | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| protein-P1-novel | protein_science | B0 | 1 | False | True | 0.000 | 0 | 0 | False | 0.333 | 154 | FAILED |
| protein-P1-novel | protein_science | B1 | 1 | True | True | 1.000 | 79 | 16 | False | 2.040 | 658 | OBSERVED |
| protein-P1-novel | protein_science | B2 | 1 | True | True | 1.000 | 3 | 16 | False | 1.227 | 578 | OBSERVED |
| protein-P1-novel | protein_science | B3 | 1 | True | True | 1.000 | 57 | 16 | False | 2.033 | 1053 | OBSERVED |
| protein-P1-novel | protein_science | M | 1 | True | True | 1.000 | 44 | 16 | True | 1.861 | 1272 | OBSERVED |
| protein-P2-closed-loop | protein_science | B0 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| protein-P2-closed-loop | protein_science | B1 | 1 | True | True | 1.000 | 101 | 24 | False | 1.760 | 463 | OBSERVED |
| protein-P2-closed-loop | protein_science | B2 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| protein-P2-closed-loop | protein_science | B3 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| protein-P2-closed-loop | protein_science | M | 1 | True | True | 1.000 | 120 | 24 | False | 2.248 | 1497 | OBSERVED |
| protein-P3-rediscovery | protein_science | B0 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| protein-P3-rediscovery | protein_science | B1 | 1 | False | False | 0.000 | 65 | 2 | False | 2.650 | 1203 | FAILED |
| protein-P3-rediscovery | protein_science | B2 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| protein-P3-rediscovery | protein_science | B3 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| protein-P3-rediscovery | protein_science | M | 1 | False | False | 1.000 | 100 | 20 | True | 1.944 | 1402 | FAILED |
| rice-R1-novel | agriculture | B0 | 1 | False | True | 0.000 | 0 | 0 | False | 0.658 | 191 | FAILED |
| rice-R1-novel | agriculture | B1 | 1 | True | True | 1.000 | 1 | 20 | False | 2.021 | 803 | OBSERVED |
| rice-R1-novel | agriculture | B2 | 1 | True | True | 1.000 | 1 | 20 | False | 1.605 | 439 | OBSERVED |
| rice-R1-novel | agriculture | B3 | 1 | True | True | 1.000 | 2 | 20 | False | 1.574 | 509 | OBSERVED |
| rice-R1-novel | agriculture | M | 1 | True | True | 1.000 | 2 | 20 | False | 1.322 | 409 | OBSERVED |
| rice-R2-closed-loop | agriculture | B0 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| rice-R2-closed-loop | agriculture | B1 | 1 | True | True | 1.000 | 3 | 30 | False | 2.145 | 813 | OBSERVED |
| rice-R2-closed-loop | agriculture | B2 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| rice-R2-closed-loop | agriculture | B3 | 1 | True | True | 1.000 | 4 | 30 | False | 1.726 | 727 | OBSERVED |
| rice-R2-closed-loop | agriculture | M | 1 | True | True | 1.000 | 1 | 30 | True | 1.960 | 866 | OBSERVED |
| rice-R3-rediscovery | agriculture | B0 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| rice-R3-rediscovery | agriculture | B1 | 1 | True | True | 1.000 | 3 | 20 | False | 1.660 | 670 | OBSERVED |
| rice-R3-rediscovery | agriculture | B2 | 0 | NOT_TESTED | NOT_TESTED | NOT_TESTED | — | — | — | — | — | NOT_TESTED |
| rice-R3-rediscovery | agriculture | B3 | 1 | True | True | 1.000 | 2 | 20 | False | 2.000 | 898 | OBSERVED |
| rice-R3-rediscovery | agriculture | M | 1 | True | True | 1.000 | 1 | 20 | True | 1.866 | 790 | OBSERVED |

## 2. 按方法汇总

| 方法 | n | SISR 率 | oracle 率 | 平均 SEV | 平均成本($) |
|---|---|---|---|---|---|
| B0 | 2 | 0.000 | 1.000 | 0.000 | 0.495 |
| B1 | 6 | 0.833 | 0.833 | 0.833 | 2.046 |
| B2 | 2 | 1.000 | 1.000 | 1.000 | 1.416 |
| B3 | 4 | 1.000 | 1.000 | 1.000 | 1.833 |
| M | 6 | 0.833 | 0.833 | 1.000 | 1.867 |

## 3. 失败与未解释项（诚实标注）

- **B0 / rice-R1-novel**：FAILED。模型调用=0，oracle 查询=0，oracle 命中=True，产物合格=False。
- **B0 / protein-P1-novel**：FAILED。模型调用=0，oracle 查询=0，oracle 命中=True，产物合格=False。
- **M / protein-P3-rediscovery**：FAILED。模型调用=100，oracle 查询=20，oracle 命中=False，产物合格=True。
- **B1 / protein-P3-rediscovery**：FAILED。模型调用=65，oracle 查询=2，oracle 命中=False，产物合格=False。

### 3.1 修复前 harness 失败（不计入方法成功率）

- **M / rice-R2-closed-loop**：`harness_output_path_bug` — pre-fix run: scientist wrote final_selection.json to the project cwd; evaluator reads the run out dir。该 run 的真实产物已保留在对应的 `rep0_prebug/` / `rep0_budgetcap/` 目录，修复后另行重跑。
- **M / rice-R3-rediscovery**：`harness_output_path_bug` — pre-fix run: scientist wrote final_selection.json to the project cwd; evaluator reads the run out dir。该 run 的真实产物已保留在对应的 `rep0_prebug/` / `rep0_budgetcap/` 目录，修复后另行重跑。
- **M / rice-R2-closed-loop**：`harness_budget_cap` — runner applied the global $2.0 cap instead of the task's $3.0 budget; session was cut at $2.019 before writing final_selection。该 run 的真实产物已保留在对应的 `rep0_prebug/` / `rep0_budgetcap/` 目录，修复后另行重跑。

## 4. NOT_TESTED（本轮未运行）

- protein-P2-closed-loop / B0
- protein-P2-closed-loop / B2
- protein-P2-closed-loop / B3
- protein-P3-rediscovery / B0
- protein-P3-rediscovery / B2
- protein-P3-rediscovery / B3
- rice-R2-closed-loop / B0
- rice-R2-closed-loop / B2
- rice-R3-rediscovery / B0
- rice-R3-rediscovery / B2

## 5. 局限

- 每个（任务, 方法）n=1，不能做显著性推断；报告效应量而非 p 值。
- 隐藏测量按预算强制访问；E1 预测从不当作 E3/E4。
- 生成失败/未写交付物按 FAILED 计入分母，未静默剔除。
