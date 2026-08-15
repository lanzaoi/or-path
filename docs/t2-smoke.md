# T2 Smoke

## Local gate

```bat
cd /d C:\Users\Lanzao\Desktop\agent
set PYTHONNOUSERSITE=1
set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
.venv-314\Scripts\python.exe scripts\t2_gate.py
```

本地门禁可离线运行：它验证仓库内已归档的 T2 关闭元数据，并打印 `current_live_run=false`，不代表本机刚完成了一次模型调用。

严格检查当前机器的真实多代理 transcript：

```bat
orpath.bat isolation
```

如果没有模型密钥或尚未生成 `.pi-subagents/artifacts/`，该命令失败是预期行为，不能拿归档证据替代当前 LIVE 证据。

## Cloud / online gate

```bat
set T2_REQUIRE_CLOUD=1
.venv-314\Scripts\python.exe scripts\t2_gate_cloud.py
```

## Runners

```bat
.venv-314\Scripts\python.exe orpath\run_t2.py --problem-id shortest_path --solve-mode mock --knowledge-mode seed
.venv-314\Scripts\python.exe orpath\run_t2.py --problem-id tsp_n8 --problem-class tsp --solve-mode ortools --knowledge-mode hybrid
.venv-314\Scripts\python.exe orpath\run_t2.py --problem-id vrp_multi --problem-class vrp --solve-mode ortools --knowledge-mode seed
set ORPATH_LIVE_PI=1
.venv-314\Scripts\python.exe orpath\run_t2.py --problem-id tsp_n8 --problem-class tsp --solve-mode ortools --live-pi --slug t2-live-bridge-tsp
```

## Live multi-agent (Pi / OpenPi)

1. `openpi.bat` → open `C:\Users\Lanzao\Desktop\agent`
2. Model: DeepSeek
3. Prompt sketch:

```text
Use pi-subagents or-researcher then or-modeler on fixtures/t2/tsp_n8.
Read notes if retrieval exists. Schema must not contain objective.
Call tools/solve_ortools.py and tools/validate_solution.py.
Then or-writer draft binding solution JSON only.
```

4. Confirm subagent cards + save screenshot to `docs/archive/evidence/t2-live-evidence-board.png (OpenPi screenshot retired)`
5. Transcripts under `.pi-subagents/artifacts/` (local, gitignored)

## Specs

Read `specs/README.md` first. Freeze: `specs/gates-and-dod.md`.
