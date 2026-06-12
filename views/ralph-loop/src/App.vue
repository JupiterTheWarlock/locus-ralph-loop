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
  sessionId: string;
  runId: string;
  status: string;
  summary: string;
  finishedAt: string;
}

interface LoopState {
  objective: string;
  sessionId: string | null;
  rootSessionId: string | null;
  batchStartedAt: string | null;
  sessionIds: string[];
  autoArchiveOnComplete: boolean;
  archivedSessionIds: string[];
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
  rootSessionId: null,
  batchStartedAt: null,
  sessionIds: [],
  autoArchiveOnComplete: false,
  archivedSessionIds: [],
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
    current?: () => Promise<ModelOption | null>;
  };
  session: typeof view.session & {
    archive?: (sessionId: string) => Promise<void>;
  };
};
const legacyModelsApi = (globalThis as typeof globalThis & {
  locus?: {
    models?: {
      list?: () => Promise<ModelOption[]>;
      current?: () => Promise<ModelOption | null>;
    };
  };
}).locus?.models;

const runtimeModels = ref<ModelOption[]>([]);
const runtimeCurrentModel = ref<ModelOption | null>(null);
const modelLoadError = ref("");
const stopRequested = ref(false);
const locusConfigDir = "C:/Users/Administrator/AppData/Roaming/locus";

const text = {
  zh: {
    ready: "就绪",
    openSession: "打开会话",
    start: "开始",
    pause: "暂停",
    reset: "重置",
    archiveBatch: "归档本批次",
    autoArchive: "完成后自动归档",
    objective: "目标",
    model: "模型",
    defaultModel: "跟随 Locus 默认模型",
    maxIterations: "最大迭代",
    session: "最近会话",
    newSession: "下一轮将新建会话",
    progress: "进展",
    noProgress: "还没有迭代记录。",
    runs: "运行记录",
    runCount: (count: number) => `${count} 条`,
    noRuns: "暂无运行记录。",
    noSummary: "没有摘要。",
    maxIterationsReached: "已达到最大迭代次数，循环暂停。",
    modelLoadFailed: "无法读取 Locus 可用模型：",
    language: "语言",
    archived: "已归档",
    archiveFailed: "归档失败：",
  },
  en: {
    ready: "Ready",
    openSession: "Open Session",
    start: "Start",
    pause: "Pause",
    reset: "Reset",
    archiveBatch: "Archive batch",
    autoArchive: "Auto archive when complete",
    objective: "Objective",
    model: "Model",
    defaultModel: "Follow Locus default model",
    maxIterations: "Max iterations",
    session: "Latest session",
    newSession: "Next iteration will create a new session",
    progress: "Progress",
    noProgress: "No iterations yet.",
    runs: "Runs",
    runCount: (count: number) => `${count} recorded`,
    noRuns: "No runs recorded.",
    noSummary: "No summary.",
    maxIterationsReached: "Stopped at the max iteration limit.",
    modelLoadFailed: "Unable to read Locus available models: ",
    language: "Language",
    archived: "Archived",
    archiveFailed: "Archive failed: ",
  },
};

const tr = computed(() => text[state.value.locale] ?? text.zh);
const modelOptions = computed(() => [
  {
    id: "",
    name: runtimeCurrentModel.value
      ? `${tr.value.defaultModel}: ${modelLabel(runtimeCurrentModel.value)}`
      : tr.value.defaultModel,
    provider: "",
  },
  ...runtimeModels.value,
]);

const busy = computed(() => state.value.status === "running");
const canRun = computed(() => state.value.objective.trim().length > 0 && !busy.value && state.value.status !== "done");
const statusText = computed(() => {
  if (state.value.status === "idle") return tr.value.ready;
  return `${state.value.status} · ${state.value.iteration}/${state.value.maxIterations}`;
});

function modelLabel(option: ModelOption) {
  if (!option.provider) return option.name;
  return `${option.name} · ${option.provider}`;
}

