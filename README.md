# ReAudit

AppWorld train 上的技能库消融实验。当前检查点：Qwen2.5-7B 的 1 任务端到端试跑；尚未批准 16 次批量运行或其他模型。

## 固定环境与来源

- Agent 环境：项目内 runtime/agent-venv，Python 3.12.13；requirements.txt 固定全部已安装依赖，pip check 通过。
- AppWorld：官方 PyPI 0.1.3.post1，官方数据 data-0.1.0.bundle；不混用 main 的 0.2.0.dev0 API。
- 官方 minimal ReAct：v0.1.3.post1 / commit 66ad8099e12188ece0d3fe45e661dbc01880813b 的 notebook prompt 和 agent class，未经修改，见 THIRD_PARTY_NOTICES.md。
- 推理：复用 /home/shn/miniconda3/envs/verl-agent 的 vLLM 0.11.0、PyTorch 2.8.0 / CUDA 12.8、Transformers 4.57.3；未更改这个环境，未下载推理依赖。
- 模型：Qwen/Qwen2.5-7B-Instruct，revision a09a35458c702b33eeacc393d103063234e8bc28，自有原缓存只读复用，BF16、不量化。
- 权重完整性目前核实为文件存在/长度与 revision 对应，未重新读取 15 GB 权重做内容哈希校验。
- 所有运行参数、模型、GPU、seed、timeout、精度、上下文和路径见 config/config.json。其他模型尚未部署或测试。

## 目录

config/ 固定配置；src/reaudit/ 适配、prompt、隔离 worker、逐次成本日志；
scripts/ 数据准备、清单选择、启动、运行、重评分和初始状态检查；
data/task_manifest.csv 为固定 8 个真实 train ID；
runs/runs.csv 为小体积完整执行汇总；
runs/traces/<run_id>/ 为完整输入、请求/响应、工具交互、初始 DB 快照和 GPU 样本（git 忽略）；
runtime/ 为环境、下载、缓存、官方 DB、官方评分输出和模型服务日志（git 忽略）；
tmp/ 为临时文件；reports/ 为证据与阶段结果；tests/ 为关键路径测试。

## 从零安装 agent 环境

需要可用的 Python 3.12、已核实可运行的 vLLM 环境和准确模型快照。本项目当前复用已有推理环境/模型；在新服务器部署它们之前必须另外核实下载大小与 CUDA 兼容性，不能照抄系统 nvcc 版本推断。

在 /data1/shn/ReAudit 执行：

    mkdir -p runtime tmp/pip-cache
    python3.12 -m venv runtime/agent-venv
    export PYTHONDONTWRITEBYTECODE=1
    export PYTHONPATH="$PWD/src"
    export TMPDIR="$PWD/tmp"
    export APPWORLD_ROOT="$PWD/runtime/appworld"
    export APPWORLD_CACHE="$PWD/runtime/appworld-cache"
    export IPYTHONDIR="$PWD/runtime/ipython"
    export XDG_CACHE_HOME="$PWD/runtime/cache"
    runtime/agent-venv/bin/python -m pip --isolated install --index-url https://pypi.org/simple --cache-dir "$PWD/tmp/pip-cache" -r requirements.txt
    runtime/agent-venv/bin/appworld install

APPWORLD_CACHE 必须在 install 前设置，否则官方安装器会把包测试写入 ~/.appworld/tests。初次安装曾发生此副作用，已公开记录在阶段报告；此处已纠正复现命令，不删除未知的既有目录。

## 官方 train 数据与任务清单

34.28 MB 官方加密数据包已经用户批准下载。只打开 train 清单、90 个 train 任务及公共资源；其他 split 和任务内容不读取或解压。原包只保留为下载载体，不将它用于加载其他 split。数据不入 git，遵守其加密再分发要求。

已下载时：

    runtime/agent-venv/bin/python scripts/prepare_train_data.py

新下载须先获得批准，再执行上述脚本的 --download。bundle URL、字节数和 SHA256 固定在 config。
清单首次生成：

    runtime/agent-venv/bin/python scripts/select_tasks.py

