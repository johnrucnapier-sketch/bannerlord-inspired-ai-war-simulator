# A-R3 发布后本地独立评测：完整数据补充

2026-10-31，按项目所有者安排，由 Mac/RIG 协助云端执行权限和资源有限的 **GPT dot** 完成测试，并公开供 **GPT dot 改进 A-R3** 与 **Grok Bot 研究破局**。最终 **168 局正式对抗**，A-R3 胜/平/负 **139/0/29**；另附 12 次短测，短测不计入正式结果。

测的是提交 `77f763fa461a82ef9b6e2102bf2c9e6d62670987` 中原样的 `independent-a-r3`，不是 A-R4。原来的 A-R3 源码、8 局开发数据、README、REPORT、MANIFEST 和 SHA256SUMS 都保持原样。本目录是随后追加的独立证据。

## 发布前发现的错误统计遗漏与补救

首轮 120 局的宿主 `agent_errors` 都为 0。完整公开审查 stderr 时发现：Grok v21 在 `seed=705074451 / A-R3 红方` 内部捕获 116 次 `KeyError: 'garrison'`；Grok v22 在 `seed=475163105 / A-R3 红方` 内部捕获 142 次相同异常。这两局都是 A-R3 获胜。策略自身捕获异常后输出合法的空命令，因此宿主没有记录为协议错误或超时。

**此前只按宿主计数概括为“零策略错误”不准确。** 已明确纠正，异常局和堆栈完整保留。根据预先声明的“策略故障也扩样”，v21、v22 分别用预登记的后 12 个新种子再交换阵营、追加 24 局；其余版本各 24 局。没有修改、重跑或替换首轮局。此问题属于旧版策略实现的观测字段处理问题，不能把受影响局当成纯战术强弱证据。

最终：宿主超时/协议错误合计 **0**；检测到策略内部捕获异常的对局 **3**（详见 [stderr-audit.json](stderr-audit.json)）；引擎拒绝命令 **59** 条。三者分别统计。

## 最终直接对抗结果

| 对手 | 局数 | A-R3 胜/平/负 | 胜率 | 蓝方 | 红方 | A-R3 均分 ± 配对SE | Grok 均分 | 内部异常局 |
|---|---:|---|---:|---|---|---:|---:|---:|
| v20 | 24 | 19/0/5 | 79.2% | 8/0/4 | 11/0/1 | 1009.4 ± 112.7 | 373.1 | 0 |
| v21 | 48 | 42/0/6 | 87.5% | 20/0/4 | 22/0/2 | 1136.5 ± 54.6 | 240.7 | 1 |
| v22 | 48 | 36/0/12 | 75.0% | 18/0/6 | 18/0/6 | 1030.7 ± 78.8 | 354.7 | 2 |
| v23 | 24 | 21/0/3 | 87.5% | 12/0/0 | 9/0/3 | 1121.5 ± 98.4 | 256.8 | 0 |
| v24 | 24 | 21/0/3 | 87.5% | 12/0/0 | 9/0/3 | 1187.5 ± 80.9 | 225.9 | 0 |

分数使用已测提交的 `score_suite.py` 单局公式，是本次直接交锋的均分，不是旧四锚点排行榜总分，不能混排。配对SE由同一种子的红蓝两局均分计算。胜平负使用引擎实际终局胜者，包括到期按城数判胜；未统一到期局在评分中仍属于未统一档。

| 对手 | 首轮24局 | 追加24局 | 排除已知内部异常局后的辅助胜/平/负 | 辅助分母 |
|---|---|---|---|---:|
| v20 | 19/0/5 | 未追加 | 19/0/5 | 24 |
| v21 | 22/0/2 | 20/0/4 | 41/0/6 | 47 |
| v22 | 22/0/2 | 14/0/10 | 34/0/12 | 46 |
| v23 | 21/0/3 | 未追加 | 21/0/3 | 24 |
| v24 | 21/0/3 | 未追加 | 21/0/3 | 24 |

辅助统计仅说明异常局影响，原始主表仍包含全部实测局，不删除失利或异常。不能据此声称修复后的 Grok 会得到相同成绩。

## 云主机先读这些轻量文件

- [games.csv](games.csv)、[results.json](results.json)：全部逐局胜负、结束时刻、分数和故障标记。
- [games/](games/)：每局 result.json、match.json、challenge.json、summary.json；终局统计和城市易手记录无需下载多 GB 的逐轮日志。
- [rejected-commands.json](rejected-commands.json)：每条被拒绝的命令、request_id、原始回执；[stderr-audit.json](stderr-audit.json)：内部捕获异常索引。
- [experiment.json](experiment.json)：初始预登记种子和源码/基线哈希；[publication-correction.json](publication-correction.json)：发布前补审与扩样记录。
- [audit.json](audit.json)、[file-manifest.json](file-manifest.json)、[assets.json](assets.json)、[SHA256SUMS.assets](SHA256SUMS.assets)：计数、文件与下载校验。

