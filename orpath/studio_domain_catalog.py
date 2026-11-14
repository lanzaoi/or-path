"""Static OR domain catalog, keyword classifier, and algorithm comparison table."""
from __future__ import annotations

from typing import Any


def detect_problem_class_from_text(combined_text: str) -> str:
    """Deterministic keyword-based problem class detection for Studio fallback."""
    low = (combined_text or "").lower()
    if any(k in low for k in ("多联", "多联骨牌", "多米诺", "拼图", "格点覆盖", "polyomino")):
        return "polyomino_cover"
    if any(k in low for k in ("微电网", "微网", "光伏", "储能", "电池", "microgrid", "pv", "bess")):
        return "microgrid_dispatch"
    if any(k in low for k in ("下料", "圆管", "切削", "余料", "tube")):
        return "tube_cut"
    if any(k in low for k in ("巡检", "旅行商", "环路", "tsp", "工位", "回路")):
        return "tsp"
    if any(k in low for k in ("车间", "作业车间", "工序", "makespan", "jssp", "fjssp", "job shop", "jobshop", "完工时间", "换模", "ft06")):
        return "job_shop"
    if any(k in low for k in ("rcpsp", "项目排程", "工期", "紧前关系", "psplib", "关键路径", "可再生资源", "j30")):
        return "rcpsp"
    if any(k in low for k in ("设施选址", "选址", "cflp", "sscflp", "厂址", "配送中心选址", "facility location", "cap41")):
        return "facility_location"
    if any(k in low for k in ("枢纽", "p-hub", "辐射网络", "中继", "hub location", "转运", "cab10", "cab25")):
        return "hub_location"
    if any(k in low for k in ("二次指派", "qap", "qaplib", "布局优化", "设备布局", "车间布局", "quadratic assignment", "nug12")):
        return "qap"
    if any(k in low for k in ("装箱", "装柜", "下料装载", "bin pack", "bin_pack", "binpacking", "1d装箱", "3d装箱", "三维装箱", "knapsack", "背包")):
        return "bin_packing"
    if any(k in low for k in ("网络流", "费用流", "最大流", "二分图匹配", "指派匹配", "min cost flow", "bipartite", "matching", "多商品流")):
        return "network_flow"
    if any(k in low for k in ("投资组合", "资产配置", "夏普比率", "均值方差", "markowitz", "portfolio", "收益率", "方差", "有效前沿")):
        return "portfolio_opt"
    if any(k in low for k in ("qubo", "ising", "量子退火", "自旋玻璃", "max cut", "最大割", "退火", "spin glass")):
        return "qubo_ising"
    if any(k in low for k in ("图着色", "染色", "色数", "graph color", "coloring", "dsatur", "冲突调度")):
        return "graph_coloring"
    if any(k in low for k in ("最大团", "最大独立集", "max clique", "independent set", "clique", "对偶互补", "团数", "独立数", "myciel")):
        return "max_clique"
    if any(k in low for k in ("随机规划", "两阶段", "stochastic", "evpi", "vss", "农民问题", "farmer")):
        return "stochastic_lp"
    if any(k in low for k in ("排班", "轮班", "护士排班", "staff rostering", "rostering", "shift", "排班表")):
        return "staff_rostering"
    if any(k in low for k in ("批量", "批次", "lot sizing", "lot_sizing", "wagner whitin", "wagner_whitin", "clsp", "订货提前期")):
        return "lot_sizing"
    if any(k in low for k in ("博弈", "纳什均衡", "game theory", "nash")):
        return "game_theory"
    if any(k in low for k in ("车辆路径", "车队", "vrp", "cvrp", "vrptw", "容量限制", "准时制")):
        return "vrp"
    if any(k in low for k in ("最短路", "导航", "shortest", "路径规划", "dijkstra")):
        return "shortest_path"
    return "unregistered"


