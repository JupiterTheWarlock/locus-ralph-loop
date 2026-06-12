# Ralph Loop Guardrails

When working under a Ralph Loop controller:

- Treat each turn as one focused checkpoint, not a broad rewrite.
- Prefer durable progress in repository files over relying on chat context.
- Verify every meaningful change with the cheapest relevant check.
- Stop with `RALPH_LOOP_BLOCKED` when user input, credentials, unavailable tools, or external state prevents meaningful progress.
- Stop with `<promise>COMPLETE</promise>` only when the objective and stated verification criteria are satisfied.
