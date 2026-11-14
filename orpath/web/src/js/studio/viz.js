// --- Dynamic OR Visualization & Convergence Dashboard (Task 6.3 - Huashu 5D Standard) ---
function initVizTabsOnce() {
  if (studioState.vizTabsBound) return;
  const tabsContainer = $("vizTabs");
  if (!tabsContainer) return;
  studioState.vizTabsBound = true;
  tabsContainer.addEventListener("click", (e) => {
    const tabBtn = e.target.closest("[data-viz-tab]");
    if (!tabBtn) return;
    const targetTab = tabBtn.getAttribute("data-viz-tab");
    document.querySelectorAll("#vizTabs [data-viz-tab]").forEach(b => {
      b.classList.toggle("active", b === tabBtn);
    });
    const panels = {
      gantt: $("vizPanelGantt"),
      routes: $("vizPanelRoutes"),
      gap: $("vizPanelGap"),
    };
    for (const [k, p] of Object.entries(panels)) {
      if (!p) continue;
      if (k === targetTab) {
        p.style.display = "block";
        p.classList.add("active");
      } else {
        p.style.display = "none";
        p.classList.remove("active");
      }
    }
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

function renderGanttChart(container, solution) {
  if (!container) return;
  const colors = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444", "#06b6d4", "#ec4899", "#84cc16"];

  if (!solution || !Array.isArray(solution.schedule) || solution.schedule.length === 0) {
    container.innerHTML = `
      <div class="viz-empty-card" style="padding:42px 20px;text-align:center;background:var(--surface-2);border:1px dashed var(--border);border-radius:12px;margin:10px 0">
        <div style="font-size:32px;margin-bottom:8px">🏭</div>
        <div style="font-weight:600;font-size:13px;color:#334155">当前算例不含工序时序排程数据</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:6px;max-width:520px;margin-left:auto;margin-right:auto;line-height:1.6">
          甘特图专用于流水/作业车间调度（JSSP/FJSSP/RCPSP）工序可视化。<br/>根据 <strong>Numbers Truth</strong> 准则：当前输出无真实 schedule 数组，系统严禁虚构排产基准。
        </div>
      </div>
    `;
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
    <div style="margin-bottom:12px;font-size:12px;color:#475569;display:flex;justify-content:space-between;align-items:center;flex-wrap:gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        <span>🏭 <strong>车间排产逐机甘特图</strong> · ${machines.length} 台设备工序时序</span>
        <span style="font-size:10px;background:#ecfdf5;color:#059669;padding:2px 8px;border-radius:6px;font-weight:700">✓ 真实排产数据 (${ops.length} 项工序)</span>
      </div>
      <span style="font-family:var(--mono);color:#059669;font-weight:700">总完工时间 (Cmax): ${makespan}</span>
    </div>
    ${svg}
  `;

  // Attach hover listener for interactive tooltip
  container.querySelectorAll(".gantt-bar").forEach(bar => {
    bar.addEventListener("mouseenter", () => showVizTooltip(bar.getAttribute("data-op-desc") || ""));
    bar.addEventListener("mouseleave", hideVizTooltip);
  });
}

function renderRouteMap(container, solution) {
  if (!container) return;
  const hasRoutes = solution && Array.isArray(solution.routes) && solution.routes.length > 0;
  const hasTour = solution && Array.isArray(solution.tour) && solution.tour.length > 0;

  if (!hasRoutes && !hasTour) {
    container.innerHTML = `
      <div class="viz-empty-card" style="padding:42px 20px;text-align:center;background:var(--surface-2);border:1px dashed var(--border);border-radius:12px;margin:10px 0">
        <div style="font-size:32px;margin-bottom:8px">🗺️</div>
        <div style="font-weight:600;font-size:13px;color:#334155">当前算例不含车辆或旅行商路径规划数据</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:6px;max-width:520px;margin-left:auto;margin-right:auto;line-height:1.6">
          路径图专用于车辆路径 (VRP/CVRP) 或旅行商回路 (TSP) 可视化。<br/>根据 <strong>Numbers Truth</strong> 准则：当前输出无 routes 或 tour 路径数据，系统严禁伪造路径拓扑。
        </div>
      </div>
    `;
    return;
  }

  const palette = ["#2563eb", "#059669", "#7c3aed", "#d97706", "#ec4899"];
  const depot = { x: 410, y: 140, name: "场站/起点 0" };

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
    customers.push({ id: nid, x: px, y: py, name: `站点 ${nid}` });
  });

  const nodeMap = new Map();
  customers.forEach(c => nodeMap.set(String(c.id), c));

  const routes = normalizedRoutes.slice(0, 6).map((r, idx) => {
    const cColor = palette[idx % palette.length];
    const routeArr = Array.isArray(r.route) ? r.route : (Array.isArray(r) ? r : []);
    const routeStops = [depot];
    routeArr.forEach(nid => {
      const pt = nodeMap.get(String(nid));
      if (pt) routeStops.push(pt);
    });
    routeStops.push(depot);
    return {
      id: hasRoutes ? `车队 ${idx + 1}` : "巡检回路",
      color: cColor,
      pts: routeStops,
      dist: r.distance != null ? `${r.distance}` : (solution.objective != null ? `${solution.objective}` : "已规划"),
    };
  });

  let svg = `<svg class="viz-svg" viewBox="0 0 820 280" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<rect width="820" height="280" fill="#ffffff" rx="10"/>`;

  // Background concentric grid
  svg += `<circle cx="410" cy="140" r="110" fill="none" stroke="#f1f5f9" stroke-width="1.5" stroke-dasharray="4,4"/>`;
  svg += `<circle cx="410" cy="140" r="210" fill="none" stroke="#f8fafc" stroke-width="1.5"/>`;

  // Draw route lines
  routes.forEach(route => {
    let pathD = "";
    route.pts.forEach((pt, pIdx) => {
      pathD += (pIdx === 0 ? "M " : " L ") + `${pt.x} ${pt.y}`;
    });
    svg += `<path d="${pathD}" fill="none" stroke="${route.color}" stroke-width="2" stroke-opacity="0.85" stroke-dasharray="6,3"/>`;
  });

  // Draw customer nodes
  customers.forEach(c => {
    const desc = `${c.name} · 拓扑受访节点`;
    svg += `
      <g class="route-node" data-node-desc="${esc(desc)}" tabindex="0" style="cursor:pointer">
        <title>${esc(desc)}</title>
        <circle cx="${c.x}" cy="${c.y}" r="6" fill="#ffffff" stroke="#2563eb" stroke-width="2"/>
        <text x="${c.x}" y="${c.y + 15}" font-size="9" font-family="var(--mono)" font-weight="600" fill="#475569" text-anchor="middle">${esc(c.id)}</text>
      </g>
    `;
  });

  // Draw Depot
  svg += `
    <g style="cursor:pointer">
      <rect x="396" y="126" width="28" height="28" rx="6" fill="#dc2626" stroke="#ffffff" stroke-width="2"/>
      <text x="410" y="144" font-size="11" font-weight="800" fill="#ffffff" text-anchor="middle">★</text>
      <text x="410" y="166" font-size="10" font-weight="700" fill="#dc2626" text-anchor="middle">起点</text>
    </g>
  `;

  svg += `</svg>`;

  const objLabel = solution.objective != null ? `目标耗费/里程: ${solution.objective}` : "路径规划完成";

  container.innerHTML = `
    <div style="margin-bottom:12px;font-size:12px;color:#475569;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <div style="display:flex;align-items:center;gap:8px">
        <span>🗺️ <strong>车辆/巡检路径拓扑图</strong> · ${customers.length} 个受访站点 <span style="font-size:10px;color:#94a3b8">(拓扑序排布)</span></span>
        <span style="font-size:10px;background:#ecfdf5;color:#059669;padding:2px 8px;border-radius:6px;font-weight:700">✓ 真实路径规划数据</span>
      </div>
      <span style="font-family:var(--mono);color:#059669;font-weight:700">${esc(objLabel)}</span>
    </div>
    ${svg}
  `;

  container.querySelectorAll(".route-node").forEach(node => {
    node.addEventListener("mouseenter", () => showVizTooltip(node.getAttribute("data-node-desc") || ""));
    node.addEventListener("mouseleave", hideVizTooltip);
  });
}

function renderConvergenceGapCurve(container, solution) {
  if (!container) return;
  const rawGap = solution?.gap_history || solution?.metrics?.gap_history || solution?.meta?.gap_history;

  if (!Array.isArray(rawGap) || rawGap.length < 2) {
    container.innerHTML = `
      <div class="viz-empty-card" style="padding:42px 20px;text-align:center;background:var(--surface-2);border:1px dashed var(--border);border-radius:12px;margin:10px 0">
        <div style="font-size:32px;margin-bottom:8px">📈</div>
        <div style="font-weight:600;font-size:13px;color:#334155">当前求解为单阶段直接交付，无多轮迭代收敛历程</div>
        <div style="font-size:11px;color:#94a3b8;margin-top:6px;max-width:520px;margin-left:auto;margin-right:auto;line-height:1.6">
          根据 <strong>Numbers Truth</strong> 准则：系统绝不伪造虚假收敛曲线与 0.00% 严密闭合结论。<br/>仅当求解器输出真实迭代历程数据（如松弛下界与上界轨迹）时呈现收敛分析。
        </div>
      </div>
    `;
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
    <div style="margin-bottom:12px;font-size:12px;color:#475569;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
      <span>📈 <strong>数学下界与启发式上界真实收敛 Gap 曲线</strong></span>
      <span style="font-family:var(--mono);color:#059669;font-weight:700">最终 Gap: ${gapStr}%</span>
    </div>
    ${svg}
  `;
}

function renderVisualizations(solution) {
  const badge = $("vizDomainBadge");
  if (badge) {
    badge.textContent = DOMAIN_BADGES[studioState.domainKey] || DOMAIN_BADGES.default;
  }

  renderGanttChart($("vizPanelGantt"), solution);
  renderRouteMap($("vizPanelRoutes"), solution);
  renderConvergenceGapCurve($("vizPanelGap"), solution);

  initVizTabsOnce();
}
