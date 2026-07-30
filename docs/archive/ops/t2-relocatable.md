# Relocatable install (ORPATH_HOME)

## Problem we fixed

Pi/OpenPi bind extensions and `or-*` agents to the **project root you open**.
Treating one absolute desktop path as the only place multi-agent works is wrong
for a product.

## Model

| Variable | Meaning | Default |
|----------|---------|---------|
| `ORPATH_HOME` | **Install root** (code, `.pi/agents`, runtime, tools) | Directory of `orpath.bat` / `orpath.sh` |
| `ORPATH_WORKDIR` | **Case/data root** (notes, outputs, papers) | Same as `ORPATH_HOME` |

You may:

- Copy/clone the tree to `D:\apps\orpath` and run from there
- Set `ORPATH_WORKDIR=E:\cases\demo` for data separation (tools that honor workdir)

## Launcher

```bat
orpath.bat doctor
orpath.bat isolation
orpath.bat gate
orpath.bat t2 --problem-id tsp_n8 --solve-mode mock
orpath.bat pi -p --provider deepseek --model deepseek-v4-flash "..."
orpath.bat openpi
```

Unix/git-bash: `./orpath.sh doctor`

`orpath.bat openpi` runs **doctor first** and refuses to start if multi-agent
prerequisites are missing (no silent cosplay).

## Doctor

```bat
orpath.bat doctor
REM or:
.venv-314\Scripts\python.exe scripts\orpath_doctor.py
```

Checks: agents md, `pi-subagents` in `.pi/settings.json`, tools, runtime Pi CLI, specs, workdir writable.

## OpenPi note (honest)

OpenPi still opens a GUI project folder. For multi-agent you must open
**`ORPATH_HOME`** (the install tree), not an unrelated folder like `OOP`.
The launcher sets cwd/env and prints that contract; it cannot rewrite OpenPi
internals if the UI later switches folder.

## Verification

```bat
set ORPATH_HOME=%CD%
orpath.bat doctor
orpath.bat isolation
```

Copy the install tree elsewhere, set `ORPATH_HOME` to the new path, run doctor again.
