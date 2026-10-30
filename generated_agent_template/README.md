# Model2Agent Generated Agent

由 Model2Agent Builder 从真实模型资产生成的独立 Agent，拥有自己的 Claude Agent SDK 会话与真实模型推理。

## 运行

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入 ANTHROPIC_API_KEY
python run.py --port 7860
```

浏览器打开 http://localhost:7860 即可与模型 Agent 对话（上传图片 / CSV，或直接推理）。

## 能力

由 `config.json` 驱动：`input_type`（image / tabular / text / vector）决定自然输入方式，
`capabilities` 列出真实推理能力，`run_model` 工具在 SDK 会话内执行真实权重推理。
