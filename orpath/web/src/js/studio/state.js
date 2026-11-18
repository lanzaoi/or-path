// Studio shared state, AI config, run-mode & 4-stage pipeline indicator
const studioState = {
  runMode: (localStorage.getItem("orpath_run_mode") || "fast") === "deep" ? "deep" : "fast",
  deepRounds: [3, 5, 8].includes(Number(localStorage.getItem("orpath_deep_rounds")))
    ? Number(localStorage.getItem("orpath_deep_rounds"))
    : 5,
  lastSolvedSlug: "",
  domainKey: "default",
  loadedFiles: [],
  currentAnalysis: null,
  analyzeAbortController: null,
  confirmAbortController: null,
  deepPollTimer: null,
  vizTabsBound: false,
  serverEnvConfigured: false,
  serverProvider: "none",
  serverDefaultModel: "deepseek-flash",
};

const DOMAIN_BADGES = {
  cutting: "下料切剖 / 共边优化",
  routing: "路径规划 / TSP · VRP",
  scheduling: "车间排产 / 析取图",
  project: "工程进度 / 累积资源",
  inventory: "供应链库存 / WW-DP",
  facility: "网络选址 / 测地距离",
  rostering: "排班轮休 / 集合覆盖",
  microgrid: "光储微网 / 分时电价",
  pricing: "定价博弈 / 收益管理",
  finance: "金融组合 / 风险平价",
  default: "运筹建模 / 精确求解",
};

function setRunMode(mode) {
  const m = mode === "deep" ? "deep" : "fast";
  const changed = studioState.runMode !== m;
  studioState.runMode = m;
  try { localStorage.setItem("orpath_run_mode", m); } catch (_) {}
  if ($("btnRunModeFast")) $("btnRunModeFast").classList.toggle("active", m === "fast");
  if ($("btnRunModeDeep")) $("btnRunModeDeep").classList.toggle("active", m === "deep");
  if ($("studioFastProgress")) $("studioFastProgress").hidden = (m !== "fast");
  if ($("studioDeepStrip")) $("studioDeepStrip").hidden = (m !== "deep");
  if ($("studioDeepRoundsGroup")) $("studioDeepRoundsGroup").hidden = (m !== "deep");
  if (changed && typeof resetStudioRunUI === "function") {
    resetStudioRunUI(false);
  }
}

function setDeepRounds(rounds) {
  const parsed = Number(rounds);
  const r = [3, 5, 8].includes(parsed) ? parsed : 5;
  studioState.deepRounds = r;
  try { localStorage.setItem("orpath_deep_rounds", String(r)); } catch (_) {}
  [3, 5, 8].forEach(val => {
    const btn = $(`btnDeepRounds${val}`);
    if (btn) btn.classList.toggle("active", val === r);
  });
  if ($("deepToolModeler")) {
    $("deepToolModeler").textContent = `R1..R${r} (≤600s/轮)`;
  }
}

function resetStudioRunUI(resetAnalysis = false) {
  if (studioState.deepPollTimer) {
    clearInterval(studioState.deepPollTimer);
    studioState.deepPollTimer = null;
  }
  const rc = $("studioResultCard");
  if (rc) {
    rc.style.display = "none";
    rc.classList.remove("is-blocked");
  }
  if (resetAnalysis && $("studioAnalysisCard")) {
    $("studioAnalysisCard").style.display = "none";
  }
  if ($("studioHeadline")) $("studioHeadline").textContent = "等待求解";
  if ($("studioObjective")) $("studioObjective").textContent = "—";
  if ($("studioValidation")) $("studioValidation").textContent = "—";
  if ($("studioSolutionDetail")) $("studioSolutionDetail").textContent = "";
  if ($("studioPaperStatus")) $("studioPaperStatus").textContent = "";
  if ($("btnStudioGeneratePaper")) $("btnStudioGeneratePaper").hidden = true;
  if ($("dlPaper")) $("dlPaper").hidden = true;
  ["dlSolution", "dlValidation", "dlPaper", "dlAnalysis"].forEach(id => {
    if ($(id)) $(id).href = "#";
  });
  ["vizPanelGantt", "vizPanelRoutes", "vizPanelMicrogrid", "vizPanelGap"].forEach(id => {
    if ($(id)) $(id).innerHTML = "";
  });
  const err2 = $("studioConfirmError");
  if (err2) { err2.style.display = "none"; err2.textContent = ""; }
  const st2 = $("studioStep2Status");
  if (st2) st2.textContent = "修改上方策略或知识库锚点后，可一键按新参数重新求解";
  setPipelineStage("idle", "待命");
}

