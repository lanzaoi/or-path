// Watch dialogue, steer submission, artifacts & Tier-2 telemetry
function renderDialogue(s) {
  const box = $("dlgBubbles");
  if (!box) return;
  const d = (s && s.dialogue) || {};
  const bubbles = d.bubbles || [];
  if (!bubbles.length) {
    box.innerHTML = `<div class="empty">暂无阶段精要 · 跑产品任务后这里会按磁盘生成对话气泡（无 LLM）</div>`;
    lastDlgCount = 0;
    return;
  }
  const roleTitle = {
    system: "系统",
    research: "调研",
    model: "建模",
    solve: "求解",
    validate: "校验",
    human: "人导",
    pi: "会话",
  };
  box.innerHTML = bubbles.map((b) => {
    const rawRole = b.role || "system";
    const roleCls = String(rawRole).replace(/[^\w-]/g, "_");
    const title = esc(b.title || roleTitle[b.role] || rawRole);
    const text = esc(b.text || "");
    return `<div class="bubble ${esc(roleCls)}"><div class="b-meta">${title}</div>${text}</div>`;
  }).join("");
  if (bubbles.length !== lastDlgCount || followTail) {
    box.scrollTop = box.scrollHeight;
  }
  lastDlgCount = bubbles.length;

  // Prefill form from existing steer once if empty
  const st = d.steer;
  if (st && typeof st === "object") {
    const lg = st.lg || {};
    const pi = st.pi || {};
    if ($("dlgMode") && !$("dlgMode").dataset.touched && lg.solve_mode) {
      $("dlgMode").value = lg.solve_mode;
    }
    if ($("dlgResume") && !$("dlgResume").dataset.touched && lg.resume_from) {
      $("dlgResume").value = lg.resume_from;
    }
    if ($("dlgMethods") && !$("dlgMethods").dataset.touched && pi.prefer_methods != null) {
      const pm = pi.prefer_methods;
      $("dlgMethods").value = Array.isArray(pm) ? pm.join(", ") : String(pm);
    }
    if ($("dlgNotes") && !$("dlgNotes").dataset.touched && pi.notes) {
      $("dlgNotes").value = typeof pi.notes === "string" ? pi.notes : JSON.stringify(pi.notes);
    }
  }
}

function renderDlgCta(acts) {
  const el = $("dlgCta");
  if (!el) return;
  if (!acts || !acts.length) {
    el.classList.remove("show");
    el.innerHTML = "";
    return;
  }
  el.classList.add("show");
  el.innerHTML =
    `<div class="na-label">引导参数已保存（无阻塞生效） · 可复制复现命令</div>` +
    acts.map((a, i) => {
      const title = esc(a.title || "action");
      const cmd = esc(a.command || "");
      const reason = esc(a.reason || "");
      return `<div class="cta-item"><strong>${title}</strong>` +
        (reason ? `<div style="color:var(--ink-48)">${reason}</div>` : "") +
        `<code id="dlgCmd${i}">${cmd}</code>` +
        `<button type="button" data-dlg-copy="${i}">复制命令</button></div>`;
    }).join("");
  el.querySelectorAll("[data-dlg-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const i = btn.getAttribute("data-dlg-copy");
      const code = $("dlgCmd" + i);
      const t = code ? code.textContent : "";
      const ok = await copyToClipboard(t);
      if (ok) {
        btn.textContent = "已复制";
        setTimeout(() => { btn.textContent = "复制命令"; }, 1200);
      } else {
        btn.textContent = "复制失败";
      }
    });
  });
}

