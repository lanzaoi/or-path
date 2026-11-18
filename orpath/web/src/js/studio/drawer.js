// Studio Process Watch Drawer (non-blocking side telemetry + sandbox repair status)
let _wdPollTimer = null;
let _wdActiveArtKind = "solution";
let _wdLastArtifacts = null;
let _wdLastSnapshotSlug = "";

function getWatchDrawerSlug() {
  return (
    studioState.lastSolvedSlug ||
    ($("studioSlugInput")?.value || "").trim() ||
    "case-my-problem"
  );
}

function isWatchDrawerOpen() {
  const dr = $("watchDrawer");
  return Boolean(dr && !dr.hidden);
}

function openWatchDrawer() {
  const dr = $("watchDrawer");
  const bd = $("watchDrawerBackdrop");
  const btn = $("btnToggleWatchDrawer");
  if (dr) dr.hidden = false;
  if (bd) bd.hidden = false;
  if (btn) btn.classList.add("on");
  refreshWatchDrawer(true);
  if (!_wdPollTimer) {
    _wdPollTimer = setInterval(() => {
      if (isWatchDrawerOpen()) refreshWatchDrawer(false);
    }, 1500);
  }
}

function closeWatchDrawer() {
  const dr = $("watchDrawer");
  const bd = $("watchDrawerBackdrop");
  const btn = $("btnToggleWatchDrawer");
  if (dr) dr.hidden = true;
  if (bd) bd.hidden = true;
  if (btn) btn.classList.remove("on");
  if (_wdPollTimer) {
    clearInterval(_wdPollTimer);
    _wdPollTimer = null;
  }
}

function toggleWatchDrawer() {
  if (isWatchDrawerOpen()) closeWatchDrawer();
  else openWatchDrawer();
}

async function loadDrawerArtifact(kind) {
  _wdActiveArtKind = kind || "solution";
  document.querySelectorAll("#wdArtTabs [data-wd-art]").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-wd-art") === _wdActiveArtKind);
  });
  const pre = $("wdArtPreview");
  if (!pre) return;
  const slug = getWatchDrawerSlug();
  if (_wdLastArtifacts && _wdLastSnapshotSlug === slug && !_wdLastArtifacts[_wdActiveArtKind]) {
    pre.textContent = `暂无 ${_wdActiveArtKind} 文件（任务 ${slug} 尚未生成该产物或未触发）。`;
    return;
  }
  try {
    const res = await fetch(`/api/artifact?slug=${encodeURIComponent(slug)}&kind=${encodeURIComponent(_wdActiveArtKind)}`);
    const data = await res.json().catch(() => null);
    if (res.ok && data && data.ok && data.content != null) {
      pre.textContent = typeof data.content === "string"
        ? data.content.slice(0, 12000)
        : JSON.stringify(data.content, null, 2).slice(0, 12000);
    } else if (!res.ok || (data && (data.exists === false || data.ok === false))) {
      pre.textContent = `暂无 ${_wdActiveArtKind} 文件（任务 ${slug} 尚未生成该产物或未触发）。`;
    } else {
      pre.textContent = JSON.stringify(data, null, 2).slice(0, 8000);
    }
  } catch (err) {
    pre.textContent = `读取产物失败: ${err.message}`;
  }
}

