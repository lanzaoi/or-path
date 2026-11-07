/* ==========================================================================
   Studio Workbench Frontend Logic (智能做题工作舱)
   ========================================================================== */

function initStudioWorkbench() {
  const btnStudio = $("btnModeStudio");
  const btnInspector = $("btnModeInspector");

  if (btnStudio) btnStudio.addEventListener("click", () => setAppMode("studio"));
  if (btnInspector) btnInspector.addEventListener("click", () => setAppMode("inspector"));
  if ($("btnStudioViewInspector")) $("btnStudioViewInspector").addEventListener("click", () => setAppMode("inspector"));

  const savedMode = localStorage.getItem("orpath_mode") || "studio";
  setAppMode(savedMode);

  // --- Studio AI Configuration ---
  const apiKeyInput = $("studioApiKeyInput");
  const modelSelect = $("studioModelSelect");
  const apiKeyBadge = $("studioApiKeyBadge");
  const btnSaveApiKey = $("btnSaveApiKey");

  function updateApiKeyBadge() {
    const key = (apiKeyInput?.value || "").trim();
    const mod = modelSelect?.value || "spark-x2.6";
    if (!apiKeyBadge) return;
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

  // Initial render of 6-agent swarm strip with default Lead active
  renderDomainAgentStrip("default", "lead", "control_plane");

  // --- Smooth Studio Scrolling Helper ---
  function scrollStudioToCard(card) {
    if (!card) return;
    card.style.display = "block";
    setTimeout(() => {
      card.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 60);
  }

  // --- Multi-Domain Swarm Profiles (10 Domains + Default, 6 Specialists per Swarm) ---
  const DOMAIN_SWARM_PROFILES = {
    cutting: {
      name: "管材下料与骨牌覆盖",
      badge: "下料切剖 / 共边DP",
      roles: [
        { id: "lead", name: "总体架构", role: "or-tube-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "几何审计", role: "or-tube-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "精确下界", role: "or-tube-exact_bound", avatar: "📐", budget: 25, tool: "b_tube_solve", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "4模共边DP", role: "or-tube-heuristic", avatar: "⚡", budget: 25, tool: "tube_optimization", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "工程避焊", role: "or-tube-realities", avatar: "🏭", budget: 10, tool: "b_tube_geometry", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-tube-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    routing: {
      name: "车辆路径与物流网络",
      badge: "物流路径 / HGS遗传",
      roles: [
        { id: "lead", name: "路径统筹", role: "or-vrp-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "矩阵审计", role: "or-vrp-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "VRPTW规划", role: "or-vrp-exact_bound", avatar: "📐", budget: 25, tool: "solve_ortools", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "HGS混合遗传", role: "or-vrp-hgs", avatar: "⚡", budget: 25, tool: "solve_pyvrp", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "实景路网", role: "or-vrp-realities", avatar: "🏭", budget: 10, tool: "osm_distance_engine", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-vrp-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    scheduling: {
      name: "作业车间与排产调度",
      badge: "车间排产 / 析取图",
      roles: [
        { id: "lead", name: "车间总控", role: "or-jssp-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "析取图审计", role: "or-jssp-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "CP-SAT下界", role: "or-jssp-exact_bound", avatar: "📐", budget: 15, tool: "solve_jssp", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "邻域大搜索", role: "or-jssp-heuristic", avatar: "⚡", budget: 35, tool: "pyjobshop_alns", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "换模与断刀", role: "or-jssp-realities", avatar: "🏭", budget: 10, tool: "setup_calendar_policy", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-jssp-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    project: {
      name: "多资源项目排程 (RCPSP)",
      badge: "工程进度 / 累积资源",
      roles: [
        { id: "lead", name: "工程主控", role: "or-project-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "紧前关系审计", role: "or-project-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "累积资源规划", role: "or-project-exact_bound", avatar: "📐", budget: 25, tool: "solve_rcpsp", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "优先规则启发", role: "or-project-heuristic", avatar: "⚡", budget: 25, tool: "rcpsp_priority_sgs", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "日历与技能", role: "or-project-realities", avatar: "🏭", budget: 10, tool: "resource_calendar_sim", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-project-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    inventory: {
      name: "多周期动态批量订货",
      badge: "供应链库存 / WW-DP",
      roles: [
        { id: "lead", name: "供应链总控", role: "or-inventory-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "库存守恒审计", role: "or-inventory-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "Wagner-Whitin DP", role: "or-inventory-exact_bound", avatar: "📐", budget: 25, tool: "solve_lot_sizing", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "Silver-Meal启发", role: "or-inventory-heuristic", avatar: "⚡", budget: 25, tool: "silver_meal_heuristic", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "库容与货架", role: "or-inventory-realities", avatar: "🏭", budget: 10, tool: "warehouse_capacity_policy", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-inventory-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    facility: {
      name: "设施选址与网络设计 (CFLP)",
      badge: "网络选址 / 测地距离",
      roles: [
        { id: "lead", name: "网络总控", role: "or-facility-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "测地距离审计", role: "or-facility-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "容量混合整数规划", role: "or-facility-exact_bound", avatar: "📐", budget: 25, tool: "solve_facility", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "拉格朗日松弛", role: "or-facility-heuristic", avatar: "⚡", budget: 25, tool: "facility_add_drop", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "地块与阶梯租金", role: "or-facility-realities", avatar: "🏭", budget: 10, tool: "gis_boundary_verifier", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-facility-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    rostering: {
      name: "企业员工排班与轮休",
      badge: "排班轮休 / 集合覆盖",
      roles: [
        { id: "lead", name: "排班总控", role: "or-rostering-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "工时劳动法审计", role: "or-rostering-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "集合覆盖规划", role: "or-rostering-exact_bound", avatar: "📐", budget: 25, tool: "solve_staff_rostering", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "遗传变异换班", role: "or-rostering-heuristic", avatar: "⚡", budget: 25, tool: "shift_swapping_alns", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "偏好与疲劳度", role: "or-rostering-realities", avatar: "🏭", budget: 10, tool: "fatigue_fairness_model", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-rostering-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    microgrid: {
      name: "微电网储能能耗调度",
      badge: "光储微网 / 分时电价",
      roles: [
        { id: "lead", name: "微网总控", role: "or-microgrid-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "功率守恒审计", role: "or-microgrid-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "多周期分时LP", role: "or-microgrid-exact_bound", avatar: "📐", budget: 25, tool: "solve_microgrid", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "滚动MPC策略", role: "or-microgrid-heuristic", avatar: "⚡", budget: 25, tool: "rolling_mpc_dispatch", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "电池衰减与需量", role: "or-microgrid-realities", avatar: "🏭", budget: 10, tool: "microgrid_reporting", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-microgrid-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    pricing: {
      name: "动态定价与收益管理",
      badge: "定价博弈 / 收益管理",
      roles: [
        { id: "lead", name: "收益总控", role: "or-pricing-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "需求弹性审计", role: "or-pricing-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "凹函数规划", role: "or-pricing-exact_bound", avatar: "📐", budget: 25, tool: "solve_highs", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "双层博弈探索", role: "or-pricing-heuristic", avatar: "⚡", budget: 25, tool: "revenue_bilevel_search", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "价格走廊与库存", role: "or-pricing-realities", avatar: "🏭", budget: 10, tool: "price_corridor_policy", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-pricing-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    finance: {
      name: "投资组合与风险均衡",
      badge: "金融组合 / 风险平价",
      roles: [
        { id: "lead", name: "组合主控", role: "or-finance-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "协方差半正定审计", role: "or-finance-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "二次规划有效前沿", role: "or-finance-exact_bound", avatar: "📐", budget: 25, tool: "solve_portfolio", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "CVaR风险平价", role: "or-finance-heuristic", avatar: "⚡", budget: 25, tool: "risk_parity_slsqp", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "交易滑点与印花税", role: "or-finance-realities", avatar: "🏭", budget: 10, tool: "turnover_friction_rules", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-finance-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
    default: {
      name: "通用运筹专家编队",
      badge: "多智能体 / 运筹求解",
      roles: [
        { id: "lead", name: "总体架构", role: "or-lead", avatar: "👑", budget: 20, tool: "control_plane", bg: "#f1f5f9", col: "#0f172a" },
        { id: "auditor", name: "数理审计", role: "or-auditor", avatar: "🛡️", budget: 10, tool: "validate_solution", bg: "#eff6ff", col: "#2563eb" },
        { id: "exact", name: "精确规划", role: "or-exact_bound", avatar: "📐", budget: 25, tool: "solve_highs", bg: "#f5f3ff", col: "#7c3aed" },
        { id: "heuristic", name: "邻域搜索", role: "or-heuristic", avatar: "⚡", budget: 25, tool: "solve_alns", bg: "#ecfdf5", col: "#059669" },
        { id: "realities", name: "实境约束", role: "or-realities", avatar: "🏭", budget: 10, tool: "engineering_rules", bg: "#fffbeb", col: "#d97706" },
        { id: "redteam", name: "对抗红队", role: "or-redteam", avatar: "🎯", budget: 10, tool: "dimo_mutator", bg: "#fef2f2", col: "#dc2626" },
      ],
    },
  };

  let currentDomainKey = "default";

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

  function renderDomainAgentStrip(domainKey, activeRoleKey, toolName) {
    const strip = $("studioAgentStrip");
    if (!strip) return;
    const normKey = normalizeDomainKey(domainKey);
    currentDomainKey = normKey;
    const profile = DOMAIN_SWARM_PROFILES[normKey] || DOMAIN_SWARM_PROFILES.default;

    // Legacy card ID aliases for backwards compatibility with test harnesses
    const legacyAliases = ["Supervisor", "Researcher", "Modeler", "Verifier", "Realities", "Redteam"];

    strip.innerHTML = profile.roles.map((r, idx) => {
      const alias = legacyAliases[idx] || r.id;
      return `
        <div class="ma-agent-card waiting" id="agentCard${esc(alias)}" data-agent-idx="${idx}" data-agent-role="${esc(r.id)}">
          <div class="ma-agent-top">
            <div class="ma-agent-avatar" style="background:${esc(r.bg)};color:${esc(r.col)}">${esc(r.avatar)}</div>
            <div class="ma-agent-info">
              <div class="ma-agent-name" id="agentName${esc(alias)}">${esc(r.name)}</div>
              <div class="ma-agent-role" id="agentRole${esc(alias)}">${esc(r.role)}</div>
            </div>
            <span class="ma-agent-status waiting" id="agentStatus${esc(alias)}">待命</span>
          </div>
          <div class="ma-agent-workload">
            <span>精力预算</span>
            <span id="agentWorkload${esc(alias)}">${esc(r.budget)}%</span>
          </div>
          <div class="ma-workload-bar">
            <div class="ma-workload-fill" id="agentBar${esc(alias)}" style="width:${esc(r.budget)}%"></div>
          </div>
          <div class="ma-agent-tool" id="agentTool${esc(alias)}">${esc(r.tool)}</div>
        </div>
      `;
    }).join("");

    if (activeRoleKey) {
      setAgentActive(activeRoleKey, null, toolName);
    }
  }

  function setAgentActive(agentKey, statusText, toolName) {
    const roleMap = {
      supervisor: 0,
      lead: 0,
      researcher: 1,
      auditor: 1,
      modeler: 2,
      exact: 2,
      exact_bound: 2,
      verifier: 3,
      heuristic: 3,
      hgs: 3,
      realities: 4,
      redteam: 5,
    };

    let targetIdx = -1;
    if (typeof agentKey === "number") {
      targetIdx = agentKey;
    } else if (typeof agentKey === "string") {
      const k = agentKey.toLowerCase().replace(/[-_]/g, "");
      if (k === "alldone" || k === "all_done") {
        targetIdx = 999;
      } else {
        for (const [rk, idx] of Object.entries(roleMap)) {
          if (k.includes(rk)) {
            targetIdx = idx;
            break;
          }
        }
      }
    }

    const cards = document.querySelectorAll("#studioAgentStrip .ma-agent-card");
    if (!cards || cards.length === 0) return;

    cards.forEach((card, idx) => {
      const st = card.querySelector(".ma-agent-status");
      const toolEl = card.querySelector(".ma-agent-tool");
      card.classList.remove("active", "done", "waiting");

      if (targetIdx === 999 || (targetIdx >= 0 && idx < targetIdx)) {
        card.classList.add("done");
        if (st) {
          st.textContent = "已完成 ✓";
          st.className = "ma-agent-status done";
        }
      } else if (idx === targetIdx) {
        card.classList.add("active");
        if (st) {
          st.textContent = statusText || "执行中…";
          st.className = "ma-agent-status active";
        }
        if (toolName && toolEl) {
          toolEl.textContent = toolName;
        }
      } else {
        card.classList.add("waiting");
        if (st) {
          st.textContent = "待命";
          st.className = "ma-agent-status waiting";
        }
      }
    });
  }

  // --- Studio Files & Drag-and-Drop ---
  const MAX_STUDIO_FILES = 200;
  const MAX_STUDIO_TOTAL_BYTES = 25 * 1024 * 1024; // 25 MB
  const MAX_STUDIO_FILE_BYTES = 10 * 1024 * 1024; // 10 MB per file
  const MAX_RECURSION_DEPTH = 12;

  let studioLoadedFiles = []; // Array of {rel_path, content_base64, size}
  const dropzone = $("studioDropzone");
  const fileInput = $("studioFileInput");
  const filesOnlyInput = $("studioFilesOnlyInput");
  const fileList = $("studioFileList");
  const btnSelectFolder = $("btnPickFolder") || $("btnStudioSelectFolder");
  const btnSelectFiles = $("btnPickFiles") || $("btnStudioSelectFiles");

  if (btnSelectFolder && fileInput) {
    btnSelectFolder.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }
  if (btnSelectFiles && filesOnlyInput) {
    btnSelectFiles.addEventListener("click", (e) => {
      e.stopPropagation();
      filesOnlyInput.click();
    });
  }
  if (dropzone) {
    dropzone.addEventListener("click", () => {
      if (fileInput) fileInput.click();
    });
  }

  function updateFileListUI() {
    if (!fileList) return;
    if (studioLoadedFiles.length === 0) {
      fileList.innerHTML = `<span style="color:var(--ink-48)">尚未载入附件 (可拖入题面文件夹、坐标矩阵、需求清单或表格)</span>`;
      if ($("studioFileActionNotice")) $("studioFileActionNotice").style.display = "none";
      return;
    }
    const totalBytes = studioLoadedFiles.reduce((acc, f) => acc + (f.size || 0), 0);
    const kbStr = fmtKB(totalBytes);
    fileList.innerHTML = `
      <div style="font-weight:700;color:var(--blue);margin-bottom:6px">
        📂 已解析待研判文件清单 (${studioLoadedFiles.length} 个文件 · 共 ${kbStr}):
      </div>
      <div style="max-height:120px;overflow-y:auto;background:var(--surface-2);border-radius:6px;padding:8px 10px;font-family:var(--mono);line-height:1.6">
        ${studioLoadedFiles.map(f => `<div>📄 ${esc(f.rel_path)} <span style="color:var(--ink-48);font-size:10px">(${fmtKB(f.size)})</span></div>`).join("")}
      </div>
    `;

    // 智能建议 slug 标识
    const slugEl = $("studioSlugInput");
    if (slugEl && (slugEl.value === "case-studio" || slugEl.value === "case-my-problem" || !slugEl.value)) {
      const first = studioLoadedFiles[0]?.rel_path || "";
      const base = first.split("/")[0].split(".")[0].replace(/[^a-zA-Z0-9_-]/g, "").toLowerCase();
      if (base && base.length >= 2) slugEl.value = "case-" + base;
    }

    // 展现快捷启动横幅
    const notice = $("studioFileActionNotice");
    if (notice) {
      notice.style.display = "flex";
      const countEl = $("studioFileReadyText") || $("studioFileCountText");
      if (countEl) countEl.textContent = `已就绪 ${studioLoadedFiles.length} 个文件 (${kbStr})`;
    }
  }

  function readFileAsBase64(file, relPath) {
    return new Promise((resolve) => {
      if (file.size > MAX_STUDIO_FILE_BYTES) {
        showToast(`文件 ${relPath} 超过 10MB 单文件限制，已跳过`, "warn");
        resolve(null);
        return;
      }
      const reader = new FileReader();
      const timer = setTimeout(() => {
        resolve({ rel_path: relPath, content_base64: "", size: file.size || 0 });
      }, 5000);
      reader.onload = () => {
        clearTimeout(timer);
        const b64 = (reader.result || "").split(",")[1] || "";
        resolve({ rel_path: relPath, content_base64: b64, size: file.size || 0 });
      };
      reader.onerror = () => {
        clearTimeout(timer);
        resolve({ rel_path: relPath, content_base64: "", size: file.size || 0 });
      };
      reader.readAsDataURL(file);
    });
  }

  async function scanFiles(items, rawFiles) {
    let usedEntries = false;
    if (items && items.length > 0 && items[0].webkitGetAsEntry) {
      const entries = [];
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item && item.webkitGetAsEntry) {
          try {
            const entry = item.webkitGetAsEntry();
            if (entry) entries.push(entry);
          } catch (_) {}
        }
      }
      if (entries.length > 0) {
        usedEntries = true;
        async function readEntry(entry, path = "", depth = 0) {
          if (depth > MAX_RECURSION_DEPTH) {
            console.warn("Directory recursion exceeded max depth: " + path);
            return;
          }
          if (studioLoadedFiles.length >= MAX_STUDIO_FILES) {
            showToast(`文件总数已达上限 (${MAX_STUDIO_FILES})，多余文件已忽略`, "warn");
            return;
          }
          const curBytes = studioLoadedFiles.reduce((acc, f) => acc + (f.size || 0), 0);
          if (curBytes >= MAX_STUDIO_TOTAL_BYTES) {
            showToast(`文件总体积已达上限 (25MB)，后续文件已忽略`, "warn");
            return;
          }
          if (entry.isFile) {
            const f = await new Promise((res) => entry.file(res, () => res(null)));
            if (f) {
              const rel = path ? `${path}/${f.name}` : f.name;
              const obj = await readFileAsBase64(f, rel);
              if (obj && studioLoadedFiles.length < MAX_STUDIO_FILES) {
                studioLoadedFiles.push(obj);
              }
            }
          } else if (entry.isDirectory) {
            const dirReader = entry.createReader();
            const readEntriesBatch = () => new Promise((res) => dirReader.readEntries(res, () => res([])));
            let batch = await readEntriesBatch();
            while (batch.length > 0) {
              for (const sub of batch) {
                if (studioLoadedFiles.length >= MAX_STUDIO_FILES) break;
                await readEntry(sub, path ? `${path}/${entry.name}` : entry.name, depth + 1);
              }
              if (studioLoadedFiles.length >= MAX_STUDIO_FILES) break;
              batch = await readEntriesBatch();
            }
          }
        }
        for (const ent of entries) {
          await readEntry(ent, "", 0);
        }
      }
    }
    if (!usedEntries && rawFiles && rawFiles.length > 0) {
      for (const f of rawFiles) {
        if (studioLoadedFiles.length >= MAX_STUDIO_FILES) {
          showToast(`文件总数已达上限 (${MAX_STUDIO_FILES})`, "warn");
          break;
        }
        const curBytes = studioLoadedFiles.reduce((acc, x) => acc + (x.size || 0), 0);
        if (curBytes + (f.size || 0) > MAX_STUDIO_TOTAL_BYTES) {
          showToast(`文件总体积超过 25MB 上限`, "warn");
          break;
        }
        const rel = f.webkitRelativePath || f.name;
        const obj = await readFileAsBase64(f, rel);
        if (obj) studioLoadedFiles.push(obj);
      }
    }
    updateFileListUI();
  }

  if (dropzone) {
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });
    dropzone.addEventListener("drop", async (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      studioLoadedFiles = [];
      if (e.dataTransfer) {
        await scanFiles(e.dataTransfer.items, e.dataTransfer.files);
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", async () => {
      studioLoadedFiles = [];
      if (fileInput.files) {
        for (const f of fileInput.files) {
          if (studioLoadedFiles.length >= MAX_STUDIO_FILES) {
            showToast(`文件总数已达上限 (${MAX_STUDIO_FILES})`, "warn");
            break;
          }
          const curBytes = studioLoadedFiles.reduce((acc, x) => acc + (x.size || 0), 0);
          if (curBytes + (f.size || 0) > MAX_STUDIO_TOTAL_BYTES) {
            showToast("文件总体积已达上限 (25MB)，后续文件已忽略", "warn");
            break;
          }
          const rel = f.webkitRelativePath || f.name;
          const obj = await readFileAsBase64(f, rel);
          if (obj) studioLoadedFiles.push(obj);
        }
      }
      fileInput.value = "";
      updateFileListUI();
    });
  }

  if (filesOnlyInput) {
    filesOnlyInput.addEventListener("change", async () => {
      studioLoadedFiles = [];
      if (filesOnlyInput.files) {
        for (const f of filesOnlyInput.files) {
          if (studioLoadedFiles.length >= MAX_STUDIO_FILES) {
            showToast(`文件总数已达上限 (${MAX_STUDIO_FILES})`, "warn");
            break;
          }
          const curBytes = studioLoadedFiles.reduce((acc, x) => acc + (x.size || 0), 0);
          if (curBytes + (f.size || 0) > MAX_STUDIO_TOTAL_BYTES) {
            showToast("文件总体积已达上限 (25MB)，后续文件已忽略", "warn");
            break;
          }
          const obj = await readFileAsBase64(f, f.name);
          if (obj) studioLoadedFiles.push(obj);
        }
      }
      filesOnlyInput.value = "";
      updateFileListUI();
    });
  }

  // --- Preset Data Loader ---
  if ($("btnStudioLoadPreset")) {
    $("btnStudioLoadPreset").addEventListener("click", () => {
      $("studioSlugInput").value = "case-tsp-8";
      $("studioPromptInput").value = "8工位智能巡检规划：请根据坐标规划一条封闭巡检路线，要求遍历8个站点并返回起点，总里程最短。";
      const coords = { coords: [
        { id: 0, x: 0, y: 0 }, { id: 1, x: 10, y: 5 }, { id: 2, x: 20, y: 10 },
        { id: 3, x: 30, y: 15 }, { id: 4, x: 40, y: 20 }, { id: 5, x: 50, y: 25 },
        { id: 6, x: 60, y: 30 }, { id: 7, x: 70, y: 35 }
      ]};
      const b64Coords = btoa(JSON.stringify(coords));
      const b64Prob = btoa("# 8工位巡检问题\n问题一：访问8个工位并返回起点\n");
      studioLoadedFiles = [
        { rel_path: "problem.md", content_base64: b64Prob, size: 120 },
        { rel_path: "data/coords.json", content_base64: b64Coords, size: 240 },
      ];
      updateFileListUI();
    });
  }

  // --- Studio Analyze ---
  let currentAnalysis = null;
  let analyzeAbortController = null;
  const btnAnalyze = $("btnStudioAnalyze");

  async function triggerStudioAnalyze() {
    if (analyzeAbortController) {
      analyzeAbortController.abort();
    }
    analyzeAbortController = new AbortController();
    const signal = analyzeAbortController.signal;

    const slug = ($("studioSlugInput")?.value || "case-studio").trim();
    const prompt = ($("studioPromptInput")?.value || "").trim();
    const apiKey = (apiKeyInput?.value || "").trim();
    const model = modelSelect?.value || "deepseek-reasoner";
    const st1 = $("studioStep1Status");
    const errBox = $("studioAnalyzeError");
    if (errBox) { errBox.style.display = "none"; errBox.textContent = ""; }
    if (st1) st1.innerHTML = `<span style="color:var(--blue)">⏳ 正在上传附件并由数据探针与深度模型研判中…</span>`;
    if (btnAnalyze) { btnAnalyze.disabled = true; btnAnalyze.textContent = "⏳ 正在研判中…"; }
    const btnQuick = $("btnStudioQuickAnalyze");
    if (btnQuick) btnQuick.disabled = true;
    if (typeof setAgentActive === "function") setAgentActive("researcher", "文献研判中…");

    try {
      if (studioLoadedFiles.length > 0) {
        const impRes = await fetch("/api/intake/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: "folder", slug, files: studioLoadedFiles }),
          signal,
        });
        if (signal.aborted) return;
        const impJson = await impRes.json();
        if (signal.aborted) return;
        if (!impJson.ok) throw new Error(impJson.error || "文件夹上传失败");
      }

      let anaJson = null;
      for (let attempt = 0; attempt < 3; attempt++) {
        if (signal.aborted) return;
        const anaRes = await fetch("/api/studio/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slug, prompt, api_key: apiKey, model }),
          signal,
        });
        if (signal.aborted) return;
        anaJson = await anaRes.json();
        if (signal.aborted) return;
        const errText = String(anaJson.error || "");
        const rText = String(anaJson.analysis?.thinking_meta?.reasoning_text || "");
        if ((anaRes.status === 429 || errText.includes("429") || rText.includes("HTTP 429") || rText.includes("限流")) && attempt < 2) {
          if (st1) st1.innerHTML = `<span style="color:#d97706">⏳ 遇到 429 限流，正在自动重试 (${attempt + 1}/2)…</span>`;
          await new Promise((resolve, reject) => {
            const tm = setTimeout(resolve, 2000 * (attempt + 1));
            signal.addEventListener("abort", () => {
              clearTimeout(tm);
              reject(new DOMException("Aborted", "AbortError"));
            }, { once: true });
          });
          continue;
        }
        break;
      }
      if (signal.aborted) return;
      if (!anaJson || !anaJson.ok) throw new Error((anaJson && anaJson.error) || "研判分析受阻");

      currentAnalysis = anaJson.analysis;
      const isLive = Boolean(currentAnalysis?.thinking_meta?.live_thinking);
      if (st1) {
        if (isLive) {
          st1.innerHTML = '<span style="color:#059669">✅ 深度思考已完成，决策卡已就绪</span>';
        } else {
          st1.innerHTML = '<span style="color:#d97706">✅ 本地规则探针研判完成，决策卡已就绪 (离线模式)</span>';
        }
      }

      renderStudioAnalysisCard(currentAnalysis);
    } catch (err) {
      if (err.name === "AbortError" || signal.aborted) return;
      if (st1) st1.innerHTML = '<span style="color:#dc2626">❌ 研判受阻</span>';
      if (errBox) {
        errBox.style.display = "block";
        errBox.innerHTML = `<strong>⚠️ 研判失败：</strong> ${esc(err.message)} <br/><span style="font-size:11px;opacity:0.8">请检查文件格式或 API 配置后重试。</span>`;
      }
    } finally {
      if (btnAnalyze) { btnAnalyze.disabled = false; btnAnalyze.textContent = "🚀 启动全流程分析研判"; }
      if (btnQuick) btnQuick.disabled = false;
    }
  }

  if (btnAnalyze) btnAnalyze.addEventListener("click", triggerStudioAnalyze);
  if ($("btnStudioQuickAnalyze")) $("btnStudioQuickAnalyze").addEventListener("click", triggerStudioAnalyze);

  function renderStudioAnalysisCard(ana) {
    const card = $("studioAnalysisCard");
    if (!card) return;
    scrollStudioToCard(card);

    const meta = ana.thinking_meta || {};
    const isLive = Boolean(meta.live_thinking);
    const badge = $("studioThinkingBadge");
    const promptBanner = $("studioKeyPromptBanner");
    if (badge) {
      if (isLive) {
        badge.style.background = "rgba(16,185,129,0.15)";
        badge.style.color = "#047857";
        const modelUsed = String(meta.model_used || "");
        const modelLabel = /spark/i.test(modelUsed)
          ? "讯飞星辰 Spark X2.6"
          : (modelUsed && modelUsed !== "deepseek-reasoner" ? modelUsed : "DeepSeek-R1");
        badge.textContent = `🟢 ${modelLabel} 实时思考已启用`;
        if (promptBanner) promptBanner.style.display = "none";
      } else {
        badge.style.background = "rgba(255,159,10,0.15)";
        badge.style.color = "#d97706";
        badge.textContent = "🟡 离线规则探针 (未配置 API Key)";
        if (promptBanner) promptBanner.style.display = "block";
      }
    }

    const diag = ana.domain_diagnosis || {};
    const diagBanner = $("studioDiagnosisBanner");
    if (diagBanner) {
      diagBanner.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:8px">
          <strong style="font-size:15px;color:#6d28d9">🎯 识别领域：${esc(diag.domain_name || diag.problem_class)}</strong>
          <span style="font-size:11px;background:#8b5cf6;color:#fff;padding:2px 8px;border-radius:10px;font-weight:600">第一推荐：${esc(diag.recommended_algorithm)}</span>
        </div>
        <p style="margin:0;font-size:12px;line-height:1.5;color:var(--ink-60)">${esc(diag.rationale || '')}</p>
      `;
    }

    const kBanner = $("studioKnowledgeBanner");
    const kHits = ana.knowledge_hits || (meta && meta.knowledge_hits) || [];
    const kSkills = ana.matched_skills || (meta && meta.matched_skills) || [];
    const kLit = ana.literature_anchors || (meta && meta.literature_anchors) || [];
    if (kBanner) {
      kBanner.style.display = "block";
      const renderHitRow = (kh, checked = true) => `
        <label style="display:flex;align-items:flex-start;gap:8px;background:#fff;border:1px solid #e0e7ff;border-radius:6px;padding:7px 10px;font-size:11px;cursor:pointer">
          <input type="checkbox" class="studio-pin-kb" ${checked ? "checked" : ""}
            data-kb-id="${esc(kh.chunk_id || kh.id || '')}"
            data-kb-title="${esc(kh.title || kh.chunk_id || '')}"
            data-kb-kind="chunk"
            data-kb-snippet="${esc((kh.snippet || '').slice(0, 180))}"
            style="margin-top:2px;cursor:pointer" />
          <div style="flex:1;min-width:0">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;gap:6px">
              <span style="font-weight:600;color:#1e1b4b">📄 ${esc(kh.title || kh.chunk_id)}</span>
              <span style="font-size:10px;color:#6366f1;font-family:var(--mono)">相关度: ${esc(kh.score ?? '-')}</span>
            </div>
            <div style="color:var(--ink-48);line-height:1.4;font-size:10.5px">${esc(kh.snippet || '')}</div>
          </div>
        </label>
      `;

      kBanner.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px">
          <strong style="font-size:13px;color:#4338ca">📚 运筹知识库先验工作台 (勾选锁定项将注入建模与论文锚点)</strong>
          <span style="font-size:10px;background:#e0e7ff;color:#3730a3;padding:2px 8px;border-radius:8px;font-weight:600">Hybrid BM25 + bge-m3 + Top500 顶刊</span>
        </div>
        ${kSkills.length > 0 ? `
          <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">
            ${kSkills.map((sk, idx) => `
              <label style="display:inline-flex;align-items:center;gap:5px;background:#eef2ff;border:1px solid #c7d2fe;color:#3730a3;padding:3px 9px;border-radius:999px;font-size:10.5px;font-weight:600;cursor:pointer">
                <input type="checkbox" class="studio-pin-kb" ${idx < 2 ? "checked" : ""}
                  data-kb-id="${esc(sk.id)}"
                  data-kb-title="${esc(sk.id)}"
                  data-kb-kind="skill"
                  data-kb-snippet="${esc((sk.excerpt || '').slice(0, 160))}" />
                🛠️ Skill: ${esc(sk.id)}
              </label>
            `).join("")}
          </div>
        ` : ""}
        <div id="studioKbItemsList" style="display:flex;flex-direction:column;gap:6px;margin-bottom:8px">
          ${kHits.map((kh, idx) => renderHitRow(kh, idx < 2)).join("")}
        </div>
        ${kLit.length > 0 ? `
          <div style="background:#f5f3ff;border:1px dashed #c4b5fd;border-radius:6px;padding:6px 10px;margin-bottom:8px;font-size:10.5px;color:#4c1d95;line-height:1.5">
            <strong>🏛️ 匹配权威顶刊文献锚点：</strong>
            ${kLit.map(l => `<span style="margin-right:10px">• ${esc(l.cite_label)} <em>${esc(l.title)}</em> (${esc(l.venue)})</span>`).join("")}
          </div>
        ` : ""}
        <div style="display:flex;gap:6px;align-items:center">
          <input type="text" id="studioKbSearchInput" placeholder="实时检索知识库方法/模型/割平面 (例如: cutting plane subtour, column generation)…"
            style="flex:1;height:30px;padding:0 10px;border:1px solid #c7d2fe;border-radius:6px;font-size:11.5px;background:#fff;outline:none" />
          <button type="button" class="wb-btn" id="btnStudioKbSearch" style="height:30px;padding:0 12px;font-size:11.5px">🔍 检索并锁定</button>
        </div>
      `;

      const kbBtn = $("btnStudioKbSearch");
      const kbInp = $("studioKbSearchInput");
      const kbList = $("studioKbItemsList");
      const doKbSearch = async () => {
        const q = (kbInp?.value || "").trim();
        if (!q || !kbList) return;
        if (kbBtn) { kbBtn.disabled = true; kbBtn.textContent = "检索中…"; }
        try {
          const pc = encodeURIComponent(diag.problem_class || "");
          const res = await fetch(`/api/knowledge/search?q=${encodeURIComponent(q)}&problem_class=${pc}&topk=4`);
          const data = await res.json();
          if (data && data.ok && Array.isArray(data.hits)) {
            const existing = new Set(Array.from(kbList.querySelectorAll(".studio-pin-kb")).map(el => el.getAttribute("data-kb-id")));
            const fresh = data.hits.filter(h => !existing.has(String(h.chunk_id)));
            if (fresh.length > 0) {
              kbList.insertAdjacentHTML("afterbegin", fresh.map(h => renderHitRow(h, true)).join(""));
            }
          }
        } catch (_) {
        } finally {
          if (kbBtn) { kbBtn.disabled = false; kbBtn.textContent = "🔍 检索并锁定"; }
        }
      };
      if (kbBtn) kbBtn.addEventListener("click", doKbSearch);
      if (kbInp) kbInp.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); doKbSearch(); } });
    }

    const algoList = $("studioAlgoList");
    if (algoList) {
      algoList.innerHTML = (diag.algorithm_comparison || []).map(al => `
        <div class="studio-algo-item" style="border:1px solid ${al.recommended ? 'var(--blue)' : 'var(--border)'};background:${al.recommended ? 'rgba(37,99,235,0.04)' : '#f8fafc'};">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <strong style="font-size:12.5px;color:#0f172a">${esc(al.name)}</strong>
            ${al.recommended ? '<span style="font-size:10.5px;background:rgba(37,99,235,0.12);color:var(--blue);font-weight:700;padding:2px 8px;border-radius:9999px">★ 推荐方案</span>' : ''}
          </div>
          <div style="font-size:11.5px;color:#64748b;line-height:1.5">
            <div><span style="color:#059669;font-weight:700">✓ 优势:</span> ${esc(al.pros || '')}</div>
            <div><span style="color:#d97706;font-weight:700">⚠ 考量:</span> ${esc(al.cons || '')}</div>
          </div>
        </div>
      `).join("");
    }

    const dataList = $("studioDataList");
    if (dataList) {
      dataList.innerHTML = (ana.data_alignment?.matched_variables || []).map(mv => `
        <div class="studio-data-item">
          <div>
            <strong style="font-size:12.5px;color:#0f172a">${esc(mv.name)}</strong>
            <div style="font-size:11px;color:#64748b;margin-top:2px">${esc(mv.source)} · ${esc(mv.details)}</div>
          </div>
          <span style="font-size:10.5px;background:rgba(16,185,129,0.15);color:#047857;border:1px solid rgba(16,185,129,0.3);padding:2px 8px;border-radius:9999px;font-weight:700">${esc(mv.status)}</span>
        </div>
      `).join("");
    }

    const thinkingContent = $("studioThinkingContent");
    if (thinkingContent) {
      thinkingContent.textContent = meta.reasoning_text || "无思考日志";
    }

    const qBox = $("studioQuestionsBox");
    if (qBox) {
      qBox.innerHTML = (ana.clarification_questions || []).map((q, idx) => `
        <div class="studio-question-card">
          <div style="font-size:12.5px;font-weight:700;margin-bottom:8px;color:#1e293b">Q${idx + 1}. ${esc(q.question)}</div>
          <div style="display:flex;flex-direction:column;gap:6px">
            ${(q.options || []).map(opt => `
              <label class="studio-option-label">
                <input type="radio" name="${esc(q.id)}" value="${esc(opt.id)}" ${opt.recommended ? 'checked' : ''} style="cursor:pointer" />
                <span style="color:#334155;font-weight:${opt.recommended ? '600' : '400'}">${esc(opt.label)}</span>
              </label>
            `).join("")}
          </div>
        </div>
      `).join("");
    }
    const domKey = normalizeDomainKey(diag.problem_class || diag.domain_name);
    renderDomainAgentStrip(domKey, "modeler", "建模反问中");
  }

  // --- Studio Confirm Solve ---
  const btnConfirm = $("btnStudioConfirmSolve");
  if (btnConfirm) {
    btnConfirm.addEventListener("click", async () => {
      const slug = ($("studioSlugInput")?.value || "case-studio").trim();
      const extraPrompt = ($("studioExtraPrompt")?.value || "").trim();
      const st2 = $("studioStep2Status");
      const errBox = $("studioConfirmError");
      if (errBox) { errBox.style.display = "none"; errBox.textContent = ""; }

      const selectedOptions = {};
      if (currentAnalysis && currentAnalysis.clarification_questions) {
        currentAnalysis.clarification_questions.forEach(q => {
          const checked = document.querySelector(`input[name="${CSS.escape(String(q.id))}"]:checked`);
          if (checked) selectedOptions[q.id] = checked.value;
        });
      }

      if (st2) st2.innerHTML = `<span style="color:var(--blue)">⏳ 正在调用多智能体与真实求解器，在物理门禁中严格验算…</span>`;
      btnConfirm.disabled = true;
      btnConfirm.textContent = "⏳ 求解中…";
      setAgentActive("verifier", "求解验算…");

      const savedKey = (apiKeyInput?.value || localStorage.getItem("orpath_deepseek_key") || "").trim();
      const savedModel = (modelSelect?.value || localStorage.getItem("orpath_model_name") || "spark-x2.6").trim();
      const isOffline = savedModel === "offline" || !savedKey;

      const confController = new AbortController();
      const confTimeout = setTimeout(() => confController.abort(), 130000);

      const pinnedKnowledge = Array.from(document.querySelectorAll(".studio-pin-kb:checked")).map(el => ({
        id: el.getAttribute("data-kb-id") || "",
        title: el.getAttribute("data-kb-title") || "",
        kind: el.getAttribute("data-kb-kind") || "chunk",
        snippet: el.getAttribute("data-kb-snippet") || "",
      })).filter(x => x.id || x.title);

      try {
        const confRes = await fetch("/api/studio/confirm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            slug,
            selected_options: selectedOptions,
            extra_prompt: extraPrompt,
            pinned_knowledge: pinnedKnowledge,
            api_key: savedKey,
            model: savedModel,
            timeout: isOffline ? 3.0 : 60.0,
          }),
          signal: confController.signal,
        });
        const confJson = await confRes.json();
        if (!confJson.ok) throw new Error(confJson.error || "求解失败");

        if (st2) st2.innerHTML = '<span style="color:#059669">✅ 求解与严格验算已完成</span>';
        renderStudioResultCard(slug, confJson);
      } catch (err) {
        if (st2) st2.innerHTML = '<span style="color:#dc2626">❌ 求解受阻</span>';
        if (errBox) {
          errBox.style.display = "block";
          const errMsg = err.name === "AbortError" ? "求解等待超时 (130s)，请检查模型响应或降低求解规模。" : err.message;
          errBox.innerHTML = `<strong>⚠️ 求解失败：</strong> ${esc(errMsg)} <br/><span style="font-size:11px;opacity:0.8">请检查题面参数或在高级选项中补充说明。</span>`;
        }
      } finally {
        clearTimeout(confTimeout);
        btnConfirm.disabled = false;
        btnConfirm.textContent = "✅ 确认决策并启动真算";
      }
    });
  }

  function renderStudioResultCard(slug, res) {
    const card = $("studioResultCard");
    if (!card) return;
    scrollStudioToCard(card);
    setAgentActive("all_done");

    const summary = res.plain_language_summary || {};
    const isProvenOpt = Boolean(
      res.proven_optimal ??
      res.solution?.proven_optimal ??
      res.solution?.meta?.proven_optimal ??
      summary.proven_optimal
    );

    if ($("studioHeadline")) {
      $("studioHeadline").textContent = summary.headline || (res.status === "COMPLETED" ? "运筹问题已成功求解" : "求解完成");
    }

    const fallbackObj = (res.solution && res.solution.objective != null)
      ? (isProvenOpt ? `严格最优目标值: ${res.solution.objective}` : `可行解目标值: ${res.solution.objective} (未证最优)`)
      : (res.status === "BLOCKED" ? "无解/求解受阻" : "等待求解产物");

    if ($("studioObjective")) {
      const objText = summary.objective_str || fallbackObj;
      const optBadge = isProvenOpt
        ? '<span style="font-size:11px;background:#ecfdf5;color:#047857;padding:3px 8px;border-radius:12px;font-weight:700;margin-left:10px;vertical-align:middle;border:1px solid #a7f3d0">★ 严格全局最优</span>'
        : (res.solution && res.solution.objective != null
          ? '<span style="font-size:11px;background:#fffbeb;color:#b45309;padding:3px 8px;border-radius:12px;font-weight:600;margin-left:10px;vertical-align:middle;border:1px solid #fde68a">⚡ 可行解 (未证最优)</span>'
          : '');
      $("studioObjective").innerHTML = `${esc(objText)} ${optBadge}`;
    }

    if ($("studioValidation")) {
      $("studioValidation").textContent = summary.validation_status || (res.status === "COMPLETED" ? "数理门禁校验合格" : "校验中或待完成");
    }
    if ($("studioSolutionDetail")) {
      $("studioSolutionDetail").textContent = summary.solution_detail || "";
    }

    const dlSol = $("dlSolution");
    if (dlSol) dlSol.href = `/api/artifact/download?slug=${encodeURIComponent(slug)}&kind=solution`;
    const dlVal = $("dlValidation");
    if (dlVal) dlVal.href = `/api/artifact/download?slug=${encodeURIComponent(slug)}&kind=validate`;
    const dlPaper = $("dlPaper");
    if (dlPaper) dlPaper.href = `/api/artifact/download?slug=${encodeURIComponent(slug)}&kind=paper`;
    const dlAna = $("dlAnalysis");
    if (dlAna) dlAna.href = `/api/artifact/download?slug=${encodeURIComponent(slug)}&kind=analysis`;

    renderVisualizations(res.solution, currentAnalysis);
  }

  // --- Live Snapshot Sync in Studio Mode (Process Visibility) ---
  window.syncStudioSnapshot = function(snap) {
    if (!snap) return;
    if (snap.domain && snap.domain !== currentDomainKey) {
      renderDomainAgentStrip(snap.domain);
    }
    if (snap.current && (snap.current.role || snap.current.agent)) {
      const activeRole = snap.current.role || snap.current.agent;
      const toolAction = snap.current.stage || snap.current.action || snap.current.tool || "执行中…";
      setAgentActive(activeRole, "执行中…", toolAction);
    } else if (snap.status === "DONE" || snap.status === "COMPLETED") {
      setAgentActive("all_done");
    }
  };

  // --- Dynamic OR Visualization & Convergence Dashboard (Task 6.3 - Huashu 5D Standard) ---
  let vizTabsBound = false;
  function initVizTabsOnce() {
    if (vizTabsBound) return;
    const tabsContainer = $("vizTabs");
    if (!tabsContainer) return;
    vizTabsBound = true;
    tabsContainer.addEventListener("click", (e) => {
      const tabBtn = e.target.closest("[data-viz-tab]");
      if (!tabBtn) return;
      const targetTab = tabBtn.getAttribute("data-viz-tab");
      document.querySelectorAll("#vizTabs [data-viz-tab]").forEach(b => {
        b.classList.toggle("active", b === tabBtn);
      });
      const panels = {
        gantt: $("vizPanelGantt"),
        routes: $("vizPanelRoutes"),
        gap: $("vizPanelGap"),
      };
      for (const [k, p] of Object.entries(panels)) {
        if (!p) continue;
        if (k === targetTab) {
          p.style.display = "block";
          p.classList.add("active");
        } else {
          p.style.display = "none";
          p.classList.remove("active");
        }
      }
    });
  }

  function showVizTooltip(text) {
    const tipBox = $("vizInteractiveTooltip");
    const tipText = $("vizTooltipText");
    if (!tipBox || !tipText) return;
    tipText.textContent = text;
    tipBox.style.display = "flex";
  }

  function hideVizTooltip() {
    const tipBox = $("vizInteractiveTooltip");
    if (tipBox) tipBox.style.display = "none";
  }

  function renderGanttChart(container, solution, domain) {
    if (!container) return;
    const colors = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899", "#84cc16"];

    if (!solution || !Array.isArray(solution.schedule) || solution.schedule.length === 0) {
      container.innerHTML = `
        <div class="viz-empty-card" style="padding:42px 20px;text-align:center;background:var(--surface-2);border:1px dashed var(--border);border-radius:12px;margin:10px 0">
          <div style="font-size:32px;margin-bottom:8px">🏭</div>
          <div style="font-weight:600;font-size:13px;color:#334155">当前算例不含工序时序排程数据</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:6px;max-width:520px;margin-left:auto;margin-right:auto;line-height:1.6">
            甘特图专用于流水/作业车间调度（JSSP/FJSSP/RCPSP）工序可视化。<br/>根据 <strong>Numbers Truth</strong> 准则：当前输出无真实 schedule 数组，系统严禁虚构排产基准。
          </div>
        </div>
      `;
      return;
    }

    const rawSched = solution.schedule;
    const mSet = new Set();
    rawSched.forEach(s => {
      if (s.machine != null) mSet.add(Number(s.machine));
    });
    const mSorted = Array.from(mSet).sort((a, b) => a - b);
    const machines = mSorted.map(m => `M${m} 机床/设备`);
    const makespan = Number(solution.metrics?.makespan || Math.max(...rawSched.map(s => s.end || 0)) || 0);

    const ops = rawSched.slice(0, 48).map(s => ({
      m: mSorted.indexOf(Number(s.machine)),
      j: Number(s.job ?? 0),
      s: Number(s.start ?? 0),
      e: Number(s.end ?? 0),
      dur: Number(s.duration ?? (s.end - s.start)),
      name: `工件${s.job ?? 0}-工序${s.task ?? s.op ?? 0}`,
    })).filter(o => o.m >= 0);

    const maxT = Math.max(makespan + 5, 20);
    const startX = 110;
    const plotW = 670;
    const scaleX = plotW / maxT;
    const numM = Math.max(1, machines.length);
    const totalH = Math.max(260, 60 + numM * 34);

    let svg = `<svg class="viz-svg" viewBox="0 0 820 ${totalH}" xmlns="http://www.w3.org/2000/svg">`;
    svg += `<rect width="820" height="${totalH}" fill="#ffffff" rx="10"/>`;

    // Horizontal grid & timeline
    const stepT = maxT > 100 ? (maxT > 300 ? 50 : 20) : 10;
    for (let t = 0; t <= maxT; t += stepT) {
      const x = startX + t * scaleX;
      svg += `<line x1="${x}" y1="20" x2="${x}" y2="${totalH - 45}" stroke="#f1f5f9" stroke-width="1"/>`;
      svg += `<text x="${x}" y="${totalH - 30}" font-size="10" fill="#94a3b8" text-anchor="middle" font-family="var(--mono)">${t}m</text>`;
    }

    // Machine Y rows
    machines.forEach((mLabel, mIdx) => {
      const y = 30 + mIdx * 33;
      svg += `<text x="${startX - 10}" y="${y + 18}" font-size="11" font-weight="600" fill="#475569" text-anchor="end">${esc(mLabel)}</text>`;
      svg += `<line x1="${startX}" y1="${y + 26}" x2="${startX + plotW}" y2="${y + 26}" stroke="#f8fafc" stroke-width="1"/>`;
    });

    // Operation Rectangles with Hover Feedback
    ops.forEach((op, opIdx) => {
      const x = startX + op.s * scaleX;
      const w = Math.max(4, op.dur * scaleX - 2);
      const y = 30 + op.m * 33 + 2;
      const c = colors[op.j % colors.length];
      const desc = `${op.name} · 起止 [${op.s}m -> ${op.e}m] (时长: ${op.dur}m) · 设备: ${machines[op.m] || op.m}`;
      svg += `
        <g class="gantt-bar" data-op-idx="${opIdx}" data-op-desc="${esc(desc)}" tabindex="0">
          <title>${esc(desc)}</title>
          <rect x="${x}" y="${y}" width="${w}" height="22" rx="4" fill="${c}" fill-opacity="0.9" stroke="#ffffff" stroke-width="1.5"/>
          ${w > 32 ? `<text x="${x + w / 2}" y="${y + 14}" font-size="9.5" font-weight="700" fill="#ffffff" text-anchor="middle" pointer-events="none">${esc(op.name.split("-")[0])}</text>` : ''}
        </g>
      `;
    });

    // Makespan marker
    if (makespan > 0) {
      const msX = startX + makespan * scaleX;
      svg += `
        <line x1="${msX}" y1="16" x2="${msX}" y2="${totalH - 42}" stroke="#dc2626" stroke-width="2" stroke-dasharray="4,4"/>
        <rect x="${msX - 52}" y="6" width="104" height="20" rx="4" fill="#fef2f2" stroke="#dc2626" stroke-width="1"/>
        <text x="${msX}" y="20" font-size="9.5" font-weight="700" fill="#dc2626" text-anchor="middle">Makespan = ${makespan}</text>
      `;
    }

    // Legend
    svg += `<g transform="translate(110, ${totalH - 12})">`;
    const numLegend = Math.min(6, Math.max(1, new Set(ops.map(o => o.j)).size));
    for (let j = 0; j < numLegend; j++) {
      const lx = j * 105;
      svg += `
        <rect x="${lx}" y="-6" width="12" height="10" rx="2" fill="${colors[j % colors.length]}"/>
        <text x="${lx + 16}" y="3" font-size="10" fill="#64748b">工件 ${j}</text>
      `;
    }
    svg += `</g></svg>`;

    container.innerHTML = `
      <div style="margin-bottom:12px;font-size:12px;color:#475569;display:flex;justify-content:space-between;align-items:center;flex-wrap:gap:8px">
        <div style="display:flex;align-items:center;gap:8px">
          <span>🏭 <strong>车间排产逐机甘特图</strong> · ${machines.length} 台设备工序时序</span>
          <span style="font-size:10px;background:#ecfdf5;color:#059669;padding:2px 8px;border-radius:6px;font-weight:700">✓ 真实排产数据 (${ops.length} 项工序)</span>
        </div>
        <span style="font-family:var(--mono);color:#059669;font-weight:700">总完工时间 (Cmax): ${makespan}</span>
      </div>
      ${svg}
    `;

    // Attach hover listener for interactive tooltip
    container.querySelectorAll(".gantt-bar").forEach(bar => {
      bar.addEventListener("mouseenter", () => showVizTooltip(bar.getAttribute("data-op-desc") || ""));
      bar.addEventListener("mouseleave", hideVizTooltip);
    });
  }

  function renderRouteMap(container, solution, domain) {
    if (!container) return;
    const hasRoutes = solution && Array.isArray(solution.routes) && solution.routes.length > 0;
    const hasTour = solution && Array.isArray(solution.tour) && solution.tour.length > 0;

    if (!hasRoutes && !hasTour) {
      container.innerHTML = `
        <div class="viz-empty-card" style="padding:42px 20px;text-align:center;background:var(--surface-2);border:1px dashed var(--border);border-radius:12px;margin:10px 0">
          <div style="font-size:32px;margin-bottom:8px">🗺️</div>
          <div style="font-weight:600;font-size:13px;color:#334155">当前算例不含车辆或旅行商路径规划数据</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:6px;max-width:520px;margin-left:auto;margin-right:auto;line-height:1.6">
            路径图专用于车辆路径 (VRP/CVRP) 或旅行商回路 (TSP) 可视化。<br/>根据 <strong>Numbers Truth</strong> 准则：当前输出无 routes 或 tour 路径数据，系统严禁伪造路径拓扑。
          </div>
        </div>
      `;
      return;
    }

    const palette = ["#2563eb", "#059669", "#7c3aed", "#d97706", "#ec4899"];
    const depot = { x: 410, y: 140, name: "场站/起点 0" };

    let normalizedRoutes = [];
    if (hasRoutes) {
      normalizedRoutes = solution.routes;
    } else if (hasTour) {
      normalizedRoutes = [{ route: solution.tour, distance: solution.objective }];
    }

    const nodeSeq = [];
    normalizedRoutes.forEach(r => {
      const arr = Array.isArray(r.route) ? r.route : (Array.isArray(r) ? r : []);
      arr.forEach(n => {
        const sid = String(n);
        if (!nodeSeq.includes(sid)) nodeSeq.push(sid);
      });
    });

    const numNodes = nodeSeq.length;
    const customers = [];
    const radiusX = 270;
    const radiusY = 85;
    nodeSeq.forEach((nid, idx) => {
      const angle = (idx / Math.max(1, numNodes)) * 2 * Math.PI - Math.PI / 2;
      const px = 410 + radiusX * Math.cos(angle);
      const py = 140 + radiusY * Math.sin(angle);
      customers.push({ id: nid, x: px, y: py, name: `站点 ${nid}` });
    });

    const nodeMap = new Map();
    customers.forEach(c => nodeMap.set(String(c.id), c));

    const routes = normalizedRoutes.slice(0, 6).map((r, idx) => {
      const cColor = palette[idx % palette.length];
      const routeArr = Array.isArray(r.route) ? r.route : (Array.isArray(r) ? r : []);
      const routeStops = [depot];
      routeArr.forEach(nid => {
        const pt = nodeMap.get(String(nid));
        if (pt) routeStops.push(pt);
      });
      routeStops.push(depot);
      return {
        id: hasRoutes ? `车队 ${idx + 1}` : "巡检回路",
        color: cColor,
        pts: routeStops,
        dist: r.distance != null ? `${r.distance}` : (solution.objective != null ? `${solution.objective}` : "已规划"),
      };
    });

    let svg = `<svg class="viz-svg" viewBox="0 0 820 280" xmlns="http://www.w3.org/2000/svg">`;
    svg += `<rect width="820" height="280" fill="#ffffff" rx="10"/>`;

    // Background concentric grid
    svg += `<circle cx="410" cy="140" r="110" fill="none" stroke="#f1f5f9" stroke-width="1.5" stroke-dasharray="4,4"/>`;
    svg += `<circle cx="410" cy="140" r="210" fill="none" stroke="#f8fafc" stroke-width="1.5"/>`;

    // Draw route lines
    routes.forEach(route => {
      let pathD = "";
      route.pts.forEach((pt, pIdx) => {
        pathD += (pIdx === 0 ? "M " : " L ") + `${pt.x} ${pt.y}`;
      });
      svg += `<path d="${pathD}" fill="none" stroke="${route.color}" stroke-width="2" stroke-opacity="0.85" stroke-dasharray="6,3"/>`;
    });

    // Draw customer nodes
    customers.forEach(c => {
      const desc = `${c.name} · 拓扑受访节点`;
      svg += `
        <g class="route-node" data-node-desc="${esc(desc)}" tabindex="0" style="cursor:pointer">
          <title>${esc(desc)}</title>
          <circle cx="${c.x}" cy="${c.y}" r="6" fill="#ffffff" stroke="#2563eb" stroke-width="2"/>
          <text x="${c.x}" y="${c.y + 15}" font-size="9" font-family="var(--mono)" font-weight="600" fill="#475569" text-anchor="middle">${esc(c.id)}</text>
        </g>
      `;
    });

    // Draw Depot
    svg += `
      <g style="cursor:pointer">
        <rect x="396" y="126" width="28" height="28" rx="6" fill="#dc2626" stroke="#ffffff" stroke-width="2"/>
        <text x="410" y="144" font-size="11" font-weight="800" fill="#ffffff" text-anchor="middle">★</text>
        <text x="410" y="166" font-size="10" font-weight="700" fill="#dc2626" text-anchor="middle">起点</text>
      </g>
    `;

    svg += `</svg>`;

    const objLabel = solution.objective != null ? `目标耗费/里程: ${solution.objective}` : "路径规划完成";

    container.innerHTML = `
      <div style="margin-bottom:12px;font-size:12px;color:#475569;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <div style="display:flex;align-items:center;gap:8px">
          <span>🗺️ <strong>车辆/巡检路径拓扑图</strong> · ${customers.length} 个受访站点 <span style="font-size:10px;color:#94a3b8">(拓扑序排布)</span></span>
          <span style="font-size:10px;background:#ecfdf5;color:#059669;padding:2px 8px;border-radius:6px;font-weight:700">✓ 真实路径规划数据</span>
        </div>
        <span style="font-family:var(--mono);color:#059669;font-weight:700">${esc(objLabel)}</span>
      </div>
      ${svg}
    `;

    container.querySelectorAll(".route-node").forEach(node => {
      node.addEventListener("mouseenter", () => showVizTooltip(node.getAttribute("data-node-desc") || ""));
      node.addEventListener("mouseleave", hideVizTooltip);
    });
  }

  function renderConvergenceGapCurve(container, solution, domain) {
    if (!container) return;
    const rawGap = solution?.gap_history || solution?.metrics?.gap_history || solution?.meta?.gap_history;

    if (!Array.isArray(rawGap) || rawGap.length < 2) {
      container.innerHTML = `
        <div class="viz-empty-card" style="padding:42px 20px;text-align:center;background:var(--surface-2);border:1px dashed var(--border);border-radius:12px;margin:10px 0">
          <div style="font-size:32px;margin-bottom:8px">📈</div>
          <div style="font-weight:600;font-size:13px;color:#334155">当前求解为单阶段直接交付，无多轮迭代收敛历程</div>
          <div style="font-size:11px;color:#94a3b8;margin-top:6px;max-width:520px;margin-left:auto;margin-right:auto;line-height:1.6">
            根据 <strong>Numbers Truth</strong> 准则：系统绝不伪造虚假收敛曲线与 0.00% 严密闭合结论。<br/>仅当求解器输出真实迭代历程数据（如松弛下界与上界轨迹）时呈现收敛分析。
          </div>
        </div>
      `;
      return;
    }

    const iters = rawGap.map((pt, idx) => ({
      i: pt.i ?? idx,
      ub: Number(pt.ub ?? pt.upper_bound ?? 0),
      lb: Number(pt.lb ?? pt.lower_bound ?? 0),
      gap: Number(pt.gap ?? 0),
    }));

    const startX = 90;
    const plotW = 680;
    const startY = 35;
    const plotH = 190;

    const scaleX = plotW / Math.max(1, iters.length - 1);
    const allVals = iters.flatMap(p => [p.ub, p.lb]).filter(v => !isNaN(v) && v > 0);
    const minVal = allVals.length > 0 ? Math.min(...allVals) * 0.9 : 0;
    const maxVal = allVals.length > 0 ? Math.max(...allVals) * 1.1 : 100;
    const scaleY = plotH / Math.max(1, maxVal - minVal);
    const getY = (val) => startY + plotH - (val - minVal) * scaleY;

    let svg = `<svg class="viz-svg" viewBox="0 0 820 280" xmlns="http://www.w3.org/2000/svg">`;
    svg += `<rect width="820" height="280" fill="#ffffff" rx="10"/>`;

    iters.forEach((pt, idx) => {
      const x = startX + idx * scaleX;
      svg += `<line x1="${x}" y1="${startY}" x2="${x}" y2="${startY + plotH}" stroke="#f8fafc" stroke-width="1"/>`;
      svg += `<text x="${x}" y="${startY + plotH + 18}" font-size="10" fill="#94a3b8" text-anchor="middle" font-family="var(--mono)">Iter ${pt.i}</text>`;
    });

    const ubPath = iters.map((pt, idx) => `${idx === 0 ? "M" : "L"} ${startX + idx * scaleX} ${getY(pt.ub)}`).join(" ");
    svg += `<path d="${ubPath}" fill="none" stroke="#2563eb" stroke-width="2.5"/>`;

    const lbPath = iters.map((pt, idx) => `${idx === 0 ? "M" : "L"} ${startX + idx * scaleX} ${getY(pt.lb)}`).join(" ");
    svg += `<path d="${lbPath}" fill="none" stroke="#7c3aed" stroke-width="2.5" stroke-dasharray="4,4"/>`;

    const last = iters[iters.length - 1];
    const lastX = startX + (iters.length - 1) * scaleX;
    const lastY = getY(last.ub);
    const gapStr = last.gap.toFixed(2);

    svg += `
      <g>
        <rect x="${lastX - 110}" y="${lastY - 32}" width="125" height="22" rx="6" fill="#ecfdf5" stroke="#10b981" stroke-width="1.5"/>
        <text x="${lastX - 48}" y="${lastY - 18}" font-size="10" font-weight="700" fill="#047857" text-anchor="middle">Gap: ${gapStr}%</text>
      </g>
    `;

    svg += `</svg>`;

    container.innerHTML = `
      <div style="margin-bottom:12px;font-size:12px;color:#475569;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <span>📈 <strong>数学下界与启发式上界真实收敛 Gap 曲线</strong></span>
        <span style="font-family:var(--mono);color:#059669;font-weight:700">最终 Gap: ${gapStr}%</span>
      </div>
      ${svg}
    `;
  }

  function renderVisualizations(solution, analysis) {
    const badge = $("vizDomainBadge");
    if (badge) {
      const prof = DOMAIN_SWARM_PROFILES[currentDomainKey] || DOMAIN_SWARM_PROFILES.default;
      badge.textContent = prof.badge || prof.name;
    }

    renderGanttChart($("vizPanelGantt"), solution, currentDomainKey);
    renderRouteMap($("vizPanelRoutes"), solution, currentDomainKey);
    renderConvergenceGapCurve($("vizPanelGap"), solution, currentDomainKey);

    initVizTabsOnce();
  }
}
