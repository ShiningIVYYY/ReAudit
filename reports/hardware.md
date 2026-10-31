# 硬件与环境探测

探测 UTC：2026-10-31T21:36:26.500718+00:00。原始命令、退出码和输出见 [hardware_probe.json](evidence/hardware_probe.json)。

## GPU

驱动 570.172.08；nvidia-smi 显示 CUDA 12.8（驱动支持上限，不等同于框架 CUDA runtime）；本机 nvcc 为 CUDA toolkit 10.1 / V10.1.243；不能用它代表 vLLM 自带的 CUDA runtime，编译依赖兼容性待核实。

|物理编号|型号|总显存 MiB|已用 MiB|可用 MiB|GPU 利用率|状态|
|---|---|---:|---:|---:|---:|---|
|0|NVIDIA GeForce RTX 4090|24564 MiB|18141 MiB|5952 MiB|0 %|他人任务，禁止使用|
|1|NVIDIA GeForce RTX 4090|24564 MiB|3 MiB|24089 MiB|0 %|探测时空闲；启动前重查|
|2|NVIDIA GeForce RTX 4090|24564 MiB|3 MiB|24089 MiB|0 %|探测时空闲；启动前重查|
|3|NVIDIA GeForce RTX 4090|24564 MiB|3 MiB|24089 MiB|0 %|探测时空闲；启动前重查|
|4|NVIDIA GeForce RTX 4090|24564 MiB|3 MiB|24089 MiB|0 %|探测时空闲；启动前重查|
|5|NVIDIA GeForce RTX 4090|24564 MiB|3 MiB|24089 MiB|0 %|探测时空闲；启动前重查|
|6|NVIDIA GeForce RTX 4090|24564 MiB|3 MiB|24089 MiB|0 %|探测时空闲；启动前重查|
|7|NVIDIA GeForce RTX 4090|24564 MiB|3 MiB|24089 MiB|0 %|探测时空闲；启动前重查|

GPU 0：PID 1169430，用户 zsc，进程 pt_main_thread，compute 显存约 18,118 MiB。0% 利用率不代表可使用：该进程仍持有显存。未打断任何进程。其余卡当时无 compute 进程。

本轮实际使用 GPU：无；GPU 执行次数为 0。后续建议首个小模型使用 CUDA_VISIBLE_DEVICES=1，27B BF16 方案考虑 1,2,3,4；这只是候选分配，不构成资源预留，必须临近启动再次探测。编号按本次 nvidia-smi 物理索引，UUID 对应见证据。

## CPU、内存和磁盘

CPU：2 × AMD EPYC 7542，每颗 32 物理核、每核 2 线程，总计 64 物理核 / 128 逻辑 CPU。内存约 251 GiB，总可用约 222 GiB。/data1 位于 /dev/nvme1n1p1，约 6.9 TiB，总剩余约 1.3 TiB（81% 已用）；精确字节数见探测 JSON。

## Python、环境与缓存

系统 /usr/bin/python3 为 3.8.10。发现 /home/shn/miniconda3 和 /data1/shn/anaconda3。完整环境清单与以 dist-info 读取的版本见 [cache_and_environments.json](evidence/cache_and_environments.json)；未向既有环境安装、升级任何包，未导入 GPU 框架。
- /home/shn/miniconda3/envs/alfworld：Python 3.9.25；vllm-0.11.0.dist-info。仅证明包元数据存在，不证明可运行。
- /home/shn/miniconda3/envs/ee-qwen38：Python 3.12.0；vllm-0.30.0.dist-info。仅证明包元数据存在，不证明可运行。
- /home/shn/miniconda3/envs/ee-qwen38-direct：Python 3.12.0；vllm-0.11.0.dist-info。仅证明包元数据存在，不证明可运行。
- /home/shn/miniconda3/envs/rlvmr-sciworld：Python 3.10.20；vllm-0.8.2.dist-info。仅证明包元数据存在，不证明可运行。
- /home/shn/miniconda3/envs/verl-agent：Python 3.12.0；vllm-0.11.0.dist-info。仅证明包元数据存在，不证明可运行。
- /home/shn/miniconda3/envs/verl-agent-webshop：Python 3.10.20；vllm-0.8.2.dist-info。仅证明包元数据存在，不证明可运行。
- /home/shn/miniconda3/envs/vllm：Python 3.10.19；vllm-0.6.6.post1.dist-info。仅证明包元数据存在，不证明可运行。
- /home/shn/miniconda3/envs/vllm-cu128：Python 3.12.13；vllm-0.24.0.dist-info。仅证明包元数据存在，不证明可运行。

