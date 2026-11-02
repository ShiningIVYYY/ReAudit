# ReAudit milestone report

## 当前结论与边界

用户批准的官方完整版 ReAct 单次试跑已结束。平台已记录真实模型调用、初始快照、完整输入、轨迹、超时与保存状态的官方评分；尚无真实任务成功案例。新的 8×2 基线、其他模型和后续阶段均未完成，不能宣称任务包一已验收。

当前 4 次真实完整执行均为 Qwen/Qwen2.5-7B-Instruct：
- 旧 official_minimal_react：3 次诊断执行，官方保存状态 TGC 0/3；2 context_overflow、1 task_failed。用户选完整版后已停队列，旧 16 次计划只完成 3 次。
- 新 official_full_react：1 次试跑，task_id=e3d6c94_3，seed=123，49 个环境步骤、0 个语法错误；第 50 次模型请求未完成时触发 600 秒 watchdog。status=error、failure_type=timeout，不能改记 task_failed。保存状态的官方 TGC=0，重复评分一致。
- 4 个 run_id 均唯一；没有删除或重跑失败来补成功率。新旧 agent 不合并为一张基线成功率表。

## 新版试跑证据

run_id：run_20261102T222456_8c8bccbc839842cc9d44895dbb00875a。
报告 full_react_pilot.md；汇总 evidence/full_react_pilot_checks.json；按执行区分 agent 的索引 evidence/run_index.json；全轨迹在服务器 runs/traces/<run_id>/，git 忽略。
完整输入哈希 0f698153689b9ccc471443af48516095b0583307f3d99347e3b392194e57e1e4；实际初始世界指纹与两次独立 reset 一致。首个实际模型输入与 build_prompt 字节一致。
实际执行耗时 600.115885 秒。49 次请求返回了 usage，最后 1 次被中断；已知 prompt tokens=260240、completion tokens=32378，仅为下界，未知部分不记成零。后置官方评分不调用模型，CPU 耗时另存在 score_enrichment.json；不冒充原执行 latency 的组成部分。
GPU 7 的服务进程已退出，复查 3 MiB / 0% 利用率。服务 launch-to-stop-record 窗口 625.303 秒，包括加载/准备，不等同于精确 GPU 活跃时长；见 evidence/full_react_pilot_release.json。没有美元单价或金额估算。

## Agent、版本与来源

AppWorld=0.1.3.post1；官方 source commit=66ad8099e12188ece0d3fe45e661dbc01880813b。
完整版实际使用官方 AppworldReactController、AppworldPromptedLMModel、AppworldEnvironmentModel、AppworldAnswerer 与 Recoma 0.0.4 BestFirstSearch 的原始方法。模型调用换成独立 OpenAI 兼容适配层；其余仅有日志/技能接口和读 config 的环境初始化。
Recoma 整包锁定的 litellm==1.37.19 当前 PyPI 不可得。没有换镜像或擅选另一个 LiteLLM；保留实际 wheel 中 core/search 源码，只调整包入口以跳过未使用后端/UI。parser/controller/search 方法原文哈希已核对。所需 Python 源码已全部进入 git，models/ 通用忽略规则有仅限 Recoma .py 源码的例外，权重仍忽略。
只新增 treelib=1.8.0、six=1.17.0（约 42 KB），未下载权重或推理框架。requirements-full-react.txt 固定依赖；pip check 通过。
vLLM=0.11.0，PyTorch=2.8.0/CUDA12.8，Transformers=4.57.3；BF16、不量化；HF commit=a09a35458c702b33eeacc393d103063234e8bc28；模型与既有推理环境只读复用。
配置：config/full_react_pilot.json。temperature=.7、top_p=.8、top_k=20、repetition_penalty=1.05、max_tokens=1024、模型上下文32768、最大模型调用/环境执行均50、代码30秒、请求60秒、完整执行600秒。官方 24000 字符 prompt 裁剪、100000 字符历史上限均固定在配置中。根 config.json 保留旧 minimal 诊断配置，未擅自将新版正式用于三模型。