_CATALOG: dict[str, tuple[str, str, list[dict[str, Any]], str]] = {
    "tsp": (
        "旅行商与闭环巡检规划 (TSP)",
        "ortools",
        [
            {
                "name": "OR-Tools Routing / CP-SAT (约束规划/整型规划)",
                "recommended": True,
                "pros": "工业级求解速度，内建强大的全局最优回路剪枝与邻域搜索，尺度支持几百站点",
                "cons": "对输入点阵的欧氏距离或距离矩阵完整性有严格要求",
            },
            {
                "name": "HiGHS / 混合整数线性规划 (MIP - MTZ/DFJ 消除子回路)",
                "recommended": False,
                "pros": "具备数学精确对偶界限与最优性证明，小规模站点表现优良",
                "cons": "DFJ 子回路消除约束随节点数呈指数级爆炸，稍大尺度极易超时",
            },
            {
                "name": "Christofides 启发式 / 最近邻快速贪婪法",
                "recommended": False,
                "pros": "毫秒级快速给出可行初始解，无外部第三方求解器依赖",
                "cons": "近似比理论上限 1.5，在大规模工业巡检中常多消耗 10%~20% 冗余里程",
            },
        ],
        (
            "根据数据探针检测，算例包含工位空间坐标信息。对于中小规模封闭巡检路线规划问题，"
            "OR-Tools CP-SAT 能在秒级内求得严格数学全局最优巡检路线并消除任何子环路，"
            "兼具精确性与工程鲁棒性，因此作为第一推荐算法。"
        ),
    ),
    "shortest_path": (
        "单源/多源最短路径规划 (Shortest Path)",
        "networkx",
        [
            {
                "name": "NetworkX Dijkstra / A* 算法",
                "recommended": True,
                "pros": "经典图论算法，针对非负权重图时间复杂度 O(E + V log V)，执行极快",
                "cons": "不支持负权回路",
            },
            {
                "name": "HiGHS 混合整数规划 (MIP 单商品流模型)",
                "recommended": False,
                "pros": "便于在最短路基础上额外叠加复杂的非线性业务约束或排队约束",
                "cons": "求解耗时较直接图论遍历高出数十倍",
            },
        ],
        "网络拓扑与点边关系明确，推荐采用标准图论 Dijkstra 算法求取严格最优单源最短路径。",
    ),
    "tube_cut": (
        "圆管下料与余料复用多批次优化 (Tube Cut BFD)",
        "tube",
        [
            {
                "name": "最佳适应降序 (BFD) + 列生成背包优化",
                "recommended": True,
                "pros": "针对多材质、多批次、非对称焊缝与余料复用场景定制，大幅压低原材料损耗率",
                "cons": "对长短零件批量配合有敏感性",
            },
            {
                "name": "首次适应贪婪切割 (First-Fit Decreasing)",
                "recommended": False,
                "pros": "计算速度极快，易于现场人工对照实施",
                "cons": "余料无法跨批次优化流转，原材料利用率偏低",
            },
        ],
        "检测到原材料切割与需求清单数据，推荐采用降序最佳适应与余料复用算法降低损耗。",
    ),
    "polyomino_cover": (
        "多联骨牌精确覆盖与拼合 (Polyomino Exact Cover)",
        "polyomino",
        [
            {
                "name": "Dancing Links X (DLX) / CP-SAT 精确覆盖",
                "recommended": True,
                "pros": "基于双向十字链表的极速回溯剪枝，能在巨大状态空间中瞬间判定无解或找出所有拼合解",
                "cons": "需要严格的网格离散化矩阵表达",
            },
            {
                "name": "简单几何贪婪放置",
                "recommended": False,
                "pros": "无矩阵构建开销",
                "cons": "极易陷入死胡同，无法证明不可行性",
            },
        ],
        "检测到网格或骨牌覆盖结构，推荐采用精确覆盖 Dancing Links / CP-SAT 算法求解。",
    ),
    "job_shop": (
        "作业车间调度优化 (JSSP / FJSSP)",
        "jssp",
        [
            {
                "name": "PyJobShop / OR-Tools CP-SAT 析取约束规划",
                "recommended": True,
                "pros": "针对机器无重叠区间与工序先后顺序列生成极速剪枝，工业基准求解性能世界领先",
                "cons": "超大规模需分解",
            },
            {
                "name": "遗传算法 / 模拟退火 (GA/SA 元启发式)",
                "recommended": False,
                "pros": "结构灵活易嵌入定制局部搜索",
                "cons": "缺少全局最优性数学证明",
            },
        ],
        "检测到工件工序与机器排产约束，推荐采用 PyJobShop CP-SAT 求解全局最优 Makespan。",
    ),
    "rcpsp": (
        "多资源约束项目排程 (RCPSP)",
        "rcpsp",
        [
            {
                "name": "OR-Tools CP-SAT 累积调度精确规划 (Cumulative Scheduling)",
                "recommended": True,
                "pros": "严格建模有限可再生资源多重容量限制与紧前时序，精准识别关键路径与零总时差",
                "cons": "资源类型过多时变量增加",
            },
            {
                "name": "传统关键路径法 (CPM / PERT)",
                "recommended": False,
                "pros": "计算极其简单快速",
                "cons": "完全忽视资源瓶颈，实景中多不可行",
            },
        ],
        "检测到工序紧前时序与有限资源约束，推荐采用 CP-SAT 累积调度模型求解最短工期与关键路径。",
    ),
    "facility_location": (
        "有容量限制设施选址优化 (CFLP / SCND)",
        "facility",
        [
            {
                "name": "混合整数线性规划 (MIP - HiGHS / OR-Tools)",
                "recommended": True,
                "pros": "严格权衡设施固定投资建造成本与运输运费，全局最优保证，支持单源/多源配置",
                "cons": "极大网络需分解",
            },
            {
                "name": "连续重心法 / 几何重力模型",
                "recommended": False,
                "pros": "快速得到连续坐标",
                "cons": "无法处理离散候选厂址与工厂容量上限",
            },
        ],
        "检测到固定投资成本与客户需求容量约束，推荐采用 MIP 混合整数规划求解最优选址与配送流。",
    ),
    "hub_location": (
        "枢纽辐射网络选址优化 (p-Hub Location)",
        "hub_location",
        [
            {
                "name": "Ernst & Krishnamoorthy 3-下标流 MIP 模型",
                "recommended": True,
                "pros": "精确刻画干线转运折扣因子与集散网络，全局最优保证",
                "cons": "三下标变量规模较高",
            },
            {
                "name": "先聚类后选址两阶段启发式",
                "recommended": False,
                "pros": "计算速度快",
                "cons": "无法折算跨枢纽网络转运折扣，总成本偏高",
            },
        ],
        "检测到节点间流量交互矩阵与转运规模折扣，推荐采用三下标流 MIP 精确求解最优枢纽选址。",
    ),
    "qap": (
        "二次指派与车间布局优化 (QAP)",
        "qap",
        [
            {
                "name": "SciPy FAQ 凸松弛 + 2-opt 局部搜索混合算法",
                "recommended": True,
                "pros": "凸松弛全局初始点结合 2-opt 极速交换，高概率命中 QAPLIB 金标已知最优",
                "cons": "强 NP-Hard，超大维度需多起点并行",
            },
            {
                "name": "全排列暴力枚举",
                "recommended": False,
                "pros": "穷举绝对精确",
                "cons": "阶乘级复杂度 O(n!)，n>12 时耗时不可承受",
            },
        ],
        "检测到距离矩阵与流矩阵乘积的二次搬运成本，推荐采用 FAQ 凸松弛与 2-opt 混合求解。",
    ),
    "bin_packing": (
        "多维工业装箱与空间装载优化 (Bin Packing 1D/2D/3D)",
        "bin_packing",
        [
            {
                "name": "混合整数规划 / 极端点几何放置启发式 (Extreme Point 3D-BPP)",
                "recommended": True,
                "pros": "支持长宽高 6 自由度旋转与空间无重叠碰撞硬约束，空间利用率高",
                "cons": "异构小包数量超大时求解时间上升",
            },
            {
                "name": "首次适应降序法 (FFD / First-Fit Decreasing)",
                "recommended": False,
                "pros": "计算极快",
                "cons": "在复杂三维货柜装载中产生严重空洞浪费",
            },
        ],
        "检测到货件多维几何尺寸与承重限制，推荐采用空间极值点 6-DOF 放置算法最大化装载率。",
    ),
    "network_flow": (
        "网络流与二部图最优匹配 (Network Flow & Matching)",
        "network_flow",
        [
            {
                "name": "NetworkX 最小费用流与增广路 / OR-Tools GLOP 多商品流",
                "recommended": True,
                "pros": "利用网络全幺模矩阵性质，直接线性规划即可得整型极值解，求解极速",
                "cons": "非网络拓扑约束需转化为广义网络",
            },
            {
                "name": "通用整型规划 MIP",
                "recommended": False,
                "pros": "通用性强",
                "cons": "未利用网络全幺模结构，计算开销大一个数量级",
            },
        ],
        "检测到节点供需平衡与弧容量/费用结构，推荐采用专业网络流算法求解。",
    ),
    "portfolio_opt": (
        "Markowitz 均值-方差现代投资组合优化 (Portfolio Optimization)",
        "portfolio_opt",
        [
            {
                "name": "PyPortfolioOpt / SciPy 二次凸规划 (QP / SLSQP)",
                "recommended": True,
                "pros": "精确解析求解最大夏普比率、最小方差并平滑绘制有效前沿，支持整数股离散配置",
                "cons": "输入资产协方差矩阵须半正定",
            },
            {
                "name": "等权重平均配置 (1/N 策略)",
                "recommended": False,
                "pros": "无参数估计误差",
                "cons": "完全忽略资产间相关性与风险对冲收益",
            },
        ],
        "检测到资产预期收益与风险协方差矩阵，推荐采用标准二次凸规划求解最大夏普比率最优资产权重。",
    ),
    "qubo_ising": (
        "量子退火与自旋玻璃优化 (QUBO & Ising)",
        "qubo_ising",
        [
            {
                "name": "D-Wave dimod 模拟退火 (Simulated Annealing) / 精确穷举",
                "recommended": True,
                "pros": "原生支持二次无约束二值优化 (QUBO) 与 Ising 自旋映射，自适应降温退火",
                "cons": "硬约束需要通过大惩罚项 (Penalty multiplier) 嵌入",
            },
            {
                "name": "贪婪局部搜索 (Greedy Local Search)",
                "recommended": False,
                "pros": "快速单步改进",
                "cons": "极易陷入多峰复杂能量曲面上的局部极小值深井",
            },
        ],
        "检测到二次二值相互作用矩阵与 Ising 偏置，推荐采用 D-Wave 模拟退火采样器寻找最低基态能量。",
    ),
    "graph_coloring": (
        "图顶点着色与冲突消解 (Graph Coloring)",
        "graph_coloring",
        [
            {
                "name": "NetworkX DSATUR 启发式上界 + OR-Tools CP-SAT 精确求解",
                "recommended": True,
                "pros": "DSATUR 毫秒级锁定高质量饱和度着色上界，CP-SAT 快速裁决色数全局最优性",
                "cons": "密集图需加入完全子图团约束加速",
            },
            {
                "name": "简单贪心着色 (Greedy Coloring)",
                "recommended": False,
                "pros": "无额外开销",
                "cons": "对节点排列顺序极其敏感，经常浪费额外 20%~50% 颜色数",
            },
        ],
        "检测到相冲突节点不共享资源的互斥拓扑，推荐采用 DSATUR 结合 CP-SAT 混合求解最小色数方案。",
    ),
    "max_clique": (
        "最大团与最大独立集图论优化 (Max Clique & MIS)",
        "max_clique",
        [
            {
                "name": "NetworkX Tomita 分支定界 + CP-SAT 对偶互补验证",
                "recommended": True,
                "pros": "基于补图对偶性 omega(G) = alpha(G_comp) 双重验证，严格保障数值真实性与证明",
                "cons": "在超大规模稠密图上需设置合理超时截断",
            },
            {
                "name": "经典 Bron-Kerbosch 简单回溯",
                "recommended": False,
                "pros": "代码精简",
                "cons": "无有效枢轴选择时搜索树极度庞大",
            },
        ],
        "检测到稠密图互连或互斥特征，推荐采用 Tomita 分支定界与补图 CP-SAT 双重对偶求解。",
    ),
    "stochastic_lp": (
        "两阶段随机线性规划 (Two-Stage Stochastic LP)",
        "stochastic_lp",
        [
            {
                "name": "OR-Tools GLOP 大规模确定性等价型 (Extensive Form)",
                "recommended": True,
                "pros": "同时输出第一阶段期望最优决策 (RP)、全知信息价值 (EVPI) 与随机解价值 (VSS)",
                "cons": "情景爆炸时需采用 L-shaped 分解",
            },
            {
                "name": "平均值均值模型 (Expected Value Problem)",
                "recommended": False,
                "pros": "仅需求解单个平均情景",
                "cons": "完全忽视极端情景尾部风险，实际落地期望收益偏低",
            },
        ],
        "检测到带概率分布的不确定情景数据，推荐采用确定性等价型大规模线性规划精确计算 VSS 与 EVPI。",
    ),
    "staff_rostering": (
        "企业员工排班与轮班优化 (Staff Rostering)",
        "staff_rostering",
        [
            {
                "name": "OR-Tools CP-SAT 连续工作天数与覆盖约束规划",
                "recommended": True,
                "pros": "完美处理每人单班、夜班后休息、最大连续出勤天数等多维硬法规约束与员工满意度",
                "cons": "班次技能等级过多元化时需扩充维度",
            },
            {
                "name": "人工轮转轮盘法 (Cyclic Roster)",
                "recommended": False,
                "pros": "易于固定排班规律",
                "cons": "对突发请假或动态波动班次需求完全缺乏柔性调配能力",
            },
        ],
        "检测到多员工出勤需求与劳动法规工时约束，推荐采用 CP-SAT 约束规划生成兼顾合规与满意度的排班表。",
    ),
    "lot_sizing": (
        "多周期动态批量订货优化 (Lot Sizing WW / CLSP)",
        "lot_sizing",
        [
            {
                "name": "Wagner-Whitin 动态规划 (无产能) / SCIP MIP (有产能限制 CLSP)",
                "recommended": True,
                "pros": "利用零库存定理实现多周期订货与库存持有总成本数学全局最优，毫秒级出解",
                "cons": "有能力限制时复杂度上升为 NP-Hard",
            },
            {
                "name": "经济订货批量 (EOQ)",
                "recommended": False,
                "pros": "平方根公式极简",
                "cons": "强行假设需求速率恒定，在动态离散需求场景下造成高额库存积压",
            },
        ],
        "检测到时变需求与固定准备/库存持有成本，推荐采用 Wagner-Whitin 动态规划与 CLSP 模型求解最优生产批量。",
    ),
    "microgrid_dispatch": (
        "园区微电网储能充放电与能耗调度 (Microgrid PV-BESS)",
        "microgrid",
        [
            {
                "name": "滚动视界模型预测控制 (MPC) + 线性规划 (LP - HiGHS)",
                "recommended": True,
                "pros": "动态跟踪分时电价峰谷差套利与需量电费消峰，兼顾电池循环衰减成本",
                "cons": "需要较为精准的短时负荷与光伏出力预测",
            },
            {
                "name": "简单阈值规则调度 (Rule-Based Control)",
                "recommended": False,
                "pros": "逻辑简单无求解器依赖",
                "cons": "缺乏前瞻性，电价尖峰时刻容易电量耗尽无法顶峰",
            },
        ],
        "检测到分时电价曲线与储能电池充放电参数，推荐采用 MPC 滚动优化与线性规划降低综合用电成本。",
    ),
    "vrp": (
        "多车带容量/时间窗路径规划 (CVRP / VRPTW)",
        "ortools",
        [
            {
                "name": "OR-Tools Routing / 导向局部搜索 (Guided Local Search)",
                "recommended": True,
                "pros": "工业物流领域标杆，支持车载容量、严格到达时间窗与异构车队调度",
                "cons": "超大尺度需结合分区聚类",
            },
            {
                "name": "逐车贪婪插入启发式 (Greedy Insertion)",
                "recommended": False,
                "pros": "速度极快",
                "cons": "路径容易产生交叉绕行，总运输里程高出 15%~30%",
            },
        ],
        "检测到客户网点需求与车队载重/时间窗约束，推荐采用 OR-Tools 导向局部搜索求解最低运力成本方案。",
    ),
    "game_theory": (
        "非合作双矩阵博弈与纳什均衡 (Game Theory)",
        "game_theory",
        [
            {
                "name": "Nashpy 支持枚举 (Support Enumeration) / Lemke-Howson",
                "recommended": True,
                "pros": "严格求取所有纯策略与混合策略纳什均衡 (Nash Equilibrium)，输出完备博弈分析",
                "cons": "高阶张量博弈维度较高",
            },
            {
                "name": "极大极小单边分析",
                "recommended": False,
                "pros": "计算直观",
                "cons": "无法反映双边动态策略互动的均衡状态",
            },
        ],
        "检测到收益矩阵与竞争对抗策略，推荐采用 Nashpy 支持枚举算法求解混合策略纳什均衡。",
    ),
}

