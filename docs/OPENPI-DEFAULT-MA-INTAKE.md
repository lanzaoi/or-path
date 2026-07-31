# OpenPi 默认多 Agent + Intake（操作说明）

**法条计划：** `.hermes/plans/2026-07-31_160212-openpi-default-ma-intake.md`  
**用户入口：** 仓库根 `ORPATH.md`

## 改了什么

1. **产品默认 live MA = ON**（`orpath.bat` / `run_orpath` 未设 env 时写 `ORPATH_LIVE_SUBAGENT=1`）  
2. **门禁 / isolation / paper-gate** 启动时强制 `ORPATH_LIVE_SUBAGENT=0`  
3. **`--auto-intake` + `inbox/`** 发现题面；`orpath.bat run-full` / `intake-auto` / `gui-demo`  
4. **`orpath.bat openpi`** 打印默认策略 + doctor + 启动 OpenPi  

## 人测封条（你签）

- [ ] 不启动 Hermes  
- [ ] `orpath.bat openpi` 控制台可见 LIVE=1 提示  
- [ ] `orpath.bat gui-demo` 或 `run-full` 产生 stages  
- [ ] 有题面时存在 `*-intake.json`  
- [ ] LIVE=1 时 `outputs/.agents/<slug>/` 日志含 `"name":"subagent"`  
- [ ] `set ORPATH_LIVE_SUBAGENT=0` 后不再 spawn（或 skip）

## 命令速查

```bat
orpath.bat run-full --slug X --thread-id X
orpath.bat run --no-live-subagent --slug cheap --thread-id cheap --fresh
orpath.bat intake-auto --slug X
orpath.bat gui-demo
```
