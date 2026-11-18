// --- Dynamic OR Visualization & Convergence Dashboard (Task 6.3 - Huashu 5D Standard) ---
function selectVizTab(targetTab) {
  document.querySelectorAll("#vizTabs [data-viz-tab]").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-viz-tab") === targetTab);
  });
  const panels = {
    gantt: $("vizPanelGantt"),
    routes: $("vizPanelRoutes"),
    microgrid: $("vizPanelMicrogrid"),
    gap: $("vizPanelGap"),
  };
  for (const [k, p] of Object.entries(panels)) {
    if (!p) continue;
    const on = k === targetTab;
    p.style.display = on ? "block" : "none";
    p.classList.toggle("active", on);
  }
}

function initVizTabsOnce() {
  if (studioState.vizTabsBound) return;
  const tabsContainer = $("vizTabs");
  if (!tabsContainer) return;
  studioState.vizTabsBound = true;
  tabsContainer.addEventListener("click", (e) => {
    const tabBtn = e.target.closest("[data-viz-tab]");
    if (!tabBtn) return;
    selectVizTab(tabBtn.getAttribute("data-viz-tab"));
  });
}

function showVizTooltip(text) {
  const tipBox = $("vizInteractiveTooltip");
  const tipText = $("vizTooltipText");
  if (!tipBox || !tipText) return;
  tipText.textContent = text;
  tipBox.style.display = "flex";
}

function hideVizTooltip() {
  const tipBox = $("vizInteractiveTooltip");
  if (tipBox) tipBox.style.display = "none";
}

function bindVizTooltips(container, selector, attrName) {
  container.querySelectorAll(selector).forEach(el => {
    const desc = el.getAttribute(attrName) || "";
    el.addEventListener("mouseenter", () => showVizTooltip(desc));
    el.addEventListener("focus", () => showVizTooltip(desc));
    el.addEventListener("click", () => showVizTooltip(desc));
    el.addEventListener("mouseleave", hideVizTooltip);
    el.addEventListener("blur", hideVizTooltip);
  });
}

function vizEmptyCard(tag, title, detailHtml) {
  return `
    <div class="viz-empty-card" style="padding:36px 20px;text-align:center;background:#fafafa;border:1px dashed var(--border-strong);border-radius:8px;margin:8px 0">
      <div style="font-family:var(--mono);font-size:11px;font-weight:600;color:var(--ink-48);margin-bottom:6px">${esc(tag)}</div>
      <div style="font-weight:600;font-size:13px;color:var(--ink)">${esc(title)}</div>
      ${detailHtml ? `<div style="font-size:11px;color:var(--ink-48);margin-top:6px;max-width:520px;margin-left:auto;margin-right:auto;line-height:1.6">${detailHtml}</div>` : ""}
    </div>
  `;
}

