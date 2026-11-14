// Watch Problem Workbench 5-tab viewer & artifact preview modal
function renderProblemWorkbench(s) {
  const pv = (s && s.problem_view) || {};
  const titleEl = $("wbTitle");
  const pillsEl = $("wbPills");
  const bodyEl = $("wbBody");
  if (!titleEl || !bodyEl) return;

  if (!pv.has_problem) {
    titleEl.textContent = "当前任务暂无题面信息 (" + (s.slug || "test") + ")";
    pillsEl.innerHTML = `<span class="wb-pill">未导入题面</span>`;
    bodyEl.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 12px;background:#fff;border:1px dashed var(--surface-2);border-radius:10px">
        <div>
          <div style="font-size:13px;font-weight:700;color:var(--ink)">尚未加载题面或当前 Slug 无题面资产</div>
          <div style="font-size:12px;color:var(--ink-48);margin-top:3px">点击右侧「📥 导入/切换题目」可一键加载全部内置工业运筹赛题（如 2026 校赛 B 题异形圆管下料、M2 多联骨牌排样、CVRP 等），或上传 PDF/图片/文本题面。</div>
        </div>
        <button type="button" class="wb-btn primary" id="wbEmptyImportBtn" style="height:34px;padding:0 16px">📥 立即导入 / 选择赛题</button>
      </div>`;
    const b = $("wbEmptyImportBtn");
    if (b) b.addEventListener("click", openIntakeModal);
    return;
  }

  titleEl.textContent = pv.title || s.slug || "运筹优化问题";
  const pills = [];
  if (pv.problem_class) pills.push(`<span class="wb-pill blue">类别: ${esc(pv.problem_class)}</span>`);
  if (pv.ocr_backend && pv.ocr_backend !== "none") pills.push(`<span class="wb-pill">来源: ${esc(pv.ocr_backend)}</span>`);
  const subs = pv.subproblems || [];
  if (subs.length) pills.push(`<span class="wb-pill">${subs.length} 个子问</span>`);
  const sol = pv.solution_summary || {};
  if (sol.exists && sol.objective != null) {
    pills.push(`<span class="wb-pill ok">目标值: ${esc(sol.objective)} (${esc(sol.status || "OK")})</span>`);
  } else if (sol.exists && sol.status === "BLOCKED") {
    pills.push(`<span class="wb-pill" style="background:#fee2e2;color:#991b1b;border-color:#fca5a5">求解受阻: BLOCKED (拒绝假优)</span>`);
  }
  const val = pv.validate_summary || {};
  if (val.exists) {
    pills.push(`<span class="wb-pill ${val.ok ? "ok" : ""}">校验: ${val.passed_checks}/${val.total_checks} 通过</span>`);
  }
  pillsEl.innerHTML = pills.join("");

  if (currentWbTab === "overview") {
    let subHtml = "";
    if (subs.length) {
      subHtml = `<div class="wb-sub-list">` + subs.map((sp) => {
        const delivArr = Array.isArray(sp.must_deliver) ? sp.must_deliver : (sp.must_deliver ? [sp.must_deliver] : []);
        const deliv = delivArr.length ? `<div class="qdeliv">交付表: ${esc(delivArr.join(", "))}</div>` : "";
        return `<div class="wb-sub-item">
          <div><span class="qid">${esc(sp.id || "Q")}</span><span class="qtitle">${esc(sp.title || "")}</span></div>
          ${sp.notes ? `<div class="qnotes">${esc(sp.notes)}</div>` : ""}
          ${deliv}
        </div>`;
      }).join("") + `</div>`;
    } else {
      subHtml = `<div class="wb-pre" style="max-height:170px">${esc(pv.brief_text || "无子问题拆分，请查看「题面原文」标签页。")}</div>`;
    }

    const assets = pv.data_assets || [];
    const assetTags = assets.slice(0, 12).map((a) =>
      `<span class="wb-pill" style="font-family:var(--mono);font-size:10.5px">${esc((a.path || "").split("/").pop())} (${esc(a.kind)})</span>`
    ).join(" ");
    const totalAssets = Number(pv.data_assets_total);
    const moreAssets = (!isNaN(totalAssets) && totalAssets > 12) ? `<span class="wb-pill">+${totalAssets - 12} 项</span>` : "";

    const delivs = Array.isArray(pv.deliverables) ? pv.deliverables.join(", ") : (pv.deliverables ? String(pv.deliverables) : "");
    bodyEl.innerHTML = `
      <div class="wb-grid">
        <div style="display:grid;gap:8px">
          <div class="wb-card">
            <h4><span>🎯 优化目标与硬约束</span><span>${esc(pv.problem_id || s.slug)}</span></h4>
            <div style="font-size:12px;line-height:1.5">
              <div><strong>优化目标：</strong>${esc(pv.objectives_text || "见题面原文与数学模型 Schema")}</div>
              <div style="margin-top:4px"><strong>约束条件：</strong>${esc(pv.constraints_text || "见题面原文与数学模型 Schema")}</div>
              ${delivs ? `<div style="margin-top:4px"><strong>交付产物：</strong><span style="font-family:var(--mono);color:var(--blue)">${esc(delivs)}</span></div>` : ""}
            </div>
          </div>
          <div class="wb-card">
            <h4><span>📦 数据附件与题面源 (${!isNaN(totalAssets) ? totalAssets : assets.length} 项)</span></h4>
            <div style="display:flex;gap:4px;flex-wrap:wrap">
              ${assetTags || `<span style="font-size:11.5px;color:var(--ink-48)">内置标准算例参数 (${esc(pv.brief_path || "fixture")})</span>`}
              ${moreAssets}
            </div>
          </div>
        </div>
        <div class="wb-card">
          <h4><span>📑 题目子问拆解 (${subs.length || 1} 问)</span><button type="button" class="art-view-btn" id="wbJumpBrief">查看完整题面原文 →</button></h4>
          ${subHtml}
        </div>
      </div>`;
    const jb = $("wbJumpBrief");
    if (jb) jb.addEventListener("click", () => switchWbTab("brief"));
    return;
  }

  if (currentWbTab === "brief") {
    bodyEl.innerHTML = `
      <div class="wb-card">
        <h4>
          <span>📄 题面完整原文 / Problem Brief (${esc(pv.brief_path || "内存")})</span>
          ${pv.has_intake ? `<button type="button" class="art-view-btn" id="wbOpenIntakeJson">查看结构化 intake.json</button>` : ""}
        </h4>
        <pre class="wb-pre" style="max-height:230px">${esc(pv.brief_text || "暂无题面原文")}</pre>
      </div>`;
    const btnIj = $("wbOpenIntakeJson");
    if (btnIj) btnIj.addEventListener("click", () => openArtifactModal("intake", "题面结构化 intake.json"));
    return;
  }

  if (currentWbTab === "schema") {
    const sc = pv.schema_summary || {};
    if (!sc.exists) {
      bodyEl.innerHTML = `<div class="wb-card"><div class="empty">当前任务尚未生成数学模型 Schema（请点击右上角「🚀 一键求解此题」运行流水线）</div></div>`;
      return;
    }
    const vars = sc.variables ? JSON.stringify(sc.variables, null, 2) : "—";
    const cList = (sc.constraints || []).map((c, i) => `<li><code>C${i + 1}:</code> ${esc(typeof c === "string" ? c : JSON.stringify(c))}</li>`).join("");
    bodyEl.innerHTML = `
      <div class="wb-grid">
        <div class="wb-card">
          <h4><span>📐 模型元信息与决策变量</span><button type="button" class="art-view-btn" id="wbOpenSchemaJson">查看完整 schema.json</button></h4>
          <div style="font-size:12px;line-height:1.6;margin-bottom:6px">
            <div><strong>问题标识：</strong><code>${esc(sc.problem_id)}</code> · <strong>类别：</strong><code>${esc(sc.problem_class)}</code> · <strong>方向：</strong><code>${esc(sc.sense)}</code></div>
            <div><strong>目标函数表达式：</strong><code>${esc(sc.objective || "—")}</code></div>
          </div>
          <pre class="wb-pre" style="max-height:130px">${esc(vars)}</pre>
        </div>
        <div class="wb-card">
          <h4><span>🔒 形式化约束方程 (${(sc.constraints || []).length} 条)</span><span style="color:var(--ok)">✓ 门禁已核验无答案泄漏</span></h4>
          <ul style="padding-left:18px;font-size:12px;line-height:1.6;max-height:185px;overflow-y:auto">${cList || "<li>默认域约束</li>"}</ul>
        </div>
      </div>`;
    const bSc = $("wbOpenSchemaJson");
    if (bSc) bSc.addEventListener("click", () => openArtifactModal("schema", "数学模型 schema.json"));
    return;
  }

  if (currentWbTab === "solution") {
    if (!sol.exists) {
      bodyEl.innerHTML = `<div class="wb-card"><div class="empty">尚未生成求解结果（请点击「🚀 一键求解此题」运行求解器与校验器）</div></div>`;
      return;
    }
    let detailHtml = "";
    const qs = sol.questions || [];
    if (qs.length) {
      detailHtml = qs.map((q) => {
        const rows = (q.stocks_preview || []).map((st) => {
          const u = Number(st.utilization);
          const hasU = st.utilization != null && !isNaN(u);
          const pct = hasU ? (u * 100).toFixed(2) : "—";
          const w = hasU ? Math.min(100, Math.max(0, u * 100)) : 0;
          const pc = Number(st.parts_count);
          const partsText = (!isNaN(pc) && pc > 12) ? " …(" + pc + "件)" : "";
          return `<tr>
            <td><strong>${esc(st.id)}</strong></td>
            <td>${esc(st.stock_length_mm)} mm</td>
            <td>${esc(st.used_length_mm)} mm</td>
            <td>${esc(st.leftover_mm)} mm</td>
            <td><span class="wb-bar-meter"><i style="width:${w}%"></i></span>${pct}%</td>
            <td>${esc(st.switches)}</td>
            <td style="font-family:var(--mono);font-size:10.5px">${esc((st.sequence_head || []).join(", "))}${partsText}</td>
          </tr>`;
        }).join("");
        return `<div style="margin-bottom:10px">
          <div style="font-size:12px;font-weight:700;margin-bottom:4px;color:var(--blue)">
            ${esc(q.id)} 排产方案 · 母材总长: ${esc(q.total_stock_length_mm ?? "—")} mm
            ${q.total_cocut_gain_mm != null ? ` · 共切省料: ${esc(q.total_cocut_gain_mm)} mm` : ""}
            ${q.total_switches != null ? ` · 切换次数: ${esc(q.total_switches)}` : ""}
            ${q.stocks_count ? ` · 母材根数: ${esc(q.stocks_count)}` : ""}
          </div>
          ${rows ? `<table class="wb-table"><thead><tr><th>母材</th><th>标准长</th><th>已用长</th><th>余料</th><th>利用率</th><th>切换</th><th>加工序列预览</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
        </div>`;
      }).join("");
    } else if (Array.isArray(sol.path)) {
      detailHtml = `<div style="font-size:12.5px"><strong>最优路径序列：</strong><code style="color:var(--blue);font-size:13px">${esc(sol.path.join(" → "))}</code></div>`;
    } else if (sol.path) {
      detailHtml = `<div style="font-size:12.5px"><strong>最优路径序列：</strong><code style="color:var(--blue);font-size:13px">${esc(String(sol.path))}</code></div>`;
    } else if (Array.isArray(sol.tour)) {
      detailHtml = `<div style="font-size:12.5px"><strong>巡检回路序列：</strong><code style="color:var(--blue);font-size:13px">${esc(sol.tour.join(" → "))}</code></div>`;
    } else if (sol.tour) {
      detailHtml = `<div style="font-size:12.5px"><strong>巡检回路序列：</strong><code style="color:var(--blue);font-size:13px">${esc(String(sol.tour))}</code></div>`;
    } else if (Array.isArray(sol.routes)) {
      detailHtml = `<div style="font-size:12px"><strong>多车配送路径 (${sol.routes.length} 辆车)：</strong>` +
        sol.routes.map((r, idx) => `<div style="margin-top:3px"><code>车辆 #${idx + 1}:</code> ${esc(Array.isArray(r) ? r.join(" → ") : JSON.stringify(r))}</div>`).join("") + `</div>`;
    } else if (sol.placements) {
      const count = Array.isArray(sol.placements) ? sol.placements.length : Object.keys(sol.placements).length;
      detailHtml = `<div style="font-size:12px"><strong>已排样多联骨牌块数：</strong>${count} 块</div>`;
    }

    const checksHtml = (val.checks || []).map((c) =>
      `<div style="display:flex;justify-content:space-between;font-size:11.5px;padding:3px 0;border-bottom:1px dashed var(--border)">
        <span><strong style="color:${c.ok ? "var(--ok)" : "var(--fail)"}">${c.ok ? "✓" : "✗"}</strong> <code>${esc(c.name)}</code></span>
        <span style="color:var(--ink-48);font-family:var(--mono)">${c.got != null ? `实测=${esc(c.got)}` : ""}${c.detail ? ` (${esc(c.detail)})` : ""}</span>
      </div>`
    ).join("");

    const isBlocked = sol.status === "BLOCKED";
    bodyEl.innerHTML = `
      <div class="wb-kpis">
        <div class="wb-kpi"><div class="k">求解状态</div><div class="v ${isBlocked ? "fail" : "ok"}">${esc(sol.status || "—")}</div></div>
        <div class="wb-kpi"><div class="k">确定性目标值 (Objective)</div><div class="v ${isBlocked ? "" : "blue"}">${isBlocked ? "无 (BLOCKED)" : esc(sol.objective ?? "—")}</div></div>
        <div class="wb-kpi"><div class="k">求解器引擎</div><div class="v">${esc(sol.solver || "—")}</div></div>
        <div class="wb-kpi"><div class="k">独立物理校验</div><div class="v ${val.ok ? "ok" : (isBlocked ? "fail" : "")}">${val.exists ? `${val.passed_checks} / ${val.total_checks} 通过` : "—"}</div></div>
      </div>
      <div class="wb-grid">
        <div class="wb-card" style="max-height:190px;overflow-y:auto">
          <h4><span>📊 方案明细与排产表</span><button type="button" class="art-view-btn" id="wbOpenSolJson">查看完整 solution.json</button></h4>
          ${isBlocked ? `<div class="empty" style="color:var(--fail)">平台规范拦截：当前领域无专用适配器，系统拒绝绑定无关金标伪造结果。</div>` : (detailHtml || `<div class="empty">请点击右上角查看完整 JSON</div>`)}
        </div>
        <div class="wb-card" style="max-height:190px;overflow-y:auto">
          <h4><span>🛡️ 确定性重算与物理约束核验项</span><button type="button" class="art-view-btn" id="wbOpenValJson">查看完整 validate.json</button></h4>
          ${checksHtml || `<div class="empty">暂无校验明细</div>`}
        </div>
      </div>`;
    const bSol = $("wbOpenSolJson");
    if (bSol) bSol.addEventListener("click", () => openArtifactModal("solution", "求解结果 solution.json"));
    const bVal = $("wbOpenValJson");
    if (bVal) bVal.addEventListener("click", () => openArtifactModal("validate", "物理校验报告 validate.json"));
    return;
  }

  if (currentWbTab === "paper") {
    bodyEl.innerHTML = `
      <div class="wb-card">
        <h4>
          <span>📝 工业技术报告 / 论文文稿 (${esc(pv.paper_path || "未生成")})</span>
          ${pv.paper_path ? `<button type="button" class="art-view-btn" id="wbOpenPaperFull">全屏阅读报告</button>` : ""}
        </h4>
        <pre class="wb-pre" style="max-height:225px">${esc(pv.paper_preview || "当前任务尚未生成技术报告（待流水线运行至 draft_paper / provenance 站后自动产出）")}</pre>
      </div>`;
    const bP = $("wbOpenPaperFull");
    if (bP) bP.addEventListener("click", () => openArtifactModal("paper", "工业技术报告 / 论文全稿"));
  }
}

