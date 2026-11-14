// Watch Intake Modal & problem catalog loader
async function openIntakeModal() {
  const modal = $("intakeModal");
  if (modal) {
    modal.classList.add("show");
    if ($("btnCloseIntake")) $("btnCloseIntake").focus();
  }
  await loadProblemsCatalog();
}

async function loadProblemsCatalog() {
  const grid = $("presetGrid");
  const casesBar = $("imCasesBar");
  if (!grid) return;
  try {
    const r = await fetch("/api/problems", { cache: "no-store" });
    const j = await r.json();
    if (!j.ok) return;
    const cases = j.cases || [];
    if (cases.length && casesBar) {
      casesBar.innerHTML = `<div style="font-weight:700;margin-bottom:5px;color:var(--ink-80)">🗂️ 当前工作区已有案例（点击一键切换查看）：</div>` +
        `<div style="display:flex;gap:6px;flex-wrap:wrap">` +
        cases.map((c) => {
          const objStr = c.objective != null ? ` · obj=${esc(c.objective)}` : "";
          return `<button type="button" class="wb-btn" data-switch-slug="${esc(c.slug)}" title="${esc(c.title)}">
            <strong>${esc(c.slug)}</strong>
            <span style="color:var(--ink-48);font-size:11px">(${esc(c.problem_class || "case")}${objStr})</span>
          </button>`;
        }).join("") + `</div>`;
      casesBar.querySelectorAll("[data-switch-slug]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const sl = btn.getAttribute("data-switch-slug");
          if ($("slug")) $("slug").value = sl;
          if ($("thread")) $("thread").value = sl;
          if ($("intakeModal")) $("intakeModal").classList.remove("show");
          applyControls();
        });
      });
    }
    const presets = j.presets || [];
    grid.innerHTML = presets.map((p) => `
      <div class="preset-card">
        <div class="p-title">${esc(p.title)}</div>
        <div class="p-tags">${(p.tags || []).map((t) => `<span class="p-tag">${esc(t)}</span>`).join("")}</div>
        <div class="p-desc">${esc(p.desc)}</div>
        <div class="p-acts">
          <button type="button" class="wb-btn primary" data-preset-import="${esc(p.id)}" style="flex:1;justify-content:center">👁️ 一键导入并查看</button>
          ${p.can_solve === false || p.intake_only
            ? `<span class="wb-pill" style="display:inline-flex;align-items:center;padding:0 8px">仅审题演示</span>`
            : `<button type="button" class="wb-btn success" data-preset-run="${esc(p.id)}" title="导入后立即启动求解流水线">⚡ 导入并求解</button>`}
        </div>
      </div>
    `).join("");
    grid.querySelectorAll("[data-preset-import]").forEach((btn) => {
      btn.addEventListener("click", () => importPreset(btn.getAttribute("data-preset-import"), false));
    });
    grid.querySelectorAll("[data-preset-run]").forEach((btn) => {
      btn.addEventListener("click", () => importPreset(btn.getAttribute("data-preset-run"), true));
    });
  } catch (err) {
    grid.innerHTML = `<div class="empty">加载题库失败: ${esc(err.message)}</div>`;
  }
}

async function applyImportedCase(j, autoRun, hintObj) {
  if ($("slug")) $("slug").value = j.slug;
  if ($("thread")) $("thread").value = j.thread_id || j.slug;
  if ($("intakeModal")) $("intakeModal").classList.remove("show");
  switchWbTab("overview");
  applyControls();
  if (autoRun) {
    await runCurrentProblem(hintObj);
  }
}

async function importPreset(presetId, autoRun) {
  try {
    const { ok, data: j } = await orpathIntakeImport({ mode: "preset", preset_id: presetId });
    if (!ok || !j.ok) {
      showToast("导入失败: " + (j.error || "unknown"), "error");
      return;
    }
    await applyImportedCase(j, autoRun, j.preset);
  } catch (err) {
    showToast("请求异常: " + err.message, "error");
  }
}

