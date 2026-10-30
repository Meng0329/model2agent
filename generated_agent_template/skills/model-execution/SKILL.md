---
name: model-execution
description: 执行生成的模型 Agent 的真实推理（真实权重），并返回结果
---

# 模型执行

## 步骤
1. 读取 `config.json` 中的 `capabilities` 与 `capability_map`。
2. 用 `run_model` 工具执行指定 capability（参数与示例 schema 一致），例如：
   - 图像分类：`{"capability":"predict","args":{"features":[64个值]}}`
   - 表格预测：`{"capability":"predict","args":{"features":[30个值]}}`
3. 只依据真实返回结果作答，不得虚构。

## 注意
- 先运行 `model_exec.selfcheck()` 确认权重可加载（真实推理）。
- 输入必须来自用户上传或示例，不允许硬编码假结果。
