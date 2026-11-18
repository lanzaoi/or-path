// --- Studio Analyze ---

async function triggerStudioAnalyze() {
  if (studioState.analyzeAbortController) {
    studioState.analyzeAbortController.abort();
  }
  studioState.analyzeAbortController = new AbortController();
  const signal = studioState.analyzeAbortController.signal;

  const slug = ($("studioSlugInput")?.value || "case-studio").trim();
  const prompt = ($("studioPromptInput")?.value || "").trim();
  const apiKey = ($("studioApiKeyInput")?.value || "").trim();
  const model = $("studioModelSelect")?.value || "deepseek-flash";
  if (typeof resetStudioRunUI === "function") resetStudioRunUI(true);
  const st1 = $("studioStep1Status");
  const errBox = $("studioAnalyzeError");
  if (errBox) { errBox.style.display = "none"; errBox.textContent = ""; }
  if (st1) st1.innerHTML = `<span style="color:var(--blue)">正在上传文件并执行模型诊断…</span>`;
  if ($("btnStudioAnalyze")) { $("btnStudioAnalyze").disabled = true; $("btnStudioAnalyze").textContent = "正在分析…"; }
  const btnQuick = $("btnStudioQuickAnalyze");
  if (btnQuick) btnQuick.disabled = true;
  setPipelineStage("analyze", "诊断中", "结构化探针与题面解析");

  try {
    if (studioState.loadedFiles.length > 0) {
      const { data: impJson } = await orpathIntakeImport(
        { mode: "folder", slug, files: studioState.loadedFiles },
        signal
      );
      if (signal.aborted) return;
      if (!impJson.ok) throw new Error(impJson.error || "文件夹上传失败");
    }

    let anaJson = null;
    for (let attempt = 0; attempt < 3; attempt++) {
      if (signal.aborted) return;
      const anaRes = await fetch("/api/studio/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug, prompt, api_key: apiKey, model, run_mode: studioState.runMode }),
        signal,
      });
      if (signal.aborted) return;
      anaJson = await anaRes.json();
      if (signal.aborted) return;
      const errText = String(anaJson.error || "");
      const rText = String(anaJson.analysis?.thinking_meta?.reasoning_text || "");
        if ((anaRes.status === 429 || errText.includes("429") || rText.includes("HTTP 429") || rText.includes("限流")) && attempt < 2) {
        if (st1) st1.innerHTML = `<span style="color:var(--warn)">请求受限 (429)，正在重试 (${attempt + 1}/2)…</span>`;
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

    studioState.currentAnalysis = anaJson.analysis;
    const isLive = Boolean(studioState.currentAnalysis?.thinking_meta?.live_thinking);
    renderStudioAnalysisCard(studioState.currentAnalysis);
    if (st1) {
      st1.innerHTML = isLive
        ? '<span style="color:#047857">诊断完成，开始求解…</span>'
        : '<span style="color:var(--ink-60)">离线探针诊断完成，开始求解…</span>';
    }
    await executeStudioSolve(signal);
    if (!signal.aborted && st1) {
      st1.innerHTML = '<span style="color:#047857">分析与求解完成</span>';
    }
  } catch (err) {
    if (err.name === "AbortError" || signal.aborted) return;
    setPipelineStage("error", "研判受阻", err.message);
    if (st1) st1.innerHTML = '<span style="color:#b91c1c">运行失败</span>';
    if (errBox) {
      errBox.style.display = "block";
      errBox.innerHTML = `<strong>运行失败：</strong> ${esc(err.message)} <br/><span style="font-size:11px;opacity:0.85">请检查文件格式或 API 配置后重试。</span>`;
    }
  } finally {
    if ($("btnStudioAnalyze")) { $("btnStudioAnalyze").disabled = false; $("btnStudioAnalyze").textContent = "分析并求解"; }
    if (btnQuick) btnQuick.disabled = false;
  }
}


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
      badge.style.background = "#ecfdf5";
      badge.style.color = "#047857";
      const modelUsed = String(meta.model_used || "");
      const modelLabel = /spark/i.test(modelUsed)
        ? "Spark X2.6"
        : (modelUsed && modelUsed !== "deepseek-reasoner" ? modelUsed : "DeepSeek-R1");
      badge.textContent = `${modelLabel} · 实时推理`;
      if (promptBanner) promptBanner.style.display = "none";
    } else {
      const mSel = $("studioModelSelect")?.value || "deepseek-flash";
      badge.style.background = "var(--surface-2)";
      badge.style.color = "var(--ink-60)";
      badge.textContent = mSel === "offline"
        ? "离线规则诊断"
        : "本地规则诊断";
      if (promptBanner) {
        promptBanner.style.display = (!studioState.serverEnvConfigured && mSel !== "offline") ? "block" : "none";
      }
    }
  }

  const diag = ana.domain_diagnosis || {};
  const diagBanner = $("studioDiagnosisBanner");
  if (diagBanner) {
    diagBanner.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:8px">
        <strong style="font-size:14px;color:var(--ink)">识别领域：${esc(diag.domain_name || diag.problem_class)}</strong>
        <span style="font-size:11px;font-family:var(--mono);background:var(--surface-2);color:var(--ink);border:1px solid var(--border);padding:2px 8px;border-radius:5px;font-weight:600">推荐求解：${esc(diag.recommended_algorithm)}</span>
      </div>
      <p style="margin:0;font-size:12px;line-height:1.55;color:var(--ink-60)">${esc(diag.rationale || '')}</p>
    `;
  }

  const kBanner = $("studioKnowledgeBanner");
  const kHits = ana.knowledge_hits || (meta && meta.knowledge_hits) || [];
  const kSkills = ana.matched_skills || (meta && meta.matched_skills) || [];
  const kLit = ana.literature_anchors || (meta && meta.literature_anchors) || [];
  if (kBanner) {
    kBanner.style.display = "block";
    const renderHitRow = (kh, checked = true) => `
      <label style="display:flex;align-items:flex-start;gap:8px;background:#fff;border:1px solid var(--border);border-radius:6px;padding:7px 10px;font-size:11px;cursor:pointer">
        <input type="checkbox" class="studio-pin-kb" ${checked ? "checked" : ""}
          data-kb-id="${esc(kh.chunk_id || kh.id || '')}"
          data-kb-title="${esc(kh.title || kh.chunk_id || '')}"
          data-kb-kind="chunk"
          data-kb-snippet="${esc((kh.snippet || '').slice(0, 180))}"
          style="margin-top:2px;cursor:pointer" />
        <div style="flex:1;min-width:0">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;gap:6px">
            <span style="font-weight:600;color:var(--ink)">${esc(kh.title || kh.chunk_id)}</span>
            <span style="font-size:10px;color:var(--ink-48);font-family:var(--mono)">score: ${esc(kh.score ?? '-')}</span>
          </div>
          <div style="color:var(--ink-48);line-height:1.4;font-size:10.5px">${esc(kh.snippet || '')}</div>
        </div>
      </label>
    `;

    kBanner.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:6px">
        <strong style="font-size:12.5px;color:var(--ink)">建模方法与参考先验（勾选条目将参与建模与论文引用）</strong>
        <span style="font-size:10px;font-family:var(--mono);background:var(--surface-2);color:var(--ink-60);border:1px solid var(--border);padding:2px 7px;border-radius:4px">Hybrid BM25 + bge-m3</span>
      </div>
      ${kSkills.filter(sk => !["or-numbers-truth", "or-verify", "or-paper-sop", "or-reviewer"].includes(String(sk.id || ""))).length > 0 ? `
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px">
          ${kSkills.filter(sk => !["or-numbers-truth", "or-verify", "or-paper-sop", "or-reviewer"].includes(String(sk.id || ""))).map((sk, idx) => `
            <label style="display:inline-flex;align-items:center;gap:5px;background:#ffffff;border:1px solid var(--border-strong);color:var(--ink-80);padding:2px 8px;border-radius:5px;font-size:11px;cursor:pointer">
              <input type="checkbox" class="studio-pin-kb" ${idx < 2 ? "checked" : ""}
                data-kb-id="${esc(sk.id)}"
                data-kb-title="${esc(sk.label || sk.id)}"
                data-kb-kind="skill"
                data-kb-snippet="" />
              ${esc(sk.label || sk.id)}
            </label>
          `).join("")}
        </div>
      ` : ""}
      <div id="studioKbItemsList" style="display:flex;flex-direction:column;gap:6px;margin-bottom:8px">
        ${kHits.map((kh, idx) => renderHitRow(kh, idx < 2)).join("")}
      </div>
      ${kLit.length > 0 ? `
        <div style="background:#ffffff;border:1px dashed var(--border-strong);border-radius:6px;padding:6px 10px;margin-bottom:8px;font-size:10.5px;color:var(--ink-60);line-height:1.5">
          <strong>匹配文献：</strong>
          ${kLit.map(l => `<span style="margin-right:10px">${esc(l.cite_label)} <em>${esc(l.title)}</em> (${esc(l.venue)})</span>`).join("")}
        </div>
      ` : ""}
      <div style="display:flex;gap:6px;align-items:center">
        <input type="text" id="studioKbSearchInput" placeholder="检索知识库方法、模型或割平面（如 cutting plane subtour, column generation）…"
          style="flex:1;height:30px;padding:0 10px;border:1px solid var(--border-strong);border-radius:6px;font-size:11.5px;background:#fff;outline:none" />
        <button type="button" class="wb-btn" id="btnStudioKbSearch" style="height:30px;padding:0 12px;font-size:11.5px">检索并添加</button>
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
        if (kbBtn) { kbBtn.disabled = false; kbBtn.textContent = "检索并添加"; }
      }
    };
    if (kbBtn) kbBtn.addEventListener("click", doKbSearch);
    if (kbInp) kbInp.addEventListener("keydown", (ev) => { if (ev.key === "Enter") { ev.preventDefault(); doKbSearch(); } });
  }

  const algoList = $("studioAlgoList");
  if (algoList) {
    algoList.innerHTML = (diag.algorithm_comparison || []).map(al => `
      <div class="studio-algo-item" style="border:1px solid ${al.recommended ? 'var(--blue)' : 'var(--border)'};background:${al.recommended ? '#f8faff' : '#fafafa'};">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
          <strong style="font-size:12.5px;color:var(--ink)">${esc(al.name)}</strong>
          ${al.recommended ? '<span style="font-size:10.5px;background:#eff6ff;color:var(--blue);border:1px solid #bfdbfe;font-weight:600;padding:1px 7px;border-radius:5px">推荐</span>' : ''}
        </div>
        <div style="font-size:11.5px;color:var(--ink-60);line-height:1.5">
          <div><span style="color:#047857;font-weight:600">优势：</span>${esc(al.pros || '')}</div>
          <div><span style="color:#b45309;font-weight:600">局限：</span>${esc(al.cons || '')}</div>
        </div>
      </div>
    `).join("");
  }

  const dataList = $("studioDataList");
  const dataCol = $("studioDataCol");
  const cmpGrid = $("studioCompareGrid");
  const matchedVars = ana.data_alignment?.matched_variables || [];
  if (dataCol && cmpGrid) {
    const showDataCol = matchedVars.length > 0;
    dataCol.style.display = showDataCol ? "block" : "none";
    cmpGrid.style.gridTemplateColumns = showDataCol ? "1fr 1fr" : "1fr";
  }
  if (dataList) {
    dataList.innerHTML = matchedVars.map(mv => `
      <div class="studio-data-item">
        <div>
          <strong style="font-size:12.5px;color:var(--ink)">${esc(mv.name)}</strong>
          <div style="font-size:11px;color:var(--ink-48);margin-top:2px">${esc(mv.source)} · ${esc(mv.details)}</div>
        </div>
        <span style="font-size:10.5px;font-family:var(--mono);background:#ecfdf5;color:#047857;border:1px solid #a7f3d0;padding:2px 7px;border-radius:5px;font-weight:600">${esc(mv.status)}</span>
      </div>
    `).join("");
  }

  const thinkingContent = $("studioThinkingContent");
  if (thinkingContent) {
    const cleaned = String(meta.reasoning_text || "无思考日志")
      .replace(/[\u{1F300}-\u{1FAFF}]/gu, "")
      .replace(/`([^`]+)`/g, "$1");
    thinkingContent.textContent = cleaned;
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
  studioState.domainKey = normalizeDomainKey(diag.problem_class || diag.domain_name);
  setPipelineStage("plan", "策略就绪", "推荐策略与参数已锁定");
}

function initStudioAnalyze() {
  const btnAnalyze = $("btnStudioAnalyze");
  if (btnAnalyze) btnAnalyze.addEventListener("click", triggerStudioAnalyze);
  if ($("btnStudioQuickAnalyze")) $("btnStudioQuickAnalyze").addEventListener("click", triggerStudioAnalyze);
}
