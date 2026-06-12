---
tools:
  - bash
  - read
  - edit
  - grep
  - ask_user_question
---

# Ralph Loop

Use this skill when the Locus Ralph Loop controller sends a `/ralph-loop` request. It follows the Ralph CLI loop shape: each iteration reads the objective, durable progress, and current repository state, then completes exactly one highest-priority pending story or one explicit checkpoint before handing context back to the next iteration.

## Loop Contract

Each invocation is one iteration. Do not treat Ralph Loop as a separate agent configuration surface; it is a prompt contract delivered through the normal Locus session input path.

1. Read the objective, repository state, and existing durable progress.
2. If PRD/story files exist, choose the highest-priority item with `passes: false`; otherwise choose the smallest checkpoint that advances the objective.
3. Complete only that item. Do not expand scope opportunistically.
4. Run the cheapest relevant verification for the work performed in this iteration.
5. Write reusable findings, pitfalls, and next-iteration context to `Locus/ralph-loop/progress.md`. If the project also has `.ralph/progress.txt` or PRD status files, keep them in sync when appropriate.
6. If this iteration completes a story and a PRD status file exists, mark that story as `passes: true`.
7. If this iteration changes code, follow the project's commit convention. If there is not enough context or the user does not want commits, clearly list the uncommitted changes.
8. If the full objective/story set is complete and verified, output exactly `<promise>COMPLETE</promise>`. Otherwise, end the response normally after completing one checkpoint.

## Output Format

Keep the final response brief:

- Checkpoint/story completed in this iteration.
- Verification result.
- Next checkpoint, if continuing.
- `<promise>COMPLETE</promise>` only when the full objective is complete.

Do not claim completion without concrete verification.
