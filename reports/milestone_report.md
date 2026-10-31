# Milestone report

## 当前边界

本轮仅执行阶段 1 步骤 1（0.1–0.4）：服务器、硬件、目录和初始仓库。
开始证据时间 2026-10-31T21:36:26.500718+00:00；报告生成 2026-10-31T21:41:20.809117+00:00。
从首次保存探测证据至此约 4.9 分钟；不含此前连接检查及用户确认等待。
尚未进入环境安装或实验阶段。

## 已做工作和证据

- ssh lab 成功连接 shn；/data1、/data1/shn 存在且可写，项目原先不存在。创建 /data1/shn/ReAudit，没有覆盖既有内容。
- 创建 README、目录骨架、requirements 占位与 .gitignore；临时目录为项目内 tmp/。
- GPU、CPU、内存、磁盘、环境、模型缓存只读探测见 hardware.md 和 evidence/。
- 3 个指定模型的准确仓库名、HF commit、权重大小、上下文和可核实参数见 model_verification.md。
- GPU 0 属于他人任务，未操作；本项目本轮没有启动 GPU 进程。
- Git main 已初始化；origin 指向指定 HTTPS URL。git ls-remote 返回码为 0、无任何 ref，远程在检查时为空，无需合并。
- 认证检查仅保存配置存在性：已有 SSH key 文件，HTTPS credential helper 未配置；未读取任何凭据内容。首次 HTTPS 推送认证失败；后续确认既有 SSH key 可用，见恢复记录。

## 执行数量和验收

实际加载 train 任务数：0。实际完整执行数：0。模型调用数：0。实验异常数：0（尚无实验）。
三模型成功率、逐任务成功次数、token、耗时和成本均为“未验证”，不是 0%。
未生成 task_manifest.csv、config.json 或 runs.csv，避免制造任务和结果。

|验收项|当前结果|
|---|---|
|8 个任务加载和重置|未验证，等待环境与官方 train 数据|
|每模型 16 个唯一 run_id 和结果/异常|未开始|
|同任务两次初始指纹一致|未验证|
|离线重读官方评分结果|未验证|
|超时/异常分类正确|未验证|
|成本表、隔离测试、备选环境调研、四条件 mock|后续阶段，未开始|

## 问题与不确定处

- Git 2.25.1 不支持 git init --initial-branch=main，已改用 git init 后 git symbolic-ref HEAD refs/heads/main；没有既有历史可改写。
- 有两次本机沙箱执行长 ssh 命令返回：ssh: connect to host 10.20.98.46 port 35461: Operation not permitted。经工具授权后仍只使用同一个 ssh lab 恢复连接，未修改 SSH 配置、未尝试其他主机。
- 服务器 GitHub API 请求失败：URLError(SSLEOFError(8, 'EOF occurred in violation of protocol (_ssl.c:1145)'))。未配置镜像或代理；AppWorld 实际版本/API 尚未验证。
- HF 模型卡与配置等小文件可直连获取；这不证明大文件下载速度或稳定性。没有下载模型权重。
- 7B 自有缓存权重长度匹配；内容哈希未核验。8B 自有缓存不完整；其他用户目录不直接作为部署依赖。27B 缓存未找到（非穷尽检查）。
- 系统 nvcc 为 CUDA 10.1，驱动报告 CUDA 12.8；不能直接假定系统 toolkit 可编译新框架，独立环境需验证 CUDA wheel/驱动兼容。
- 27B BF16 四卡、推理框架兼容性、上下文限制和耗时均未实测。低成功率适用性结论须待真实数据，当前无法判断。
- 全部后续依赖精确 pins、运行配置、官方 agent、train-only 数据准备方式和许可需在下一检查点核实。

## 用户决策与下一步

本检查点提交与 push 尝试后停止。下一步须确认继续，并选择第一个模型；建议 Qwen/Qwen2.5-7B-Instruct（完整自有缓存，单卡容量预计够用）。
确认后先创建项目内独立 Python 环境，核实安装版本、官方 agent 和 train 数据，只做 1 任务 × 1 次完整执行。
如有模型或其他大文件下载，另行提交大小、路径供确认。
推送状态与 commit 以实际 git 证据/本轮最终汇报为准；不得将本报告生成时的“尚待 push”当作已推送。

## 本检查点提交、验证和推送结果

初始提交：38d024c754091c72c9ccb99fd6d70b845252ca37。执行 git push -u origin main 退出码 128。完整错误：

    fatal: could not read Username for 'https://github.com': terminal prompts disabled

证据：[git_push_attempt.json](evidence/git_push_attempt.json)。首次推送未发布本地提交；最新状态见下文恢复记录。HTTPS 未配置可用认证，需要用户在服务器处理；不要求粘贴 token，不更换 URL、不修改 SSH 配置、不尝试替代认证。

提交前已运行 git status 与 git diff --cached --stat；检查已暂存文本凭据模式、私钥、权重扩展名及 >50 MiB 文件，未发现问题，仓库约 200 KB，最大单文件约 92 KB。见 prepush_checks.json。忽略规则已验证覆盖 .env、credentials、权重、环境缓存、轨迹、tmp 与字节码。原始官方模型卡保留字节和 SHA256，包含上游行末空格；本项目自写文件通过 whitespace 检查。

本轮没有实现运行代码，未运行实验或代码单元测试。JSON 证据解析、官方原文 SHA256 和忽略规则属于文档/仓库检查，不替代阶段 1 实验验收。到此停止等待用户处理认证并确认下一阶段。

## 既有 SSH 认证核实与推送恢复

用户指出已配置认证后，实测默认 SSH 与显式 id_ed25519 都成功认证为 ShiningIVYYY。之前的 HTTPS 失败只表明 HTTPS 未获得凭据，不能推出 SSH 未配置。初次诊断未先测试 SSH，现已纠正，无需用户重新添加 key。

只对本仓库设置 remote.origin.pushurl=git@github.com:ShiningIVYYY/ReAudit.git，保留 origin 的 HTTPS fetch URL。不改 SSH 配置、不读私钥内容、不新增 token。测试启用 StrictHostKeyChecking=yes 和 UpdateHostKeys=no，未写 known_hosts。证据：[github_ssh_auth.json](evidence/github_ssh_auth.json)。

恢复推送前再次检查远程，仍为空；已执行原定 git push -u origin main，退出码 0，main 成功创建并设置跟踪 origin/main。首次成功推送 commit：1865d59b15b66f13da2748efd93eee0538b64ee3，UTC 2026-10-31T21:53:05.666752+00:00。随后读取 refs/heads/main 与该 commit 一致。证据：[git_ssh_push_success.json](evidence/git_ssh_push_success.json)。

本恢复记录将再提交并正常推送；最终分支一致性检查保存在项目 tmp/git_sync_verification.json，并在最终汇报给出最新 commit。当前检查点只处理仓库发布，未安装环境或运行实验；下一阶段仍需用户确认。
