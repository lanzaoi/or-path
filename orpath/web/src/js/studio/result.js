// --- Studio Solve (auto-chained after Analyze, or re-run with tweaked params) ---

async function executeStudioSolve(externalSignal) {
  if (studioState.confirmAbortController) {
    studioState.confirmAbortController.abort();
  }
  studioState.confirmAbortController = new AbortController();
  const confController = studioState.confirmAbortController;
  const onExternalAbort = () => confController.abort();
  if (externalSignal) {
    if (externalSignal.aborted) {
      confController.abort();
      return;
    }
    externalSignal.addEventListener("abort", onExternalAbort, { once: true });
  }

  const slug = ($("studioSlugInput")?.value || "case-studio").trim();
  const extraPrompt = ($("studioExtraPrompt")?.value || "").trim();
  const st2 = $("studioStep2Status");
  const errBox = $("studioConfirmError");
  if (errBox) { errBox.style.display = "none"; errBox.textContent = ""; }

  const selectedOptions = {};
  if (studioState.currentAnalysis && studioState.currentAnalysis.clarification_questions) {
    studioState.currentAnalysis.clarification_questions.forEach(q => {
      const checked = document.querySelector(`input[name="${CSS.escape(String(q.id))}"]:checked`);
      if (checked) selectedOptions[q.id] = checked.value;
    });
  }

  if (st2) st2.innerHTML = `<span style="color:var(--blue)">⏳ 正在调用${studioState.runMode === "deep" ? "多智能体与" : ""}真实求解器，在物理门禁中严格验算…</span>`;
  if ($("btnStudioConfirmSolve")) {
    $("btnStudioConfirmSolve").disabled = true;
    $("btnStudioConfirmSolve").textContent = "⏳ 求解中…";
  }
  setPipelineStage("solve", "真算中…", "执行确定性算子求解与验算");

  const savedKey = ($("studioApiKeyInput")?.value || localStorage.getItem("orpath_deepseek_key") || "").trim();
  const savedModel = ($("studioModelSelect")?.value || localStorage.getItem("orpath_model_name") || "spark-x2.6").trim();
  const isOffline = savedModel === "offline" || !savedKey;

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
        run_mode: studioState.runMode,
        skip_paper: studioState.runMode === "fast",
        api_key: savedKey,
        model: savedModel,
        timeout: isOffline ? 3.0 : 60.0,
      }),
      signal: confController.signal,
    });
    if (confController.signal.aborted) return;
    const confJson = await confRes.json();
    if (!confJson.ok) throw new Error(confJson.error || "求解失败");

    const confBlocked = (
      String(confJson.status || "").toUpperCase() === "BLOCKED" ||
      String(confJson.solution?.status || "").toUpperCase() === "BLOCKED" ||
      Boolean(confJson.solution?.meta?.blocked)
    );
    if (st2) {
      st2.innerHTML = confBlocked
        ? '<span style="color:#b91c1c">⛔ 求解已诚实阻断（未通过数值条件）</span>'
        : '<span style="color:#059669">✅ 求解与严格验算已完成</span>';
    }
    renderStudioResultCard(slug, confJson);
  } catch (err) {
    if (err.name === "AbortError" && externalSignal && externalSignal.aborted) return;
    if (st2) st2.innerHTML = '<span style="color:#dc2626">❌ 求解受阻</span>';
    if (errBox) {
      errBox.style.display = "block";
      const errMsg = err.name === "AbortError" ? "求解等待超时 (130s)，请检查模型响应或降低求解规模。" : err.message;
      errBox.innerHTML = `<strong>⚠️ 求解失败：</strong> ${esc(errMsg)} <br/><span style="font-size:11px;opacity:0.8">请检查题面参数或在高级选项中补充说明。</span>`;
    }
  } finally {
    clearTimeout(confTimeout);
    if (externalSignal) externalSignal.removeEventListener("abort", onExternalAbort);
    if ($("btnStudioConfirmSolve")) {
      $("btnStudioConfirmSolve").disabled = false;
      $("btnStudioConfirmSolve").textContent = "🔄 应用参数微调并重算";
    }
  }
}


