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
      sel.innerHTML = html || `<option value="deepseek|deepseek-v4-flash">DeepSeek V4 Flash</option>`;
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

    function renderMetaphor(s) {
      const cur = (s && s.current) || {};
      const stages = (s && s.stages) || [];
      const last = stages.length ? stages[stages.length - 1] : null;
      const art = (s && s.artifacts) || {};
      if ($("mLg")) $("mLg").textContent = last
        ? ("最新: " + nodeLabel(last.node) + " · " + statusLabel(last.state || s.status))
        : ("状态 " + statusLabel(s && s.status));
      if ($("mPi")) $("mPi").textContent = cur.node
        ? ("当前节点 " + nodeLabel(cur.node))
        : (s && s.live_subagent ? "多智能体已开" : "多智能体关 · 确定性路径");
      const disp = (s && s.dispatches) || [];
      if ($("mSub")) $("mSub").textContent = disp.length
        ? ("派工 " + disp.length + " 条")
        : "暂无派工记录";
      if ($("mScript")) $("mScript").textContent = art.solution
        ? ("解: " + art.solution)
        : (art.validate ? ("校验: " + art.validate) : "等待求解产物");
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
      renderMetaphor(s);
      if (s.pi_model) fillModelSelect(s.pi_model);
    }

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

    // Detect multi-agent handoffs (transfer_to_or_*) and OR tool invocations
    // (execute_or_solver / validate_solution_tool) inside a single event.
    const HANDOFF_RE = /transfer_to_(or_[a-z0-9_]+)/i;

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
        if ($("dlgAtStage") && !$("dlgAtStage").dataset.touched && st.at_stage) {
          $("dlgAtStage").value = st.at_stage;
        }
        if ($("dlgPause") && !$("dlgPause").dataset.touched && lg.pause_next) {
          $("dlgPause").checked = !!lg.pause_next;
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
        `<div class="na-label">人导已写入 · 复制命令到终端（不会自动续跑）</div>` +
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
        const atStage = ($("dlgAtStage")?.value || "manual").trim();
        const pauseNext = !!($("dlgPause")?.checked);
        const fresh = !!($("dlgFresh")?.checked);

        const body = {
          slug,
          source: "watch_form",
          at_stage: atStage,
          pause_next: pauseNext,
          lg: {
            solve_mode: solveMode,
            resume_from: resumeFrom,
            fresh: fresh,
            pause_next: pauseNext,
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
        if (!body.lg.pause_next) delete body.lg.pause_next;
        if (!body.pause_next) delete body.pause_next;

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

    let currentWbTab = "overview";
    let wbCollapsed = false;
    let selectedUploadFile = null;

    function renderProblemWorkbench(s) {
      const pv = (s && s.problem_view) || {};
      const titleEl = $("wbTitle");
      const pillsEl = $("wbPills");
      const bodyEl = $("wbBody");
      if (!titleEl || !bodyEl) return;

      if (!pv.has_problem) {
        titleEl.textContent = "当前任务暂无题面信息 (" + (s.slug || "test") + ")";
        pillsEl.innerHTML = `<span class="wb-pill">未导入题面</span>`;
        bodyEl.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:8px 12px;background:#fff;border:1px dashed var(--surface-2);border-radius:10px">
            <div>
              <div style="font-size:13px;font-weight:700;color:var(--ink)">尚未加载题面或当前 Slug 无题面资产</div>
              <div style="font-size:12px;color:var(--ink-48);margin-top:3px">点击右侧「📥 导入/切换题目」可一键加载 9 大内置工业运筹赛题（如 2026 校赛 B 题异形圆管下料、M2 多联骨牌排样、CVRP 等），或上传 PDF/图片/文本题面。</div>
            </div>
            <button type="button" class="wb-btn primary" id="wbEmptyImportBtn" style="height:34px;padding:0 16px">📥 立即导入 / 选择赛题</button>
          </div>`;
        const b = $("wbEmptyImportBtn");
        if (b) b.addEventListener("click", openIntakeModal);
        return;
      }

      titleEl.textContent = pv.title || s.slug || "运筹优化问题";
      const pills = [];
      if (pv.problem_class) pills.push(`<span class="wb-pill blue">类别: ${esc(pv.problem_class)}</span>`);
      if (pv.ocr_backend && pv.ocr_backend !== "none") pills.push(`<span class="wb-pill">来源: ${esc(pv.ocr_backend)}</span>`);
      const subs = pv.subproblems || [];
      if (subs.length) pills.push(`<span class="wb-pill">${subs.length} 个子问</span>`);
      const sol = pv.solution_summary || {};
      if (sol.exists && sol.objective != null) {
        pills.push(`<span class="wb-pill ok">目标值: ${esc(sol.objective)} (${esc(sol.status || "OK")})</span>`);
      } else if (sol.exists && sol.status === "BLOCKED") {
        pills.push(`<span class="wb-pill" style="background:#fee2e2;color:#991b1b;border-color:#fca5a5">求解受阻: BLOCKED (拒绝假优)</span>`);
      }
      const val = pv.validate_summary || {};
      if (val.exists) {
        pills.push(`<span class="wb-pill ${val.ok ? "ok" : ""}">校验: ${val.passed_checks}/${val.total_checks} 通过</span>`);
      }
      pillsEl.innerHTML = pills.join("");

      if (currentWbTab === "overview") {
        let subHtml = "";
        if (subs.length) {
          subHtml = `<div class="wb-sub-list">` + subs.map((sp) => {
            const delivArr = Array.isArray(sp.must_deliver) ? sp.must_deliver : (sp.must_deliver ? [sp.must_deliver] : []);
            const deliv = delivArr.length ? `<div class="qdeliv">交付表: ${esc(delivArr.join(", "))}</div>` : "";
            return `<div class="wb-sub-item">
              <div><span class="qid">${esc(sp.id || "Q")}</span><span class="qtitle">${esc(sp.title || "")}</span></div>
              ${sp.notes ? `<div class="qnotes">${esc(sp.notes)}</div>` : ""}
              ${deliv}
            </div>`;
          }).join("") + `</div>`;
        } else {
          subHtml = `<div class="wb-pre" style="max-height:170px">${esc(pv.brief_text || "无子问题拆分，请查看「题面原文」标签页。")}</div>`;
        }

        const assets = pv.data_assets || [];
        const assetTags = assets.slice(0, 12).map((a) =>
          `<span class="wb-pill" style="font-family:var(--mono);font-size:10.5px">${esc((a.path || "").split("/").pop())} (${esc(a.kind)})</span>`
        ).join(" ");
        const totalAssets = Number(pv.data_assets_total);
        const moreAssets = (!isNaN(totalAssets) && totalAssets > 12) ? `<span class="wb-pill">+${totalAssets - 12} 项</span>` : "";

        const delivs = Array.isArray(pv.deliverables) ? pv.deliverables.join(", ") : (pv.deliverables ? String(pv.deliverables) : "");
        bodyEl.innerHTML = `
          <div class="wb-grid">
            <div style="display:grid;gap:8px">
              <div class="wb-card">
                <h4><span>🎯 优化目标与硬约束</span><span>${esc(pv.problem_id || s.slug)}</span></h4>
                <div style="font-size:12px;line-height:1.5">
                  <div><strong>优化目标：</strong>${esc(pv.objectives_text || "见题面原文与数学模型 Schema")}</div>
                  <div style="margin-top:4px"><strong>约束条件：</strong>${esc(pv.constraints_text || "见题面原文与数学模型 Schema")}</div>
                  ${delivs ? `<div style="margin-top:4px"><strong>交付产物：</strong><span style="font-family:var(--mono);color:var(--blue)">${esc(delivs)}</span></div>` : ""}
                </div>
              </div>
              <div class="wb-card">
                <h4><span>📦 数据附件与题面源 (${!isNaN(totalAssets) ? totalAssets : assets.length} 项)</span></h4>
                <div style="display:flex;gap:4px;flex-wrap:wrap">
                  ${assetTags || `<span style="font-size:11.5px;color:var(--ink-48)">内置标准算例参数 (${esc(pv.brief_path || "fixture")})</span>`}
                  ${moreAssets}
                </div>
              </div>
            </div>
            <div class="wb-card">
              <h4><span>📑 题目子问拆解 (${subs.length || 1} 问)</span><button type="button" class="art-view-btn" id="wbJumpBrief">查看完整题面原文 →</button></h4>
              ${subHtml}
            </div>
          </div>`;
        const jb = $("wbJumpBrief");
        if (jb) jb.addEventListener("click", () => switchWbTab("brief"));
        return;
      }

      if (currentWbTab === "brief") {
        bodyEl.innerHTML = `
          <div class="wb-card">
            <h4>
              <span>📄 题面完整原文 / Problem Brief (${esc(pv.brief_path || "内存")})</span>
              ${pv.has_intake ? `<button type="button" class="art-view-btn" id="wbOpenIntakeJson">查看结构化 intake.json</button>` : ""}
            </h4>
            <pre class="wb-pre" style="max-height:230px">${esc(pv.brief_text || "暂无题面原文")}</pre>
          </div>`;
        const btnIj = $("wbOpenIntakeJson");
        if (btnIj) btnIj.addEventListener("click", () => openArtifactModal("intake", "题面结构化 intake.json"));
        return;
      }

      if (currentWbTab === "schema") {
        const sc = pv.schema_summary || {};
        if (!sc.exists) {
          bodyEl.innerHTML = `<div class="wb-card"><div class="empty">当前任务尚未生成数学模型 Schema（请点击右上角「🚀 一键求解此题」运行流水线）</div></div>`;
          return;
        }
        const vars = sc.variables ? JSON.stringify(sc.variables, null, 2) : "—";
        const cList = (sc.constraints || []).map((c, i) => `<li><code>C${i + 1}:</code> ${esc(typeof c === "string" ? c : JSON.stringify(c))}</li>`).join("");
        bodyEl.innerHTML = `
          <div class="wb-grid">
            <div class="wb-card">
              <h4><span>📐 模型元信息与决策变量</span><button type="button" class="art-view-btn" id="wbOpenSchemaJson">查看完整 schema.json</button></h4>
              <div style="font-size:12px;line-height:1.6;margin-bottom:6px">
                <div><strong>问题标识：</strong><code>${esc(sc.problem_id)}</code> · <strong>类别：</strong><code>${esc(sc.problem_class)}</code> · <strong>方向：</strong><code>${esc(sc.sense)}</code></div>
                <div><strong>目标函数表达式：</strong><code>${esc(sc.objective || "—")}</code></div>
              </div>
              <pre class="wb-pre" style="max-height:130px">${esc(vars)}</pre>
            </div>
            <div class="wb-card">
              <h4><span>🔒 形式化约束方程 (${(sc.constraints || []).length} 条)</span><span style="color:var(--ok)">✓ 门禁已核验无答案泄漏</span></h4>
              <ul style="padding-left:18px;font-size:12px;line-height:1.6;max-height:185px;overflow-y:auto">${cList || "<li>默认域约束</li>"}</ul>
            </div>
          </div>`;
        const bSc = $("wbOpenSchemaJson");
        if (bSc) bSc.addEventListener("click", () => openArtifactModal("schema", "数学模型 schema.json"));
        return;
      }

      if (currentWbTab === "solution") {
        if (!sol.exists) {
          bodyEl.innerHTML = `<div class="wb-card"><div class="empty">尚未生成求解结果（请点击「🚀 一键求解此题」运行求解器与校验器）</div></div>`;
          return;
        }
        let detailHtml = "";
        const qs = sol.questions || [];
        if (qs.length) {
          detailHtml = qs.map((q) => {
            const rows = (q.stocks_preview || []).map((st) => {
              const u = Number(st.utilization);
              const hasU = st.utilization != null && !isNaN(u);
              const pct = hasU ? (u * 100).toFixed(2) : "—";
              const w = hasU ? Math.min(100, Math.max(0, u * 100)) : 0;
              const pc = Number(st.parts_count);
              const partsText = (!isNaN(pc) && pc > 12) ? " …(" + pc + "件)" : "";
              return `<tr>
                <td><strong>${esc(st.id)}</strong></td>
                <td>${esc(st.stock_length_mm)} mm</td>
                <td>${esc(st.used_length_mm)} mm</td>
                <td>${esc(st.leftover_mm)} mm</td>
                <td><span class="wb-bar-meter"><i style="width:${w}%"></i></span>${pct}%</td>
                <td>${esc(st.switches)}</td>
                <td style="font-family:var(--mono);font-size:10.5px">${esc((st.sequence_head || []).join(", "))}${partsText}</td>
              </tr>`;
            }).join("");
            return `<div style="margin-bottom:10px">
              <div style="font-size:12px;font-weight:700;margin-bottom:4px;color:var(--blue)">
                ${esc(q.id)} 排产方案 · 母材总长: ${esc(q.total_stock_length_mm ?? "—")} mm
                ${q.total_cocut_gain_mm != null ? ` · 共切省料: ${esc(q.total_cocut_gain_mm)} mm` : ""}
                ${q.total_switches != null ? ` · 切换次数: ${esc(q.total_switches)}` : ""}
                ${q.stocks_count ? ` · 母材根数: ${esc(q.stocks_count)}` : ""}
              </div>
              ${rows ? `<table class="wb-table"><thead><tr><th>母材</th><th>标准长</th><th>已用长</th><th>余料</th><th>利用率</th><th>切换</th><th>加工序列预览</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
            </div>`;
          }).join("");
        } else if (Array.isArray(sol.path)) {
          detailHtml = `<div style="font-size:12.5px"><strong>最优路径序列：</strong><code style="color:var(--blue);font-size:13px">${esc(sol.path.join(" → "))}</code></div>`;
        } else if (sol.path) {
          detailHtml = `<div style="font-size:12.5px"><strong>最优路径序列：</strong><code style="color:var(--blue);font-size:13px">${esc(String(sol.path))}</code></div>`;
        } else if (Array.isArray(sol.tour)) {
          detailHtml = `<div style="font-size:12.5px"><strong>巡检回路序列：</strong><code style="color:var(--blue);font-size:13px">${esc(sol.tour.join(" → "))}</code></div>`;
        } else if (sol.tour) {
          detailHtml = `<div style="font-size:12.5px"><strong>巡检回路序列：</strong><code style="color:var(--blue);font-size:13px">${esc(String(sol.tour))}</code></div>`;
        } else if (Array.isArray(sol.routes)) {
          detailHtml = `<div style="font-size:12px"><strong>多车配送路径 (${sol.routes.length} 辆车)：</strong>` +
            sol.routes.map((r, idx) => `<div style="margin-top:3px"><code>车辆 #${idx + 1}:</code> ${esc(Array.isArray(r) ? r.join(" → ") : JSON.stringify(r))}</div>`).join("") + `</div>`;
        } else if (sol.placements) {
          const count = Array.isArray(sol.placements) ? sol.placements.length : Object.keys(sol.placements).length;
          detailHtml = `<div style="font-size:12px"><strong>已排样多联骨牌块数：</strong>${count} 块</div>`;
        }

        const checksHtml = (val.checks || []).map((c) =>
          `<div style="display:flex;justify-content:space-between;font-size:11.5px;padding:3px 0;border-bottom:1px dashed var(--border)">
            <span><strong style="color:${c.ok ? "var(--ok)" : "var(--fail)"}">${c.ok ? "✓" : "✗"}</strong> <code>${esc(c.name)}</code></span>
            <span style="color:var(--ink-48);font-family:var(--mono)">${c.got != null ? `实测=${esc(c.got)}` : ""}${c.detail ? ` (${esc(c.detail)})` : ""}</span>
          </div>`
        ).join("");

        const isBlocked = sol.status === "BLOCKED";
        bodyEl.innerHTML = `
          <div class="wb-kpis">
            <div class="wb-kpi"><div class="k">求解状态</div><div class="v ${isBlocked ? "fail" : "ok"}">${esc(sol.status || "—")}</div></div>
            <div class="wb-kpi"><div class="k">确定性目标值 (Objective)</div><div class="v ${isBlocked ? "" : "blue"}">${isBlocked ? "无 (BLOCKED)" : esc(sol.objective ?? "—")}</div></div>
            <div class="wb-kpi"><div class="k">求解器引擎</div><div class="v">${esc(sol.solver || "—")}</div></div>
            <div class="wb-kpi"><div class="k">独立物理校验</div><div class="v ${val.ok ? "ok" : (isBlocked ? "fail" : "")}">${val.exists ? `${val.passed_checks} / ${val.total_checks} 通过` : "—"}</div></div>
          </div>
          <div class="wb-grid">
            <div class="wb-card" style="max-height:190px;overflow-y:auto">
              <h4><span>📊 方案明细与排产表</span><button type="button" class="art-view-btn" id="wbOpenSolJson">查看完整 solution.json</button></h4>
              ${isBlocked ? `<div class="empty" style="color:var(--fail)">平台规范拦截：当前领域无专用适配器，系统拒绝绑定无关金标伪造结果。</div>` : (detailHtml || `<div class="empty">请点击右上角查看完整 JSON</div>`)}
            </div>
            <div class="wb-card" style="max-height:190px;overflow-y:auto">
              <h4><span>🛡️ 确定性重算与物理约束核验项</span><button type="button" class="art-view-btn" id="wbOpenValJson">查看完整 validate.json</button></h4>
              ${checksHtml || `<div class="empty">暂无校验明细</div>`}
            </div>
          </div>`;
        const bSol = $("wbOpenSolJson");
        if (bSol) bSol.addEventListener("click", () => openArtifactModal("solution", "求解结果 solution.json"));
        const bVal = $("wbOpenValJson");
        if (bVal) bVal.addEventListener("click", () => openArtifactModal("validate", "物理校验报告 validate.json"));
        return;
      }

      if (currentWbTab === "paper") {
        bodyEl.innerHTML = `
          <div class="wb-card">
            <h4>
              <span>📝 工业技术报告 / 论文文稿 (${esc(pv.paper_path || "未生成")})</span>
              ${pv.paper_path ? `<button type="button" class="art-view-btn" id="wbOpenPaperFull">全屏阅读报告</button>` : ""}
            </h4>
            <pre class="wb-pre" style="max-height:225px">${esc(pv.paper_preview || "当前任务尚未生成技术报告（待流水线运行至 draft_paper / provenance 站后自动产出）")}</pre>
          </div>`;
        const bP = $("wbOpenPaperFull");
        if (bP) bP.addEventListener("click", () => openArtifactModal("paper", "工业技术报告 / 论文全稿"));
      }
    }

    function switchWbTab(tab) {
      currentWbTab = tab;
      document.querySelectorAll("#wbTabs [data-wb-tab]").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-wb-tab") === tab);
      });
      if (wbCollapsed) {
        wbCollapsed = false;
        $("problemWorkbench").classList.remove("collapsed");
        $("wbBtnCollapse").textContent = "收起 ▲";
        $("btnToggleWorkbench").classList.add("on");
      }
      if (lastSnap) renderProblemWorkbench(lastSnap);
    }

    let artifactAbortController = null;
    async function openArtifactModal(kind, title) {
      if (artifactAbortController) {
        artifactAbortController.abort();
      }
      artifactAbortController = new AbortController();
      const signal = artifactAbortController.signal;
      const slug = ($("slug")?.value || "").trim() || "test";
      if ($("artModalTitle")) $("artModalTitle").textContent = (title || kind) + " · " + slug;
      if ($("artModalPath")) $("artModalPath").textContent = "加载中…";
      if ($("artModalContent")) $("artModalContent").textContent = "正在读取磁盘文件…";
      const modal = $("artifactModal");
      if (modal) {
        modal.classList.add("show");
        if ($("btnCloseArtifact")) $("btnCloseArtifact").focus();
      }
      try {
        const r = await fetch(`/api/artifact?slug=${encodeURIComponent(slug)}&kind=${encodeURIComponent(kind)}`, { cache: "no-store", signal });
        if (signal.aborted) return;
        const j = await r.json();
        if (signal.aborted) return;
        if (!r.ok || !j.ok) {
          if ($("artModalPath")) $("artModalPath").textContent = "读取失败";
          if ($("artModalContent")) $("artModalContent").textContent = j.error || "文件不存在";
          return;
        }
        if ($("artModalPath")) $("artModalPath").textContent = "路径: " + (j.path || "");
        if ($("artModalContent")) $("artModalContent").textContent = j.content || "";
      } catch (err) {
        if (err.name === "AbortError" || signal.aborted) return;
        if ($("artModalContent")) $("artModalContent").textContent = "请求异常: " + err.message;
      }
    }

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

    async function importPreset(presetId, autoRun) {
      try {
        const r = await fetch("/api/intake/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: "preset", preset_id: presetId }),
        });
        const j = await r.json();
        if (!r.ok || !j.ok) {
          showToast("导入失败: " + (j.error || "unknown"), "error");
          return;
        }
        if ($("slug")) $("slug").value = j.slug;
        if ($("thread")) $("thread").value = j.thread_id || j.slug;
        if ($("intakeModal")) $("intakeModal").classList.remove("show");
        switchWbTab("overview");
        applyControls();
        if (autoRun) {
          await runCurrentProblem(j.preset);
        }
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
          const r = await fetch("/api/intake/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              mode: "upload",
              slug: customSlug,
              file_name: selectedUploadFile.name,
              file_base64: b64,
            }),
          });
          const j = await r.json();
          if (!r.ok || !j.ok) {
            if (statusEl) statusEl.textContent = "导入失败: " + (j.error || "unknown");
            return;
          }
          if (statusEl) statusEl.textContent = "✓ 识别成功！已生成 " + j.slug;
          if ($("slug")) $("slug").value = j.slug;
          if ($("thread")) $("thread").value = j.thread_id || j.slug;
          if ($("intakeModal")) $("intakeModal").classList.remove("show");
          switchWbTab("overview");
          applyControls();
          if (autoRun) {
            await runCurrentProblem(j.domain_guess);
          }
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
        const r = await fetch("/api/intake/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            mode: "text",
            slug: customSlug,
            title,
            raw_text: rawText,
          }),
        });
        const j = await r.json();
        if (!r.ok || !j.ok) {
          if (statusEl) statusEl.textContent = "解析失败: " + (j.error || "unknown");
          return;
        }
        if (statusEl) statusEl.textContent = "✓ 解析完成！";
        if ($("slug")) $("slug").value = j.slug;
        if ($("thread")) $("thread").value = j.thread_id || j.slug;
        if ($("intakeModal")) $("intakeModal").classList.remove("show");
        switchWbTab("overview");
        applyControls();
        if (autoRun) {
          await runCurrentProblem(j.domain_guess);
        }
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

    function renderTier2(s) {
      const panel = $("tier2Panel");
      if (!panel) return;
      const t2 = (s && s.tier2) || {};
      panel.hidden = false;
      const ps = t2.package_status || {};
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
        <h3>Tier-2 深链 · Session / kanban / supervise</h3>
        <div class="t2-meta">
          ORPATH_PI_SESSION ${t2.pi_session_env ? "开" : "关"} ·
          sessions_root: ${esc(t2.sessions_root || "—")}
          ${t2.sessions_root_exists ? "" : " （目录尚无）"}
        </div>
        <div class="t2-badges">
          ${badge("pi-kanban", !!ps["pi-kanban"])}
          ${badge("pi-supervisor", !!ps["pi-supervisor"])}
          ${badge("ask-user", !!ps["rpiv-ask-user-question"])}
          <span class="${t2.pi_session_env ? "on" : "off"}">会话 ${t2.pi_session_env ? "on" : "off"}</span>
        </div>
        <div class="t2-meta">文档: ${esc(t2.docs || "docs/d3-tier2-deep-link.md")} · ${esc(t2.docs_p4 || "docs/p4-tier2-deep-look.md")}</div>
        <div class="t2-meta">${esc(t2.kanban_hint || "")} · ${esc(t2.supervise_hint || "")}</div>
        ${recentHtml}
        <div class="k" style="margin-top:8px">可复制命令（不会自动执行）</div>
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

    let fetchToken = 0;

    function renderAll(s) {
      lastSnap = s;
      renderBadges(s);
      const poll = s.poll || {};
      if ($("pollInfo")) {
        $("pollInfo").textContent =
          "轮询 " + (poll.fingerprint || "—").toString().slice(0, 12) +
          " · 事件 " + (poll.events_count != null ? poll.events_count : "—") +
          (paused ? " · 暂停" : "");
      }
      if ($("genInfo")) {
        $("genInfo").textContent =
          (s.workdir ? "工作区 " + s.workdir : "") +
          (s.generated_at ? " · " + s.generated_at : "");
      }
      if (document.body.classList.contains("mode-studio")) {
        if (typeof window.syncStudioSnapshot === "function") {
          window.syncStudioSnapshot(s);
        }
        return;
      }
      renderProblemWorkbench(s);
      renderSwim(s);
      renderStages(s);
      renderDialogue(s);
      renderTree(s);
      renderThinking(s);
      renderEvents(s);
      renderArtifacts(s);
    }

    async function fetchSnapshot(force) {
      if (paused && !force) return;
      const myToken = ++fetchToken;
      try {
        const slugEl = $("slug");
        const threadEl = $("thread");
        const slug = (slugEl ? slugEl.value.trim() : "") || "test";
        const thread = (threadEl ? threadEl.value.trim() : "") || slug || "test";

        const p = new URLSearchParams();
        p.set("slug", slug);
        p.set("thread", thread);
        if (lastFp && !force) p.set("prev_fp", lastFp);
        if (lastEventsCount != null && !force) p.set("prev_events", String(lastEventsCount));

        if (!force && lastFp) {
          const pr = await fetch("/api/poll?" + p.toString(), { cache: "no-store" });
          if (myToken !== fetchToken) return;
          const pi = await pr.json();
          if (myToken !== fetchToken) return;
          if (pi && pi.dirty === false) {
            if ($("pollInfo")) $("pollInfo").textContent = "轮询 干净 · " + (pi.fingerprint || "").toString().slice(0, 12);
            return;
          }
        }
        const r = await fetch("/api/snapshot?" + p.toString(), { cache: "no-store" });
        if (myToken !== fetchToken) return;
        if (!r.ok) throw new Error("HTTP " + r.status);
        const s = await r.json();
        if (myToken !== fetchToken) return;
        if (s.error && !s.stages) throw new Error(s.error);
        lastFp = (s.poll && s.poll.fingerprint) || lastFp;
        lastEventsCount = (s.poll && s.poll.events_count != null) ? s.poll.events_count : lastEventsCount;
        if ($("fetchErr")) $("fetchErr").textContent = "";
        renderAll(s);
      } catch (err) {
        if (myToken !== fetchToken) return;
        if ($("fetchErr")) $("fetchErr").textContent = "拉取失败: " + err.message;
      }
    }

    function applyControls() {
      const slug = $("slug").value.trim() || "test";
      const thread = $("thread").value.trim() || slug;
      setQS(slug, thread);
      lastFp = null;
      lastEventsCount = null;
      autoJumpedError = false;
      errDismissed = "";
      fetchSnapshot(true);
    }

    function boot() {
      const on = (id, event, handler) => {
        const el = $(id);
        if (el) el.addEventListener(event, handler);
      };

      const q = qs();
      if ($("slug")) $("slug").value = q.slug;
      if ($("thread")) $("thread").value = q.thread || q.slug;

      const onEnter = (id, fn) => {
        const el = $(id);
        if (el) {
          el.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              fn();
            }
          });
        }
      };
      onEnter("slug", applyControls);
      onEnter("thread", applyControls);

      // ESC key closes any open modal and restores focus
      window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          const im = $("intakeModal");
          const am = $("artifactModal");
          if (im && im.classList.contains("show")) {
            im.classList.remove("show");
            if ($("btnOpenIntake")) $("btnOpenIntake").focus();
          }
          if (am && am.classList.contains("show")) {
            am.classList.remove("show");
          }
        }
      });

      on("btnApply", "click", applyControls);
      on("btnRefresh", "click", () => fetchSnapshot(true));
      on("btnFollow", "click", () => {
        followTail = !followTail;
        if ($("btnFollow")) $("btnFollow").classList.toggle("on", followTail);
      });
      on("btnPause", "click", () => {
        paused = !paused;
        if ($("btnPause")) $("btnPause").classList.toggle("on", paused);
        if (!paused) fetchSnapshot(true);
      });
      on("errCopy", "click", copyErrorText);
      on("errJump", "click", jumpToErrorStage);
      on("errDismiss", "click", () => {
        const e = errorPayload(lastSnap || {});
        errDismissed = (e.last_error || "").trim();
        if ($("errBanner")) $("errBanner").classList.remove("show");
      });
      on("btnModelApply", "click", applyModel);
      const markTouch = (id) => {
        const el = $(id);
        if (el) el.addEventListener("change", () => { el.dataset.touched = "1"; });
        if (el) el.addEventListener("input", () => { el.dataset.touched = "1"; });
      };
      ["dlgMode", "dlgResume", "dlgMethods", "dlgNotes", "dlgFresh", "dlgAtStage", "dlgPause"].forEach(markTouch);
      if ($("dlgSubmit")) $("dlgSubmit").addEventListener("click", submitSteer);
      if ($("dlgClear")) $("dlgClear").addEventListener("click", () => {
        ["dlgMode", "dlgResume", "dlgMethods", "dlgNotes", "dlgAtStage"].forEach((id) => {
          const el = $(id);
          if (!el) return;
          el.value = id === "dlgAtStage" ? "manual" : "";
          delete el.dataset.touched;
        });
        if ($("dlgFresh")) $("dlgFresh").checked = false;
        if ($("dlgPause")) { $("dlgPause").checked = false; delete $("dlgPause").dataset.touched; }
        if ($("dlgToast")) {
          $("dlgToast").textContent = "";
          $("dlgToast").classList.remove("err");
        }
        renderDlgCta([]);
      });

      // Problem Workbench & One-Click Intake wiring
      document.querySelectorAll("#wbTabs [data-wb-tab]").forEach((btn) => {
        btn.addEventListener("click", () => switchWbTab(btn.getAttribute("data-wb-tab")));
      });
      const toggleWb = () => {
        wbCollapsed = !wbCollapsed;
        const wb = $("problemWorkbench");
        if (wb) wb.classList.toggle("collapsed", wbCollapsed);
        if ($("wbBtnCollapse")) $("wbBtnCollapse").textContent = wbCollapsed ? "展开 ▼" : "收起 ▲";
        if ($("btnToggleWorkbench")) $("btnToggleWorkbench").classList.toggle("on", !wbCollapsed);
      };
      if ($("wbBtnCollapse")) $("wbBtnCollapse").addEventListener("click", toggleWb);
      if ($("btnToggleWorkbench")) $("btnToggleWorkbench").addEventListener("click", toggleWb);
      if ($("btnOpenIntake")) $("btnOpenIntake").addEventListener("click", openIntakeModal);
      if ($("wbBtnImport")) $("wbBtnImport").addEventListener("click", openIntakeModal);
      if ($("wbBtnRun")) $("wbBtnRun").addEventListener("click", () => runCurrentProblem());
      if ($("btnCloseIntake")) $("btnCloseIntake").addEventListener("click", () => {
        if ($("intakeModal")) $("intakeModal").classList.remove("show");
      });
      if ($("btnCloseArtifact")) $("btnCloseArtifact").addEventListener("click", () => {
        if ($("artifactModal")) $("artifactModal").classList.remove("show");
      });

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

      initStudioWorkbench();
      loadModel();
      applyControls();
      timer = setInterval(() => fetchSnapshot(false), POLL_MS);
    }

