# 官方模型信息核实（检查点 0）

仅获取官方模型卡、模型配置与文件元数据，未下载权重、未启动服务。具体 HF commit 已从官方 API 实际读取；源 URL 和源文件 SHA256 见 [official_source_index.json](evidence/official_source_index.json)。以下是候选信息，不是已批准运行配置。

|完整模型 ID|HF commit|BF16 权重文件大小|上下文|思考模式|
|---|---|---:|---|---|
|Qwen/Qwen2.5-7B-Instruct|a09a35458c702b33eeacc393d103063234e8bc28|15.231 GB|配置默认 32,768；模型卡称 131,072（需 YaRN），生成 8,192。|无 Qwen3 式开关|
|Qwen/Qwen3-8B|b968826d9c46dd6066d109eabc6255188de91218|16.382 GB|模型卡原生 32,768 / YaRN 131,072；config 为 40,960，模型卡解释为常用输入/输出预留。|支持 enable_thinking；后续需显式固定|
|Qwen/Qwen3.5-27B|fc05daec18b0a78c049392ed2e771dde82bdf654|55.563 GB|原生 262,144，可扩展到 1,010,000；长上下文显存必须另外验证。|支持 enable_thinking；后续需显式固定|

来源：[Qwen2.5-7B-Instruct 官方卡](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)、[Qwen3-8B 官方卡](https://huggingface.co/Qwen/Qwen3-8B)、[Qwen3.5-27B 官方卡](https://huggingface.co/Qwen/Qwen3.5-27B)。仓库内保存的对应 revision 原文优先于未来会变化的 main 页面。

## 推理参数与工具调用

- Qwen2.5：固定 revision 的 generation_config.json 给出 temperature=0.7、top_p=0.8、top_k=20、repetition_penalty=1.05。所保存模型卡未明确说明具体工具调用协议/模板，故其原生 function calling 协议仍待确认，不能据此臆造工具 parser；AppWorld 官方 ReAct 的文本代码执行接口需下一步读实际实现。

- Qwen3-8B：模型卡推荐思考模式 temperature=0.6、top_p=0.95、top_k=20、min_p=0；非思考 temperature=0.7、top_p=0.8、top_k=20、min_p=0。明确支持工具调用，推荐 Qwen-Agent。模型卡列 vLLM>=0.8.5 的 OpenAI 兼容接口。官方工具 parser 与 AppWorld agent 的代码块解析属于不同层，不能为适配弱模型修改官方 agent 解析。

- Qwen3.5-27B：支持工具调用，vLLM 示例包含 qwen3_coder tool parser，非思考模式以 chat_template_kwargs.enable_thinking=False 配置。一般任务非思考推荐 temperature=0.7、top_p=0.8、top_k=20、min_p=0、presence_penalty=1.5、repetition_penalty=1；一般思考推荐 temperature=1、top_p=0.95，精确编程思考推荐 temperature=0.6、top_p=0.95，其余见源卡。不从配置文件 transformers_version 字段推断最低支持版本。

Qwen3.5 固定 revision 的示例采样说明与文末 Best Practices 对“非思考 reasoning”参数存在不一致；文末为 temperature=1、top_p=1、top_k=40、presence_penalty=2，而前文不同。保留原文，不声称有唯一推荐值；后续拟采用一致的非思考一般任务策略，仍待确认。

## 部署候选与待确认

建议首个模型使用已有完整缓存的 Qwen2.5；三个模型尽量统一非思考策略、agent、步数、超时和采样参数。Qwen2.5 没有同类思考开关，运行日志应记录 not_applicable；Qwen3 系列显式关闭，不往任务文本追加软开关。尚未选择模型、统一采样参数或 max_model_len，也未安装/固定 vLLM 版本。

既有 vLLM 环境的包元数据不等同于新项目已经安装或兼容；最终 requirements 与 config 必须在独立环境实际安装、核实官方实现后写定。27B 模型卡演示的 8 卡长上下文不是最低显卡要求；4 卡受限上下文只是基于权重容量的候选方案。

后续如下载，目标计划为 /data1/shn/ReAudit/runtime/hf/；8B 完整 BF16 权重约 16.382 GB，27B 约 55.563 GB，另有 tokenizer/配置和框架缓存开销。当前没有请求或取得大文件下载授权，也未下载；实际申请前须按当时 commit 再核实大小、路径和磁盘余量。

AppWorld：[官方仓库](https://github.com/stonybrooknlp/appworld) 当前 README 要求 Python 3.11+。本机尚未安装项目环境。服务器访问 GitHub API 时发生 SSL EOF，错误已保存在源索引，AppWorld 源代码 revision 暂未取得；浏览器已能读官方 README。下一检查点需核实官方 agent 代码、版本、train-only 数据下载/加载与评分 API；本轮不调用未知 API，也不读取任何任务。
