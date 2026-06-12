<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { view } from "@locus/view-runtime";

type LoopStatus = "idle" | "running" | "paused" | "done" | "blocked" | "error";
type Locale = "zh" | "en";

interface ModelOption {
  id: string;
  name: string;
  provider: string;
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
  locale: Locale;
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
  locale: "zh",
  maxIterations: 20,
  iteration: 0,
  status: "idle",
  progress: "",
  lastError: "",
  runs: [],
});

const runtimeView = view as typeof view & {
  models?: {
    list?: () => Promise<ModelOption[]>;
  };
};

const runtimeModels = ref<ModelOption[]>([]);
const modelLoadError = ref("");

const text = {
  zh: {
    ready: "就绪",
    openSession: "打开会话",
    start: "开始",
    pause: "暂停",
    reset: "重置",
    objective: "目标",
    model: "模型",
    defaultModel: "跟随当前会话默认模型",
    maxIterations: "最大迭代",
    session: "会话",
    newSession: "首次运行时创建/复用默认输入流程",
    progress: "进展",
    noProgress: "还没有迭代记录。",
    runs: "运行记录",
    runCount: (count: number) => `${count} 条`,
    noRuns: "暂无运行记录。",
    noSummary: "没有摘要。",
    maxIterationsReached: "已达到最大迭代次数，循环暂停。",
    modelLoadFailed: "读取 Locus 可用模型失败：",
    language: "语言",
  },
  en: {
    ready: "Ready",
    openSession: "Open Session",
    start: "Start",
    pause: "Pause",
    reset: "Reset",
    objective: "Objective",
    model: "Model",
    defaultModel: "Follow current session default",
    maxIterations: "Max iterations",
    session: "Session",
    newSession: "Create/reuse default input flow on first run",
    progress: "Progress",
    noProgress: "No iterations yet.",
    runs: "Runs",
    runCount: (count: number) => `${count} recorded`,
    noRuns: "No runs recorded.",
    noSummary: "No summary.",
    maxIterationsReached: "Stopped at the max iteration limit.",
    modelLoadFailed: "Failed to read Locus available models: ",
    language: "Language",
  },
};

const tr = computed(() => text[state.value.locale] ?? text.zh);
const modelOptions = computed(() => [
  { id: "", name: tr.value.defaultModel, provider: "" },
  ...runtimeModels.value,
]);

const busy = computed(() => state.value.status === "running");
const canRun = computed(() => state.value.objective.trim().length > 0 && !busy.value);
const statusText = computed(() => {
  if (state.value.status === "idle") return tr.value.ready;
  return `${state.value.status} · ${state.value.iteration}/${state.value.maxIterations}`;
});

function modelLabel(option: ModelOption) {
  if (!option.provider) return option.name;
  return `${option.name} · ${option.provider}`;
}

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

async function loadModels() {
  modelLoadError.value = "";
  try {
    if (!runtimeView.models?.list) {
      throw new Error("当前 Locus View runtime 未暴露会话模型列表，请先使用已更新的 Locus。");
    }
    const list = await runtimeView.models.list();
    runtimeModels.value = Array.isArray(list) ? list : [];
    if (state.value.model && !runtimeModels.value.some((model) => model.id === state.value.model)) {
      state.value.model = "";
      await saveState();
    }
  } catch (error) {
    runtimeModels.value = [];
    modelLoadError.value = error instanceof Error ? error.message : String(error);
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
      state.value.lastError = tr.value.maxIterationsReached;
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
  void loadState().then(loadModels);
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
        <label class="locale-switch">
          <span>{{ tr.language }}</span>
          <select v-model="state.locale" :disabled="busy" @change="saveState">
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </label>
        <button :disabled="!state.sessionId" @click="openSession">{{ tr.openSession }}</button>
        <button :disabled="!canRun" @click="startLoop">{{ tr.start }}</button>
        <button :disabled="!busy" @click="pauseLoop">{{ tr.pause }}</button>
        <button :disabled="busy" @click="resetLoop">{{ tr.reset }}</button>
      </div>
    </header>

    <section class="view-content">
      <section class="control-panel">
        <label>
          <span>{{ tr.objective }}</span>
          <textarea v-model="state.objective" :disabled="busy" rows="6" @change="saveState" />
        </label>
        <div class="control-grid">
          <label>
            <span>{{ tr.model }}</span>
            <select v-model="state.model" :disabled="busy" @change="saveState">
              <option v-for="option in modelOptions" :key="option.id" :value="option.id">
                {{ modelLabel(option) }}
              </option>
            </select>
          </label>
          <label>
            <span>{{ tr.maxIterations }}</span>
            <input v-model.number="state.maxIterations" :disabled="busy" type="number" min="1" max="200" @change="saveState" />
          </label>
          <label>
            <span>{{ tr.session }}</span>
            <input :value="state.sessionId || tr.newSession" disabled />
          </label>
        </div>
      </section>

      <section v-if="state.lastError" class="notice error">{{ state.lastError }}</section>
      <section v-if="modelLoadError" class="notice error">{{ tr.modelLoadFailed }}{{ modelLoadError }}</section>

      <section class="progress-panel">
        <div class="panel-heading">
          <span>{{ tr.progress }}</span>
          <small>{{ statePath }}</small>
        </div>
        <pre>{{ state.progress || tr.noProgress }}</pre>
      </section>

      <section class="runs-panel">
        <div class="panel-heading">
          <span>{{ tr.runs }}</span>
          <small>{{ tr.runCount(state.runs.length) }}</small>
        </div>
        <div v-if="state.runs.length === 0" class="empty">{{ tr.noRuns }}</div>
        <article v-for="run in state.runs" :key="run.runId" class="run-row">
          <div class="run-meta">
            <strong>#{{ run.iteration }}</strong>
            <span>{{ run.status }}</span>
            <small>{{ run.finishedAt }}</small>
          </div>
          <p>{{ run.summary || tr.noSummary }}</p>
        </article>
      </section>
    </section>
  </main>
</template>
