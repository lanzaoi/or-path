# inbox/ — 题面投放区（auto-intake）

把题面文件丢这里，然后：

```bat
orpath.bat run-full --slug myrun --thread-id myrun
```

或只审题：

```bat
orpath.bat intake-auto --slug myrun
```

## 接受的扩展名

`.md` · `.txt` · `.pdf` · `.png` · `.jpg` · `.jpeg` · `.webp`

## 规则

- 只扫 `inbox/` 下一层文件或一层子目录内的文件（防附件深树误吞）
- 忽略 `README*` / `.gitkeep`
- **大 PDF 可不进 git**（本目录默认仅 README；题面本地放即可）
- 无文件时 `run-full` → `skip_intake`（legacy fixture 路径）并打日志

## 证据

- `outputs/<slug>-intake.json`
- `notes/<slug>-problem-brief.md`