function renderGanttChart(container, solution) {
  if (!container) return;
  const colors = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899", "#84cc16"];

  if (!solution || !Array.isArray(solution.schedule) || solution.schedule.length === 0) {
    container.innerHTML = vizEmptyCard(
      "SCHEDULE UNAVAILABLE",
      "当前算例不含工序时序排程数据",
      "甘特图用于流水/作业车间调度（JSSP / FJSSP / RCPSP）工序可视化。<br/>遵循 Numbers Truth 准则：未返回真实 schedule 数组时不展示虚构排产图。"
    );
    return;
  }

  const rawSched = solution.schedule;
  const mSet = new Set();
  rawSched.forEach(s => {
    if (s.machine != null) mSet.add(Number(s.machine));
  });
  const mSorted = Array.from(mSet).sort((a, b) => a - b);
  const machines = mSorted.map(m => `M${m} 机床/设备`);
  const makespan = Number(solution.metrics?.makespan || Math.max(...rawSched.map(s => s.end || 0)) || 0);

  const ops = rawSched.slice(0, 48).map(s => ({
    m: mSorted.indexOf(Number(s.machine)),
    j: Number(s.job ?? 0),
    s: Number(s.start ?? 0),
    e: Number(s.end ?? 0),
    dur: Number(s.duration ?? (s.end - s.start)),
    name: `工件${s.job ?? 0}-工序${s.task ?? s.op ?? 0}`,
  })).filter(o => o.m >= 0);

  const maxT = Math.max(makespan + 5, 20);
  const startX = 110;
  const plotW = 670;
  const scaleX = plotW / maxT;
  const numM = Math.max(1, machines.length);
  const totalH = Math.max(260, 60 + numM * 34);

  let svg = `<svg class="viz-svg" viewBox="0 0 820 ${totalH}" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<rect width="820" height="${totalH}" fill="#ffffff" rx="10"/>`;

  // Horizontal grid & timeline
  const stepT = maxT > 100 ? (maxT > 300 ? 50 : 20) : 10;
  for (let t = 0; t <= maxT; t += stepT) {
    const x = startX + t * scaleX;
    svg += `<line x1="${x}" y1="20" x2="${x}" y2="${totalH - 45}" stroke="#f1f5f9" stroke-width="1"/>`;
    svg += `<text x="${x}" y="${totalH - 30}" font-size="10" fill="#94a3b8" text-anchor="middle" font-family="var(--mono)">${t}m</text>`;
  }

  // Machine Y rows
  machines.forEach((mLabel, mIdx) => {
    const y = 30 + mIdx * 33;
    svg += `<text x="${startX - 10}" y="${y + 18}" font-size="11" font-weight="600" fill="#475569" text-anchor="end">${esc(mLabel)}</text>`;
    svg += `<line x1="${startX}" y1="${y + 26}" x2="${startX + plotW}" y2="${y + 26}" stroke="#f8fafc" stroke-width="1"/>`;
  });

  // Operation Rectangles with Hover Feedback
  ops.forEach((op, opIdx) => {
    const x = startX + op.s * scaleX;
    const w = Math.max(4, op.dur * scaleX - 2);
    const y = 30 + op.m * 33 + 2;
    const c = colors[op.j % colors.length];
    const desc = `${op.name} · 起止 [${op.s}m -> ${op.e}m] (时长: ${op.dur}m) · 设备: ${machines[op.m] || op.m}`;
    svg += `
      <g class="gantt-bar" data-op-idx="${opIdx}" data-op-desc="${esc(desc)}" tabindex="0">
        <title>${esc(desc)}</title>
        <rect x="${x}" y="${y}" width="${w}" height="22" rx="4" fill="${c}" fill-opacity="0.9" stroke="#ffffff" stroke-width="1.5"/>
        ${w > 32 ? `<text x="${x + w / 2}" y="${y + 14}" font-size="9.5" font-weight="700" fill="#ffffff" text-anchor="middle" pointer-events="none">${esc(op.name.split("-")[0])}</text>` : ''}
      </g>
    `;
  });

  // Makespan marker
  if (makespan > 0) {
    const msX = startX + makespan * scaleX;
    svg += `
      <line x1="${msX}" y1="16" x2="${msX}" y2="${totalH - 42}" stroke="#dc2626" stroke-width="2" stroke-dasharray="4,4"/>
      <rect x="${msX - 52}" y="6" width="104" height="20" rx="4" fill="#fef2f2" stroke="#dc2626" stroke-width="1"/>
      <text x="${msX}" y="20" font-size="9.5" font-weight="700" fill="#dc2626" text-anchor="middle">Makespan = ${makespan}</text>
    `;
  }

  // Legend
  svg += `<g transform="translate(110, ${totalH - 12})">`;
  const numLegend = Math.min(6, Math.max(1, new Set(ops.map(o => o.j)).size));
  for (let j = 0; j < numLegend; j++) {
    const lx = j * 105;
    svg += `
      <rect x="${lx}" y="-6" width="12" height="10" rx="2" fill="${colors[j % colors.length]}"/>
      <text x="${lx + 16}" y="3" font-size="10" fill="#64748b">工件 ${j}</text>
    `;
  }
  svg += `</g></svg>`;

  container.innerHTML = `
    <div style="margin-bottom:12px;font-size:12px;color:var(--ink-60);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        <span><strong>车间排产逐机甘特图</strong> · ${machines.length} 台设备工序时序</span>
        <span style="font-size:10px;background:#ecfdf5;color:#047857;border:1px solid #a7f3d0;padding:2px 7px;border-radius:5px;font-weight:600">真实排产 (${ops.length} 项工序)</span>
      </div>
      <span style="font-family:var(--mono);color:#047857;font-weight:600">Makespan (Cmax): ${makespan}</span>
    </div>
    ${svg}
  `;

  bindVizTooltips(container, ".gantt-bar", "data-op-desc");
}