async function handleFileUpload(autoRun) {
  const statusEl = $("upStatus");
  if (!selectedUploadFile) {
    if (statusEl) statusEl.textContent = "请先选择或拖拽一个题面文件";
    return;
  }
  if (selectedUploadFile.size > 25 * 1024 * 1024) {
    if (statusEl) statusEl.textContent = "文件过大，单文件上限 25MB";
    showToast("题面文件过大 (超过 25MB)", "warn");
    return;
  }
  if (statusEl) statusEl.textContent = "正在上传并执行 OCR 与结构化审题…";
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const rawRes = reader.result || "";
      const b64 = rawRes.includes(",") ? rawRes.split(",")[1] : rawRes;
      const customSlug = ($("upSlug")?.value || "").trim();
      const { ok, data: j } = await orpathIntakeImport({
        mode: "upload",
        slug: customSlug,
        file_name: selectedUploadFile.name,
        file_base64: b64,
      });
      if (!ok || !j.ok) {
        if (statusEl) statusEl.textContent = "导入失败: " + (j.error || "unknown");
        return;
      }
      if (statusEl) statusEl.textContent = "✓ 识别成功！已生成 " + j.slug;
      await applyImportedCase(j, autoRun, j.domain_guess);
    } catch (err) {
      if (statusEl) statusEl.textContent = "上传异常: " + err.message;
    }
  };
  reader.readAsDataURL(selectedUploadFile);
}

async function handleTextImport(autoRun) {
  const statusEl = $("txtStatus");
  const rawText = ($("txtRaw")?.value || "").trim();
  const title = ($("txtTitle")?.value || "").trim();
  const customSlug = ($("txtSlug")?.value || "").trim() || "case-custom";
  if (!rawText) {
    if (statusEl) statusEl.textContent = "请先输入或粘贴题面正文";
    return;
  }
  if (statusEl) statusEl.textContent = "正在解析子问题与约束…";
  try {
    const { ok, data: j } = await orpathIntakeImport({
      mode: "text",
      slug: customSlug,
      title,
      raw_text: rawText,
    });
    if (!ok || !j.ok) {
      if (statusEl) statusEl.textContent = "解析失败: " + (j.error || "unknown");
      return;
    }
    if (statusEl) statusEl.textContent = "✓ 解析完成！";
    await applyImportedCase(j, autoRun, j.domain_guess);
  } catch (err) {
    if (statusEl) statusEl.textContent = "请求异常: " + err.message;
  }
}

async function runCurrentProblem(hintObj) {
  const slug = ($("slug").value || "").trim() || "test";
  const btn = $("wbBtnRun");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ 正在启动求解流水线…";
  }
  try {
    const pv = (lastSnap && lastSnap.problem_view) || {};
    const payload = {
      slug,
      thread_id: ($("thread").value || "").trim() || slug,
      problem_id: (hintObj && hintObj.problem_id) || pv.problem_id || "",
      problem_class: (hintObj && hintObj.problem_class) || pv.problem_class || "",
      solve_mode: ($("dlgMode") && $("dlgMode").value) || (hintObj && hintObj.solve_mode) || "",
    };
    const r = await fetch("/api/intake/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const j = await r.json();
    if (!r.ok || !j.ok) {
      lastFp = null;
      await fetchSnapshot(true);
      switchWbTab("solution");
      showToast("【求解拦截 / BLOCKED】 " + (j.error || "启动失败"), "warn");
      return;
    }
    lastFp = null;
    setTimeout(() => fetchSnapshot(true), 400);
  } catch (err) {
    showToast("启动异常: " + err.message, "error");
  } finally {
    setTimeout(() => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "🚀 一键求解此题";
      }
    }, 1500);
  }
}