function updateApiKeyBadge() {
  const apiKeyInput = $("studioApiKeyInput");
  const modelSelect = $("studioModelSelect");
  const apiKeyBadge = $("studioApiKeyBadge");
  if (!apiKeyBadge) return;
  const key = (apiKeyInput?.value || "").trim();
  const mod = modelSelect?.value || "deepseek-flash";
  if (mod === "offline") {
    apiKeyBadge.style.background = "var(--surface-2)";
    apiKeyBadge.style.color = "var(--ink-48)";
    apiKeyBadge.style.borderColor = "var(--border)";
    apiKeyBadge.textContent = "离线规则模式";
  } else if (key.length > 5) {
    apiKeyBadge.style.background = "#ecfdf5";
    apiKeyBadge.style.color = "#047857";
    apiKeyBadge.style.borderColor = "#a7f3d0";
    if (key.startsWith("ak-") || mod.startsWith("spark")) {
      apiKeyBadge.textContent = "已配置 · Spark X2.6";
    } else {
      const dsLabel = mod === "deepseek-flash" ? "Flash" : (mod === "deepseek-reasoner" ? "R1" : "V3");
      apiKeyBadge.textContent = `已配置 · DeepSeek-${dsLabel}`;
    }
  } else if (studioState.serverEnvConfigured) {
    apiKeyBadge.style.background = "#ecfdf5";
    apiKeyBadge.style.color = "#047857";
    apiKeyBadge.style.borderColor = "#a7f3d0";
    const provLabel = studioState.serverProvider === "spark" ? "Spark" : (studioState.serverProvider || "服务端");
    apiKeyBadge.textContent = `服务端 Key · ${provLabel} / ${mod}`;
  } else {
    apiKeyBadge.style.background = "#fffbeb";
    apiKeyBadge.style.color = "#b45309";
    apiKeyBadge.style.borderColor = "#fde68a";
    apiKeyBadge.textContent = "离线规则探针（未配置 Key）";
  }
}

async function fetchEnvStatus() {
  try {
    const res = await fetch("/api/studio/env_status");
    if (!res.ok) return;
    const data = await res.json();
    if (!data || !data.ok) return;
    studioState.serverEnvConfigured = Boolean(data.env_configured);
    studioState.serverProvider = String(data.provider || "none");
    studioState.serverDefaultModel = String(data.default_model || "deepseek-flash");
    const savedOverride = localStorage.getItem("orpath_model_name");
    const modelSelect = $("studioModelSelect");
    if (modelSelect && !savedOverride && studioState.serverDefaultModel) {
      modelSelect.value = studioState.serverDefaultModel;
    }
    updateApiKeyBadge();
  } catch (_) {}
}