function renderRouteMap(container, solution) {
  if (!container) return;
  const hasRoutes = solution && Array.isArray(solution.routes) && solution.routes.length > 0;
  const hasTour = solution && Array.isArray(solution.tour) && solution.tour.length > 0;

  if (!hasRoutes && !hasTour) {
    container.innerHTML = vizEmptyCard(
      "ROUTES UNAVAILABLE",
      "当前算例不含车辆或旅行商路径数据",
      "路径图用于车辆路径（VRP / CVRP）或巡检回路（TSP）可视化。<br/>遵循 Numbers Truth 准则：当前输出无 routes 或 tour 字段时不生成路径拓扑。"
    );
    return;
  }

  const palette = ["#1d4ed8", "#059669", "#6d28d9", "#d97706", "#db2777"];
  const pureTourMode = hasTour && !hasRoutes;

  let normalizedRoutes = [];
  if (hasRoutes) {
    normalizedRoutes = solution.routes;
  } else if (hasTour) {
    normalizedRoutes = [{ route: solution.tour, distance: solution.objective }];
  }

  const nodeSeq = [];
  normalizedRoutes.forEach(r => {
    const arr = Array.isArray(r.route) ? r.route : (Array.isArray(r) ? r : []);
    arr.forEach(n => {
      const sid = String(n);
      if (!nodeSeq.includes(sid)) nodeSeq.push(sid);
    });
  });

  const numNodes = nodeSeq.length;
  const customers = [];
  const radiusX = 270;
  const radiusY = 85;
  nodeSeq.forEach((nid, idx) => {
    const angle = (idx / Math.max(1, numNodes)) * 2 * Math.PI - Math.PI / 2;
    const px = 410 + radiusX * Math.cos(angle);
    const py = 140 + radiusY * Math.sin(angle);
    customers.push({ id: nid, idx, x: px, y: py, name: `站点 ${nid}` });
  });

  const nodeMap = new Map();
  customers.forEach(c => nodeMap.set(String(c.id), c));

  const startId = nodeSeq[0] || "0";
  const depot = { x: 410, y: 140, name: "场站 / 起点" };
  const routes = normalizedRoutes.slice(0, 6).map((r, idx) => {
    const cColor = palette[idx % palette.length];
    const routeArr = Array.isArray(r.route) ? r.route : (Array.isArray(r) ? r : []);
    const routeStops = [];
    if (!pureTourMode) routeStops.push(depot);
    routeArr.forEach(nid => {
      const pt = nodeMap.get(String(nid));
      if (pt) routeStops.push(pt);
    });
    if (pureTourMode && routeStops.length > 1) {
      routeStops.push(routeStops[0]);
    } else if (!pureTourMode) {
      routeStops.push(depot);
    }
    return {
      id: hasRoutes ? `车队 ${idx + 1}` : "巡检回路",
      color: cColor,
      pts: routeStops,
      dist: r.distance != null ? `${r.distance}` : (solution.objective != null ? `${solution.objective}` : "已规划"),
    };
  });

  let svg = `<svg class="viz-svg" viewBox="0 0 820 280" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<rect width="820" height="280" fill="#ffffff" rx="8"/>`;

  // Background concentric grid
  svg += `<circle cx="410" cy="140" r="110" fill="none" stroke="#f1f5f9" stroke-width="1.5" stroke-dasharray="4,4"/>`;
  svg += `<circle cx="410" cy="140" r="210" fill="none" stroke="#f8fafc" stroke-width="1.5"/>`;

  // Draw route lines
  routes.forEach(route => {
    let pathD = "";
    route.pts.forEach((pt, pIdx) => {
      pathD += (pIdx === 0 ? "M " : " L ") + `${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`;
    });
    svg += `<path d="${pathD}" fill="none" stroke="${route.color}" stroke-width="2" stroke-opacity="0.85" stroke-dasharray="5,3"/>`;
  });

  // Draw customer nodes
  customers.forEach(c => {
    const isStart = pureTourMode && c.id === startId;
    const desc = isStart
      ? `${c.name} · 回路起点与终点（第 1 站）`
      : `${c.name} · 访问次序第 ${c.idx + 1} 站`;
    const stroke = isStart ? "#059669" : "#1d4ed8";
    const fill = isStart ? "#059669" : "#ffffff";
    const r = isStart ? 8 : 6;
    const label = isStart ? `${esc(c.id)} (起点)` : esc(c.id);
    svg += `
      <g class="route-node" data-node-desc="${esc(desc)}" tabindex="0" role="button" aria-label="${esc(desc)}" style="cursor:pointer">
        <title>${esc(desc)}</title>
        <circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="20" fill="rgba(0,0,0,0.001)" pointer-events="all"/>
        <circle cx="${c.x.toFixed(1)}" cy="${c.y.toFixed(1)}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="2.2"/>
        <text x="${c.x.toFixed(1)}" y="${(c.y + 17).toFixed(1)}" font-size="9.5" font-family="var(--mono)" font-weight="${isStart ? 700 : 600}" fill="${isStart ? "#047857" : "#475569"}" text-anchor="middle">${label}</text>
      </g>`;
  });

  // Draw center depot only for multi-vehicle routes
  if (!pureTourMode) {
    const depotDesc = "配送中心 / 车队出发与回场场站";
    svg += `
      <g class="route-node" data-node-desc="${esc(depotDesc)}" tabindex="0" role="button" aria-label="${esc(depotDesc)}" style="cursor:pointer">
        <title>${esc(depotDesc)}</title>
        <rect x="392" y="122" width="36" height="48" fill="rgba(0,0,0,0.001)" pointer-events="all"/>
        <rect x="396" y="126" width="28" height="28" rx="6" fill="#111827" stroke="#ffffff" stroke-width="2"/>
        <text x="410" y="144" font-size="10.5" font-weight="700" font-family="var(--mono)" fill="#ffffff" text-anchor="middle">D0</text>
        <text x="410" y="166" font-size="10" font-weight="600" fill="#374151" text-anchor="middle">场站</text>
      </g>`;
  }

  svg += `</svg>`;

  const objLabel = solution.objective != null ? `目标耗费/里程: ${solution.objective}` : "路径规划完成";

  container.innerHTML = `
    <div style="margin-bottom:12px;font-size:12px;color:var(--ink-60);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        <span><strong>路径拓扑视图</strong> · ${customers.length} 个站点 <span style="font-size:10px;color:var(--ink-48)">(拓扑序)</span></span>
        <span style="font-size:10px;background:#ecfdf5;color:#047857;border:1px solid #a7f3d0;padding:2px 7px;border-radius:5px;font-weight:600">真实路径数据</span>
      </div>
      <span style="font-family:var(--mono);color:#047857;font-weight:600">${esc(objLabel)}</span>
    </div>
    ${svg}
  `;

  bindVizTooltips(container, ".route-node", "data-node-desc");
}

