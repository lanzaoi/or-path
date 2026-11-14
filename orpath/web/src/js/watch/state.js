/* ==========================================================================
   OR-Path Live Watch Inspector State & Renderer
   ========================================================================== */
const POLL_MS = 1000;
const EVENT_WINDOW = 80; // P5: only paint last N into DOM
let selectedStageSeq = null;
let selectedDispatch = null;
let lastSnap = null;
let lastFp = null;
let lastEventsCount = null;
let timer = null;
let followTail = true;
let paused = false;
let errDismissed = "";
let eventLimit = EVENT_WINDOW;
let autoJumpedError = false;
let copyToastTimer = null;
let modelPresets = [];
let lastDlgCount = 0;

let currentWbTab = "overview";
let wbCollapsed = false;
let selectedUploadFile = null;
let artifactAbortController = null;
let fetchToken = 0;

function showErrorBanner(s) {
  const e = errorPayload(s);
  const t = (e.last_error || "").trim();
  const ex = e.explain || {};
  const banner = $("errBanner");
  if (!e.has_error || !t || t === errDismissed) {
    if ((!e.has_error || !t) && banner) banner.classList.remove("show");
    renderNextActions(s);
    return;
  }
  const headline = (ex.headline || "").trim()
    || (e.human_required ? "需要你看一下" : "运行出错");
  if ($("errTitle")) $("errTitle").textContent = e.human_required ? "需要人工处理" : "出错了";
  if ($("errHeadline")) {
    $("errHeadline").hidden = false;
    if ($("errHeadlineText")) $("errHeadlineText").textContent = headline;
    if ($("errIcon")) $("errIcon").textContent = iconFor(ex.icon);
  }
  if ($("errExplain")) {
    $("errExplain").hidden = false;
    if ($("errWhat")) $("errWhat").textContent = ex.what || ("卡在「" + nodeLabel(e.node || e.stage) + "」。");
    if ($("errWhy")) $("errWhy").textContent = ex.why || t;
    if ($("errDo")) $("errDo").textContent = ex.do || "复制下方命令到终端执行；网页不会自动续跑。";
  }
  if ($("errText")) $("errText").textContent = t;
  const meta = [
    e.status ? "状态：" + statusLabel(e.status) : "",
    (ex.where || e.node) ? "位置：" + (ex.where || nodeLabel(e.node)) : "",
    e.stage_seq != null ? "步骤序号：" + e.stage_seq : "",
  ].filter(Boolean).join("  ·  ");
  if ($("errMeta")) $("errMeta").textContent = meta;
  if (banner) banner.classList.add("show");
  if (!autoJumpedError && e.stage_seq != null) {
    autoJumpedError = true;
    selectedStageSeq = Number(e.stage_seq);
  }
  renderNextActions(s);
}

function renderNextActions(s) {
  const box = $("nextActions");
  const list = $("nextActionsList");
  if (!box || !list) return;
  const acts = (s && (s.next_actions || (s.error && s.error.next_actions))) || [];
  if (!acts.length) {
    box.classList.remove("show");
    list.innerHTML = "";
    return;
  }
  box.classList.add("show");
  const banner = $("errBanner");
  if (banner && !banner.classList.contains("show")) {
    banner.classList.add("show");
    if ($("errTitle")) $("errTitle").textContent = "建议下一步";
    if ($("errHeadline")) {
      $("errHeadline").hidden = false;
      if ($("errHeadlineText")) $("errHeadlineText").textContent = "可以继续，但要你在终端执行";
      if ($("errIcon")) $("errIcon").textContent = "👉";
    }
    if ($("errExplain")) $("errExplain").hidden = true;
    if ($("errText")) $("errText").textContent = "";
    if ($("errMeta")) $("errMeta").textContent = "状态：" + statusLabel((s && s.status) || "");
  }
  list.innerHTML = acts.map((a, i) => {
    const title = esc(a.title || ("操作 " + (i + 1)));
    const reason = esc(a.reason || "");
    const cmd = esc(a.command || "");
    const rec = i === 0 || /推荐/.test(a.title || "");
    return `<div class="na-item${rec ? " rec" : ""}" data-na-idx="${i}">
      <strong>${title}</strong>
      <button type="button" class="na-copy" data-na-copy="${i}">复制命令</button>
      <div class="na-reason">${reason}</div>
      <pre class="na-cmd" id="naCmd${i}">${cmd}</pre>
    </div>`;
  }).join("");
  list.querySelectorAll("[data-na-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const i = btn.getAttribute("data-na-copy");
      const pre = document.getElementById("naCmd" + i);
      const text = pre ? pre.textContent : "";
      if (!text) return;
      const ok = await copyToClipboard(text);
      if (ok) {
        btn.textContent = "已复制 ✓";
        setTimeout(() => { btn.textContent = "复制命令"; }, 1200);
      } else {
        if ($("fetchErr")) $("fetchErr").textContent = "复制命令失败";
      }
    });
  });
}

