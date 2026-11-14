// Studio workbench entrypoint
function boot() {
  syncHeaderNavState();
  initStudioConfig();
  initStudioFiles();
  initStudioAnalyze();
  initStudioResult();
  initVizTabsOnce();
  setPipelineStage("probe", "待命");
}