## 完整原始记录下载

[GitHub 数据 Release](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/a-r3-validation-20261031)。按对手和轮次分包，每包 24 局，可按需下载；另附 12 次短测的独立包。正式包按 16 MiB 传输分片上传，download_data.py 会自动下载、逐片验哈希、拼接并校验完整压缩包；已下载且校验通过的分片可复用。

| 包 | 局数 | MiB | 类型 |
|---|---:|---:|---|
| [a-r3-v20-round1-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/a-r3-validation-20261031) | 24 | 75.1 | 正式 |
| [a-r3-v21-round1-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/a-r3-validation-20261031) | 24 | 75.4 | 正式 |
| [a-r3-v21-round2-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/a-r3-validation-20261031) | 24 | 73.6 | 正式 |
| [a-r3-v22-round1-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/a-r3-validation-20261031) | 24 | 67.2 | 正式 |
| [a-r3-v22-round2-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/a-r3-validation-20261031) | 24 | 77.5 | 正式 |
| [a-r3-v23-round1-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/a-r3-validation-20261031) | 24 | 68.4 | 正式 |
| [a-r3-v24-round1-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/a-r3-validation-20261031) | 24 | 58.9 | 正式 |
| [a-r3-calibration-20261031.tar.zst](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/download/a-r3-validation-20261031/a-r3-calibration-20261031.tar.zst) | 12 | 4.5 | 短测，不计成绩 |

```sh
python benchmarks/community/a-r3-local-validation-20261031/inspect_results.py --opponent v24 --losses
python benchmarks/community/a-r3-local-validation-20261031/download_data.py --opponent v21 --round 1 --output ./downloaded-ar3
python benchmarks/community/a-r3-local-validation-20261031/extract_data.py --archive ./downloaded-ar3/a-r3-v21-round1-20261031.tar.zst --output ./ar3-data
```

下载脚本验证分片及完整压缩包的大小和 SHA256，不自动解包或运行策略；传输中断后重试会复用已验证分片。解包脚本支持系统 zstd 或 Python zstandard 模块；没有系统安装权限时可在自己的 Python 环境安装 zstandard（例如 python -m pip install --user zstandard）。轻量 JSON/CSV 无需任何额外依赖；可省略 `--round` 下载该版本的两轮。包内每局有双方观察/命令/回执 JSONL（归档整体采用 Zstandard 无损压缩）、stderr、终局结果、协议元数据、challenge 配置与模拟器 `final.save.json`。JSONL 解压后的原始字节及模拟器存档保持不变；发布前对每个解压文件再验 SHA256，压缩方式变化也在清单记录；路径规范化项在文件清单中明确标记，原文件与公开文件哈希同时保留。stderr 的堆栈和异常内容不删除，只替换本机路径。

存档均由本独立模拟器生成，不含第三方游戏存档或资产。全知终局存档仅供离线复盘，不能用于策略运行时输入；公平输入仍仅是该方协议观察。

12 次 84 天短测包括 Mac 4 次和 RIG 8 次，两机共有的 4 个样本物理摘要一致；它们是性能检查和正式种子的截短重复，不是额外独立验证样本。

## 给 dot 与 Grok Bot 的重点入口

1. 先研究并修复 `KeyError: garrison` 的观测字段处理，再用新种子验证；完整堆栈在原始包中，相关局在 stderr-audit.json 中。不要读全知存档弥补运行时迷雾信息。
2. 首轮 v23/v24 中，A-R3 蓝方均 12–0，红方均 9–3；红方失利种子相同：567252128、21462426、119526798。可以对照同种子另一阵营的完整时间线；这只是有限样本现象，尚不是阵营缺陷的因果证明。
3. 首轮 v20 的 475163105 使 A-R3 红蓝两边都失败，是另一类复盘入口。
4. 对照命令拒绝记录，检查可见目标、路径、编制容量和粮食条件；合法性修复不自动等于胜率提升。
5. 发布后的这些种子成为公开开发集；后续策略另建版本并用新预登记种子做独立确认。本次测试不证明普遍最优。

### 所有 A-R3 失利（Grok 获胜）

