# ReAudit milestone report

## 当前结论与范围

Qwen/Qwen2.5-7B-Instruct 的官方完整版 ReAct 基线已完成：8 个实际 train 任务 × 2 次，共 16 次，TGC 成功 0/16。每个任务均为 0/2。15 次为正常执行后 task_failed，1 次为 600 秒 timeout；超时保存状态也由官方评分为 0，但仍保留 timeout 分类。原先获批的完整版试跑计入这 16 次，没有丢弃失败或重跑补成功。

另有 3 次旧 minimal 诊断（2 context_overflow、1 task_failed）和 1 次独立 0.05 秒受控超时检查；总账 runs/runs.csv 共 20 个唯一 run_id。旧 agent 与故障注入均不混入新基线成功率。全部真实执行仅涉及 Qwen2.5-7B，其他模型和后续阶段未运行。任务包一整体尚未完成。

分任务结果、基线 run_id、用量及逐次失败类型见 qwen25_baseline.md、evidence/qwen25_batch_summary.json；20 次执行的 agent/配置来源见 evidence/run_index.json。完整模型输入输出、工具交互、GPU 样本及原始评分留在服务器 runs/traces/<run_id>/，不进 git。

## 成本与资源

16 次平均完整执行耗时 127.921 秒，串行执行；不包含服务启动/检查点等待和后置补充评分。15 次有完整 token usage，子集平均 prompt 84,283.467、completion 4,649.867、总计 88,933.333 tokens。这不是全部 16 次的精确均值。超时试跑最后请求缺 usage，未知部分留空；全部基线已知下界为 prompt 1,524,492、completion 102,126 tokens。

实际只用当时空闲的物理 GPU7（RTX4090，UUID GPU-3f53fb52-ef85-176b-8607-e21dc9d9d4b2）。批次服务已停止，记录的服务 PID 不存在，释放后 GPU7 为 3 MiB / 0%。证据 evidence/qwen25_batch_cleanup.json。启动至清理记录窗口包含加载与空闲，不冒充精确 GPU 活跃时间。没有单价来源，不估金额。

## 逐条验收

|项目|结果与证据|
|---|---|
|官方 train 任务|只提取获批官方数据包中的 train 清单、90 个 train 任务与公共资源；未加载其他划分任务|
|固定 8 任务及覆盖|Random(1729).sample(sorted(official_train_ids), 8)，不按成功率筛选；实际 ID 见 data/task_manifest.csv；公开文本覆盖 Spotify/Venmo/phone/simple_note|
|8 任务可加载和重置|8/8 两次独立 CPU 初始化指纹一致；evidence/initial_state_checks.json|
|Qwen2.5 新版 16 次唯一完整执行|16/16，结果均为 0 或明确 timeout；run_id 唯一；evidence/qwen25_batch_summary.json|
|同任务两次初始状态一致|8/8 重复对及全部 16 次快照匹配独立 reset 基准；evidence/qwen25_batch_validation.json|
|输入可追溯|16/16 保存的完整初始输入哈希吻合；8/8 重复对初始输入逐字节一致；同上|
|官方评分可重读|16/16 保存状态重新评分一致；timeout 类型未被改成 task_failed；同上|
|异常路径|独立 run_20261102T232619_d1f788291b9e4596983df4b27ec84989 在 0.055872 秒记为 timeout，尚未初始化世界或调用模型，故无状态指纹/评分，实际模型调用为 0；不计入基线|
|关键测试|此前 20 项通过及官方搜索/解析/执行/评分 CPU mock；本轮复核结果见 evidence/qwen25_final_checks.json|
|其他两个模型各 16 次|未完成，等待本模型汇报后的用户确认|
|成本对比表/备选环境/输入隔离/四条件脚手架|后续阶段尚未完成，不宣称整体验收|

## 低成功率排查与解释