function renderConvergenceGapCurve(container, solution) {
  if (!container) return;
  const rawGap = solution?.gap_history || solution?.metrics?.gap_history || solution?.meta?.gap_history;

  if (!Array.isArray(rawGap) || rawGap.length < 2) {
    container.innerHTML = vizEmptyCard(
      "NO CONVERGENCE HISTORY",
      "本次为单阶段直接求解，无迭代收敛轨迹",
      "遵循 Numbers Truth 准则：仅当求解器返回真实迭代上下界轨迹（gap_history）时绘制收敛曲线。"
    );
    return;
  }

  const iters = rawGap.map((pt, idx) => ({
    i: pt.i ?? idx,
    ub: Number(pt.ub ?? pt.upper_bound ?? 0),
    lb: Number(pt.lb ?? pt.lower_bound ?? 0),
    gap: Number(pt.gap ?? 0),
  }));

  const startX = 90;
  const plotW = 680;
  const startY = 35;
  const plotH = 190;

  const scaleX = plotW / Math.max(1, iters.length - 1);
  const allVals = iters.flatMap(p => [p.ub, p.lb]).filter(v => !isNaN(v) && v > 0);
  const minVal = allVals.length > 0 ? Math.min(...allVals) * 0.9 : 0;
  const maxVal = allVals.length > 0 ? Math.max(...allVals) * 1.1 : 100;
  const scaleY = plotH / Math.max(1, maxVal - minVal);
  const getY = (val) => startY + plotH - (val - minVal) * scaleY;

  let svg = `<svg class="viz-svg" viewBox="0 0 820 280" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<rect width="820" height="280" fill="#ffffff" rx="10"/>`;

  iters.forEach((pt, idx) => {
    const x = startX + idx * scaleX;
    svg += `<line x1="${x}" y1="${startY}" x2="${x}" y2="${startY + plotH}" stroke="#f8fafc" stroke-width="1"/>`;
    svg += `<text x="${x}" y="${startY + plotH + 18}" font-size="10" fill="#94a3b8" text-anchor="middle" font-family="var(--mono)">Iter ${pt.i}</text>`;
  });

  const ubPath = iters.map((pt, idx) => `${idx === 0 ? "M" : "L"} ${startX + idx * scaleX} ${getY(pt.ub)}`).join(" ");
  svg += `<path d="${ubPath}" fill="none" stroke="#2563eb" stroke-width="2.5"/>`;

  const lbPath = iters.map((pt, idx) => `${idx === 0 ? "M" : "L"} ${startX + idx * scaleX} ${getY(pt.lb)}`).join(" ");
  svg += `<path d="${lbPath}" fill="none" stroke="#7c3aed" stroke-width="2.5" stroke-dasharray="4,4"/>`;

  const last = iters[iters.length - 1];
  const lastX = startX + (iters.length - 1) * scaleX;
  const lastY = getY(last.ub);
  const gapStr = last.gap.toFixed(2);

  svg += `
    <g>
      <rect x="${lastX - 110}" y="${lastY - 32}" width="125" height="22" rx="6" fill="#ecfdf5" stroke="#10b981" stroke-width="1.5"/>
      <text x="${lastX - 48}" y="${lastY - 18}" font-size="10" font-weight="700" fill="#047857" text-anchor="middle">Gap: ${gapStr}%</text>
    </g>
  `;

  svg += `</svg>`;

  container.innerHTML = `
    <div style="margin-bottom:12px;font-size:12px;color:var(--ink-60);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <span><strong>下界与启发式上界收敛曲线</strong></span>
      <span style="font-family:var(--mono);color:#047857;font-weight:600">最终 Gap: ${gapStr}%</span>
    </div>
    ${svg}
  `;
}

