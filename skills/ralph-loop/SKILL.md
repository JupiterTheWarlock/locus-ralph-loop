---
tools:
  - bash
  - read
  - edit
  - grep
  - ask_user_question
---

# Ralph Loop

Use this skill when a Locus Ralph Loop controller asks you to advance a long-running task by one checkpoint.

## Loop Contract

Each invocation is one iteration. Keep the step focused, verify what changed, and leave durable state in files the next iteration can read.

1. Read the objective and current repository state.
2. Choose one checkpoint that moves the objective forward.
3. Make only the scoped change needed for that checkpoint.
4. Run the most relevant lightweight verification available.
5. Append useful findings to `Locus/ralph-loop/progress.md` when the controller has created it.
6. End with exactly one marker on its own line:
   - `RALPH_LOOP_DONE` when the objective is complete and verified.
   - `RALPH_LOOP_BLOCKED` when user input or an external state change is required.
   - `RALPH_LOOP_CONTINUE` when more work remains.

## Output Shape

Keep the final response short:

- Checkpoint completed.
- Verification result.
- Next checkpoint, if any.
- One required marker line.

Do not claim completion without concrete verification.
