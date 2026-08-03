# T3-mini — CVRPTW 叶（详细）

**状态：** 矩阵叶，非 T3 标题  
**对齐：** `t3-lg-skeleton.md` · `solvers-and-validate.md`

---

## 1. 范围

| 项 | 值 |
|----|-----|
| Fixture | `fixtures/t3/vrp_tw/` |
| class | 仍为 `vrp`；TW 在 fixture 级 |
| Gold objective | **58**（仅来自 solver+validate） |
| 能力 | capacity + time_windows（可等待；start≤due） |

---

## 2. Solve

- `tools/solve_ortools.py` Time dimension  
- transit = travel + service_at_from  
- 目标仍为 **距离**  
- meta：`has_time_windows` 等  

---

## 3. Validate

- 无 TW 的 fixture：检查 ok + detail 无窗  
- 有 TW：仿真到达与服务开始  

---

## 4. 路径解析

fixture_dir 顺序：**t3 → t2 → t1**

---

## 5. 门禁

含于 `scripts/t3_gate.py`。  
保持 t1/t2 绿；不重开其 DoD。

---

## 6. 非目标

- 新 problem_class 枚举名 `vrp_tw`（可选以后）  
- 把 TW 叶当成整个 T3 故事  

---

## 7. Verify

```bat
.venv-314\Scripts\python.exe scripts\t3_gate.py
.venv-314\Scripts\python.exe tools\solve_ortools.py vrp_tw --class vrp
```
