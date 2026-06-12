---
tools:
  - bash
  - read
  - edit
  - grep
  - ask_user_question
---

# Ralph Loop

当 Locus Ralph Loop 控制器投递 `/ralph-loop` 请求时使用本技能。它对齐 Ralph CLI 的核心循环：每轮读取目标、PRD/进展记录和当前仓库状态，只完成一个最高优先级的 pending story 或一个明确 checkpoint，然后把结果留给下一轮继续。

## 循环契约

每次调用就是一次迭代。不要把 Ralph Loop 当成新的 agent 配置入口；它只是普通 Locus 会话输入链路里的循环提示契约。

1. 读取目标、当前仓库状态、已有进展记录。
2. 如果存在 PRD/story 文件，优先选择最高优先级且 `passes: false` 的一项；否则选择一个能推进目标的最小 checkpoint。
3. 只完成这一项，不顺手扩大范围。
4. 运行与本轮改动匹配的轻量验证。
5. 将可复用发现、踩坑、下一轮上下文写入 `Locus/ralph-loop/progress.md`，如果项目中有 `.ralph/progress.txt` 或 PRD 状态文件，也同步维护。
6. 如果本轮完成了一个 story，并且存在 PRD 状态文件，把该 story 标记为 `passes: true`。
7. 如果本轮产生代码改动，按项目习惯提交；没有足够上下文或用户不希望提交时，至少明确列出未提交改动。
8. 最后一行必须单独输出一个停止标记：
   - `<promise>COMPLETE</promise>`：全部目标/story 已完成并通过验证。
   - `RALPH_LOOP_BLOCKED`：需要用户输入或外部状态变化。
   - `RALPH_LOOP_CONTINUE`：还需要下一轮。

## 输出格式

最终回复保持简短：

- 本轮完成的 checkpoint/story。
- 验证结果。
- 下一轮 checkpoint，如果还要继续。
- 最后一行输出唯一状态标记。

没有具体验证，不要声称完成。
