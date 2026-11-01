# Model2Agent Generated Agent

由 Model2Agent Builder 从真实模型资产生成的独立 Agent：三栏界面（会话 / 对话+输入 / 结果·执行轨迹·API 文档），拥有自己的 Claude Agent SDK 会话与真实模型推理。

## 运行

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入 ANTHROPIC_API_KEY
python run.py --port 7860
```

浏览器打开 http://localhost:7860

## 结构

- `config.json`：真实模型事实（input_type、labels、capabilities、feature_names、image_preprocess）。
- `agent_ui.json`：该模型的输入方式、恰好 3 个预设提问、执行轨迹管线、结果视图（由外层 agent 设计/可改写）。
- `adapters.py`：按资产声明的约定把图片/CSV 转成真实特征（不做启发式猜测，缺声明即报错）。
- `store.py`：会话持久化到项目内 `conversations.json`（与 Builder 主平台隔离）。
- `app.py`：`/api/model/run`、`/api/upload`、`/api/chat`(SSE)、`/api/conversations`、`/api/apidocs`。
- `model_exec.py`：加载资产原生 `infer.py`，执行真实推理。

## 验证

外层 Model2Agent agent 在生成后调用 `verify_agent`，对产物做真实可用性验证（启动、真实推理、输入适配 fixture、会话 CRUD、API 文档、chat 回环），失败则依据证据改写后重验。
