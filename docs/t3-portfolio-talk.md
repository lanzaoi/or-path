# T3 portfolio talk track (~30s)

**One-liner:** LangGraph 产品骨架完整垂直 —— Sqlite checkpointer + 续跑/from-stage + 图内 bridge_pi（默认 before_research） + NodeContext 横切 + orpath.bat CLI + 矩阵门禁（SP42/TSP45/VRP58/TW58）。

**30 秒口述：**

1. **问题：** T1/T2 后需要统一的产品运行时，支持持久化、脏制品检测、阶段快照、Pi 桥接可配置插入、CLI 续跑，而非每次从头。  
2. **做法：** `graph_product` + `run_orpath` 实现全阶段机（orchestrate → retrieve → bridge_pi → research → model → gate_schema → solve → gate_validate → ... → provenance）；每节点退出写 `stages/N_xxx.json` + 更新 `artifact_hashes.json`；bridge_pi 默认在 research 前（可配 before_retrieve）；NodeContext 运行时 owner assert（非 solve 节点禁写 objective）；t1 保持旧 graph；t2 薄委托产品图。  
3. **关卡：** `t3_lg_gate`（拓扑、owner、happy path、status、脏检 exit-3、ckpt、snapshots）；`t3_gate`（业务矩阵 SP/TSP/VRP + vrp_tw 58 + hybrid）；R1/R2 内部通过。  
4. **入口：** `orpath.bat run | status --thread-id ID | resume | list | gate-t3`（relocatable）。  
5. **证据：** `runs/<tid>/stages/` + `artifact_hashes.json` + `outputs/<slug>-*.json` + `provenance.md` + `specs/t3-lg-skeleton.md` + gate 真实输出。

**不要说：**  
- 完整 T3 交付（codegen 沙箱、compose/k8s 硬、OpenPi 大改、Teams/bus、新题类等 Q12 OUT 项）。  
- 全局最优保证（仅来自 solve+validate 工具）。  
- live Pi 多 Agent 全矩阵截图/口播/dual-frame resume 演示已完成（工程骨架 PASS，作品集可视化可能需人工残留）。  
- Hermes 就是 OR 运行时本身。

**证据指针：** `docs/t3-lg-closeout.md`、`outputs/t3-lg/`、`runs/orpath.sqlite`、`orpath/stage_map.json`。