function renderMicrogridChart(container, solution) {
  if (!container) return;
  const subs = solution?.subproblems || {};
  const q1 = subs.q1 || {};
  const grid = Array.isArray(q1.purchase_kwh) ? q1.purchase_kwh.map(Number) : [];
  const soc = Array.isArray(q1.soc_kwh) ? q1.soc_kwh.map(Number) : [];
  if (grid.length === 0 && soc.length === 0) {
    container.innerHTML = vizEmptyCard(
      "MICROGRID DATA UNAVAILABLE",
      "当前问题未包含分时购电与储能 SoC 调度序列",
      ""
    );
    return;
  }
  const N = Math.max(grid.length, soc.length, 24);
  const maxGrid = Math.max(...grid, 10);
  const maxSoc = Math.max(...soc, 10);
  const startX = 56, plotW = 730, baseY = 205, plotH = 155;
  const barW = Math.max(8, (plotW / N) * 0.58);
  let bars = "", socPts = [];
  for (let h = 0; h < N; h++) {
    const x = startX + (h + 0.5) * (plotW / N);
    const g = grid[h] || 0;
    const bh = (g / maxGrid) * plotH;
    bars += `<rect class="mg-bar" x="${(x - barW / 2).toFixed(1)}" y="${(baseY - bh).toFixed(1)}" width="${barW.toFixed(1)}" height="${bh.toFixed(1)}" rx="3" fill="#3b82f6" opacity="0.78" data-mg="时段 ${h + 1}: 购电 ${g.toFixed(2)} kWh | SoC ${(soc[h] || 0).toFixed(2)} kWh" />`;
    if (h < soc.length) {
      const sy = baseY - (soc[h] / maxSoc) * plotH;
      socPts.push(`${h === 0 ? "M" : "L"} ${x.toFixed(1)} ${sy.toFixed(1)}`);
    }
    if (h % 3 === 0) bars += `<text x="${x.toFixed(1)}" y="${baseY + 16}" font-size="9.5" fill="#64748b" text-anchor="middle">${h + 1}h</text>`;
  }
  const chips = [
    ["Q1 基础运行成本", q1.total_cost],
    ["Q2 有序充电", subs.q2?.total_cost],
    ["Q3 屋顶光伏协同", subs.q3?.total_cost],
    ["Q4 优化配置最优年成本", subs.q4_3?.total_cost ?? subs.q4_2?.total_cost],
  ].filter(([, v]) => v != null).map(([k, v]) =>
    `<span style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:4px 10px;font-size:11px;font-family:var(--mono)"><strong>${k}:</strong> ${Number(v).toLocaleString()}</span>`
  ).join("");
  const svg = `<svg class="viz-svg" viewBox="0 0 820 245" xmlns="http://www.w3.org/2000/svg"><rect width="820" height="245" fill="#ffffff" rx="10"/><line x1="${startX}" y1="${baseY}" x2="${startX + plotW}" y2="${baseY}" stroke="#cbd5e1"/>${bars}${socPts.length ? `<path d="${socPts.join(" ")}" fill="none" stroke="#10b981" stroke-width="2.6"/>` : ""}</svg>`;
  container.innerHTML = `<div style="margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;font-size:12px"><span><strong>微电网 24h 网购电柱状与储能 SoC 曲线</strong></span><div style="display:flex;gap:6px;flex-wrap:wrap">${chips}</div></div>${svg}`;
  bindVizTooltips(container, ".mg-bar", "data-mg");
}