function initIntakeModalControls() {
  const on = (id, event, handler) => {
    const el = $(id);
    if (el) el.addEventListener(event, handler);
  };
  on("btnOpenIntake", "click", openIntakeModal);
  on("wbBtnImport", "click", openIntakeModal);
  on("wbBtnRun", "click", () => runCurrentProblem());
  on("btnCloseIntake", "click", () => { if ($("intakeModal")) $("intakeModal").classList.remove("show"); });
  on("btnCloseArtifact", "click", () => { if ($("artifactModal")) $("artifactModal").classList.remove("show"); });
  // Close modals on backdrop click
  ["intakeModal", "artifactModal"].forEach((mid) => {
    const m = $(mid);
    if (m) {
      m.addEventListener("click", (ev) => {
        if (ev.target === m) m.classList.remove("show");
      });
    }
  });

  // Intake modal tabs
  document.querySelectorAll("#intakeModalTabs [data-im-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-im-tab");
      document.querySelectorAll("#intakeModalTabs [data-im-tab]").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-im-tab") === tab);
      });
      $("imTabPresets").hidden = tab !== "presets";
      $("imTabUpload").hidden = tab !== "upload";
      $("imTabText").hidden = tab !== "text";
    });
  });

  // File upload / drag-and-drop
  const dz = $("upDropzone");
  const fi = $("upFileInput");
  if (dz && fi) {
    dz.addEventListener("click", () => fi.click());
    fi.addEventListener("change", () => {
      if (fi.files && fi.files[0]) {
        selectedUploadFile = fi.files[0];
        $("upFileLabel").textContent = "已选择文件: " + selectedUploadFile.name + " (" + Math.round(selectedUploadFile.size / 1024) + " KB)";
      }
    });
    dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("dragover"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      dz.classList.remove("dragover");
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
        selectedUploadFile = e.dataTransfer.files[0];
        $("upFileLabel").textContent = "已拖拽文件: " + selectedUploadFile.name + " (" + Math.round(selectedUploadFile.size / 1024) + " KB)";
      }
    });
  }
  if ($("btnDoUpload")) $("btnDoUpload").addEventListener("click", () => handleFileUpload(false));
  if ($("btnDoUploadAndRun")) $("btnDoUploadAndRun").addEventListener("click", () => handleFileUpload(true));
  if ($("btnDoTextImport")) $("btnDoTextImport").addEventListener("click", () => handleTextImport(false));
  if ($("btnDoTextAndRun")) $("btnDoTextAndRun").addEventListener("click", () => handleTextImport(true));
  if ($("btnFillSampleText")) {
    $("btnFillSampleText").addEventListener("click", () => {
      $("txtTitle").value = "车间多批次异形管材激光下料与余料优化问题";
      $("txtSlug").value = "case-sample-tube";
      $("txtRaw").value = [
        "某高端装备制造车间使用激光切管机加工 10 种异形圆管构件，标准母材可选长度为 9m、10m、11m、12m（单位统一按 mm 计）。",
        "",
        "问题一：每种工件各需加工 50 件，请根据三维点云几何数据计算各工件轴向占用长度，并在组合选用 4 种标准母材的条件下设计定长下料方案，使母材总长度最小，结果写入 result1.xlsx。",
        "",
        "问题二：考虑相邻工件端部 LL/LR/RL/RR 四种拼接方式的共切效应，计算共切省料矩阵，并在保持问题一母材分配不变的前提下优化单根母材内加工顺序与切换次数，结果写入 result2.xlsx。",
        "",
        "问题三：综合考虑共切收益与换刀切换次数，重新制定全局下料方案；剩余长度不小于 200mm 的余料可入库复用，结果写入 result3.xlsx。",
        "",
        "问题四：针对 3 个连续生产批次的动态订单需求，优先调用前序批次余料，使三批次消耗的新标准母材总长度最小，结果写入 result4.xlsx。",
        "",
        "约束条件：切割位置非负，禁止几何干涉，单根母材总占用长度不超过所选母材标准长度。",
        "主目标：最小化所选标准母材总长度；次目标：最大化共切收益；再次目标：最小化同批工件切换次数。"
      ].join("\n");
    });
  }
}