function renderStudioResultCard(slug, res) {
  const card = $("studioResultCard");
  if (!card) return;
  scrollStudioToCard(card);
  studioState.lastSolvedSlug = slug;

  const summary = res.plain_language_summary || {};
  const isBlocked = (
    String(res.status || "").toUpperCase() === "BLOCKED" ||
    String(res.solution?.status || "").toUpperCase() === "BLOCKED" ||
    Boolean(res.solution?.meta?.blocked)
  );
  setPipelineStage(
    isBlocked ? "blocked" : "done",
    isBlocked ? "已阻断" : "已完成 ✓",
    isBlocked ? "触发诚实阻断门禁" : "物理与数理门禁全量通过"
  );
  card.classList.toggle("is-blocked", isBlocked);
  const blockedReason = (
    res.blocked_reason ||
    res.reason ||
    res.solution?.meta?.reason ||
    "缺少可执行的结构化算例或匹配领域适配器，系统已诚实阻断求解。"
  );
  const dataSource = res.data_source || res.solution?.meta?.data_source || "";

  const banner = $("studioResultBanner");
  if (banner) {
    if (isBlocked) {
      banner.style.background = "rgba(239,68,68,0.08)";
      banner.style.borderColor = "rgba(239,68,68,0.35)";
    } else {
      banner.style.background = "rgba(16,185,129,0.08)";
      banner.style.borderColor = "rgba(16,185,129,0.25)";
    }
  }
  if ($("studioStep3Sub")) {
    if (isBlocked) {
      $("studioStep3Sub").textContent = "诚实阻断 · 未执行虚假数值求解";
    } else {
      const srcTag = dataSource ? ` · 数据来源: ${dataSource === "fixture" ? "fixture 回放" : "case 实算"}` : "";
      $("studioStep3Sub").textContent = `纯真数字 · 数学验算合格${srcTag}`;
    }
  }

  const isProvenOpt = !isBlocked && Boolean(
    res.proven_optimal ??
    res.solution?.proven_optimal ??
    res.solution?.meta?.proven_optimal ??
    summary.proven_optimal
  );

  if ($("studioHeadline")) {
    if (isBlocked) {
      $("studioHeadline").textContent = "求解已诚实阻断";
    } else {
      $("studioHeadline").textContent = summary.headline || (res.status === "COMPLETED" ? "运筹问题已成功求解" : "求解状态待确认");
    }
  }

  const fallbackObj = (!isBlocked && res.solution && res.solution.objective != null)
    ? (isProvenOpt ? `严格最优目标值: ${res.solution.objective}` : `可行解目标值: ${res.solution.objective} (未证最优)`)
    : (isBlocked ? "无解/求解受阻" : "等待求解产物");

  if ($("studioObjective")) {
    const objText = isBlocked ? fallbackObj : (summary.objective_str || fallbackObj);
    const optBadge = isBlocked
      ? '<span style="font-size:11px;background:#fef2f2;color:#b91c1c;padding:3px 8px;border-radius:12px;font-weight:700;margin-left:10px;vertical-align:middle;border:1px solid #fecaca">⛔ 已诚实阻断</span>'
      : (isProvenOpt
        ? '<span style="font-size:11px;background:#ecfdf5;color:#047857;padding:3px 8px;border-radius:12px;font-weight:700;margin-left:10px;vertical-align:middle;border:1px solid #a7f3d0">★ 严格全局最优</span>'
        : (res.solution && res.solution.objective != null
          ? '<span style="font-size:11px;background:#fffbeb;color:#b45309;padding:3px 8px;border-radius:12px;font-weight:600;margin-left:10px;vertical-align:middle;border:1px solid #fde68a">⚡ 可行解 (未证最优)</span>'
          : ''));
    $("studioObjective").innerHTML = `${esc(objText)} ${optBadge}`;
  }

  if ($("studioValidation")) {
    $("studioValidation").textContent = isBlocked
      ? "求解受阻，未通过数值求解"
      : (summary.validation_status || (res.status === "COMPLETED" ? "数理门禁校验合格" : "校验中或待完成"));
  }
  if ($("studioSolutionDetail")) {
    if (isBlocked) {
      const gaps = Array.isArray(res.gap_list) && res.gap_list.length
        ? `（缺口项: ${res.gap_list.join("；")}）`
        : "";
      $("studioSolutionDetail").textContent = `${blockedReason}${gaps}`;
    } else {
      const srcLine = dataSource ? `[data_source=${dataSource}] ` : "";
      $("studioSolutionDetail").textContent = `${srcLine}${summary.solution_detail || ""}`;
    }
  }

  const dlSol = $("dlSolution");
  if (dlSol) dlSol.href = `/api/artifact/download?slug=${encodeURIComponent(slug)}&kind=solution`;
  const dlVal = $("dlValidation");
  if (dlVal) dlVal.href = `/api/artifact/download?slug=${encodeURIComponent(slug)}&kind=validate`;
  const dlPaper = $("dlPaper");
  const paperReady = !isBlocked && Boolean(res.paper_generated);
  if (dlPaper) {
    dlPaper.href = `/api/artifact/download?slug=${encodeURIComponent(slug)}&kind=paper`;
    dlPaper.hidden = !paperReady;
  }
  const dlAna = $("dlAnalysis");
  if (dlAna) dlAna.href = `/api/artifact/download?slug=${encodeURIComponent(slug)}&kind=analysis`;

  const btnGenPaper = $("btnStudioGeneratePaper");
  const paperStatus = $("studioPaperStatus");
  if (btnGenPaper) {
    btnGenPaper.hidden = isBlocked || paperReady;
    btnGenPaper.disabled = false;
    btnGenPaper.textContent = "📑 按需生成完整学术论文";
  }
  if (paperStatus) {
    if (isBlocked) {
      paperStatus.textContent = "求解受阻，未生成学术论文";
    } else if (paperReady) {
      paperStatus.textContent = "✅ 完整学术论文已生成";
    } else {
      paperStatus.textContent = "快速模式已跳过写稿（数值已校验，可按需生成论文）";
    }
  }

  const viewInsp = $("btnStudioViewInspector");
  if (viewInsp) {
    const q = encodeURIComponent(slug);
    viewInsp.href = `/?slug=${q}&thread=${q}`;
  }

  renderVisualizations(res.solution);
}