function renderVisualizations(solution) {
  const badge = $("vizDomainBadge");
  if (badge) {
    badge.textContent = DOMAIN_BADGES[studioState.domainKey] || DOMAIN_BADGES.default;
  }

  renderGanttChart($("vizPanelGantt"), solution);
  renderRouteMap($("vizPanelRoutes"), solution);
  renderMicrogridChart($("vizPanelMicrogrid"), solution);
  renderConvergenceGapCurve($("vizPanelGap"), solution);

  initVizTabsOnce();
  const hasMg = Boolean(solution?.subproblems?.q1?.purchase_kwh?.length);
  const pc = String(solution?.problem_class || "").toLowerCase();
  const hasRouteData = (Array.isArray(solution?.routes) && solution.routes.length > 0)
    || (Array.isArray(solution?.tour) && solution.tour.length > 0);
  if (hasMg || pc.includes("microgrid") || studioState.domainKey === "microgrid") {
    selectVizTab("microgrid");
  } else if (hasRouteData) {
    selectVizTab("routes");
  } else if (Array.isArray(solution?.schedule) && solution.schedule.length > 0) {
    selectVizTab("gantt");
  } else if (Array.isArray(solution?.gap_history) && solution.gap_history.length >= 2) {
    selectVizTab("gap");
  }
}
