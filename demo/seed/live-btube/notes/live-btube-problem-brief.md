# Problem brief — live-btube

## Sources
- `inbox/b-tube-live-once/problem.pdf` (pdf)
- ocr_backend: `pdf_text`

## Full problem statement (normalized)
## Source: `inbox/b-tube-live-once/problem.pdf`



2026 杭州电子科技大学第 27 届大学生数学建模竞赛题目
（请先阅读“杭州电子科技大学数学建模竞赛须知”）
B 题 异形圆管工件下料优化问题
在装备制造、汽车零部件及工业管路等领域，异形圆管工件应用广泛。某管材加工企业
采用激光切割方式加工一批异形圆管工件。经过筛选，现选取其中 10 种工件作为研究对象，
每个工件的外半径为 20mm，内半径为 19mm，壁厚 1mm。企业生产中可选用的标准母材长度
为 9m、10m、11m、12m。附件 1 给出了各类工件的离散坐标数据，每个工件由一组空间点
（X,Y,Z）描述其外形特征。
图 1 工件切割示意图（由 ChatGPT 生成）
企业希望依据工件的几何信息，合理确定母材选取、工件拼接与下料加工方案，在满足
生产需求的前提下尽可能减少管材浪费。除节材目标外，企业还关注加工过程的组织效率。
在实际生产中，若不同类型工件频繁交替加工，会增加排产和现场操作的复杂性，不利于同
类工件的连续生产。因此，在方案设计中，企业希望相同工件尽可能集中、连续加工，尽量
减少不同工件之间的切换次数。
为突出主要矛盾，本题暂不考虑切割损耗与首尾夹持余量。各问题均以所选母材总长度
尽可能小为主要优化目标，以总共切收益尽可能大为次要目标（除问题一），并进一步以不
同工件之间的切换次数尽可能少为再次目标。
请建立合适的数学模型，完成下列任务。
问题一：设 10 种工件每种均需加工 50 件。请根据附件 1 计算各类工件的轴向占用长
度，并在允许组合选用 4 种标准母材的条件下，设计合理的下料方案，给出母材长度选取、


工件在各根母材上的加工顺序、母材利用率及总切换次数，使所选母材总长度尽可能小，并
将结果保存至附件 result1.xlsx 中。
问题二：在问题一的基础上，考虑相邻工件端部之间可能存在共切效应。任意两种工件
相邻加工时，可存在 4 种端部拼接方式。请根据 10种工件的几何形状，建立省料计算的通
用模型，求出各工件对在不同端部组合下的共切收益。针对问题一的下料方案，保持各工件
分配到各母材不变，仅在每根母材内部对各工件重新排序。给出工件新加工顺序以及拼接方
式，计算总共切收益、总切换次数，并将结果保存至附件 result2.xlsx中。
问题三：在问题一、二的基础上，结合工件之间拼接的共切收益，制定所有工件的新下
料方案，综合考虑母材总长度、总共切收益、总切换次数，给出母材长度选取、工件拼接方
式、加工顺序及母材利用率，将结果保存至附件 result3.xlsx中。
由企业经验设定：若某批次加工后剩余母材长度不小于 0.2m，则该余料可入库，并在
后续批次中优先被使用；否则视为废料。
问题四：附件 2 给出了 3 个连续加工批次中 10 种工件的需求数据。请在问题三的基础
上，保证每个批次内工件加工后的余料尽可能少并结合余料优先使用原则，建立多批次加工
优化模型，确定各批次中的余料调用、新母材选取、工件拼接方式、加工顺序及母材利用率，
使 3 个批次总共使用的标准母材总长度尽可能小，总共切收益尽可能高、总切换次数尽可能
少，并将结果保存至附件 result4.xlsx中。
附录 A：术语说明
1.轴向占用长度
工件的轴向占用长度是指该工件沿圆管轴线方向的投影长度，即工件在轴向上的最左
切割位置与最右切割位置之间的距离。
2.共切效应与共切收益
共切效应：当两个工件在同一根母材上相邻加工，且其相邻端部进行拼接时，可减少中
间多余切割而节约材料。
共切收益：对每种工件，先确定其轴向方向，再将轴向投影值较小的一端记为 L 端，较
大的一端记为 R 端。设工件i 和工件 j 的两个端部分别记为 L 和 R ，两工件相邻加工时可存
在 4种端部拼接方式，即  LL LR RL RR、 、 、 。记 ab
ij 为工件i 的端部a 与工件 j 的端部b
拼接时的共切收益，则有


    ab ab
ij i j ijl l L , a { R },b L,     ，
其中 il 为工件i 的轴向占用长度， jl 为工件 j 的轴向占用长度， ab
ijL 为工件i 、 j 在给定端部
组合a,b 下，按最佳方式拼接后，两工件拼接加工所需的最小轴向占用长度。
3.母材、余料与废料
母材是指用于切割加工的原始圆管材料。
余料是指某批次加工结束后剩余、且仍具有后续利用价值的母材部分。
废料是指不能继续用于后续加工的剩余母材部分。
4.母材利用率
在问题一中，由于不考虑共切效应，总体母材利用率定义为全部工件的轴向占用长度总
和与所选母材总长度之比；在问题二至四中，由于考虑共切效应，总体母材利用率定义为全
部工件独立加工时的轴向占用长度总和减去总共切收益后，与所选母材总长度之比。单根母
材上的利用率定义方式类似。
附录 B：提交附件格式说明
每一问的结果，需填入附件中“结果”文件夹中对应的 excel 表格中，然后压缩包随论
文一并提交。填写规范请参照附件中的“结果填写说明”文档。
·统一采用以下记号与单位：
1. 长度单位统一使用 mm（所有结果建议保留至千分位）；
2. 批次编号统一记为 B1、B2、B3；
3. 母材编号建议记为 M1、M2、M3，…；
4. 余料编号建议记为 R1、R2、R3，…。