function switchWbTab(tab) {
  currentWbTab = tab;
  document.querySelectorAll("#wbTabs [data-wb-tab]").forEach((b) => {
    b.classList.toggle("active", b.getAttribute("data-wb-tab") === tab);
  });
  if (wbCollapsed) {
    wbCollapsed = false;
    $("problemWorkbench").classList.remove("collapsed");
    $("wbBtnCollapse").textContent = "收起 ▲";
    $("btnToggleWorkbench").classList.add("on");
  }
  if (lastSnap) renderProblemWorkbench(lastSnap);
}

async function openArtifactModal(kind, title) {
  if (artifactAbortController) {
    artifactAbortController.abort();
  }
  artifactAbortController = new AbortController();
  const signal = artifactAbortController.signal;
  const slug = ($("slug")?.value || "").trim() || "test";
  if ($("artModalTitle")) $("artModalTitle").textContent = (title || kind) + " · " + slug;
  if ($("artModalPath")) $("artModalPath").textContent = "加载中…";
  if ($("artModalContent")) $("artModalContent").textContent = "正在读取磁盘文件…";
  const modal = $("artifactModal");
  if (modal) {
    modal.classList.add("show");
    if ($("btnCloseArtifact")) $("btnCloseArtifact").focus();
  }
  try {
    const r = await fetch(`/api/artifact?slug=${encodeURIComponent(slug)}&kind=${encodeURIComponent(kind)}`, { cache: "no-store", signal });
    if (signal.aborted) return;
    const j = await r.json();
    if (signal.aborted) return;
    if (!r.ok || !j.ok) {
      if ($("artModalPath")) $("artModalPath").textContent = "读取失败";
      if ($("artModalContent")) $("artModalContent").textContent = j.error || "文件不存在";
      return;
    }
    if ($("artModalPath")) $("artModalPath").textContent = "路径: " + (j.path || "");
    if ($("artModalContent")) $("artModalContent").textContent = j.content || "";
  } catch (err) {
    if (err.name === "AbortError" || signal.aborted) return;
    if ($("artModalContent")) $("artModalContent").textContent = "请求异常: " + err.message;
  }
}