function padIteration(value: number) {
  return String(value).padStart(2, "0");
}

function batchTimestamp(date = new Date()) {
  return date.toISOString().replace(/\.\d{3}Z$/, "Z").replace(/[:]/g, "-");
}

function sessionTitle(iteration: number) {
  const batch = state.value.batchStartedAt || batchTimestamp();
  return `Ralph Loop ${batch} #${padIteration(iteration)}/${padIteration(state.value.maxIterations)}`;
}

function normalizeState() {
  if (state.value.locale !== "zh" && state.value.locale !== "en") {
    state.value.locale = "zh";
  }
  if (!Number.isFinite(state.value.maxIterations) || state.value.maxIterations < 1) {
    state.value.maxIterations = 1;
  }
  state.value.maxIterations = Math.min(Math.floor(state.value.maxIterations), 200);
  state.value.runs = Array.isArray(state.value.runs) ? state.value.runs : [];
  state.value.sessionIds = Array.isArray(state.value.sessionIds) ? state.value.sessionIds : [];
  state.value.archivedSessionIds = Array.isArray(state.value.archivedSessionIds)
    ? state.value.archivedSessionIds
    : [];
}

function configPath(fileName: string) {
  return `${locusConfigDir}/${fileName}`;
}

async function readConfigText(fileName: string) {
  const raw = await view.fs.readFile(configPath(fileName), "utf8");
  return String(raw);
}

async function readConfigJson<T>(fileName: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await readConfigText(fileName)) as T;
  } catch {
    return fallback;
  }
}

async function readLastModel() {
  try {
    return (await readConfigText("last_model.txt")).trim();
  } catch {
    return "";
  }
}

function formatCodexModelName(id: string, fallbackName?: string) {
  const slug = id.startsWith("openai/") ? id.slice("openai/".length) : id;
  const parts = slug.trim().toLowerCase().split("-").filter(Boolean);
  const formatted = parts.map((part) => {
    if (part === "gpt") return "GPT";
    if (part === "codex") return "Codex";
    if (part === "mini") return "Mini";
    if (part === "spark") return "Spark";
    if (part === "pro") return "Pro";
    if (/^\d/.test(part)) return part;
    return part.charAt(0).toUpperCase() + part.slice(1);
  }).join(" ");
  return formatted || fallbackName?.trim() || id;
}

function uniqueModels(models: ModelOption[]) {
  const seen = new Set<string>();
  const result: ModelOption[] = [];
  for (const model of models) {
    const id = model.id.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    result.push({ ...model, id });
  }
  return result;
}

async function loadFallbackModels() {
  const defaults = await readConfigJson<{ mainModel?: string }>("model_defaults.json", {});
  const cache = await readConfigJson<{
    models?: Array<{ slug?: string; display_name?: string }>;
  }>("codex_models_cache.json", {});
  const customEndpoints = await readConfigJson<Array<{ id?: string; name?: string }>>("custom_endpoints.json", []);
  const lastModel = await readLastModel();
  const codexModels = Array.isArray(cache.models)
    ? cache.models
        .map((model) => {
          const slug = typeof model.slug === "string" ? model.slug.trim() : "";
          if (!slug) return null;
          const id = `openai/${slug}`;
          return {
            id,
            name: formatCodexModelName(id, model.display_name),
            provider: "openai_codex",
          };
        })
        .filter((model): model is ModelOption => !!model)
    : [];
  const customModels = Array.isArray(customEndpoints)
    ? customEndpoints
        .map((endpoint) => {
          const id = typeof endpoint.id === "string" ? endpoint.id.trim() : "";
          if (!id) return null;
          return {
            id: `custom/${id}`,
            name: typeof endpoint.name === "string" && endpoint.name.trim() ? endpoint.name.trim() : id,
            provider: "custom",
          };
        })
        .filter((model): model is ModelOption => !!model)
    : [];
  const list = uniqueModels([...codexModels, ...customModels]);
  const ids = new Set(list.map((model) => model.id));
  const selectedId = defaults.mainModel && ids.has(defaults.mainModel)
    ? defaults.mainModel
    : lastModel && ids.has(lastModel)
      ? lastModel
      : list[0]?.id ?? "";
  return {
    list,
    current: list.find((model) => model.id === selectedId) ?? null,
  };
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
    normalizeState();
  } catch {
    normalizeState();
    await saveState();
  }
}