async function submitSteer() {
  const toast = $("dlgToast");
  if (toast) {
    toast.classList.remove("err");
    toast.textContent = "提交中…";
  }
  try {
    const slug = ($("slug")?.value || "").trim() || "test";
    const solveMode = ($("dlgMode")?.value || "").trim();
    const resumeFrom = ($("dlgResume")?.value || "").trim();
    const preferMethods = ($("dlgMethods")?.value || "").trim();
    const notes = ($("dlgNotes")?.value || "").trim();
    const fresh = !!($("dlgFresh")?.checked);

    const body = {
      slug,
      source: "watch_form",
      at_stage: "manual",
      lg: {
        solve_mode: solveMode,
        resume_from: resumeFrom,
        fresh: fresh,
        pause_next: false,
      },
      pi: {
        prefer_methods: preferMethods,
        notes: notes,
      },
    };
    // strip empty lg keys for cleaner file
    if (!body.lg.solve_mode) delete body.lg.solve_mode;
    if (!body.lg.resume_from) delete body.lg.resume_from;
    if (!body.lg.fresh) delete body.lg.fresh;

    const r = await fetch("/api/steer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const j = await r.json();
    if (!r.ok || !j.ok) {
      const errs = (j.errors || [j.error || "failed"]).join("; ");
      if (toast) {
        toast.classList.add("err");
        toast.textContent = errs;
      }
      renderDlgCta([]);
      return;
    }
    if (toast) toast.textContent = "已写入 " + (j.path || "human-steer.json");
    renderDlgCta(j.next_actions || []);
    // force refresh bubbles
    lastFp = null;
    fetchSnapshot(true);
  } catch (err) {
    if (toast) {
      toast.classList.add("err");
      toast.textContent = String(err.message || err);
    }
  }
}

function renderArtifacts(s) {
  // Both the ordinary artifacts and the long Tier-2 panel live in this
  // same scroll container.  Keeping Tier-2 outside used to clip it below
  // the viewport because the parent section intentionally hides overflow.
  const box = $("artifactList");
  if (!box) return;
  const a = s.artifacts || {};
  const keys = ["solution", "validate", "schema", "paper", "intake", "plan", "provenance", "runs_dir", "agents_dir"];
  const labels = {
    solution: "求解结果",
    validate: "校验报告",
    schema: "问题结构",
    paper: "文稿",
    intake: "题面 intake",
    plan: "任务账本",
    provenance: "溯源",
    runs_dir: "运行目录",
    agents_dir: "智能体日志",
  };
  const viewable = new Set(["solution", "validate", "schema", "paper", "intake", "plan", "provenance"]);
  let html = "";
  keys.forEach((k) => {
    if (!a[k]) return;
    const btn = viewable.has(k)
      ? `<button type="button" class="art-view-btn" data-art-kind="${esc(k)}" data-art-label="${esc(labels[k] || k)}">查看</button>`
      : "";
    html += `<div class="art-row"><div><div class="k">${esc(labels[k] || k)}</div><span class="path">${esc(a[k])}</span></div>${btn}</div>`;
  });
  const dlg = s.dialogue || {};
  if (dlg.steer_path) {
    html += `<div class="k">人导单</div><span class="path">${esc(dlg.steer_path)}${dlg.steer_exists ? "" : " （尚未写入）"}</span>`;
  }
  const honest = (s.honesty && s.honesty.messages) || [];
  if (honest.length) {
    html += `<div class="honesty"><strong>说明</strong><br/>${honest.map(esc).join("<br/>")}</div>`;
  }
  if (!html) html = `<div class="empty">暂无产物路径</div>`;
  box.innerHTML = html;
  box.querySelectorAll("[data-art-kind]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openArtifactModal(btn.getAttribute("data-art-kind"), btn.getAttribute("data-art-label"));
    });
  });
  renderTier2(s);
}

function renderTier2(s) {
  const panel = $("tier2Panel");
  if (!panel) return;
  const t2 = (s && s.tier2) || {};
  panel.hidden = false;
  const badge = (name, on) =>
    `<span class="${on ? "on" : "off"}">${esc(name)} ${on ? "✓" : "—"}</span>`;
  const links = t2.deep_links || [];
  const recent = t2.recent || [];
  let linksHtml = links.map((L, i) => {
    const ready = L.ready === false ? " · 包未声明" : (L.ready === true ? " · 已声明" : "");
    return `<div class="t2-link">
      <strong>${esc(L.title || L.id || ("link-" + i))}${ready}</strong>
      <div class="why">${esc(L.reason || "")}</div>
      <pre id="t2Cmd${i}">${esc(L.command || "")}</pre>
      <button type="button" data-t2-copy="${i}">复制命令</button>
    </div>`;
  }).join("");
  if (!linksHtml) {
    linksHtml = `<div class="empty">暂无深链（snapshot.tier2.deep_links）</div>`;
  }
  const recentHtml = recent.length
    ? `<div class="k">最近 session</div><div class="t2-recent">${recent.slice(0, 6).map((r) =>
        esc((r.name || "") + " · " + (r.parent || "").slice(0, 48))
      ).join("<br/>")}</div>`
    : `<div class="k">最近 session</div><div class="t2-meta">无历史会话记录</div>`;

  panel.innerHTML = `
    <h3>控制面观测 · Lean 4-Agent Runtime</h3>
    <div class="t2-meta">
      会话状态: ${t2.pi_session_env ? "已配置" : "标准无状态"} ·
      runs_root: ${esc(t2.sessions_root || "runs/")}
    </div>
    <div class="t2-badges">
      ${badge("or_analyst", true)}
      ${badge("or_modeler", true)}
      ${badge("or_writer", true)}
      ${badge("or_reviewer", true)}
    </div>
    <div class="t2-meta">架构文档: ${esc(t2.docs || "docs/ARCHITECTURE.md")}</div>
    ${recentHtml}
    <div class="k" style="margin-top:8px">可复制等价 CLI 命令</div>
    ${linksHtml}
  `;
  panel.querySelectorAll("[data-t2-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const i = btn.getAttribute("data-t2-copy");
      const pre = document.getElementById("t2Cmd" + i);
      const text = pre ? pre.textContent : "";
      if (!text) return;
      const ok = await copyToClipboard(text);
      if (ok) {
        btn.textContent = "已复制";
        setTimeout(() => { btn.textContent = "复制命令"; }, 1000);
      } else {
        if ($("fetchErr")) $("fetchErr").textContent = "复制失败";
      }
    });
  });
}