_ALIASES: dict[str, str] = {
    "jssp": "job_shop",
    "fjssp": "job_shop",
    "facility": "facility_location",
    "hub": "hub_location",
    "binpack": "bin_packing",
    "portfolio": "portfolio_opt",
    "qubo": "qubo_ising",
    "stochastic": "stochastic_lp",
    "inventory_planning": "lot_sizing",
    "microgrid": "microgrid_dispatch",
}


def get_domain_spec(detected_class: str) -> tuple[str, str, list[dict[str, Any]], str]:
    """Return (domain_name, recommended_algorithm, algorithm_comparison, rationale)."""
    key = _ALIASES.get(detected_class, detected_class)
    if key in _CATALOG:
        return _CATALOG[key]
    return (
        f"未注册运筹领域 ({detected_class})",
        "none",
        [
            {
                "name": "定性数学建模与模型框架构建",
                "recommended": True,
                "pros": "自动抽取目标函数、决策变量与约束集合，形成标准 Markdown / LaTeX 数学规划公式",
                "cons": "当前系统工业适配器尚未注册该特定专有求解器，需要接入领域适配器方可直接数值计算",
            }
        ],
        "当前题面属于自定义或扩展运筹问题，系统已完成语义解析并给出建议，但诚实限制数值虚假绑定。",
    )
