# ReAudit

研究技能 A 修改后，技能 B 的边际作用。基于 AppWorld 官方 train 任务、官方 agent/示例与评分实现，逐次记录模型调用、完整执行成本和可复查结果。

当前仅完成服务器与仓库准备；尚无实验流水线、任务 ID、分数或成本测量。requirements.txt 暂无运行依赖，不能据此复现实验。

## 服务器与目录

    ssh lab
    cd /data1/shn/ReAudit

所有服务器写入必须在 /data1/shn 内；本项目后续运行数据、缓存、独立环境和临时目录均计划放在项目内。共享机器不得修改他人进程或系统配置。

- config/：后续固定的 config.json；当前未选择首个模型，未生成运行配置。
- src/：后续 prompt 构造、官方 agent 适配、模型调用、轨迹和计费。
- scripts/：后续模型启动、实验、输入隔离、四条件脚本。
- data/：后续从官方 train 实际读取的 task_manifest.csv；大型下载不进 git。
- runs/：后续 runs.csv 汇总；其余原始输入输出、轨迹不进 git。
- reports/：硬件、模型核实、阶段报告和小体积原始证据。
- tests/：后续隔离、四条件 mock 与必要的故障路径验证。
- tmp/：项目临时目录（git 忽略）。
- runtime/：后续独立环境、官方数据、模型/框架缓存和实验输出（git 忽略）。

## 当前证据与检查点

见 [硬件报告](reports/hardware.md)、[模型核实](reports/model_verification.md)、
[阶段报告](reports/milestone_report.md)。
reports/evidence/ 保存时间戳、命令、退出码、硬件输出、只读缓存检查、
模型官方 commit 与小体积源文件。缓存文件仅核对存在性和字节数，未进行完整内容哈希校验。

第一个检查点（0.1–0.4）提交并尝试推送后，须用户确认才能创建 Python 环境、
安装 AppWorld 或执行任务。模型大文件下载还需事先报告大小、路径并获得单独确认。
任何未实测结论均不视为验收通过。

## 后续复现要求（尚未实现）

优先使用 AppWorld 官方 ReAct agent/示例；确认实际安装版本和 API 后，
才补充固定依赖、安装命令、模型启动命令和运行命令。官方入口：
https://github.com/stonybrooknlp/appworld 。官方当前 README 要求 Python 3.11+，
系统 Python 3.8.10 不可直接作为项目环境。

仅从官方 train 选取 8 个任务，固定选取种子并尽量覆盖至少两类应用/操作；
逐模型先做 1 次完整执行，再经用户确认运行 16 次。
同一任务每次从相同初始状态开始；基础设施异常与 task_failed 分开。
max_model_len、temperature、seed、步数、超时、模型 revision、精度、思考模式、
框架版本和 GPU 分配必须来自后续 config.json，不得在代码中隐藏默认值。
技能版本仅写日志，移除技能只去掉该技能文本；四条件复用执行按 run_id 去重成本。

密钥仅从环境变量读取，不进入 prompt、日志或 git。
禁止接触 test-normal/test-challenge 任务，禁止改评分或为模型放宽解析。

## Git 传输

origin 的读取地址保持 https://github.com/ShiningIVYYY/ReAudit.git；本仓库单独设置 SSH 推送地址 git@github.com:ShiningIVYYY/ReAudit.git，复用服务器已有、已认证为 ShiningIVYYY 的 SSH key。未修改全局 Git 或 SSH 配置。
