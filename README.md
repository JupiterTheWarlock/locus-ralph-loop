# Locus Ralph Loop

Locus Ralph Loop is a Locus plugin that adds a Ralph-style controller View for long-running agent work.

The plugin does not patch Locus core or launch a separate coding CLI. It runs inside a Locus View and drives Locus sessions through the public View runtime session API.

## Components

- `views/ralph-loop`: controller panel for starting, pausing, and tracking loop iterations.
- `skills/ralph-loop`: iteration contract for Locus agents.
- `rules/ralph-loop-guardrails.md`: lightweight guardrails for focused checkpoint work.

## Install From Source

Use Locus plugin install from this repository root or GitHub repository:

```text
locus.plugin.json
views/ralph-loop/
skills/ralph-loop/
rules/ralph-loop-guardrails.md
```

## How It Works

The View stores loop state in the active workspace:

- `Locus/ralph-loop/state.json`
- `Locus/ralph-loop/progress.md`

Each iteration sends one focused prompt to a Locus session, waits for the run to finish, records the result, and continues until the agent emits one of:

- `RALPH_LOOP_DONE`
- `RALPH_LOOP_BLOCKED`
- `RALPH_LOOP_CONTINUE`

## Status

This is an early public scaffold. It is designed to validate the plugin-based loop architecture before adding richer verifiers, PRD import, and task-list scheduling.
