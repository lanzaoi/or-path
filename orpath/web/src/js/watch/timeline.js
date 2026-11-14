// Watch timeline: swimlane, stage detail, dispatch tree, thinking & event stream
function renderSwim(s) {
  const box = $("swim");
  if (!box) return;
  const stages = s.stages || [];
  if (!stages.length) {
    box.innerHTML = `<span class="empty" style="padding:0">暂无阶段</span>`;
    return;
  }
  let view = stages;
  if (stages.length > 24) view = stages.slice(-24);
  box.innerHTML = view.map((st) => {
    const stt = st.state || "idle";
    const active = selectedStageSeq === st.seq ? " active" : "";
    const errish = (st.last_error || st.state === "fail" || st.human_required) ? " fail" : "";
    return `<button type="button" class="cell ${esc(stt)}${active}${errish}" data-seq="${esc(st.seq)}" title="${esc(st.node)} ${esc(st.stage || "")} ${esc(st.last_error || "")}">
      <span class="sq">${String(st.seq).padStart(3,"0")}</span>
      <span class="nm">${esc(NODE_ZH[st.node] || st.node)}</span>
    </button>`;
  }).join("");
  box.querySelectorAll(".cell").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedStageSeq = Number(btn.dataset.seq);
      followTail = false;
      if ($("btnFollow")) $("btnFollow").classList.remove("on");
      renderSwim(lastSnap);
      renderStages(lastSnap);
    });
  });
  if (followTail && ((s.poll && s.poll.sources_fresh) || s.status === "running")) {
    const rail = $("rail");
    if (rail) rail.scrollLeft = rail.scrollWidth;
  }
}

function renderStageDetail(s) {
  const box = $("stageDetail");
  if (!box) return;
  const stages = s.stages || [];
  const st = stages.find((x) => x.seq === selectedStageSeq);
  if (!st) {
    box.classList.remove("show");
    box.innerHTML = "";
    return;
  }
  const err = (st.last_error || "").trim();
  box.classList.add("show");
  box.innerHTML = `
    <div><span class="k">已选</span> #${esc(st.seq)} <strong>${esc(nodeLabel(st.node))}</strong> · ${esc(st.stage || "")}
      · ${esc(statusLabel(st.state || ""))}${st.human_required ? " · 需人工" : ""}</div>
    ${err ? `<div class="k" style="margin-top:4px">本阶段错误</div><pre id="stageErrText">${esc(err)}</pre>
      <button type="button" id="stageErrCopy" style="margin-top:6px">复制阶段错误</button>` : `<div class="k" style="margin-top:4px">本阶段无错误信息</div>`}
  `;
  const btn = document.getElementById("stageErrCopy");
  if (btn) {
    btn.addEventListener("click", async () => {
      const ok = await copyToClipboard(err);
      if (ok) {
        btn.textContent = "已复制";
        setTimeout(() => { btn.textContent = "复制阶段错误"; }, 1000);
      }
    });
  }
}

function renderStages(s) {
  const box = $("stages");
  const stages = s.stages || [];
  if (!stages.length) {
    box.innerHTML = `<div class="empty">暂无阶段 — ${esc((s.honesty && s.honesty.messages || []).join("; ") || "尚无产品跑次")}</div>`;
    renderStageDetail(s);
    return;
  }
  box.innerHTML = stages.map((st) => {
    const active = selectedStageSeq === st.seq ? " active" : "";
    const run = st.state === "running" ? " running" : "";
    const hasErr = (st.last_error || st.state === "fail" || st.human_required) ? " has-err" : "";
    const errHint = (st.last_error || "").trim()
      ? `<div style="color:var(--fail);font-size:11px;margin-top:2px">${esc(String(st.last_error).slice(0, 120))}</div>`
      : "";
    return `<button type="button" class="stage${active}${run}${hasErr}" data-seq="${esc(st.seq)}">
      <span class="dot ${esc(st.state)}"></span>
      <span class="n">${String(st.seq).padStart(4,"0")}</span>
      <strong>${esc(NODE_ZH[st.node] || st.node)}</strong>
      <span style="color:var(--muted)"> · ${esc(st.stage || "")}</span>
      ${errHint}
    </button>`;
  }).join("");
  box.querySelectorAll(".stage").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedStageSeq = Number(btn.dataset.seq);
      followTail = false;
      if ($("btnFollow")) $("btnFollow").classList.remove("on");
      renderStages(lastSnap);
      renderSwim(lastSnap);
    });
  });
  if (followTail && ((s.poll && s.poll.sources_fresh) || s.status === "running")) {
    const last = stages[stages.length - 1];
    if (last) {
      selectedStageSeq = last.seq;
      const el = box.querySelector(`.stage[data-seq="${CSS.escape(String(last.seq))}"]`);
      if (el) el.scrollIntoView({ block: "nearest" });
    }
  } else if (selectedStageSeq != null) {
    const el = box.querySelector(`.stage[data-seq="${CSS.escape(String(selectedStageSeq))}"]`);
    if (el) el.scrollIntoView({ block: "nearest" });
  }
  renderStageDetail(s);
}

