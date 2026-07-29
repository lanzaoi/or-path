# Pi runtime (runnable CLI)

Official npm package install for day-to-day use of Pi in this project.

- `@earendil-works/pi-coding-agent@0.82.1`
- `pi-subagents@0.37.2` (nicobailon)

From repo root:

```bat
pi.bat
```

Git Bash:

```bash
./pi.sh
```

First time: set model keys via `/login` inside Pi, or env:

```bat
set DEEPSEEK_API_KEY=...
set GEMINI_API_KEY=...
pi.bat
```


Note: `pi-main/` is the monorepo source (A1). Full monorepo `npm run build` may need a clean install + Node >= 22.19. This `runtime/` folder is the practical launcher.


GUI: use repo-root `openpi.bat` / `openpi.sh` (OpenPi Electron), not pi-web.
