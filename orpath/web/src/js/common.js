/* ==========================================================================
   OR-Path Common JavaScript Utilities
   ========================================================================== */

const $ = (id) => document.getElementById(id);

const NODE_ZH = {
  intake_ocr: "题面识别",
  intake_parse: "题面解析",
  orchestrate: "编排",
  or_analyst: "领域研判",
  or_modeler: "数学建模",
  or_writer: "学术写稿",
  or_reviewer: "审稿红队",
  retrieve: "检索",
  research: "调研",
  model: "建模",
  gate_schema: "结构门禁",
  solve: "求解",
  gate_validate: "校验",
  human_stop: "人工确认",
  explain: "解释",
  draft_paper: "写稿",
  cite_pack: "引用打包",
  review_pack: "审稿",
  revise_or_done: "修订/完成",
  provenance: "溯源",
  end: "结束",
};

const STATUS_ZH = {
  ok: "正常",
  fail: "失败",
  blocked: "受阻",
  running: "运行中",
  idle: "空闲",
  no_product_run: "尚无产品跑次",
  available: "有思维链",
  thinking_unavailable: "无思维链",
};

function nodeLabel(n) {
  const k = String(n || "");
  return NODE_ZH[k] || k;
}

function statusLabel(st) {
  const k = String(st || "idle");
  return STATUS_ZH[k] ? STATUS_ZH[k] : k;
}

function qs() {
  const p = new URLSearchParams(location.search);
  return {
    slug: p.get("slug") || "test",
    thread: p.get("thread") || p.get("thread_id") || "",
  };
}

function setQS(slug, thread) {
  const p = new URLSearchParams();
  p.set("slug", slug);
  if (thread) p.set("thread", thread);
  history.replaceState(null, "", "?" + p.toString());
}

function statusClass(st) {
  const sanitized = String(st || "idle").replace(/[^\w-]/g, "_");
  return "badge st-" + esc(sanitized);
}

function esc(x) {
  return String(x == null ? "" : x)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function fmtKB(bytes) {
  if (bytes == null || isNaN(bytes)) return "? KB";
  return Math.round(bytes / 1024) + " KB";
}

function showToast(msg, type = "info") {
  let box = $("orToastContainer");
  if (!box) {
    box = document.createElement("div");
    box.id = "orToastContainer";
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    box.style.cssText = "position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:10px;pointer-events:none;max-width:420px;";
    document.body.appendChild(box);
  }
  const toast = document.createElement("div");
  const bg = type === "error" ? "rgba(239, 68, 68, 0.95)" : (type === "warn" ? "rgba(245, 158, 11, 0.95)" : "rgba(15, 23, 42, 0.92)");
  toast.style.cssText = `background:${bg};color:#fff;padding:10px 16px;border-radius:10px;font-size:12.5px;box-shadow:0 10px 25px -5px rgba(0,0,0,0.3);backdrop-filter:blur(8px);pointer-events:auto;cursor:pointer;transition:transform 0.2s ease, opacity 0.2s ease;display:flex;align-items:center;gap:8px;line-height:1.4;`;
  const icon = type === "error" ? "✕" : (type === "warn" ? "⚠" : "ℹ");
  toast.innerHTML = `<span style="font-weight:700">${icon}</span> <span style="flex:1">${esc(msg)}</span>`;
  toast.onclick = () => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 200);
  };
  box.appendChild(toast);
  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(8px)";
      setTimeout(() => toast.remove(), 200);
    }
  }, 4000);
}

async function copyToClipboard(text) {
  if (!text) return false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (_) {}
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  } catch (_) {
    return false;
  }
}

function errorPayload(s) {
  const e = (s && s.error) || {};
  const cur = (s && s.current) || {};
  const last = (e.last_error || cur.last_error || "").trim();
  const has = e.has_error != null
    ? !!e.has_error
    : !!(last || cur.human_required || ["fail", "blocked"].includes(s && s.status));
  return {
    has_error: has,
    last_error: last,
    stage_seq: e.stage_seq != null ? e.stage_seq : cur.error_stage_seq,
    node: e.node || cur.node,
    stage: e.stage || cur.stage,
    human_required: !!(e.human_required || cur.human_required),
    status: e.status || (s && s.status) || "",
    copy_text: e.copy_text || last,
    explain: e.explain || {},
  };
}

function iconFor(kind) {
  const m = {
    clock: "⏱",
    hand: "🖐",
    warn: "⚠",
    gate: "🚪",
    schema: "📐",
    solve: "🧮",
    paper: "📄",
    intake: "📥",
  };
  return m[kind] || "⚠";
}

/**
 * 同步顶部导航栏激活状态 (/studio vs /)
 */
function syncHeaderNavState() {
  const isStudio = document.body.classList.contains("mode-studio");
  if ($("btnModeStudio")) $("btnModeStudio").classList.toggle("on", isStudio);
  if ($("btnModeInspector")) $("btnModeInspector").classList.toggle("on", !isStudio);
}
