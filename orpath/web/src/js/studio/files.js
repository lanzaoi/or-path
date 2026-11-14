// Studio folder/file intake, size caps & preset loader
// --- Studio Files & Drag-and-Drop ---
const MAX_STUDIO_FILES = 200;
const MAX_STUDIO_TOTAL_BYTES = 25 * 1024 * 1024; // 25 MB
const MAX_STUDIO_FILE_BYTES = 10 * 1024 * 1024; // 10 MB per file
const MAX_RECURSION_DEPTH = 12;


function updateFileListUI() {
  if (!$("studioFileList")) return;
  if (studioState.loadedFiles.length === 0) {
    $("studioFileList").innerHTML = `<span style="color:var(--ink-48)">尚未载入附件 (可拖入题面文件夹、坐标矩阵、需求清单或表格)</span>`;
    if ($("studioFileActionNotice")) $("studioFileActionNotice").style.display = "none";
    return;
  }
  const totalBytes = studioState.loadedFiles.reduce((acc, f) => acc + (f.size || 0), 0);
  const kbStr = fmtKB(totalBytes);
  $("studioFileList").innerHTML = `
    <div style="font-weight:700;color:var(--blue);margin-bottom:6px">
      📂 已解析待研判文件清单 (${studioState.loadedFiles.length} 个文件 · 共 ${kbStr}):
    </div>
    <div style="max-height:120px;overflow-y:auto;background:var(--surface-2);border-radius:6px;padding:8px 10px;font-family:var(--mono);line-height:1.6">
      ${studioState.loadedFiles.map(f => `<div>📄 ${esc(f.rel_path)} <span style="color:var(--ink-48);font-size:10px">(${fmtKB(f.size)})</span></div>`).join("")}
    </div>
  `;

  // 智能建议 slug 标识
  const slugEl = $("studioSlugInput");
  if (slugEl && (slugEl.value === "case-studio" || slugEl.value === "case-my-problem" || !slugEl.value)) {
    const first = studioState.loadedFiles[0]?.rel_path || "";
    const base = first.split("/")[0].split(".")[0].replace(/[^a-zA-Z0-9_-]/g, "").toLowerCase();
    if (base && base.length >= 2) slugEl.value = "case-" + base;
  }

  // 展现快捷启动横幅
  const notice = $("studioFileActionNotice");
  if (notice) {
    notice.style.display = "flex";
    const countEl = $("studioFileReadyText");
    if (countEl) countEl.textContent = `已就绪 ${studioState.loadedFiles.length} 个文件 (${kbStr})`;
  }
}

function readFileAsBase64(file, relPath) {
  return new Promise((resolve) => {
    if (file.size > MAX_STUDIO_FILE_BYTES) {
      showToast(`文件 ${relPath} 超过 10MB 单文件限制，已跳过`, "warn");
      resolve(null);
      return;
    }
    const reader = new FileReader();
    const timer = setTimeout(() => {
      resolve({ rel_path: relPath, content_base64: "", size: file.size || 0 });
    }, 5000);
    reader.onload = () => {
      clearTimeout(timer);
      const b64 = (reader.result || "").split(",")[1] || "";
      resolve({ rel_path: relPath, content_base64: b64, size: file.size || 0 });
    };
    reader.onerror = () => {
      clearTimeout(timer);
      resolve({ rel_path: relPath, content_base64: "", size: file.size || 0 });
    };
    reader.readAsDataURL(file);
  });
}

async function ingestFileList(files, preserveRelPath) {
  if (!files || !files.length) return;
  for (const f of files) {
    if (studioState.loadedFiles.length >= MAX_STUDIO_FILES) {
      showToast(`文件总数已达上限 (${MAX_STUDIO_FILES})，多余文件已忽略`, "warn");
      break;
    }
    const curBytes = studioState.loadedFiles.reduce((acc, x) => acc + (x.size || 0), 0);
    if (curBytes + (f.size || 0) > MAX_STUDIO_TOTAL_BYTES) {
      showToast("文件总体积已达上限 (25MB)，后续文件已忽略", "warn");
      break;
    }
    const rel = preserveRelPath ? (f.webkitRelativePath || f.name) : f.name;
    const obj = await readFileAsBase64(f, rel);
    if (obj) studioState.loadedFiles.push(obj);
  }
}

