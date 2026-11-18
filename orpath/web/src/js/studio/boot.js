// Studio workbench entrypoint
function boot() {
  syncHeaderNavState();
  const slugInp = $("studioSlugInput");
  const urlSlug = (new URLSearchParams(location.search).get("slug") || "").trim();
  if (slugInp && urlSlug && urlSlug !== "test") {
    slugInp.value = urlSlug;
  }
  initStudioConfig();
  fetchEnvStatus();
  initStudioFiles();
  initStudioAnalyze();
  initStudioResult();
  initVizTabsOnce();
  if (typeof initWatchDrawer === "function") initWatchDrawer();
  if (slugInp) {
    slugInp.addEventListener("change", () => {
      if (typeof resetStudioRunUI === "function") resetStudioRunUI(false);
    });
  }
  setPipelineStage("idle", "待命");
}
