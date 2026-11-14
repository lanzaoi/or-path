// Watch polling controller & main bootstrap
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

  syncHeaderNavState();
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
  ["dlgMode", "dlgResume", "dlgMethods", "dlgNotes", "dlgFresh"].forEach(markTouch);
  if ($("dlgSubmit")) $("dlgSubmit").addEventListener("click", submitSteer);
  if ($("dlgClear")) $("dlgClear").addEventListener("click", () => {
    ["dlgMode", "dlgResume", "dlgMethods", "dlgNotes"].forEach((id) => {
      const el = $(id);
      if (!el) return;
      el.value = "";
      delete el.dataset.touched;
    });
    if ($("dlgFresh")) $("dlgFresh").checked = false;
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
  initIntakeModalControls();

  loadModel();
  applyControls();
  timer = setInterval(() => fetchSnapshot(false), POLL_MS);
}
