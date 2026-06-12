<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { view } from "@locus/view-runtime";

type LoopStatus = "idle" | "running" | "paused" | "done" | "blocked" | "error";

interface LoopRun {
  iteration: number;
  runId: string;
  status: string;
  summary: string;
  finishedAt: string;
}

interface LoopState {
  objective: string;
  sessionId: string | null;
  agentId: string;
  model: string;
  maxIterations: number;
  iteration: number;
  status: LoopStatus;
  progress: string;
  lastError: string;
  runs: LoopRun[];
}

const statePath = "Locus/ralph-loop/state.json";
const progressPath = "Locus/ralph-loop/progress.md";

const state = ref<LoopState>({
  objective: "",
  sessionId: null,
  agentId: "dev",
  model: "",
  maxIterations: 20,
  iteration: 0,
  status: "idle",
  progress: "",
  lastError: "",
  runs: [],
});

const busy = computed(() => state.value.status === "running");
const canRun = computed(() => state.value.objective.trim().length > 0 && !busy.value);
const statusText = computed(() => {
  if (state.value.status === "idle") return "Ready";
  return `${state.value.status} · ${state.value.iteration}/${state.value.maxIterations}`;
});

async function ensureStateDir() {
  await view.fs.mkdir("Locus/ralph-loop", { recursive: true });
}

async function saveState() {
  await ensureStateDir();
  await view.fs.writeFile(statePath, JSON.stringify(state.value, null, 2), "utf8");
}

async function appendProgress(text: string) {
  await ensureStateDir();
  await view.fs.appendFile(progressPath, `${text.trim()}\n\n`, "utf8");
}

async function loadState() {
  try {
    const raw = await view.fs.readFile(statePath, "utf8");
    const parsed = JSON.parse(String(raw)) as Partial<LoopState>;
    state.value = {
      ...state.value,
      ...parsed,
      runs: Array.isArray(parsed.runs) ? parsed.runs : [],
    };
  } catch {
    await saveState();
  }
}

function iterationPrompt(iteration: number) {
  return [
    "You are running inside a Locus Ralph Loop controller.",
    "",
    `Objective: ${state.value.objective.trim()}`,
    "",
    "Work one focused checkpoint only. Use normal Locus tools and project context.",
    "Before ending, report exactly one status marker on its own line:",
    "- RALPH_LOOP_DONE when the objective is complete and verified.",
    "- RALPH_LOOP_BLOCKED when you need user input or cannot make meaningful progress.",
    "- RALPH_LOOP_CONTINUE when more work remains.",
    "",
    "Also include a short progress summary and the next checkpoint if continuing.",
    `Iteration: ${iteration}/${state.value.maxIterations}`,
  ].join("\n");
}

function classify(text: string): LoopStatus {
  if (text.includes("RALPH_LOOP_DONE")) return "done";
  if (text.includes("RALPH_LOOP_BLOCKED")) return "blocked";
  return "running";
}

async function ensureSession() {
  if (state.value.sessionId) return state.value.sessionId;
  const sessionId = await view.session.create({
    title: "Ralph Loop",
    sessionType: "chat",
    agentId: state.value.agentId || "dev",
  });
  state.value.sessionId = sessionId;
  await saveState();
  return sessionId;
}

async function runOneIteration() {
  const sessionId = await ensureSession();
  const iteration = state.value.iteration + 1;
  const response = await view.session.chat({
    sessionId,
    text: iterationPrompt(iteration),
    agentId: state.value.agentId || "dev",
    model: state.value.model.trim() || null,
    mode: "build",
    show: true,
    wait: {
      sessionId,
      timeoutMs: 1000 * 60 * 45,
      pollIntervalMs: 1200,
      includeEvents: true,
      returnOnWaitingInput: true,
    },
  });

  const result = response.result;
  const finalText = result?.finalText || "";
  const runStatus = result?.status || "unknown";
  const nextStatus = classify(finalText);
  const summary = finalText.trim().slice(0, 1200);

  state.value.iteration = iteration;
  state.value.progress = summary;
  state.value.runs.unshift({
    iteration,
    runId: response.runId,
    status: runStatus,
    summary,
    finishedAt: new Date().toISOString(),
  });
  state.value.runs = state.value.runs.slice(0, 50);

  await appendProgress([
    `## Iteration ${iteration}`,
    "",
    `Run: ${response.runId}`,
    `Status: ${runStatus}`,
    "",
    summary || "(no final text)",
  ].join("\n"));

  if (runStatus === "waiting_input") {
    state.value.status = "blocked";
  } else {
    state.value.status = nextStatus;
  }
  await saveState();
}