function renderTree(s) {
  const box = $("tree");
  const items = s.dispatches || [];
  if (!items.length) {
    box.innerHTML = `<div class="empty">暂无派工</div>`;
    return;
  }
  box.innerHTML = `<div class="toolbar"><span class="k">派工树</span></div>` + items.map((d, i) => {
    const active = selectedDispatch === i ? " active" : "";
    const hit = d.tool_call_detected ? "hit" : "miss";
    const raw = d.role || d.name || ("agent-" + i);
    const zh = nodeLabel(raw);
    const labelHtml = zh && zh !== raw
      ? `<span class="role-zh">${esc(zh)}</span><span class="role-key">(${esc(raw)})</span>`
      : `<span class="role-zh">${esc(zh)}</span>`;
    return `<div class="tree-row${active}" data-di="${i}">
      <strong>${labelHtml}</strong>
      <span class="tag ${hit}">${d.tool_call_detected ? "有工具调用" : "未见工具"}</span>
      <div style="color:var(--muted);font-size:11px;margin-top:2px">${esc((d.path || d.log || "").toString().slice(-80))}</div>
    </div>`;
  }).join("");
  box.querySelectorAll(".tree-row").forEach((el) => {
    el.addEventListener("click", () => {
      selectedDispatch = Number(el.dataset.di);
      renderTree(lastSnap);
      renderEvents(lastSnap);
    });
  });
}

function renderThinking(s) {
  const box = $("thinking");
  const th = s.thinking || {};
  const chunks = th.chunks || th.texts || [];
  if (!chunks.length && !th.status) {
    box.innerHTML = "";
    return;
  }
  const rawBody = (Array.isArray(chunks) ? chunks : [chunks]).map((c) => (typeof c === "string" ? c : JSON.stringify(c))).join("\n---\n");
  const body = rawBody.length > 8000 ? rawBody.slice(0, 8000) + "\n... (已截断显示前 8KB)" : rawBody;
  box.innerHTML = `<details class="thinking-box" open>
    <summary>思考片段 · ${esc(statusLabel(th.status || "available"))}</summary>
    <pre style="white-space:pre-wrap;font-family:var(--mono);font-size:11px;margin-top:6px">${esc(body || "（空）")}</pre>
  </details>`;
}

// Detect Lean 4-Agent stages & OR tool invocations inside a single event.
const HANDOFF_RE = /(?:transfer_to_)?(or_(?:analyst|modeler|writer|reviewer))/i;

function eventBadges(ev) {
  const sig = [ev && ev.tool, ev && ev.toolName, ev && ev.type, ev && ev.kind,
    ev && ev.text, ev && ev.content, ev && ev.summary, ev && ev.role]
    .filter(Boolean).join(" \n ");
  const badges = [];
  const m = sig.match(HANDOFF_RE);
  if (m) {
    badges.push(`<span class="pill pill-handoff" title="多智能体换手">⇄ 换手: ${esc(nodeLabel(m[1]))}</span>`);
  }
  if (/execute_or_solver/.test(sig)) {
    badges.push(`<span class="pill pill-solver" title="调用确定性求解算子">⚙ 求解算子</span>`);
  }
  if (/validate_solution_tool/.test(sig)) {
    badges.push(`<span class="pill pill-validate" title="独立数字验算">✓ 数字验算</span>`);
  }
  return badges.join("");
}

function renderEvents(s) {
  const box = $("events");
  if (!box) return;
  let events = s.events || [];
  if (selectedDispatch != null && s.dispatches && s.dispatches[selectedDispatch]) {
    const d = s.dispatches[selectedDispatch];
    if (d.events && d.events.length) events = d.events;
  }
  if (!events.length) {
    box.innerHTML = `<div class="empty">暂无事件流</div>`;
    return;
  }
  const slice = events.slice(-eventLimit);
  box.innerHTML = slice.map((ev) => {
    const rawType = ev.type || ev.kind || "meta";
    const tCls = String(rawType).replace(/[^\w-]/g, "_");
    const t = esc(rawType);
    const role = esc(ev.role || "");
    const text = esc(ev.text || ev.content || ev.summary || JSON.stringify(ev).slice(0, 400));
    const badges = eventBadges(ev);
    return `<div class="ev ${esc(tCls)}">
      ${badges ? `<div class="ev-badges">${badges}</div>` : ""}
      <span class="k">${t}</span> ${role ? "[" + role + "] " : ""}${text}
    </div>`;
  }).join("");
  if (followTail) box.scrollTop = box.scrollHeight;
}
