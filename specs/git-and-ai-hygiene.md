# Git and AI Hygiene — Git 与 AI 卫生

## 默认禁止（除非用户当次明确授权）

- `git add .` / `git add -A`  
- `force push`、`reset --hard`、`clean -fd`  
- 改写已推送 commit  
- 全局 git config 乱改  
- 提交 `.env`、token、密钥、大体积 `node_modules/`、`openpi` 依赖树、knowledge 工作区缓存  

## 默认要求

1. 提交前 `git status` + `git diff`  
2. `git add <精确路径>`  
3. 提交信息：`feat(t2):` / `fix:` / `test:` / `docs(t2):` / `chore:`  
4. 验证标签诚实：smoke ≠ e2e ≠ cloud 全过  

## 建议忽略（实现时核对 `.gitignore`）

```text
.env
runs/
knowledge/mineru_out/
knowledge/lightrag_ws/
knowledge/bm25/
knowledge/fts/
knowledge/corpus/*.pdf
.pi/memory/
.pi-subagents/
**/node_modules/
openpi/  # 若已是独立重树
vendor/  # 按现有策略
outputs/ notes/ papers/  # 或仅忽略大产物，evidence 精选入库
```

## AI 实现座右铭（Task）

```text
Only Task: <name>
Allowed paths: <list>
Forbidden: scope creep, git add ., secrets, weaken tests, capability bragging
Read first: specs/README.md + relevant specs
Verify: <command> → expect <result>
Report: changes / paths / verify output / specs updated?
```

## 与 specs 的更新

行为变更时 **同一 PR/同一提交批次** 更新 specs；禁止「代码已变、法条仍旧」长期漂移。
