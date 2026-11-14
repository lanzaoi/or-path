// Studio shared state, AI config, run-mode & 4-stage pipeline indicator
const studioState = {
  runMode: (localStorage.getItem("orpath_run_mode") || "fast") === "deep" ? "deep" : "fast",
  lastSolvedSlug: "",
  domainKey: "default",
  loadedFiles: [],
  currentAnalysis: null,
  analyzeAbortController: null,
  confirmAbortController: null,
  vizTabsBound: false,
};

const DOMAIN_BADGES = {
  cutting: "下料切剖 / 共边DP",
  routing: "物流路径 / HGS遗传",
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
  studioState.runMode = m;
  try { localStorage.setItem("orpath_run_mode", m); } catch (_) {}
  if ($("btnRunModeFast")) $("btnRunModeFast").classList.toggle("active", m === "fast");
  if ($("btnRunModeDeep")) $("btnRunModeDeep").classList.toggle("active", m === "deep");
  if ($("studioFastProgress")) $("studioFastProgress").hidden = (m !== "fast");
  if ($("studioDeepStrip")) $("studioDeepStrip").hidden = (m !== "deep");
}

function updateApiKeyBadge() {
  const apiKeyInput = $("studioApiKeyInput");
  const modelSelect = $("studioModelSelect");
  const apiKeyBadge = $("studioApiKeyBadge");
  if (!apiKeyBadge) return;
  const key = (apiKeyInput?.value || "").trim();
  const mod = modelSelect?.value || "spark-x2.6";
  if (mod === "offline") {
    apiKeyBadge.style.background = "rgba(142,142,147,0.15)";
    apiKeyBadge.style.color = "var(--ink-48)";
    apiKeyBadge.style.borderColor = "rgba(142,142,147,0.3)";
    apiKeyBadge.textContent = "⚪ 离线探针模式 (无需 Key)";
  } else if (key.length > 5) {
    apiKeyBadge.style.background = "rgba(52,199,89,0.15)";
    apiKeyBadge.style.color = "#30d158";
    apiKeyBadge.style.borderColor = "rgba(52,199,89,0.35)";
    if (key.startsWith("ak-") || mod.startsWith("spark")) {
      apiKeyBadge.textContent = "🟢 讯飞星辰深度思考已就绪 (Spark X2.6)";
    } else {
      apiKeyBadge.textContent = "🟢 DeepSeek 深度思考已就绪 (" + (mod === "deepseek-reasoner" ? "R1" : "V3") + ")";
    }
  } else {
    apiKeyBadge.style.background = "rgba(255,159,10,0.15)";
    apiKeyBadge.style.color = "#d97706";
    apiKeyBadge.style.borderColor = "rgba(255,159,10,0.35)";
    apiKeyBadge.textContent = "⚠️ 离线规则探针 (未配置 API Key)";
  }
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
    probe: 0,
    analyze: 0,
    plan: 1,
    solve: 2,
    gate: 3,
    paper: 2,
    gate_done: 99,
    done: 99,
    paper_done: 99,
    blocked: -2,
  };
  const activeIdx = stageIdxMap[stageKey] !== undefined ? stageIdxMap[stageKey] : 0;

  function updateGroup(ids, badgeSel) {
    ids.forEach((id, idx) => {
      const el = $(id);
      if (!el) return;
      const badge = el.querySelector(badgeSel);
      el.classList.remove("active", "done", "blocked");
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

function initStudioConfig() {
  const btnModeFast = $("btnRunModeFast");
  const btnModeDeep = $("btnRunModeDeep");
  if (btnModeFast) btnModeFast.addEventListener("click", () => setRunMode("fast"));
  if (btnModeDeep) btnModeDeep.addEventListener("click", () => setRunMode("deep"));
  setRunMode(studioState.runMode);

  const apiKeyInput = $("studioApiKeyInput");
  const modelSelect = $("studioModelSelect");
  const btnSaveApiKey = $("btnSaveApiKey");
  const savedKey = localStorage.getItem("orpath_deepseek_key") || "";
  const savedModel = localStorage.getItem("orpath_model_name") || "spark-x2.6";
  if (apiKeyInput) apiKeyInput.value = savedKey;
  if (modelSelect) modelSelect.value = savedModel;
  updateApiKeyBadge();

  if (apiKeyInput) {
    apiKeyInput.addEventListener("input", () => {
      const val = apiKeyInput.value.trim();
      if (val.startsWith("ak-") && modelSelect && modelSelect.value !== "spark-x2.6" && modelSelect.value !== "offline") {
        modelSelect.value = "spark-x2.6";
      } else if (val.startsWith("sk-") && modelSelect && modelSelect.value === "spark-x2.6") {
        modelSelect.value = "deepseek-reasoner";
      }
      localStorage.setItem("orpath_deepseek_key", val);
      updateApiKeyBadge();
    });
  }

  if (btnSaveApiKey) {
    btnSaveApiKey.addEventListener("click", () => {
      localStorage.setItem("orpath_deepseek_key", (apiKeyInput?.value || "").trim());
      localStorage.setItem("orpath_model_name", modelSelect?.value || "deepseek-reasoner");
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