async function scanFiles(items, rawFiles) {
  let usedEntries = false;
  if (items && items.length > 0 && items[0].webkitGetAsEntry) {
    const entries = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item && item.webkitGetAsEntry) {
        try {
          const entry = item.webkitGetAsEntry();
          if (entry) entries.push(entry);
        } catch (_) {}
      }
    }
    if (entries.length > 0) {
      usedEntries = true;
      async function readEntry(entry, path = "", depth = 0) {
        if (depth > MAX_RECURSION_DEPTH) {
          console.warn("Directory recursion exceeded max depth: " + path);
          return;
        }
        if (studioState.loadedFiles.length >= MAX_STUDIO_FILES) {
          showToast(`文件总数已达上限 (${MAX_STUDIO_FILES})，多余文件已忽略`, "warn");
          return;
        }
        const curBytes = studioState.loadedFiles.reduce((acc, f) => acc + (f.size || 0), 0);
        if (curBytes >= MAX_STUDIO_TOTAL_BYTES) {
          showToast("文件总体积已达上限 (25MB)，后续文件已忽略", "warn");
          return;
        }
        if (entry.isFile) {
          const f = await new Promise((res) => entry.file(res, () => res(null)));
          if (f) {
            const rel = path ? `${path}/${f.name}` : f.name;
            const obj = await readFileAsBase64(f, rel);
            if (obj && studioState.loadedFiles.length < MAX_STUDIO_FILES) {
              studioState.loadedFiles.push(obj);
            }
          }
        } else if (entry.isDirectory) {
          const dirReader = entry.createReader();
          const readEntriesBatch = () => new Promise((res) => dirReader.readEntries(res, () => res([])));
          let batch = await readEntriesBatch();
          while (batch.length > 0) {
            for (const sub of batch) {
              if (studioState.loadedFiles.length >= MAX_STUDIO_FILES) break;
              await readEntry(sub, path ? `${path}/${entry.name}` : entry.name, depth + 1);
            }
            if (studioState.loadedFiles.length >= MAX_STUDIO_FILES) break;
            batch = await readEntriesBatch();
          }
        }
      }
      for (const ent of entries) {
        await readEntry(ent, "", 0);
      }
    }
  }
  if (!usedEntries && rawFiles && rawFiles.length > 0) {
    await ingestFileList(rawFiles, true);
  }
  updateFileListUI();
}


function initStudioFiles() {
  const dropzone = $("studioDropzone");
  const fileInput = $("studioFileInput");
  const filesOnlyInput = $("studioFilesOnlyInput");
  const fileList = $("studioFileList");
  const btnSelectFolder = $("btnPickFolder");
  const btnSelectFiles = $("btnPickFiles");
  
  if (btnSelectFolder && fileInput) {
    btnSelectFolder.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }
  if (btnSelectFiles && filesOnlyInput) {
    btnSelectFiles.addEventListener("click", (e) => {
      e.stopPropagation();
      filesOnlyInput.click();
    });
  }
  if (dropzone) {
    dropzone.addEventListener("click", () => {
      if (fileInput) fileInput.click();
    });
  }
  
  if (dropzone) {
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });
    dropzone.addEventListener("drop", async (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      studioState.loadedFiles = [];
      if (e.dataTransfer) {
        await scanFiles(e.dataTransfer.items, e.dataTransfer.files);
      }
    });
  }
  
  if (fileInput) {
    fileInput.addEventListener("change", async () => {
      studioState.loadedFiles = [];
      await ingestFileList(fileInput.files, true);
      fileInput.value = "";
      updateFileListUI();
    });
  }
  
  if (filesOnlyInput) {
    filesOnlyInput.addEventListener("change", async () => {
      studioState.loadedFiles = [];
      await ingestFileList(filesOnlyInput.files, false);
      filesOnlyInput.value = "";
      updateFileListUI();
    });
  }
  
  // --- Preset Data Loader ---
  if ($("btnStudioLoadPreset")) {
    $("btnStudioLoadPreset").addEventListener("click", () => {
      $("studioSlugInput").value = "case-tsp-8";
      $("studioPromptInput").value = "8工位智能巡检规划：请根据坐标规划一条封闭巡检路线，要求遍历8个站点并返回起点，总里程最短。";
      const coords = { coords: [
        { id: 0, x: 0, y: 0 }, { id: 1, x: 10, y: 5 }, { id: 2, x: 20, y: 10 },
        { id: 3, x: 30, y: 15 }, { id: 4, x: 40, y: 20 }, { id: 5, x: 50, y: 25 },
        { id: 6, x: 60, y: 30 }, { id: 7, x: 70, y: 35 }
      ]};
      const b64Coords = btoa(JSON.stringify(coords));
      const b64Prob = btoa("# 8工位巡检问题\n问题一：访问8个工位并返回起点\n");
      studioState.loadedFiles = [
        { rel_path: "problem.md", content_base64: b64Prob, size: 120 },
        { rel_path: "data/coords.json", content_base64: b64Coords, size: 240 },
      ];
      updateFileListUI();
    });
  }
}