async function createIterationSession(iteration: number) {
  if (!state.value.batchStartedAt) {
    state.value.batchStartedAt = batchTimestamp();
  }
  const parentSessionId = iteration > 1 ? state.value.rootSessionId : null;
  const sessionId = await view.session.create({
    title: sessionTitle(iteration),
    parentSessionId,
    sessionType: "chat",
  });
  if (!state.value.rootSessionId) {
    state.value.rootSessionId = sessionId;
  }
  state.value.sessionId = sessionId;
  if (!state.value.sessionIds.includes(sessionId)) {
    state.value.sessionIds.push(sessionId);
  }
  await saveState();
  return sessionId;
}

async function archiveBatchSessions() {
  const archive = runtimeView.session.archive;
  if (!archive) {
    throw new Error("The installed Locus View runtime does not expose session archive API yet.");
  }
  const targets = state.value.sessionIds.filter(
    (sessionId) => sessionId && !state.value.archivedSessionIds.includes(sessionId),
  );
  for (const sessionId of targets) {
    await archive(sessionId);
    state.value.archivedSessionIds.push(sessionId);
  }
  await saveState();
}

async function archiveBatchFromUi() {
  try {
    state.value.lastError = "";
    await archiveBatchSessions();
  } catch (error) {
    state.value.lastError = `${tr.value.archiveFailed}${error instanceof Error ? error.message : String(error)}`;
    await saveState();
  }
}

async function loadModels() {
  modelLoadError.value = "";
  try {
    const listModels = runtimeView.models?.list ?? legacyModelsApi?.list;
    const currentModel = runtimeView.models?.current ?? legacyModelsApi?.current;
    if (listModels) {
      const list = await listModels();
      runtimeCurrentModel.value = currentModel ? await currentModel() : null;
      runtimeModels.value = Array.isArray(list) ? list : [];
    } else {
      const fallback = await loadFallbackModels();
      runtimeModels.value = fallback.list;
      runtimeCurrentModel.value = fallback.current;
    }
    if (state.value.model && !runtimeModels.value.some((model) => model.id === state.value.model)) {
      state.value.model = "";
      await saveState();
    }
  } catch (error) {
    runtimeModels.value = [];
    runtimeCurrentModel.value = null;
    modelLoadError.value = error instanceof Error ? error.message : String(error);
  }
}

async function resolveModelForRun() {
  const explicit = state.value.model.trim();
  if (explicit) return explicit;
  const currentModel = runtimeView.models?.current ?? legacyModelsApi?.current;
  if (currentModel) {
    const model = await currentModel();
    runtimeCurrentModel.value = model;
    if (model?.id) return model.id;
  }
  const fallback = await loadFallbackModels();
  runtimeModels.value = fallback.list;
  runtimeCurrentModel.value = fallback.current;
  return fallback.current?.id ?? null;
}

function iterationPrompt(iteration: number) {
  return [
    "/ralph-loop",
    "",
    "You are running one iteration under the Locus Ralph Loop controller.",
    "",
    `Objective: ${state.value.objective.trim()}`,
    "",
    "Ralph Loop contract: read the objective, repository state, and durable progress, then advance exactly one clear checkpoint.",
    "Do not rely on prior chat context. Each iteration runs in a fresh Locus session; use repository files and Locus/ralph-loop/progress.md for continuity.",
    "Before finishing, persist reusable findings or next-step context when useful.",
    "Stop condition aligned with Ralph: if the full objective is complete and verified, output exactly <promise>COMPLETE</promise>.",
    "Otherwise, end your response normally after completing one checkpoint. The controller will start the next fresh session.",
    "",
    "Also include a brief progress summary, verification result, and the next checkpoint if continuing.",
    `Iteration: ${iteration}/${state.value.maxIterations}`,
  ].join("\n");
}