function renderWatchDrawerSnapshot(snap) {
  if (!snap || typeof snap !== "object") return;
  const slug = snap.slug || getWatchDrawerSlug();
  _wdLastSnapshotSlug = slug;
  _wdLastArtifacts = (snap.artifacts && typeof snap.artifacts === "object") ? snap.artifacts : null;
  if ($("wdSlugTag")) $("wdSlugTag").textContent = slug;

  const cur = snap.current || {};
  const st = String(snap.status || "idle").toLowerCase();
  const errBox = $("wdErrorBox");
  if (errBox) {
    const ep = errorPayload(snap);
    const overallOk = st === "ok" && !ep.human_required;
    if (!overallOk && ep.has_error && ep.last_error) {
      const ex = ep.explain || {};
      if ($("wdErrorTitle")) $("wdErrorTitle").textContent = ex.headline || "运行出现异常";
      if ($("wdErrorDesc")) {
        $("wdErrorDesc").textContent = [ex.what, ex.do || "可点击右上角「重新求解」或调整输入后重试。"].filter(Boolean).join(" ");
      }
      errBox.hidden = false;
    } else {
      errBox.hidden = true;
    }
  }
  const pill = $("wdStatusPill");
  if (pill) {
    pill.className = "wd-status-pill";
    if (st === "running") {
      pill.classList.add("running");
      pill.textContent = "运行中";
    } else if (st === "ok" || st === "completed") {
      pill.classList.add("ok");
      pill.textContent = "已完成";
    } else if (st === "fail" || st === "blocked") {
      pill.classList.add("warn");
      pill.textContent = st === "blocked" ? "待补充数据" : "待自愈";
    } else {
      pill.textContent = statusLabel(st);
    }
  }

  if ($("wdStageText")) {
    const rawStage = cur.node || cur.stage || "idle";
    $("wdStageText").textContent = rawStage === "idle" ? "空闲" : nodeLabel(rawStage);
  }
  const repCount = Number(cur.schema_repair || 0) + Number(cur.validate_repair || 0) + Number(cur.solver_tune || 0);
  if ($("wdRepairCount")) $("wdRepairCount").textContent = `${repCount} 轮`;
  if ($("wdEngineText")) $("wdEngineText").textContent = studioState.runMode === "deep" ? `Deep 4-Agent (${studioState.deepRounds || 5}轮)` : "Fast Single-Agent";

  const evo = snap.evolution;
  const evoSec = $("wdEvolutionSection");
  const evoList = $("wdEvolutionList");
  const evoInc = $("wdEvoIncumbent");
  if (evoSec && evoList) {
    const evoRounds = (evo && Array.isArray(evo.rounds)) ? evo.rounds : [];
    if (!evoRounds.length) {
      evoSec.hidden = true;
      evoList.innerHTML = "";
    } else {
      evoSec.hidden = false;
      const inc = evo.incumbent || {};
      const incObj = inc.objective != null ? Number(inc.objective).toFixed(4) : "—";
      const incRound = inc.round != null ? `R${inc.round}` : "—";
      if (evoInc) {
        evoInc.textContent = `最优基线: ${incObj} (${incRound}) · 目标 ${evo.target_rounds || 5}/${evo.max_rounds || 10} 轮`;
      }
      evoList.innerHTML = evoRounds.map(r => {
        const isPromo = Boolean(r.promoted || r.improved);
        const cls = !r.validation_ok ? "invalid" : (isPromo ? "improved" : "");
        const tag = r.proven_optimal ? "⭐最优" : (!r.validation_ok ? "✗未过检" : (isPromo ? "↑刷新" : "•持平"));
        const objStr = r.objective != null ? Number(r.objective).toFixed(4) : "—";
        const wtStr = r.wall_time_s != null ? `${Number(r.wall_time_s).toFixed(1)}s` : "";
        return `
          <div class="wd-evo-row ${cls}">
            <span><strong>R${esc(String(r.round || ""))}</strong> ${esc(r.strategy_stage || "")}</span>
            <span style="font-family:var(--mono)">${esc(tag)} · obj=${esc(objStr)} · ${esc(wtStr)}</span>
          </div>
        `;
      }).join("");
    }
  }

  const stages = Array.isArray(snap.stages) ? snap.stages : [];
  const sBox = $("wdStagesList");
  if (sBox) {
    if (!stages.length) {
      sBox.innerHTML = `<div class="wd-empty">当前任务尚无过程阶段日志（可在工作台点击「分析并求解」）</div>`;
    } else {
      sBox.innerHTML = stages.slice(-16).map(stItem => {
        const nm = nodeLabel(stItem.node || stItem.stage || "stage");
        const stLbl = statusLabel(stItem.state || stItem.status || "ok");
        const rawStage = String(stItem.stage || "").trim();
        const stageHint = !rawStage
          ? ""
          : (/^\d+$/.test(rawStage) ? `#${rawStage}` : (rawStage === stItem.node ? "" : `→ ${nodeLabel(rawStage)}`));
        const dur = stItem.duration_ms != null ? `${stItem.duration_ms}ms` : "";
        return `
          <div class="wd-stage-row">
            <span><strong>${esc(nm)}</strong> <span style="color:var(--ink-48)">${esc(stageHint)}</span></span>
            <span style="font-family:var(--mono);font-size:10.5px;color:var(--ink-60)">${esc(stLbl)} ${esc(dur)}</span>
          </div>
        `;
      }).join("");
    }
  }

  const events = Array.isArray(snap.events) ? snap.events : [];
  const eBox = $("wdEventsList");
  if (eBox) {
    if (!events.length) {
      eBox.innerHTML = `<div class="wd-empty">暂无沙箱执行事件</div>`;
    } else {
      eBox.innerHTML = events.slice(-18).reverse().map(ev => {
        const actor = ev.agent || ev.node || ev.source || "system";
        let msg = ev.text || ev.summary || ev.detail || ev.kind || JSON.stringify(ev).slice(0, 180);
        const stageM = String(msg).match(/^(stage|agent_start|agent_end)\s+step=(\S+)\s+agent=(\S+)/i);
        if (stageM) {
          const verbMap = { stage: "节点推进", agent_start: "智能体启动", agent_end: "智能体完成" };
          const verb = verbMap[stageM[1].toLowerCase()] || stageM[1];
          msg = `${verb} · ${nodeLabel(stageM[3])} (#${stageM[2]})`;
        }
        const isWarn = /err|fail|retry|repair/i.test(String(ev.kind || "") + " " + msg);
        return `<div class="wd-event-row ${isWarn ? "err" : ""}">[${esc(actor)}] ${esc(msg)}</div>`;
      }).join("");
    }
  }
}