未在此次可枚举的 Python 环境中发现 AppWorld dist-info；不能据此断言整机任何位置均未安装。

你名下 HF 缓存中 Qwen2.5-7B-Instruct commit a09a35458c702b33eeacc393d103063234e8bc28 的四片权重存在，文件长度逐一与官方元数据一致；只读原缓存、未复制。Qwen3-8B 同一用户的快照缺少全部五片最终权重，存在 .incomplete，不能当完整模型使用。证据：[own_cache_validation.json](evidence/own_cache_validation.json)。

有限深度只读扫描 /data1 常见模型/缓存目录，发现 /data1/laip/models/Qwen/Qwen3-8B 的五片文件，但未验证其官方 revision，也未使用该他人目录。发现其他名字相似的 Base、微调、Qwen3.5-9B、Qwen3.8-27B 等，均不替代指定候选。未找到可确认的准确 Qwen3.5-27B 缓存。扫描非穷尽，权限不足的目录跳过并记录；“未找到”不等于服务器绝对不存在。

## 显存可行性：推算，未部署验证

权重大小来自官方 HF safetensors 元数据，见 [模型核实](model_verification.md)。BF16 的近似存储为参数数 × 2 字节；运行还需 KV/state cache、activation、CUDA graph 和框架开销。GiB 使用 2^30 字节。

|模型|官方权重文件合计|权重近似显存|当前空闲卡上的判断|
|---|---:|---:|---|
|Qwen/Qwen2.5-7B-Instruct|15.231 GB|14.19 GiB|单张 4090 BF16 + 受限上下文/并发预计可行，无需量化；实际启动待验证。|
|Qwen/Qwen3-8B|16.382 GB|15.26 GiB|单张 4090 BF16 + 受限上下文/并发预计可行，无需量化；长上下文更紧张。|
|Qwen/Qwen3.5-27B|55.563 GB|51.75 GiB|单卡与双卡 BF16 均放不下权重；建议 4 张空闲卡 TP=4 + 受限上下文，约 12.94 GiB 权重/卡，实际支持/性能待验证。|

两张卡标称总显存约 47.98 GiB，小于 27B 的约 51.75 GiB 权重，不能仅用 BF16 TP=2。TP=4 与其 24 attention heads / 4 KV heads 可整除，当前有足够空闲卡；仍须检查框架对 hybrid 架构的分片约束和 PCIe 通信性能，不保证可启动。4-bit 的理想权重下限约 12.94 GiB、8-bit 约 25.87 GiB，另需量化元数据/缓存；单卡 4-bit 仅是可考虑方案，未选择量化格式或核实 kernel，不可声称量化部署已可行。

普通 GQA BF16 KV 粗估：2 × 层数 × KV heads × head_dim × token数 × 2 bytes。7B 在 32,768 tokens 约 1.75 GiB，8B 约 4.50 GiB，未计 activation 等。因此不能把模型卡最大上下文当作单卡可用上下文。Qwen3.5 有 hybrid recurrent state，不能照搬该 GQA 公式。建议先以单并发、较短上下文探测，再固定三个模型一致的执行约束；具体值等待官方 agent 输入长度核实和用户确认。

Qwen3.5 模型卡演示 TP=8 的 262,144 上下文方案；当前 8 张中有 1 张被他人占用，不能照搬该示例。关闭思考和降低上下文有可比性/性能权衡，未实测前不作成功率判断。

## 待确认事项

- 首个模型待用户决定，建议优先已有完整缓存的 Qwen2.5-7B-Instruct。
- GPU 分配仅为当前时点建议，尚未启动或预留。
- 需要独立 Python 3.11+ 环境；AppWorld、官方 agent、推理框架实际安装版本和 CUDA 兼容性尚未验证。
- 任务、评分、平均 token、耗时、GPU 小时、金额均未测量。
