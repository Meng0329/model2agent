---
name: react-ui-generation
description: 为生成的 Model Agent 生成 React 聊天式 UI，依据真实 input_type 选择自然输入控件（image 上传 / tabular CSV 上传 / text 输入框 / vector 高级输入）。
---
# React UI 生成

生成的 Agent 前端是 ChatGPT 式 React 外壳 + 专属模型输入适配（由 `config.json` 驱动，绝不写死控件）：

- `input_type == "image"` → 真实图片上传（缩放到模型输入尺寸，经 `adapters.image_to_features`）。
- `input_type == "tabular"` → 真实 CSV 上传（按 `feature_names` 排序列，经 `adapters.tabular_rows_to_features`）。
- `input_type == "text"` → 文本输入。
- `input_type == "vector"` → 高级原始特征输入（默认折叠，非首选）。

禁止让用户手工输入 30/64 个空格分隔数字作为唯一交互方式。输入控件必须来自实际模型能力。
