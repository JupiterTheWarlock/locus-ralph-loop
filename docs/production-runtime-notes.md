# 生产环境 Runtime 备注

这个插件在判断“可用/稳定”之前，需要放到实际安装版 Locus 生产环境里测试。仅看源码或 View 预览不够，因为插件依赖的是安装版 Locus View host 实际开放出来的 runtime API。

## 当前已知卡点

- 归档 API 没有开放给 Locus View。
  - 影响：`归档本批次` 和 `完成后自动归档` 不能真正归档 Ralph Loop 创建的会话。
  - 当前插件表现：View 会显示 `The installed Locus View runtime does not expose session archive API yet.`
  - 期望能力：开放 View 安全的 `session.archive(sessionId)`，映射到 Locus 现有会话归档能力。

- Models API 没有开放给 Locus View。
  - 影响：模型选择不能稳定依赖 runtime 的模型列表和当前模型能力。
  - 当前插件表现：如果 `view.models` 或旧版 `window.locus.models` 不存在，View 会退回读取本地 Locus 配置/缓存文件。
  - 期望能力：开放 View 安全的 `models.list()` 和 `models.current()`，或等价的稳定会话模型选择 API。

## 生产环境测试清单

以下检查需要在实际安装版 Locus 中执行，不只是在源码或 dev host 中执行：

- 从源码安装插件，并打开 `Ralph Loop` View。
- 确认 View 可以加载、保存、重载这些状态：
  - 目标
  - 语言
  - 已选模型
  - 最大迭代次数
  - 会话 ID 列表
  - 运行记录
- 跑一个 2-3 轮的短批次，确认：
  - 每轮都会创建新会话
  - 第一轮会话被记录为 root session
  - 后续会话保持预期的父子关系
  - 每轮后都会更新 `Locus/ralph-loop/state.json`
  - 每轮后都会追加 `Locus/ralph-loop/progress.md`
- 检查等待运行结果的行为：
  - 已完成 run 会继续下一轮
  - `waiting_input` 会把循环置为 `blocked`
  - 达到最大迭代次数会把循环置为 `paused`
  - 输出 `<promise>COMPLETE</promise>` 会把循环置为 `done`
- 检查模型行为：
  - 如果 runtime 暴露 models API，模型列表能正常出现
  - 如果 runtime 没暴露 models API，fallback 模型列表能正常工作
  - 新建会话实际使用了选择的模型
- 检查归档行为：
  - runtime 有归档 API 时，手动 `归档本批次` 会归档全部记录的 session IDs
  - `完成后自动归档` 只在循环进入 `done` 后触发
  - 重复归档会跳过已经归档的会话
  - 归档失败时不破坏状态，并显示可见错误
- 检查重置行为：
  - reset 会清空运行/会话/归档状态
  - reset 会保留目标、模型、语言、最大迭代次数
  - reset 会清空 `Locus/ralph-loop/progress.md`

## 后续需要统计的 Runtime 缺口

后续测试如果继续发现卡点，建议整理成一个统一的 Locus runtime API 请求/PR，而不是拆成多个零散请求：

- `session.archive(sessionId)`：用于 View 自己创建的批次会话清理。
- `models.list()` 和 `models.current()`：用于 View 内稳定模型选择。
- 确认 `session.chat(... wait.includeEvents)` 在生产环境是否返回足够的 final text/status 信息，支撑自动循环控制。
- 确认 View 创建的 parent session 关系在普通会话树中是否可见且稳定。
- 确认 View 对 `Locus/ralph-loop/*` 的文件读写在不同 workspace 和已安装插件环境下是否稳定。
- 确认 View 能否安全读取自己创建会话的 active run 状态和事件。

## 统一请求/PR 应包含

- 插件名和使用场景：Ralph Loop controller View，用于长批次会话循环。
- 每个 API 缺口阻塞了哪个用户功能。
- 希望开放的最小 runtime API 面。
- 上面生产环境测试清单中的复现结果。
- 被阻塞功能的错误文本或截图。
