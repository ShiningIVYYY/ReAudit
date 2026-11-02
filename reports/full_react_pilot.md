# Qwen2.5-7B single-run smoke

- Agent: official_full_react; configuration: per-run snapshot.
- run_id：run_20261102T222456_8c8bccbc839842cc9d44895dbb00875a
- task_id：e3d6c94_3（官方 train，固定清单第一个任务）
- status：error；failure_type：timeout；官方 TGC：未验证/未知；SGC：单次执行不定义。
- 模型调用：50；环境步骤：49；语法错误步骤：0。
- prompt tokens：未验证/未知；completion tokens：未验证/未知；usage_complete：False。
- 已知部分：260240 prompt / 32378 completion tokens；不把未知部分记成零。
- 完整执行耗时：600.1158854402602 秒；LLM 调用耗时合计：574.4012886099517 秒。
- GPU：物理卡 [7]，RTX 4090；采样显存峰值 21325 MiB；串行、单并发。
- 初始指纹与两次独立 reset 一致：True；完整输入哈希一致：True。
- 重读官方评分退出码：0；评分过程不调用模型。汇总见 evidence/smoke_checks.json；原始评分明细只保存在 git 忽略的本地轨迹中。
- 当前 agent 配置只试跑这 1 次；旧 minimal 的 3 次单独保留，不混入新版基线；不能由单次试跑估计总体成功率。
- 官方 agent 解析规则保持原文；完整版使用其自带代码块提取，minimal 直接执行原文。没有自定义修复模型输出。
- 模型服务已收到本项目限定的停止信号；需结合 service_stop.json 和进程状态确认释放。
- 全轨迹：runs/traces/run_20261102T222456_8c8bccbc839842cc9d44895dbb00875a（服务器本地、git 忽略）；小体积结果：runs/runs.csv。

后台范围到此结束；没有自动扩大实验规模。下一步等待用户确认。