## Subproblems (Q1…Qn)
### Q1
设 10 种工件每种均需加工 50 件。请根据附件 1 计算各类工件的轴向占用长

度，并在允许组合选用 4 种标准母材的条件下，设计合理的下料方案，给出母材长度选取、


工件在各根母材上的加工顺序、母材利用率及总切换次数，使所选母材总长度尽可能小，并
将结果保存至附件 result1.xlsx 中。

Must deliver later: result1.xlsx

### Q2
在问题一的基础上，考虑相邻工件端部之间可能存在共切效应。任意两种工件

相邻加工时，可存在 4 种端部拼接方式。请根据 10种工件的几何形状，建立省料计算的通
用模型，求出各工件对在不同端部组合下的共切收益。针对问题一的下料方案，保持各工件
分配到各母材不变，仅在每根母材内部对各工件重新排序。给出工件新加工顺序以及拼接方
式，计算总共切收益、总切换次数，并将结果保存至附件 result2.xlsx中。

Must deliver later: result2.xlsx

### Q3
在问题一、二的基础上，结合工件之间拼接的共切收益，制定所有工件的新下

料方案，综合考虑母材总长度、总共切收益、总切换次数，给出母材长度选取、工件拼接方
式、加工顺序及母材利用率，将结果保存至附件 result3.xlsx中。
由企业经验设定：若某批次加工后剩余母材长度不小于 0.2m，则该余料可入库，并在
后续批次中优先被使用；否则视为废料。

Must deliver later: result3.xlsx

### Q4
附件 2 给出了 3 个连续加工批次中 10 种工件的需求数据。请在问题三的基础

上，保证每个批次内工件加工后的余料尽可能少并结合余料优先使用原则，建立多批次加工
优化模型，确定各批次中的余料调用、新母材选取、工件拼接方式、加工顺序及母材利用率，
使 3 个批次总共使用的标准母材总长度尽可能小，总共切收益尽可能高、总切换次数尽可能
少，并将结果保存至附件 result4.xlsx中。
附录 A：术语说明
1.轴向占用长度
工件的轴向占用长度是指该工件沿圆管轴线方向的投影长度，即工件在轴向上的最左
切割位置与最右切割位置之间的距离。
2.共切效应与共切收益
共切效应：当两个工件在同一根母材上相邻加工，且其相邻端部进行拼接时，可减少中
间多余切割而节约材料。
共切收益：对每种工件，先确定其轴向方向，再将轴向投影值较小的一端记为 L 端，较
大的一端记为 R 端。设工件i 和工件 j 的两个端部分别记为 L 和 R ，两工件相邻加工时可存
在 4种端部拼接方式，即  LL L…

Must deliver later: result4.xlsx

## Data assets
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/10圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/1圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/2圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/3圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/4圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/5圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/6圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/7圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/8圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/9圆管.stp` — kind=stp, role=geometry
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管1.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管10.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管2.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管3.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管4.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管5.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管6.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管7.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管8.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件1_10种工件/圆管9.csv` — kind=csv, role=unknown
- `inbox/b-tube-live-once/assets/B题 附件/B题 数据/附件2_三批次工件需求数据.xlsx` — kind=xlsx, role=demand_table
- `inbox/b-tube-live-once/assets/B题 附件/B题 结果/result1.xlsx` — kind=xlsx, role=result_template
- `inbox/b-tube-live-once/assets/B题 附件/B题 结果/result2.xlsx` — kind=xlsx, role=result_template
- `inbox/b-tube-live-once/assets/B题 附件/B题 结果/result3.xlsx` — kind=xlsx, role=result_template
- `inbox/b-tube-live-once/assets/B题 附件/B题 结果/result4.xlsx` — kind=xlsx, role=result_template
- `inbox/b-tube-live-once/assets/B题 附件/B题 结果/结果填写说明.docx` — kind=other, role=unknown
- `inbox/b-tube-live-once/problem.pdf` — kind=pdf, role=unknown

## Objectives (qualitative)
- 同工件之间的切换次数尽可能少为再次目标。
- 组合a,b 下，按最佳方式拼接后，两工件拼接加工所需的最小轴向占用长度。

## Constraints (qualitative)
- See problem statement; constraints not auto-extracted as a clean list.

## Deliverables
- result1.xlsx
- result2.xlsx
- result3.xlsx
- result4.xlsx

## Ambiguities / OCR gaps
- None detected by deterministic parse.

## Non-goals for intake
- No objective / optimal numeric claims
- No calling solvers or writing solution.json
- Soft class hints are not a validated schema
