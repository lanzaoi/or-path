# ADR-0006：仓库表面卫生（docs 活/归档 + 带外树）

**状态：** Accepted 且已实现（2026-07-30）  
**日期：** 2026-07-30  
**来源：** 架构评审候选 #6

## 背景

- `docs/` 关单/证据/口播/设计笔记平铺，AI 默认上下文过噪。  
- `vendor/` `openpi/` `pi-main/` 体量大且已 gitignore，但仍需写明「带外」。

## 决策

1. **活文档面**仅保留：1.0-closeout、architecture-refactor-status、solver-stack、anti-cosplay、smoke、t3-stage-map、adr/、tickets/、导航 README。  
2. **历史**迁入 `docs/archive/{closeouts,evidence,portfolio,design-notes,ops}/`。  
3. **`docs/OUT_OF_BAND.md`** 声明 vendor/openpi/pi-main 等。  
4. **不改**运行时行为、门禁脚本逻辑（`t3-stage-map.mmd` 仍在 `docs/`）。  
5. 更新 README/AGENTS/specs 中的路径指针。

## 后果

- **正：** 默认可读面更小；导航清晰。  
- **负：** 旧链接需改 `archive/...`。  
- **不变：** specs 优先级；数字真理。
