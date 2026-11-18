// --- Studio Solve (auto-chained after Analyze, or re-run with tweaked params) ---

function clearDeepPollTimer() {
  if (studioState.deepPollTimer) {
    clearInterval(studioState.deepPollTimer);
    studioState.deepPollTimer = null;
  }
}

function pollDeepJob(slug, signal) {
  clearDeepPollTimer();
  const st2 = $("studioStep2Status");
  const startedAt = Date.now();
  const maxWaitMs = 660000;
  return new Promise((resolve, reject) => {
    let busy = false;
    const stopWith = (fn, arg) => {
      clearDeepPollTimer();
      fn(arg);
    };
    if (signal) {
      if (signal.aborted) {
        stopWith(reject, new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener("abort", () => {
        stopWith(reject, new DOMException("Aborted", "AbortError"));
      }, { once: true });
    }
    const tick = async () => {
      if (busy || (signal && signal.aborted)) return;
      if (Date.now() - startedAt > maxWaitMs) {
        stopWith(reject, new Error("深度多智能体协作超时 (480s)，请查看过程监视抽屉日志。"));
        return;
      }
      busy = true;
      try {
        const [jobRes, snapRes] = await Promise.all([
          fetch(`/api/studio/job?slug=${encodeURIComponent(slug)}`, { signal }),
          fetch(`/api/snapshot?slug=${encodeURIComponent(slug)}&thread=${encodeURIComponent(slug)}`, { signal }).catch(() => null),
        ]);
        if (snapRes && snapRes.ok) {
          const snap = await snapRes.json().catch(() => null);
          if (snap) {
            if (typeof updateDeepPipelineFromSnapshot === "function") updateDeepPipelineFromSnapshot(snap);
            if (st2 && snap.current && snap.current.node) {
              const elapsed = Math.round((Date.now() - startedAt) / 1000);
              st2.innerHTML = `<span style="color:var(--blue)">多智能体运行中 · 当前节点：<strong>${esc(nodeLabel(snap.current.node))}</strong> (${elapsed}s)…</span>`;
            }
          }
        }
        if (typeof isWatchDrawerOpen === "function" && isWatchDrawerOpen() && typeof refreshWatchDrawer === "function") {
          refreshWatchDrawer(false);
        }
        if (!jobRes.ok) return;
        const jData = await jobRes.json();
        const job = jData && jData.job;
        if (!job) return;
        if (job.status === "done") {
          stopWith(resolve, job.result || {});
        } else if (job.status === "error") {
          const errMsg = (job.result && job.result.error) || "深度模式后端执行失败";
          stopWith(reject, new Error(errMsg));
        }
      } catch (e) {
        if (e && e.name === "AbortError") stopWith(reject, e);
      } finally {
        busy = false;
      }
    };
    studioState.deepPollTimer = setInterval(tick, 1500);
    tick();
  });
}

async function executeStudioSolve(externalSignal) {
  clearDeepPollTimer();
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

  const isDeep = studioState.runMode === "deep";
  const deepRounds = isDeep ? ([3, 5, 8].includes(Number(studioState.deepRounds)) ? Number(studioState.deepRounds) : 5) : 1;
  if (st2) {
    st2.innerHTML = `<span style="color:var(--blue)">正在调用${isDeep ? "多智能体与" : ""}确定性求解器并进行独立验算…</span>`;
  }
  if ($("btnStudioConfirmSolve")) {
    $("btnStudioConfirmSolve").disabled = true;
    $("btnStudioConfirmSolve").textContent = "求解中…";
  }
  setPipelineStage(isDeep ? "analyze" : "solve", isDeep ? "启动中" : "求解中", "执行确定性算子求解与验算");

  const savedKey = ($("studioApiKeyInput")?.value || localStorage.getItem("orpath_deepseek_key") || "").trim();
  const savedModel = ($("studioModelSelect")?.value || localStorage.getItem("orpath_model_name") || "deepseek-flash").trim();
  const isOffline = savedModel === "offline" || (savedKey.length <= 5 && !studioState.serverEnvConfigured);

  const confTimeout = setTimeout(() => confController.abort(), isDeep ? Math.max(1800000, deepRounds * 450000) : 480000);

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
        deep_rounds: deepRounds,
        async_run: isDeep,
        skip_paper: !isDeep,
        api_key: savedKey,
        model: savedModel,
        timeout: isOffline ? 3.0 : (isDeep ? Math.max(1200.0, deepRounds * 450.0) : 180.0),
      }),
      signal: confController.signal,
    });
    if (confController.signal.aborted) return;
    let confJson = await confRes.json();
    if (confRes.status === 202 && confJson && confJson.async_started) {
      confJson = await pollDeepJob(slug, confController.signal);
    }
    if (!confJson || !confJson.ok) throw new Error((confJson && confJson.error) || "求解失败");

    const confBlocked = (
      String(confJson.status || "").toUpperCase() === "BLOCKED" ||
      String(confJson.solution?.status || "").toUpperCase() === "BLOCKED" ||
      Boolean(confJson.solution?.meta?.blocked)
    );
    if (st2) {
      st2.innerHTML = confBlocked
        ? '<span style="color:#b91c1c">求解已诚实阻断（未通过数值条件）</span>'
        : '<span style="color:#047857">求解与独立验算已完成</span>';
    }
    renderStudioResultCard(slug, confJson);
  } catch (err) {
    clearDeepPollTimer();
    if (err.name === "AbortError" && externalSignal && externalSignal.aborted) return;
    const errMsg = err.name === "AbortError"
      ? `求解等待超时 (${isDeep ? "680s" : "480s"})，可打开过程监视查看日志。`
      : err.message;
    setPipelineStage("error", "求解受阻", errMsg);
    if (st2) st2.innerHTML = '<span style="color:#b91c1c">求解受阻</span>';
    if (errBox) {
      errBox.style.display = "block";
      errBox.innerHTML = `<strong>求解失败：</strong> ${esc(errMsg)} <br/><span style="font-size:11px;opacity:0.85">请检查题面参数或在上方补充说明。</span>`;
    }
    throw err;
  } finally {
    clearDeepPollTimer();
    clearTimeout(confTimeout);
    if (externalSignal) externalSignal.removeEventListener("abort", onExternalAbort);
    if ($("btnStudioConfirmSolve")) {
      $("btnStudioConfirmSolve").disabled = false;
      $("btnStudioConfirmSolve").textContent = "按新参数重算";
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
      banner.style.background = "#fef2f2";
      banner.style.borderColor = "#fecaca";
    } else {
      banner.style.background = "#fafafa";
      banner.style.borderColor = "var(--border)";
    }
  }
  if ($("studioStep3Sub")) {
    if (isBlocked) {
      $("studioStep3Sub").textContent = "已阻断 · 未输出虚假数值结果";
    } else {
      const srcTag = dataSource ? ` · 来源: ${dataSource === "fixture" ? "fixture 回放" : "实算"}` : "";
      $("studioStep3Sub").textContent = `数值已独立验算${srcTag}`;
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
      $("studioHeadline").textContent = summary.headline || (res.status === "COMPLETED" ? "求解已完成" : "求解状态待确认");
    }
  }

  const fallbackObj = (!isBlocked && res.solution && res.solution.objective != null)
    ? (isProvenOpt ? `严格最优目标值: ${res.solution.objective}` : `可行解目标值: ${res.solution.objective} (未证最优)`)
    : (isBlocked ? "无解/求解受阻" : "等待求解产物");

  if ($("studioObjective")) {
    const objText = isBlocked ? fallbackObj : (summary.objective_str || fallbackObj);
    const optBadge = isBlocked
      ? '<span style="font-size:11px;background:#fef2f2;color:#b91c1c;padding:2px 8px;border-radius:5px;font-weight:600;margin-left:10px;vertical-align:middle;border:1px solid #fecaca">已阻断</span>'
      : (isProvenOpt
        ? '<span style="font-size:11px;background:#ecfdf5;color:#047857;padding:2px 8px;border-radius:5px;font-weight:600;margin-left:10px;vertical-align:middle;border:1px solid #a7f3d0">全局最优</span>'
        : (res.solution && res.solution.objective != null
          ? '<span style="font-size:11px;background:#fffbeb;color:#b45309;padding:2px 8px;border-radius:5px;font-weight:500;margin-left:10px;vertical-align:middle;border:1px solid #fde68a">可行解（未证最优）</span>'
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
      const srcLine = dataSource ? `数据来源: ${dataSource === "fixture" ? "基准算例" : "实算求解"} · ` : "";
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
    btnGenPaper.textContent = "生成学术论文";
  }
  if (paperStatus) {
    if (isBlocked) {
      paperStatus.textContent = "求解受阻，未生成学术论文";
    } else if (paperReady) {
      paperStatus.textContent = "学术论文已生成";
    } else {
      paperStatus.textContent = "快速模式已跳过写稿（可按需生成论文）";
    }
  }

  const viewInsp = $("btnStudioViewInspector");
  if (viewInsp && viewInsp.tagName === "A") {
    const q = encodeURIComponent(slug);
    viewInsp.href = `/?slug=${q}&thread=${q}`;
  }

  renderVisualizations(res.solution);
}


function initStudioResult() {
  const btnConfirm = $("btnStudioConfirmSolve");
  if (btnConfirm) btnConfirm.addEventListener("click", () => executeStudioSolve(null).catch(() => {}));
  const viewInsp = $("btnStudioViewInspector");
  if (viewInsp && typeof openWatchDrawer === "function") {
    viewInsp.addEventListener("click", () => openWatchDrawer());
  }
  const btnGenPaper = $("btnStudioGeneratePaper");
  if (btnGenPaper) {
    btnGenPaper.addEventListener("click", async () => {
      const slug = studioState.lastSolvedSlug || ($("studioSlugInput")?.value || "case-studio").trim();
      const paperStatus = $("studioPaperStatus");
      const dlPaper = $("dlPaper");
      const savedKey = ($("studioApiKeyInput")?.value || localStorage.getItem("orpath_deepseek_key") || "").trim();
      const savedModel = ($("studioModelSelect")?.value || localStorage.getItem("orpath_model_name") || "deepseek-flash").trim();
  
      btnGenPaper.disabled = true;
      btnGenPaper.textContent = "正在生成学术论文…";
      if (paperStatus) paperStatus.textContent = "正在执行写稿与 R1/R2 数值校验…";

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
          paperStatus.textContent = `学术论文已生成 (${pj.paper_quality || "ready"})`;
        }
        if (typeof isWatchDrawerOpen === "function" && isWatchDrawerOpen() && typeof refreshWatchDrawer === "function") {
          refreshWatchDrawer(true);
        }
      } catch (err) {
        if (paperStatus) paperStatus.textContent = `论文生成受阻: ${err.message}`;
        btnGenPaper.disabled = false;
        btnGenPaper.textContent = "生成学术论文";
      }
    });
  }
}
