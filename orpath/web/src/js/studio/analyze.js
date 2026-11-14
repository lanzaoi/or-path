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
  const model = $("studioModelSelect")?.value || "deepseek-reasoner";
  const st1 = $("studioStep1Status");
  const errBox = $("studioAnalyzeError");
  if (errBox) { errBox.style.display = "none"; errBox.textContent = ""; }
  if (st1) st1.innerHTML = `<span style="color:var(--blue)">⏳ 正在上传附件并由数据探针与深度模型研判中…</span>`;
  if ($("btnStudioAnalyze")) { $("btnStudioAnalyze").disabled = true; $("btnStudioAnalyze").textContent = "⏳ 正在研判中…"; }
  const btnQuick = $("btnStudioQuickAnalyze");
  if (btnQuick) btnQuick.disabled = true;
  setPipelineStage("analyze", "研判中…", "结构化探针与题面解析");

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

    studioState.currentAnalysis = anaJson.analysis;
    const isLive = Boolean(studioState.currentAnalysis?.thinking_meta?.live_thinking);
    renderStudioAnalysisCard(studioState.currentAnalysis);
    if (st1) {
      st1.innerHTML = isLive
        ? '<span style="color:#059669">✅ 深度研判完成，正在自动直通真算…</span>'
        : '<span style="color:#d97706">✅ 离线探针研判完成，正在自动直通真算…</span>';
    }
    await executeStudioSolve(signal);
    if (!signal.aborted && st1) {
      st1.innerHTML = '<span style="color:#059669">✅ 研判与自动求解已闭环完成</span>';
    }
  } catch (err) {
    if (err.name === "AbortError" || signal.aborted) return;
    if (st1) st1.innerHTML = '<span style="color:#dc2626">❌ 研判或求解受阻</span>';
    if (errBox) {
      errBox.style.display = "block";
      errBox.innerHTML = `<strong>⚠️ 运行失败：</strong> ${esc(err.message)} <br/><span style="font-size:11px;opacity:0.8">请检查文件格式或 API 配置后重试。</span>`;
    }
  } finally {
    if ($("btnStudioAnalyze")) { $("btnStudioAnalyze").disabled = false; $("btnStudioAnalyze").textContent = "🚀 一键分析并求解"; }
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
  studioState.domainKey = normalizeDomainKey(diag.problem_class || diag.domain_name);
  setPipelineStage("plan", "策略就绪", "推荐策略与参数已锁定");
}

function initStudioAnalyze() {
  const btnAnalyze = $("btnStudioAnalyze");
  if (btnAnalyze) btnAnalyze.addEventListener("click", triggerStudioAnalyze);
  if ($("btnStudioQuickAnalyze")) $("btnStudioQuickAnalyze").addEventListener("click", triggerStudioAnalyze);
}
