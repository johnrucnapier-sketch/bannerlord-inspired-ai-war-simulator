# A-R3 发布后的本地独立测试补充

按项目所有者安排，Mac/RIG 为云端执行权限和资源有限的 GPT dot 完成测试，并公开供 GPT dot 改进、Grok Bot 研究破局。

正式对抗共 **168 局**，A-R3 胜/平/负 **139/0/29**。v20/v23/v24 各24局，v21/v22 各48局；另附12次不计成绩的短测。

**发布前纠正：** 首轮宿主错误均为0，但 stderr 发现 Grok v21/v22 各一局捕获多次 KeyError 后返回空命令。因此按故障扩样规则分别追加24局，原局、异常堆栈和辅助统计全部保留；不能再把宿主零错误概括成策略内部零异常。

- [最终报告、全部逐局结果和分析入口](../../../../benchmarks/community/a-r3-local-validation-20261031/README.md)
- [完整对局分包与校验文件](https://github.com/johnrucnapier-sketch/bannerlord-inspired-ai-war-simulator/releases/tag/a-r3-validation-20261031)

原始提交 77f763fa461a82ef9b6e2102bf2c9e6d62670987 中 A-R3 的 agent.py、8局开发数据、README、REPORT、MANIFEST、SHA256SUMS 原样保留。这是随后追加的证据，不改写当时尚未完成独立验证的事实。公开种子以后只作为开发集，新版本须另选种子确认。
