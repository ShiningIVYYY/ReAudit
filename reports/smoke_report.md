# Qwen2.5-7B single-run smoke

- run_id：run_20261102T204402_a2ede390b641484bb7412ff0cffcb191
- task_id：e3d6c94_3（官方 train，固定清单第一个任务）
- status：error；failure_type：context_overflow；官方 TGC：未验证/未知；SGC：单次执行不定义。
- 模型调用：38；环境步骤：37；语法错误步骤：36。
- prompt tokens：未验证/未知；completion tokens：未验证/未知；usage_complete：False。
- 已知部分：586846 prompt / 28617 completion tokens；不把未知部分记成零。
- 完整执行耗时：532.951364217326 秒；LLM 调用耗时合计：525.5272280778736 秒。
- GPU：物理卡 [7]，RTX 4090；采样显存峰值 20753 MiB；串行、单并发。
- 初始指纹与两次独立 reset 一致：True；完整输入哈希一致：True。
- 重读官方评分退出码：0；评分过程不调用模型。汇总见 evidence/smoke_checks.json；原始明细保存在本地 git 忽略轨迹。
- 只运行了这一个完整执行；其余 7 个任务未运行，8×2 与其他模型未开始；不能由 1 次试跑估计总体成功率。
- 没有修改官方 agent 输出解析、没有剥围栏或修复模型代码。具体格式问题以逐步原文和官方执行返回为证。
- 模型服务进程已退出；再次观测 GPU 7 仅 3 MiB、0% 利用率，已释放。见 evidence/gpu_release.json。
- 全轨迹：runs/traces/run_20261102T204402_a2ede390b641484bb7412ff0cffcb191（服务器本地、git 忽略）；小体积结果：runs/runs.csv。

后台范围到此结束；没有自动扩大实验规模。下一步等待用户确认。

官方离线诊断评分 TGC=0，重复读取保存的输出得到相同 success/difficulty/num_tests：True。主运行仍保留 context_overflow 和 score 空值，不能把基础设施异常改记 task_failed。

服务启动至停止记录落盘约 29.45 分钟，包括加载、准备和闲置等待；单次执行为 532.95 秒。前者不是精确 GPU 活跃时长，不能忽略这些额外占用，也不据此外推 1000 次成本。
