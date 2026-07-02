# Technical Documentation Index

本目录保存后续开发和代码索引用的技术文档。文档按工程边界拆分，避免把所有事实堆在一个文件里。

## Core Documents

- [Phase 1/2 Runtime and UI Implementation Notes](phase-1-2-runtime-ui-implementation.md)
- [系统架构](architecture.md)
- [Agent 协作与开发规则](agents.md)
- [模型与运行时](models-runtime.md)
- [前端架构](frontend.md)
- [后端与 API](backend-api.md)
- [存储与数据模型](storage-data.md)
- [测试与验收](testing-acceptance.md)

## 阅读顺序

1. 先读 [系统架构](architecture.md)，理解三板块和双模型边界。
2. 再读 [模型与运行时](models-runtime.md)，理解显存互斥、runtime 配置和真实模型接入风险。
3. 实现前端时读 [前端架构](frontend.md)。
4. 实现后端接口时读 [后端与 API](backend-api.md)。
5. 做迁移和任务系统时读 [存储与数据模型](storage-data.md)。
6. 开始编码前读 [Agent 协作与开发规则](agents.md) 和 [测试与验收](testing-acceptance.md)。