证据 evidence/qwen25_failure_diagnostics.json 来自全部 16 次原始事件与 worker 日志，不新增模型执行。311 次请求开始、310 次返回均 HTTP200，1 次被 watchdog 中断；最大已知单请求 prompt 6,865 tokens，低于上下文 32,768。基线中没有 service_error、context_overflow 或 environment_error。297 个实际执行代码块均无 Python 语法错误，但有不存在的 API/属性、传错参数和字段读取错误等模型生成代码错误。

15 次正常结束中，13 次执行 supervisor.complete_task 但未满足官方评分要求，2 次用完 50 次模型调用预算。3 次执行的官方 parser 日志合计 11 条无代码块提示，不能说完全没有中间格式问题，也不能记为 11 次完整执行失败。原始解析器、评分、任务和失败槽位均未修改。

预算因素未被排除：超时试跑有 12 条回复达到 1024-token 输出上限；其余 15 次返回均正常 stop。官方 24,000 字符历史裁剪发生在 8 次执行的 166 个调用输入；另外 8 次没有裁剪也全部失败。基础服务或单一裁剪因素解释不了整体 0/16。

当前最有证据的解释是本模型在固定 agent/提示词/预算下的 API 使用、规划和完成判断能力不足，尚不能因果归结为模型本身。没有更强模型对照、预算消融或真实 agent 成功案例；完整权重内容哈希未验证。因此只判定“当前配置下 Qwen2.5-7B 不适合用于有效的后续技能效用实验”，不推论所有 7B 使用方式均不可行。

## 固定版本与实现边界

AppWorld=0.1.3.post1，官方源提交 66ad8099e12188ece0d3fe45e661dbc01880813b。完整版官方 controller、parser、prompted LM、environment、answerer 和 Recoma0.0.4 search/core 原方法保留；只替换模型 backend 并加入配置、日志和技能接口。来源/原文哈希见 evidence/full_react_provenance.json。Recoma 固定的旧 LiteLLM 版本当前 PyPI 不可得，使用其官方 wheel 中实际 core/search 源码，包入口跳过未用 provider/UI；没有换镜像或另选 LiteLLM。

vLLM0.11.0、torch2.8.0/CUDA12.8、transformers4.57.3；BF16、不量化；模型 HF commit a09a35458c702b33eeacc393d103063234e8bc28。既有环境/模型只读复用。config/config.json 为用户已批准的正式 full-ReAct 配置，config/minimal_diagnostic.json 留存旧配置，试跑配置单独留存。温度.7、top_p.8、top_k20、repetition_penalty1.05、max_tokens1024、模型上下文32768、50次模型/环境调用、代码30秒/请求60秒/总600秒、环境seed123/采样seed123和124全部固定。

## 问题、偏离与待确认事项

- 初次官方安装器曾写 /home/shn/.appworld/tests，违反写入范围；已告知用户，未知是否覆盖原内容，未擅删。之后明确设置 APPWORLD_CACHE 为项目内。
- 早先提交 60868c60217db18136c19910708816d4a07fdf83 误含原始评测明细；当前版本已移除，只在忽略轨迹保存，但旧历史仍包含。遵守禁止改写已推送历史的要求，未 force push；历史处置待用户决定。
- 未修改缺 CUDA13 的旧 vLLM0.24 环境或系统配置，实际使用已有可运行的0.11环境。
- 权重目前验证存在性、长度与快照 revision；未做15GB全文件内容哈希。因此不能声称已排除所有权重缓存问题。
- 结果提交 da5f8a7 已通过 SSH 正常推送；随后的 HTTPS ls-remote 出现 TLS 中断。已用既有 SSH 地址读回 main，确认与本地一致，不是认证失败，未修改 fetch URL 或 SSH 配置。
- 在本模型阶段汇报后停止。是否开展更强模型对照、预算诊断或后续阶段，由用户确认；任何新大文件下载须另外报告大小、目标路径并取得确认。
