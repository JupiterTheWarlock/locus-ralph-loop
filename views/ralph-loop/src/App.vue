<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { view } from "@locus/view-runtime";

type LoopStatus = "idle" | "running" | "paused" | "done" | "blocked" | "error";

interface ModelOption {
  id: string;
  label: string;
}

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
  model: "",
  maxIterations: 20,
  iteration: 0,
  status: "idle",
  progress: "",
  lastError: "",
  runs: [],
});

const modelOptions: ModelOption[] = [
  { id: "", label: "跟随当前会话默认模型" },
  { id: "claude_code/sonnet", label: "Claude Code CLI · Sonnet" },
  { id: "claude_code/opus", label: "Claude Code CLI · Opus" },
  { id: "openai/gpt-5.5", label: "OpenAI · GPT-5.5" },
  { id: "openai/gpt-5.5-codex", label: "OpenAI · GPT-5.5 Codex" },
  { id: "openrouter/claude-sonnet-4.6", label: "OpenRouter · Claude Sonnet 4.6" },
  { id: "openrouter/claude-opus-4.6", label: "OpenRouter · Claude Opus 4.6" },
];

const busy = computed(() => state.value.status === "running");
const canRun = computed(() => state.value.objective.trim().length > 0 && !busy.value);
const statusText = computed(() => {
  if (state.value.status === "idle") return "就绪";
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
    "/ralph-loop",
    "",
    "你正在 Locus Ralph Loop 控制器里运行一次循环迭代。",
    "",
    `目标：${state.value.objective.trim()}`,
    "",
    "对齐 Ralph Loop 的工作方式：读取目标和已有进展，只推进一个清晰 checkpoint，使用普通 Locus 会话、工具和项目上下文完成工作。",
    "每轮结束前请写入可持久化进展；如果存在 Locus/ralph-loop/progress.md，请追加本轮发现。",
    "结束时必须单独输出一个状态标记：",
    "- <promise>COMPLETE</promise>：目标已经完成并验证。",
    "- RALPH_LOOP_BLOCKED：需要用户输入或外部状态变化。",
    "- RALPH_LOOP_CONTINUE：还需要继续下一轮。",
    "",
    "同时给出简短进展、验证结果，以及如果继续时的下一个 checkpoint。",
    `迭代：${iteration}/${state.value.maxIterations}`,
  ].join("\n");
}

function classify(text: string): LoopStatus {
  if (text.includes("<promise>COMPLETE</promise>") || text.includes("RALPH_LOOP_DONE")) return "done";
  if (text.includes("RALPH_LOOP_BLOCKED")) return "blocked";
  return "running";
}

async function runOneIteration() {
  const iteration = state.value.iteration + 1;
  const response = await view.session.chat({
    text: iterationPrompt(iteration),
    sessionId: state.value.sessionId,
    sessionTitle: "Ralph Loop",
    sessionType: "chat",
    model: state.value.model.trim() || null,
    mode: "build",
    show: true,
    wait: {
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

  state.value.sessionId = response.sessionId;
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
    `运行：${response.runId}`,
    `状态：${runStatus}`,
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
      state.value.lastError = "已达到最大迭代次数，循环暂停。";
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
        <button :disabled="!state.sessionId" @click="openSession">打开会话</button>
        <button :disabled="!canRun" @click="startLoop">开始</button>
        <button :disabled="!busy" @click="pauseLoop">暂停</button>
        <button :disabled="busy" @click="resetLoop">重置</button>
      </div>
    </header>

    <section class="view-content">
      <section class="control-panel">
        <label>
          <span>目标</span>
          <textarea v-model="state.objective" :disabled="busy" rows="6" @change="saveState" />
        </label>
        <div class="control-grid">
          <label>
            <span>模型</span>
            <select v-model="state.model" :disabled="busy" @change="saveState">
              <option v-for="option in modelOptions" :key="option.id" :value="option.id">
                {{ option.label }}
              </option>
            </select>
          </label>
          <label>
            <span>最大迭代</span>
            <input v-model.number="state.maxIterations" :disabled="busy" type="number" min="1" max="200" @change="saveState" />
          </label>
          <label>
            <span>会话</span>
            <input :value="state.sessionId || '首次运行时创建/复用默认输入流程'" disabled />
          </label>
        </div>
      </section>

      <section v-if="state.lastError" class="notice error">{{ state.lastError }}</section>

      <section class="progress-panel">
        <div class="panel-heading">
          <span>进展</span>
          <small>{{ statePath }}</small>
        </div>
        <pre>{{ state.progress || "还没有迭代记录。" }}</pre>
      </section>

      <section class="runs-panel">
        <div class="panel-heading">
          <span>运行记录</span>
          <small>{{ state.runs.length }} 条</small>
        </div>
        <div v-if="state.runs.length === 0" class="empty">暂无运行记录。</div>
        <article v-for="run in state.runs" :key="run.runId" class="run-row">
          <div class="run-meta">
            <strong>#{{ run.iteration }}</strong>
            <span>{{ run.status }}</span>
            <small>{{ run.finishedAt }}</small>
          </div>
          <p>{{ run.summary || "没有摘要。" }}</p>
        </article>
      </section>
    </section>
  </main>
</template>