| 对手 | seed | A-R3 | 结束原因 | 天数 | 记录 |
|---|---:|---|---|---:|---|
| v20 | 475163105 | blue | unification | 316.50 | [对局](games/v20-i02-blue-s475163105-d1680/) |
| v20 | 475163105 | red | unification | 427.58 | [对局](games/v20-i02-red-s475163105-d1680/) |
| v20 | 705074451 | blue | unification | 307.79 | [对局](games/v20-i05-blue-s705074451-d1680/) |
| v20 | 1978498092 | blue | unification | 1262.38 | [对局](games/v20-i09-blue-s1978498092-d1680/) |
| v20 | 1628009501 | blue | unification | 290.25 | [对局](games/v20-i10-blue-s1628009501-d1680/) |
| v21 | 475163105 | blue | time_limit | 1680.00 | [对局](games/v21-i02-blue-s475163105-d1680/) |
| v21 | 1903971585 | blue | unification | 1247.88 | [对局](games/v21-i11-blue-s1903971585-d1680/) |
| v21 | 1726246682 | red | unification | 356.17 | [对局](games/v21-i13-red-s1726246682-d1680/) |
| v21 | 30693680 | blue | unification | 1311.29 | [对局](games/v21-i18-blue-s30693680-d1680/) |
| v21 | 151764629 | blue | unification | 784.38 | [对局](games/v21-i20-blue-s151764629-d1680/) |
| v21 | 345226652 | red | unification | 274.12 | [对局](games/v21-i23-red-s345226652-d1680/) |
| v22 | 549308449 | red | unification | 1571.62 | [对局](games/v22-i01-red-s549308449-d1680/) |
| v22 | 1903971585 | blue | time_limit | 1680.00 | [对局](games/v22-i11-blue-s1903971585-d1680/) |
| v22 | 1263819167 | blue | unification | 1542.17 | [对局](games/v22-i16-blue-s1263819167-d1680/) |
| v22 | 1263819167 | red | unification | 355.67 | [对局](games/v22-i16-red-s1263819167-d1680/) |
| v22 | 519911378 | blue | unification | 1374.58 | [对局](games/v22-i17-blue-s519911378-d1680/) |
| v22 | 30693680 | blue | unification | 435.46 | [对局](games/v22-i18-blue-s30693680-d1680/) |
| v22 | 30693680 | red | unification | 811.04 | [对局](games/v22-i18-red-s30693680-d1680/) |
| v22 | 238519751 | red | time_limit | 1680.00 | [对局](games/v22-i19-red-s238519751-d1680/) |
| v22 | 151764629 | blue | unification | 474.25 | [对局](games/v22-i20-blue-s151764629-d1680/) |
| v22 | 2132858661 | blue | unification | 586.62 | [对局](games/v22-i21-blue-s2132858661-d1680/) |
| v22 | 1675816856 | red | unification | 856.42 | [对局](games/v22-i22-red-s1675816856-d1680/) |
| v22 | 345226652 | red | unification | 437.25 | [对局](games/v22-i23-red-s345226652-d1680/) |
| v23 | 567252128 | red | unification | 957.79 | [对局](games/v23-i03-red-s567252128-d1680/) |
| v23 | 21462426 | red | unification | 665.50 | [对局](games/v23-i04-red-s21462426-d1680/) |
| v23 | 119526798 | red | unification | 513.92 | [对局](games/v23-i08-red-s119526798-d1680/) |
| v24 | 567252128 | red | unification | 957.79 | [对局](games/v24-i03-red-s567252128-d1680/) |
| v24 | 21462426 | red | unification | 1118.62 | [对局](games/v24-i04-red-s21462426-d1680/) |
| v24 | 119526798 | red | unification | 513.92 | [对局](games/v24-i08-red-s119526798-d1680/) |

## 方法与执行

- 冻结 v0.2.0，官方 tools/play.py，1680 天、6 小时决策间隔、2 秒决策时限；策略独立 JSONL 进程，清除 GB_* 环境变量覆盖，UTF-8，PYTHONHASHSEED=0。
- 每个对手先 12 个新种子交换阵营，共24局；首轮 8 < 胜 + 平/2 < 16 时追加24局，或发现策略故障时追加；最多48局。所有对手共享预登记序列。扩样规则是任务分流标准，不是严格固定显著性检验。
- 初轮按 v20→v21→v22→v23→v24 执行；发布审查发现内部异常后补做 v21、v22 的第二轮，异常原因和时点完整公开。
- Mac Python 3.12.10 / 4并发，共92局；RIG Python 3.12.3 / 8并发，共76局。PC不可达未参与。v20批次实测412秒/516秒，从v22起按Mac14/RIG10局分派整对种子。
- 远端结果回收后逐文件 SHA256 校验；最终逐局核对完整状态、源码、配置、种子、阵营、物理摘要和计分。公开检查另扫描全部压缩日志解压内容，去除本机连接信息和绝对路径。
- reproduce.py 仅在显式给定对手、种子、阵营、输出目录时运行；验证已测策略及冻结源码哈希后调用原版比赛入口。原始宿主速度或超时表现可能不同。

本目录及模拟器原创数据按仓库 MIT 许可发布。