function initStudioResult() {
  const btnConfirm = $("btnStudioConfirmSolve");
  if (btnConfirm) btnConfirm.addEventListener("click", () => executeStudioSolve(null));
  const btnGenPaper = $("btnStudioGeneratePaper");
  if (btnGenPaper) {
    btnGenPaper.addEventListener("click", async () => {
      const slug = studioState.lastSolvedSlug || ($("studioSlugInput")?.value || "case-studio").trim();
      const paperStatus = $("studioPaperStatus");
      const dlPaper = $("dlPaper");
      const savedKey = ($("studioApiKeyInput")?.value || localStorage.getItem("orpath_deepseek_key") || "").trim();
      const savedModel = ($("studioModelSelect")?.value || localStorage.getItem("orpath_model_name") || "spark-x2.6").trim();
  
      btnGenPaper.disabled = true;
      btnGenPaper.textContent = "⏳ 正在生成学术论文与审稿打包…";
      if (paperStatus) paperStatus.textContent = "正在调用写稿与 R1/R2 数字校验…";
  
      try {
        const pr = await fetch("/api/studio/paper", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            slug,
            api_key: savedKey,
            model: savedModel,
          }),
        });
        const pj = await pr.json();
        if (!pr.ok || !pj.paper_generated) {
          throw new Error(pj.error || pj.paper_degraded_reason || "论文生成失败");
        }
        if (dlPaper) {
          dlPaper.href = `/api/artifact/download?slug=${encodeURIComponent(slug)}&kind=paper`;
          dlPaper.hidden = false;
        }
        btnGenPaper.hidden = true;
        if (paperStatus) {
          paperStatus.textContent = `✅ 学术论文已生成 (${pj.paper_quality || "ready"})`;
        }
      } catch (err) {
        if (paperStatus) paperStatus.textContent = `❌ 论文生成受阻: ${err.message}`;
        btnGenPaper.disabled = false;
        btnGenPaper.textContent = "📑 按需生成完整学术论文";
      }
    });
  }
}