async function copyErrorText() {
  const s = lastSnap;
  const e = errorPayload(s || {});
  const text = (e.copy_text || e.last_error || "").trim();
  if (!text) return;
  const ok = await copyToClipboard(text);
  if (ok) {
    const toast = $("errCopyToast");
    if (toast) {
      toast.classList.add("show");
      if (copyToastTimer) clearTimeout(copyToastTimer);
      copyToastTimer = setTimeout(() => toast.classList.remove("show"), 1200);
    }
  } else {
    if ($("fetchErr")) $("fetchErr").textContent = "复制失败";
  }
}

function jumpToErrorStage() {
  const e = errorPayload(lastSnap || {});
  if (e.stage_seq == null || !lastSnap) return;
  selectedStageSeq = Number(e.stage_seq);
  followTail = false;
  if ($("btnFollow")) $("btnFollow").classList.remove("on");
  renderSwim(lastSnap);
  renderStages(lastSnap);
  const el = document.querySelector(`.stage[data-seq="${CSS.escape(String(selectedStageSeq))}"]`);
  if (el) el.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function fillModelSelect(info) {
  const sel = $("modelSelect");
  if (!sel) return;
  const presets = (info && info.presets) || modelPresets || [];
  modelPresets = presets;
  const curP = (info && info.provider) || "deepseek";
  const curM = (info && info.model) || "";
  const key = curP + "|" + curM;
  let html = "";
  let found = false;
  presets.forEach((p) => {
    const k = p.provider + "|" + p.model;
    if (k === key) found = true;
    html += `<option value="${esc(k)}" ${k === key ? "selected" : ""}>${esc(p.label || p.model)}</option>`;
  });
  if (curM && !found) {
    html = `<option value="${esc(key)}" selected>${esc(curP + " / " + curM)}（当前）</option>` + html;
  }
  sel.innerHTML = html || `<option value="">暂未加载模型</option>`;
}

async function loadModel() {
  try {
    const r = await fetch("/api/model", { cache: "no-store" });
    const j = await r.json();
    if (j && j.ok !== false) fillModelSelect(j);
  } catch (_) { /* ignore */ }
}

async function applyModel() {
  const sel = $("modelSelect");
  if (!sel || !sel.value) return;
  const [provider, ...rest] = sel.value.split("|");
  const model = rest.join("|");
  try {
    const r = await fetch("/api/model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, model }),
    });
    const j = await r.json();
    if (!r.ok || j.ok === false) {
      $("fetchErr").textContent = "切换模型失败: " + (j.error || r.status);
      return;
    }
    fillModelSelect(j);
    const t = $("modelToast");
    t.classList.add("show");
    t.textContent = "已保存 " + (j.model || model);
    setTimeout(() => t.classList.remove("show"), 2000);
  } catch (err) {
    if ($("fetchErr")) $("fetchErr").textContent = "切换模型失败: " + err.message;
  }
}

function renderBadges(s) {
  const live = s.live_subagent;
  const poll = s.poll || {};
  const t2 = s.tier2 || {};
  const t3 = s.tier3 || {};
  const pm = s.pi_model || {};
  const html = [
    `<span class="badge">任务 ${esc(s.slug)}</span>`,
    `<span class="badge">线程 ${esc(s.thread_id)}</span>`,
    `<span class="badge ${live ? "on" : "off"}">多智能体 ${live ? "开" : "关"}</span>`,
    `<span class="${statusClass(s.status)}">${esc(statusLabel(s.status))}</span>`,
    pm.model ? `<span class="badge">模型 ${esc(pm.model)}</span>` : "",
    poll.sources_fresh ? `<span class="badge st-running">有更新</span>` : "",
    s.current && s.current.human_required
      ? `<span class="badge st-blocked">需人工</span>` : "",
    s.thinking
      ? `<span class="badge">${esc(statusLabel(s.thinking.status))}</span>` : "",
    poll.events_truncated ? `<span class="badge st-fail">事件截断</span>` : "",
    t2.pi_session_env ? `<span class="badge on">会话</span>` : `<span class="badge off">无会话</span>`,
    t3.enabled ? `<span class="badge on">观测</span>` : "",
    paused ? `<span class="badge st-blocked">已暂停</span>` : "",
  ].filter(Boolean).join("");
  if ($("badges")) $("badges").innerHTML = html;
  showErrorBanner(s);
  if (s.pi_model) fillModelSelect(s.pi_model);
}