function classify(text: string): LoopStatus {
  if (text.includes("<promise>COMPLETE</promise>")) return "done";
  return "running";
}

async function runOneIteration() {
  const iteration = state.value.iteration + 1;
  const sessionId = await createIterationSession(iteration);
  const response = await view.session.chat({
    text: iterationPrompt(iteration),
    sessionId,
    sessionTitle: sessionTitle(iteration),
    sessionType: "chat",
    model: await resolveModelForRun(),
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
    sessionId: response.sessionId,
    runId: response.runId,
    status: runStatus,
    summary,
    finishedAt: new Date().toISOString(),
  });
  state.value.runs = state.value.runs.slice(0, 50);

  await appendProgress([
    `## Iteration ${iteration}`,
    "",
    `Session: ${response.sessionId}`,
    `Run: ${response.runId}`,
    `Status: ${runStatus}`,
    "",
    summary || "(no final text)",
  ].join("\n"));

  if (runStatus === "waiting_input") {
    state.value.status = "blocked";
  } else if (stopRequested.value && nextStatus === "running") {
    state.value.status = "paused";
  } else {
    state.value.status = nextStatus;
  }
  await saveState();
}

async function startLoop() {
  if (!canRun.value) return;
  stopRequested.value = false;
  if (state.value.status === "idle") {
    state.value.sessionId = null;
    state.value.rootSessionId = null;
    state.value.batchStartedAt = batchTimestamp();
    state.value.sessionIds = [];
    state.value.archivedSessionIds = [];
  }
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
    if (state.value.status === "done" && state.value.autoArchiveOnComplete) {
      try {
        await archiveBatchSessions();
      } catch (error) {
        state.value.lastError = `${tr.value.archiveFailed}${error instanceof Error ? error.message : String(error)}`;
        await saveState();
      }
    }
  } catch (error) {
    state.value.status = "error";
    state.value.lastError = error instanceof Error ? error.message : String(error);
    await saveState();
  }
}

async function pauseLoop() {
  if (state.value.status === "running") {
    stopRequested.value = true;
    state.value.status = "paused";
    await saveState();
  }
}

async function resetLoop() {
  stopRequested.value = false;
  const locale = state.value.locale;
  const model = state.value.model;
  const maxIterations = state.value.maxIterations;
  const objective = state.value.objective;
  state.value.iteration = 0;
  state.value.sessionId = null;
  state.value.rootSessionId = null;
  state.value.batchStartedAt = null;
  state.value.sessionIds = [];
  state.value.archivedSessionIds = [];
  state.value.objective = objective;
  state.value.model = model;
  state.value.locale = locale;
  state.value.maxIterations = maxIterations;
  state.value.status = "idle";
  state.value.progress = "";
  state.value.lastError = "";
  state.value.runs = [];
  await ensureStateDir();
  await view.fs.writeFile(progressPath, "", "utf8");
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
        <label class="archive-toggle">
          <input v-model="state.autoArchiveOnComplete" type="checkbox" :disabled="busy" @change="saveState" />
          <span>{{ tr.autoArchive }}</span>
        </label>
        <button :disabled="busy || state.sessionIds.length === 0" @click="archiveBatchFromUi">{{ tr.archiveBatch }}</button>
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
            <span v-if="state.archivedSessionIds.includes(run.sessionId)">{{ tr.archived }}</span>
            <small>{{ run.finishedAt }}</small>
          </div>
          <p>{{ run.summary || tr.noSummary }}</p>
        </article>
      </section>
    </section>
  </main>
</template>