## 数据与验收逐条结果

|项目|结果与证据|
|---|---|
|只用官方 train|官方 data-0.1.0.bundle 经批准下载；仅提取 train.txt、90 个 train 任务与公共资源；不加载其他划分任务|
|固定8任务与覆盖|实际官方 ID；Random(1729) 抽样；公开文本覆盖 Spotify/Venmo/phone/simple_note；data/task_manifest.csv|
|8任务加载/重置|每个任务2次独立进程初始化，8/8 指纹相同；evidence/initial_state_checks.json|
|新版初始状态一致|真实 full-ReAct 试跑与其两次 reset 指纹一致|
|每模型16次|未完成；旧3次停止，新版1次，不混合统计|
|执行记录唯一/异常原因|4个真实 run_id 唯一；timeout/context_overflow/task_failed 分开；runs/runs.csv|
|评分可读保存结果|新版超时后的官方保存状态 TGC=0，复读一致；保持 timeout，不把基础设施失败改为 task_failed|
|异常路径|真实 watchdog 超时和上下文溢出已发生并记录；专门0.05秒注入测试尚未运行|
|关键测试|20项通过；CPU mock 官方搜索→执行→评分通过，真实模型调用0，未冒充GPU试跑|
|输入隔离脚本/四条件mock|后续阶段，未完成；当前只预留技能接口|
|成本表/备选环境|完整对比和1000次成本推算尚未完成，不能用单次或混合agent结果外推|

## 失败原因与适用性

旧 minimal 的主要问题是把自然语言直接当 Python 执行；新版原生 parser 消除了本次语法格式失败，但未让任务成功。新版反复使用不存在的 spotify.session，把 headers/params 传给 Munch.get，并有函数名拼写不一致；是模型 API 使用错误，不能归咎于输出解析器或声称已解决任务。
一个任务未成功不足以推断该模型所有任务的成功率。新版正常成功完成路径尚无真实任务通过证据；是否适合后续技能实验仍待完整基线。没有扩大上下文、修改官方解析/评分，或隐藏失败。

## 遇到的问题、偏离与待处理事项

- 初次官方安装器把包测试写入 /home/shn/.appworld/tests，违反写入范围；已告知用户，未知是否覆盖原内容，未擅删。后续均显式 APPWORLD_CACHE 在项目内。
- 早先提交 60868c6 的评分摘要误含原始评测明细；当前版本已移除，明细仅留忽略轨迹，但历史仍含该内容。遵守用户禁止改写已推送历史要求，未 force push，不能声称历史已清理；待用户决定。
- 旧 vLLM 0.24.0 环境需要缺失的 CUDA13 库，未修改它或系统配置，改用已有可导入且实测启动的0.11.0环境。
- 模型完整权重只验证存在性、长度和快照 revision，未重新读取15GB做全文件内容哈希。
- GPU 2 被他人占用时启动脚本拒绝启动；实际仅使用当时空闲GPU7，未停止他人进程。
- 新增的异常后官方评分只补充实际 TGC，原始 status/failure_type 和请求/响应轨迹不改；评分错误留未知，不猜成0。

当前停在“官方完整版单次试跑”检查点。需用户确认是否采用该 agent 统一三个模型，并先完成 Qwen2.5-7B 的新版8×2基线。本次失败可占新版一个固定重复槽位，不重新计费。其他模型部署/大文件下载须另行确认。

## Approved full baseline continuation

用户已确认继续 Qwen2.5-7B 新版8×2。根配置切换为已试跑的 official_full_react，模型/解码/50步/600秒上限/seed未变；仅 purpose 元数据改为 baseline_full_react。续跑应复用新版已有 timeout 试跑，新增15次，不重试失败；完成后受控0.05秒超时检查单列，停止并释放GPU、复读官方评分、提交推送，等待下一模型确认。