function scrollStudioToCard(card) {
  if (!card) return;
  card.style.display = "block";
  setTimeout(() => {
    card.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 60);
}

function normalizeDomainKey(raw) {
  if (!raw) return "default";
  const s = String(raw).toLowerCase().replace(/[-_]/g, "");
  if (s.includes("sched") || s.includes("jssp") || s.includes("jobshop")) return "scheduling";
  if (s.includes("rout") || s.includes("vrp") || s.includes("tsp")) return "routing";
  if (s.includes("tube") || s.includes("cut") || s.includes("polyomino")) return "cutting";
  if (s.includes("project") || s.includes("rcpsp") || s.includes("psplib")) return "project";
  if (s.includes("inventory") || s.includes("lotsiz") || s.includes("wagner")) return "inventory";
  if (s.includes("facility") || s.includes("cflp") || s.includes("hub") || s.includes("scnd")) return "facility";
  if (s.includes("roster") || s.includes("staff") || s.includes("shift")) return "rostering";
  if (s.includes("microgrid") || s.includes("pv") || s.includes("bess")) return "microgrid";
  if (s.includes("pricing") || s.includes("revenue") || s.includes("yield")) return "pricing";
  if (s.includes("finance") || s.includes("portfolio") || s.includes("markowitz")) return "finance";
  return "default";
}

function setPipelineStage(stageKey, stateText, detailText) {
  const fastIds = ["fastStepProbe", "fastStepPlan", "fastStepSolve", "fastStepGate"];
  const deepIds = ["deepCardAnalyst", "deepCardModeler", "deepCardWriter", "deepCardReviewer"];
  const stageIdxMap = {
    idle: -1,
    probe: 0,
    analyze: 0,
    plan: 1,
    solve: 2,
    gate: 3,
    paper: 2,
    review: 3,
    gate_done: 99,
    done: 99,
    paper_done: 99,
    blocked: -2,
    error: -3,
  };
  const activeIdx = stageIdxMap[stageKey] !== undefined ? stageIdxMap[stageKey] : 0;

  function updateGroup(ids, badgeSel) {
    ids.forEach((id, idx) => {
      const el = $(id);
      if (!el) return;
      const badge = el.querySelector(badgeSel);
      const wasActive = el.classList.contains("active");
      el.classList.remove("active", "done", "blocked");
      if (activeIdx === -1) {
        if (badge) { badge.className = "fast-step-badge waiting"; badge.textContent = "待命"; }
        return;
      }
      if (activeIdx === -3) {
        if (wasActive || idx === ids.length - 1) {
          el.classList.add("blocked");
          if (badge) { badge.className = "fast-step-badge blocked"; badge.textContent = stateText || "异常中止"; }
        } else {
          if (badge) { badge.className = "fast-step-badge waiting"; badge.textContent = "待命"; }
        }
        return;
      }
      if (activeIdx === -2) {
        if (idx <= 2) {
          el.classList.add("done");
          if (badge) { badge.className = "fast-step-badge done"; badge.textContent = "已完成"; }
        } else {
          el.classList.add("blocked");
          if (badge) { badge.className = "fast-step-badge blocked"; badge.textContent = stateText || "已阻断"; }
        }
        return;
      }
      if (activeIdx === 99 || idx < activeIdx) {
        el.classList.add("done");
        if (badge) { badge.className = "fast-step-badge done"; badge.textContent = "已完成 ✓"; }
      } else if (idx === activeIdx) {
        el.classList.add("active");
        if (badge) { badge.className = "fast-step-badge active"; badge.textContent = stateText || "执行中…"; }
      } else {
        if (badge) { badge.className = "fast-step-badge waiting"; badge.textContent = "待命"; }
      }
    });
  }

  updateGroup(fastIds, ".fast-step-badge");
  updateGroup(deepIds, ".fast-step-badge");
  if (detailText && activeIdx >= 0 && activeIdx < fastIds.length) {
    const subEl = $(fastIds[activeIdx] + "Sub");
    if (subEl) subEl.textContent = detailText;
  }
}

function updateDeepPipelineFromSnapshot(snap) {
  if (!snap || typeof snap !== "object") return;
  const node = String((snap.current && snap.current.node) || "").toLowerCase();
  if (node.includes("review") || node.includes("validate") || node.includes("provenance") || node.includes("cite")) {
    setPipelineStage("review", "审稿验算中…");
  } else if (node.includes("writer") || node.includes("paper") || node.includes("draft")) {
    setPipelineStage("paper", "学术写稿中…");
  } else if (node.includes("model") || node.includes("solve")) {
    setPipelineStage("solve", "多智能体建模求解中…");
  } else if (node.includes("analyst") || node.includes("intake") || node.includes("research")) {
    setPipelineStage("analyze", "领域研判中…");
  }
}

function initStudioConfig() {
  const btnModeFast = $("btnRunModeFast");
  const btnModeDeep = $("btnRunModeDeep");
  if (btnModeFast) btnModeFast.addEventListener("click", () => setRunMode("fast"));
  if (btnModeDeep) btnModeDeep.addEventListener("click", () => setRunMode("deep"));
  [3, 5, 8].forEach(val => {
    const btn = $(`btnDeepRounds${val}`);
    if (btn) btn.addEventListener("click", () => setDeepRounds(val));
  });
  setRunMode(studioState.runMode);
  setDeepRounds(studioState.deepRounds);

  const apiKeyInput = $("studioApiKeyInput");
  const modelSelect = $("studioModelSelect");
  const btnSaveApiKey = $("btnSaveApiKey");
  const savedKey = localStorage.getItem("orpath_deepseek_key") || "";
  const savedModel = localStorage.getItem("orpath_model_name") || "deepseek-flash";
  if (apiKeyInput) apiKeyInput.value = savedKey;
  if (modelSelect) modelSelect.value = savedModel;
  updateApiKeyBadge();

  if (apiKeyInput) {
    apiKeyInput.addEventListener("input", () => {
      const val = apiKeyInput.value.trim();
      if (val.startsWith("ak-") && modelSelect && modelSelect.value !== "spark-x2.6" && modelSelect.value !== "offline") {
        modelSelect.value = "spark-x2.6";
      } else if (val.startsWith("sk-") && modelSelect && modelSelect.value === "spark-x2.6") {
        modelSelect.value = "deepseek-flash";
      }
      localStorage.setItem("orpath_deepseek_key", val);
      updateApiKeyBadge();
    });
  }

  if (btnSaveApiKey) {
    btnSaveApiKey.addEventListener("click", () => {
      localStorage.setItem("orpath_deepseek_key", (apiKeyInput?.value || "").trim());
      localStorage.setItem("orpath_model_name", modelSelect?.value || "deepseek-flash");
      updateApiKeyBadge();
      btnSaveApiKey.textContent = "已保存 ✓";
      setTimeout(() => { if (btnSaveApiKey) btnSaveApiKey.textContent = "保存"; }, 1500);
    });
  }

  if (modelSelect) {
    modelSelect.addEventListener("change", () => {
      localStorage.setItem("orpath_model_name", modelSelect.value);
      updateApiKeyBadge();
    });
  }
}