async function startLoop() {
  if (!canRun.value) return;
  state.value.status = "running";
  state.value.lastError = "";
  await saveState();

  try {
    while (state.value.status === "running" && state.value.iteration < state.value.maxIterations) {
      await runOneIteration();
    }
    if (state.value.status === "running") {
      state.value.status = "paused";
      state.value.lastError = "Stopped at max iteration limit.";
      await saveState();
    }
  } catch (error) {
    state.value.status = "error";
    state.value.lastError = error instanceof Error ? error.message : String(error);
    await saveState();
  }
}

async function pauseLoop() {
  if (state.value.status === "running") {
    state.value.status = "paused";
    await saveState();
  }
}

async function resetLoop() {
  state.value.iteration = 0;
  state.value.status = "idle";
  state.value.progress = "";
  state.value.lastError = "";
  state.value.runs = [];
  await saveState();
}

async function openSession() {
  if (state.value.sessionId) {
    await view.session.show(state.value.sessionId);
  }
}

onMounted(() => {
  void loadState();
});
</script>

<template>
  <main class="view-shell ralph-loop-view" data-locus-template="blank">
    <header class="view-toolbar">
      <div class="toolbar-title">
        <span>Ralph Loop</span>
        <small>{{ statusText }}</small>
      </div>
      <div class="toolbar-actions">
        <button :disabled="!state.sessionId" @click="openSession">Session</button>
        <button :disabled="!canRun" @click="startLoop">Run</button>
        <button :disabled="!busy" @click="pauseLoop">Pause</button>
        <button :disabled="busy" @click="resetLoop">Reset</button>
      </div>
    </header>

    <section class="view-content">
      <section class="control-panel">
        <label>
          <span>Objective</span>
          <textarea v-model="state.objective" :disabled="busy" rows="6" @change="saveState" />
        </label>
        <div class="control-grid">
          <label>
            <span>Agent</span>
            <input v-model="state.agentId" :disabled="busy" @change="saveState" />
          </label>
          <label>
            <span>Model</span>
            <input v-model="state.model" :disabled="busy" placeholder="default" @change="saveState" />
          </label>
          <label>
            <span>Max Iterations</span>
            <input v-model.number="state.maxIterations" :disabled="busy" type="number" min="1" max="200" @change="saveState" />
          </label>
          <label>
            <span>Session</span>
            <input :value="state.sessionId || 'new session on run'" disabled />
          </label>
        </div>
      </section>

      <section v-if="state.lastError" class="notice error">{{ state.lastError }}</section>

      <section class="progress-panel">
        <div class="panel-heading">
          <span>Progress</span>
          <small>{{ statePath }}</small>
        </div>
        <pre>{{ state.progress || "No iterations yet." }}</pre>
      </section>

      <section class="runs-panel">
        <div class="panel-heading">
          <span>Runs</span>
          <small>{{ state.runs.length }} recorded</small>
        </div>
        <div v-if="state.runs.length === 0" class="empty">No runs recorded.</div>
        <article v-for="run in state.runs" :key="run.runId" class="run-row">
          <div class="run-meta">
            <strong>#{{ run.iteration }}</strong>
            <span>{{ run.status }}</span>
            <small>{{ run.finishedAt }}</small>
          </div>
          <p>{{ run.summary || "No summary." }}</p>
        </article>
      </section>
    </section>
  </main>
</template>
