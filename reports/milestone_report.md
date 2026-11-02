# Milestone report — checkpoint 1 smoke

当前范围：用户已批准先用 Qwen2.5-7B-Instruct 搭建流水线；只试跑 1 个任务 × 1 次，结束后等待确认，不跑 16 次或其他模型。检查点 0 记录已移至 checkpoint0.md。

## 固定内容与已验证事项

- AppWorld 正式包 0.1.3.post1；独立 Python 3.12.13 venv；requirements.txt 精确固定安装版本，pip check 通过。
- 官方 minimal ReAct notebook 固定 commit 66ad8099e12188ece0d3fe45e661dbc01880813b；保留 prompt assignment 与 agent class 的原文，AST 源码哈希验证通过。仅调整 Task 为 type-only import、调用封装和技能 prompt 接口；不修改模型输出或评分。
- 官方包对应的数据版本为 data-0.1.0.bundle。经用户明确批准下载 34,280,074 bytes；SHA256 fd9f9608c2ec71ed0ac25c3633a738b9129a318a129e31230425b9188e508250。只读取 train 清单、90 个 train 任务和公共资源；未加载其他划分的任务内容。原加密包仍含全部划分，作为官方传输载体保留，不将其余内容解压或使用。
- 从实际 load_task_ids("train") 固定 Random(1729) 无放回抽样 8 个 ID；清单见 data/task_manifest.csv。按公开 instruction 词面覆盖 Spotify、Venmo、phone、simple_note；allowed_apps 只是环境可用列表，不能当实际任务覆盖证据。
- 全部 8 个任务两次独立进程初始化；保存实际初始 DB 快照并计算 SHA256，8/8 指纹相同。16 次 CPU reset 检查不调用模型、不算完整执行。证据 initial_state_checks.json。
- 10 项关键测试通过：官方源码保真、no_skill prompt 一致、技能移除、token usage、真实时钟、context_overflow/parse_error/service_error/timeout 和请求中断用量未知。异常测试使用 mock HTTP，不消耗 GPU，不冒充真实异常执行验收。
- 模型 revision a09a35458c702b33eeacc393d103063234e8bc28，BF16、无量化、32768 上下文，单张 RTX 4090 物理 GPU 7，串行 max_num_seqs=1，temperature=0.7，top_p=0.8，top_k=20，repetition_penalty=1.05，max_tokens=1024，max_steps=50，完整执行超时600秒，单次请求60秒，单次代码30秒；所有值来自 config。
- vLLM 0.11.0 / PyTorch 2.8.0 CUDA 12.8 / Transformers 4.57.3 既有环境已导入并启动成功；/v1/models 能正确列出目标模型和 32768 上下文。单次模型执行现已结束，详见结果。

## 真实执行结果

单次执行已结束：run_id=run_20261102T204402_a2ede390b641484bb7412ff0cffcb191，task_id=e3d6c94_3，status=error，failure_type=context_overflow，score=未验证/未知。结果和 token/耗时/初始状态/重评分证据见 smoke_report.md 与 evidence/smoke_checks.json。本次只完成 1 个完整执行，不能估计总体成功率或典型成本。

## 实现语义与限制

- 每次完整执行新进程 + 新 AppWorld + 唯一 experiment_name/run_id，不继承前次任务状态。run_id 唯一写入 CSV。
- full_input_hash 是 build_prompt 生成的完整 role-tagged UTF-8 文本哈希。逐次模型调用另存完整 messages/参数及 request_hash，服务端 chat template 固定于模型 revision；不误称为最终 token ID 哈希。
- token 以服务 usage 为准；无 usage 或中断请求时总量为空并记录 usage_complete=False、known_* 已知部分。无自动重试。latency 使用不受 freezegun 冻结的真实时钟。
- status=completed/failure_type=task_failed 表示正常执行到官方评分但 TGC 不通过；基础设施异常单列。纯语法失败单列 parse_error，原始输出仍原样传给官方环境。
- 单次执行 SGC 不定义，留空；金额单价未查证，留空。GPU 样本为整卡观测，不能精确归因每个 kernel 的成本。
- 整体超时由外部父进程监控，只结束该次执行创建的进程组。模型服务 stop 同样仅作用于本项目核验过的进程。

## 遇到的问题与偏离

1. 初次执行官方 appworld install 时未预先设置 APPWORLD_CACHE，安装器把其包测试解压到 /home/shn/.appworld/tests。这违反用户限定的写入范围；已立即告知用户，未擅自删除未知的已有文件，不能确认是否覆盖了原文件。该处是 AppWorld 包自身的测试代码，不是 test_normal/test_challenge 任务。后续所有调用和 README 安装命令显式设置 APPWORLD_CACHE=/data1/shn/ReAudit/runtime/appworld-cache。记录见 tmp/setup-logs/appworld-install.log；不得声称本轮所有写入都在项目内。
2. 初选 GPU 2 在启动前变成他人占用，启动脚本拒绝分配；重新检查后选择 GPU 7。未抢占或停止他人进程。见 gpu_before_smoke.json。
3. 既有 vllm-cu128 环境的 vLLM 0.24.0 实际导入需要缺失的 libcudart.so.13，虽然 torch 报告 CUDA 12.8。没有修改环境、系统 CUDA 或自行安装大文件；改用另一个已验证的既有 vLLM 0.11.0 环境。失败日志与配置见 service_bootstrap_failure.json。这是服务启动故障，未产生完整执行，不能混入 task_failed。
4. GitHub API rate limit 403，改用官方 git ls-remote 获取 release tag 的实际 commit；官方原始源码仍从 raw.githubusercontent.com 获取，未配置镜像或代理。

## 未完成与待确认

8×2=16 完整执行、真实极短超时路径、其他模型、成本批量统计、隔离脚本、四条件脚本和备选环境调研尚未开始。单次试跑不能估计模型总体成功率或适用性。完成单次试跑与重评分、提交推送后停下来等待用户确认。