固定 Random(1729).sample(sorted(official_train_ids), 8)，不依据成功率筛选。脚本拒绝覆盖已有清单。allowed_apps 是可用应用，不能当作任务实际所需应用；instruction_app_mentions 仅标记公开任务文本中的应用名，样本确实覆盖 Spotify、Venmo、phone、simple_note。

## 检查和启动模型

    runtime/agent-venv/bin/python -m pytest -q tests/test_pipeline.py
    runtime/agent-venv/bin/python scripts/check_initial_states.py
    runtime/agent-venv/bin/python scripts/serve_model.py start

初始状态脚本为 CPU 检查，读取每个任务两次，不调用模型、不算完整执行；它拒绝覆盖已有检查目录。已有结果见 reports/evidence/initial_state_checks.json。
启动前检查所选物理卡 UUID、已用显存及利用率；若被占用则拒绝启动，不杀他人进程。只更改 config 中 GPU 分配后才能重试。端口仅绑定 127.0.0.1。
就绪检查 GET http://127.0.0.1:18123/v1/models 不产生模型生成调用。模型服务离线读取缓存，写入仅到 runtime/ 和 tmp/，不改已有环境。
模型服务日志：runtime/vllm-service.log。进程记录：runtime/vllm-service.json。

## 一次完整执行与官方重评分

    runtime/agent-venv/bin/python scripts/run_experiment.py --task-id e3d6c94_3 --repeat-index 0
    runtime/agent-venv/bin/python scripts/rescore_run.py RUN_ID

一次执行=从新 AppWorld 初始世界开始，到 task_completed、步数上限或异常/超时。父进程在整个执行期间独占项目执行锁，禁止同时跑多个完整执行；每次 worker 为新进程。重复 seed 从 config.experiment.sampling_seeds 取值，不允许从 CLI 暗改解码配置。
官方 agent 原样把模型文字传给 world.execute：不剥围栏、不修复代码；语法检查只记录诊断，仍让官方环境处理。评分单独调用官方 evaluate_task，重读保存的官方 DB，不修改评分逻辑。不给模型任何 ground truth。
build_prompt(task, skills, condition) 返回完整 role-tagged UTF-8 文本；no_skill 与官方 prompt_messages 的消息内容逐字一致。full_input_hash 为该文本 SHA256；每次调用还保存完整 OpenAI messages/参数和其 canonical JSON SHA256。服务端 chat template 由固定模型 revision 决定；未声称 full_input_hash 是 chat-template 渲染后的 token ID 哈希。
技能版本/移除条件只写日志；模型输入只添加所选技能文本。移除 B 不替换其他文本。

## 成本、异常与日志语义

不自动重试模型请求。每次调用记录完整请求/响应、token usage、真实单调时钟耗时。AppWorld 冻结模拟时间不影响成本时钟；UTC 时间也取真实 CLOCK_REALTIME。
若服务未返回 usage，或 watchdog 中断请求，prompt_tokens/completion_tokens 留空，usage_complete=False；known_* 只计已知部分，不把未知用量当成 0。
latency_seconds 包含初始化、agent、官方评分，排除模型服务启动和检查点等待；llm_latency_seconds 为已返回调用耗时之和。GPU 样本包含整卡显存和利用率，不能据此精确拆出每次调用能耗或美元成本。
status=completed 表示正常到评分；failure_type=task_failed 表示官方 TGC 未通过。timeout、service_error、context_overflow、parse_error、environment_error 单列。纯格式失败在没有任何合法 Python 输出时记 parse_error；个别语法错误保留为逐步诊断，不擅改官方重试行为。
SGC 是多任务场景聚合指标，本次单次执行不填 SGC；没有金额单价，不估美元。

## 停止与版本控制

    runtime/agent-venv/bin/python scripts/serve_model.py stop

只操作本项目记录且核验 UID、启动时间和命令的进程组。检查点结束即释放 GPU。
origin fetch URL 保持 HTTPS，push URL 为 git@github.com:ShiningIVYYY/ReAudit.git，仅此仓库生效。提交前检查敏感内容/权重/大文件，严禁 force push。密钥仅从 REAUDIT_API_KEY 环境变量读取，不写日志或 git；当前本地服务无需密钥。
