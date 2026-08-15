# 公开 VRP 主线：CVRPLIB A-n32-k5

Tube 原始附件不在公开仓库，因此新的可复现实验主线使用公开 CVRPLIB 实例 `A-n32-k5`。官方页面给出：31 个客户、5 辆车、容量 100、最优参考值 784。

## 一键运行

```bat
orpath.bat vrp-baseline
```

等价命令：

```bat
.venv-314\Scripts\python.exe eval_or_bench\run_cvrp_baseline.py --time-limit-ms 5000
```

链路固定为：公开数据 → `locations.json` 模型 → OR-Tools baseline → `validate_solution.py` 重算 → 与公开参考值比较 → JSON 报告。

## 诚实口径

- CVRPLIB 参考解：`OPTIMAL` / 784。
- 本仓库 OR-Tools Routing：只标 `FEASIBLE`，即使碰巧得到 784 也不自行宣称证明了最优性。
- baseline PASS 表示候选解可行、目标值重算一致、公开参考解也通过同一 validator；不表示算法优于公开最优值。

## 下一步工作包

1. 固定多个随机种子/时间预算，报告均值、最好值、运行时间和 gap。
2. 加入更强的 CVRP 求解器（如 PyVRP）作为第二条 baseline，但保持同一 validator。
3. 扩展到 10–20 个 CVRPLIB 实例，按规模分层，不挑单一好看的案例。
4. 只有精确求解器给出证明时，候选解才可升级为 `OPTIMAL`。

## 来源

- https://galgos.inf.puc-rio.br/cvrplib/en/instances/1
- https://galgos.inf.puc-rio.br/cvrplib/en/download/instance/4
- https://galgos.inf.puc-rio.br/cvrplib/en/download/bks/4
