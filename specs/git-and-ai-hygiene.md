# Git and AI Hygiene — 仓库与 AI 卫生

**对齐：** `product-flow-sdd.md`  
**状态：** LAW 2026-08-01

---

## 1. 永不提交

| 项 | |
|----|--|
| `.env` / 密钥 / token | |
| 竞赛 PDF 大宗（desktop-attachments、inbox 题） | |
| `outputs/` `notes/` `papers/` `runs/` 默认 | |
| `node_modules/` `pi-main/` `vendor/`（默认 ignore） | |
| `.pi/memory` 数据库 | |

---

## 2. Git 操作

- **禁止**盲目 `git add -A`  
- 提交前 `git status` / diff  
- 大二进制需显式理由  
- 远端：`rika-sleep/or-path`（private）时注意 token 不进 chat  

---

## 3. AI 协作

| | |
|--|--|
| 产品法 | specs 优先于 chat |
| Hermes | 规划/门禁/监控；Pi 做题时不代改 objective |
| DeepSeek | 不做环境/装依赖（用户偏好） |
| 假绿 | 禁止 |

---

## 4. 证据进仓

- closeout / 小证据可进 `docs/archive/evidence`  
- 截图注意 gitignore `*.png` 例外规则  
- 时间线样例可手工挑小文件  

---

## 5. 忽略策略意图

| ignore | 原因 |
|--------|------|
| pi-main | 上游 monorepo 大；npm 装 runtime |
| vendor | 对照源；许可与体积 |
| openpi | 已删防回潮 |

若未来要 push 对照源：单独立项改 ignore + 许可审查。

---

## 6. 检查清单（提交前）

- [ ] 无密钥  
- [ ] 无竞赛原题 PDF  
- [ ] specs 已随行为更新  
- [ ] 相关 gate 想过是否要跑  
