# Tube B 题本地数据清单

这个目录在公开仓库中只保留题目描述、schema 和引用白名单。原竞赛附件从未进入 Git，发布包也不会携带它们；没有原件时，求解器必须返回 `BLOCKED`，不能生成替代数字。

如项目负责人找回其有权使用的原始附件，请在本机按下列结构放置（`raw/` 已被 `.gitignore` 排除）：

```text
raw/
└─ B题 附件/
   ├─ B题 数据/
   │  ├─ 附件1_10种工件/
   │  │  ├─ 圆管1.csv
   │  │  ├─ …
   │  │  └─ 圆管10.csv
   │  └─ 附件2_三批次工件需求数据.xlsx
   └─ B题 结果/
      ├─ result1.xlsx
      ├─ result2.xlsx
      ├─ result3.xlsx
      └─ result4.xlsx
```

运行预检：

```bat
.venv-314\Scripts\python.exe tools\solve_dispatch.py tube_cut_b2026 --mode tube
```

- 数据齐全：执行 Tube 启发式并返回 `FEASIBLE`（不宣称全局最优）。
- 数据不全：返回 `status=BLOCKED`、`objective=null` 和 `missing_inputs`。

不要提交原始竞赛附件、密钥或 `outputs/`。