async function refreshWatchDrawer(reloadArtifact) {
  const slug = getWatchDrawerSlug();
  if ($("wdSlugTag")) $("wdSlugTag").textContent = slug;
  try {
    const res = await fetch(`/api/snapshot?slug=${encodeURIComponent(slug)}&thread=${encodeURIComponent(slug)}`);
    const snap = await res.json();
    renderWatchDrawerSnapshot(snap);
  } catch (_) {}
  if (reloadArtifact) {
    loadDrawerArtifact(_wdActiveArtKind);
  }
}

function initWatchDrawer() {
  const btnHeader = $("btnToggleWatchDrawer");
  const btnBottom = $("btnStudioViewInspector");
  const btnClose = $("btnWdClose");
  const bd = $("watchDrawerBackdrop");
  const btnRefresh = $("btnWdRefresh");
  if (btnHeader) btnHeader.addEventListener("click", toggleWatchDrawer);
  if (btnBottom) {
    btnBottom.addEventListener("click", (e) => {
      e.preventDefault();
      openWatchDrawer();
    });
  }
  if (btnClose) btnClose.addEventListener("click", closeWatchDrawer);
  if (bd) bd.addEventListener("click", closeWatchDrawer);
  if (btnRefresh) btnRefresh.addEventListener("click", () => refreshWatchDrawer(true));
  const btnRetry = $("btnWdRetry");
  if (btnRetry) {
    btnRetry.addEventListener("click", async () => {
      if (typeof executeStudioSolve === "function") {
        btnRetry.disabled = true;
        btnRetry.textContent = "求解中…";
        try {
          await executeStudioSolve(null);
          refreshWatchDrawer(true);
        } catch (_) {
        } finally {
          btnRetry.disabled = false;
          btnRetry.textContent = "重新求解";
        }
      }
    });
  }
  document.querySelectorAll("#wdArtTabs [data-wd-art]").forEach(btn => {
    btn.addEventListener("click", () => loadDrawerArtifact(btn.getAttribute("data-wd-art")));
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && isWatchDrawerOpen()) closeWatchDrawer();
  });
}
