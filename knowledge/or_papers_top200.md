# 运筹学论文择优清单（Top 200）

> **来源**: Crossref + arXiv（+ 可用时的 Semantic Scholar / OpenAlex）——**真实 API 元数据，未虚构**  
> **未下载 PDF**；仅书目清单。  
> **流程**: 20 运筹子域 × 多查询 ×（相关排序 + 高被引排序 + 近年过滤）→ 去重 → OR 相关度/期刊加权 → 域多样性软上限 → **200**  
> **相关候选池**: **10458** 篇  
> **脚本**: `scripts/build_or_paper_list.py`  
> **JSON/CSV**: `knowledge/or_papers_top200.json` · `knowledge/or_papers_top200.csv`

## 子域覆盖（选中计数）

- `nonlinear_convex`: 47
- `multiobjective`: 46
- `stochastic_or`: 44
- `dynamic_programming`: 42
- `inventory_supply_chain`: 41
- `metaheuristics`: 38
- `queuing_simulation`: 37
- `combinatorial_optimization`: 34
- `game_theory_or`: 29
- `ml_or_hybrid`: 29
- `graph_or`: 28
- `cutting_packing`: 28
- `constraint_programming`: 24
- `linear_programming`: 23
- `network_flows`: 23
- `or_foundations_survey`: 20
- `integer_programming`: 17
- `scheduling`: 16
- `column_generation_decomp`: 16
- `tsp_routing`: 16

---

## Top 200 清单

### 1. Array programming with NumPy

- **Year**: 2020 · **Citations**: 23379 · **Type**: journal-article · **API**: crossref
- **Authors**: Charles R. Harris, K. Jarrod Millman, Stéfan J. van der Walt, Ralf Gommers, Pauli Virtanen, David Cournapeau, Eric Wieser, Julian Taylor, Sebastian Berg, Nathan
- **Venue**: Nature
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming, or_foundations_survey
- **DOI**: https://doi.org/10.1038/s41586-020-2649-2
- **Link**: https://doi.org/10.1038/s41586-020-2649-2
- **Abstract**: Abstract                                        Array programming provides a powerful, compact and expressive syntax for accessing, manipulating and operating on data in vectors, matrices and higher-dimensional arrays. NumPy is the primary array programming library for the Python language. It has an…
- **Score**: 9.805

### 2. The Whale Optimization Algorithm

- **Year**: 2016 · **Citations**: 13506 · **Type**: journal-article · **API**: crossref
- **Authors**: Seyedali Mirjalili, Andrew Lewis
- **Venue**: Advances in Engineering Software
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.advengsoft.2016.01.008
- **Link**: https://doi.org/10.1016/j.advengsoft.2016.01.008
- **Score**: 9.327

### 3. AutoDock Vina: Improving the speed and accuracy of docking with a new scoring function, efficient optimization, and multithreading

- **Year**: 2010 · **Citations**: 33728 · **Type**: journal-article · **API**: crossref
- **Authors**: Oleg Trott, Arthur J. Olson
- **Venue**: Journal of Computational Chemistry
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1002/jcc.21334
- **Link**: https://doi.org/10.1002/jcc.21334
- **Abstract**: AbstractAutoDock Vina, a new program for molecular docking and virtual screening, is presented. AutoDock Vina achieves an approximately two orders of magnitude speed‐up compared with the molecular docking software previously developed in our lab (AutoDock 4), while also significantly improving the a…
- **Score**: 9.217

### 4. Harris hawks optimization: Algorithm and applications

- **Year**: 2019 · **Citations**: 5983 · **Type**: journal-article · **API**: crossref
- **Authors**: Ali Asghar Heidari, Seyedali Mirjalili, Hossam Faris, Ibrahim Aljarah, Majdi Mafarja, Huiling Chen
- **Venue**: Future Generation Computer Systems
- **Domains**: combinatorial_optimization, network_flows, scheduling, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, column_generation_decomp, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.future.2019.02.028
- **Link**: https://doi.org/10.1016/j.future.2019.02.028
- **Score**: 9.200

### 5. CasADi: a software framework for nonlinear optimization and optimal control

- **Year**: 2019 · **Citations**: 3458 · **Type**: journal-article · **API**: crossref
- **Authors**: Joel A. E. Andersson, Joris Gillis, Greg Horn, James B. Rawlings, Moritz Diehl
- **Venue**: Mathematical Programming Computation
- **Domains**: linear_programming, integer_programming, combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, constraint_programming, ml_or_hybrid, or_foundations_survey
- **DOI**: https://doi.org/10.1007/s12532-018-0139-4
- **Link**: https://doi.org/10.1007/s12532-018-0139-4
- **Score**: 9.106

### 6. Distributed Optimization and Statistical Learning via the Alternating Direction Method of Multipliers

- **Year**: 2011 · **Citations**: 14599 · **Type**: journal-article · **API**: crossref
- **Authors**: Stephen Boyd, Neal Parikh, Eric Chu, Borja Peleato, Jonathan Eckstein
- **Venue**: Foundations and Trends® in Machine Learning
- **Domains**: linear_programming, combinatorial_optimization, scheduling, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1561/2200000016
- **Link**: https://doi.org/10.1561/2200000016
- **Abstract**: Many problems of recent interest in statistics and machine learning can be posed in the framework of convex optimization. Due to the explosion in size and complexity of modern datasets, it is increasingly important to be able to solve problems with a very large number of features or training example…
- **Score**: 8.854

### 7. Slime mould algorithm: A new method for stochastic optimization

- **Year**: 2020 · **Citations**: 2896 · **Type**: journal-article · **API**: crossref
- **Authors**: Shimin Li, Huiling Chen, Mingjing Wang, Ali Asghar Heidari, Seyedali Mirjalili
- **Venue**: Future Generation Computer Systems
- **Domains**: linear_programming, combinatorial_optimization, network_flows, scheduling, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, column_generation_decomp, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.future.2020.03.055
- **Link**: https://doi.org/10.1016/j.future.2020.03.055
- **Score**: 8.808

### 8. An Evolutionary Many-Objective Optimization Algorithm Using Reference-Point-Based Nondominated Sorting Approach, Part I: Solving Problems With Box Constraints

- **Year**: 2014 · **Citations**: 6432 · **Type**: journal-article · **API**: crossref
- **Authors**: Kalyanmoy Deb, Himanshu Jain
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: linear_programming, combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, constraint_programming, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1109/tevc.2013.2281535
- **Link**: https://doi.org/10.1109/tevc.2013.2281535
- **Score**: 8.750

### 9. Differential Evolution – A Simple and Efficient Heuristic for global Optimization over Continuous Spaces

- **Year**: 1997 · **Citations**: 24700 · **Type**: journal-article · **API**: crossref
- **Authors**: Rainer Storn, Kenneth Price
- **Venue**: Journal of Global Optimization
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1023/a:1008202821328
- **Link**: https://doi.org/10.1023/a:1008202821328
- **Score**: 8.747

### 10. A novel swarm intelligence optimization approach: sparrow search algorithm

- **Year**: 2020 · **Citations**: 3630 · **Type**: journal-article · **API**: crossref
- **Authors**: Jiankai Xue, Bo Shen
- **Venue**: Systems Science &amp; Control Engineering
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1080/21642583.2019.1708830
- **Link**: https://doi.org/10.1080/21642583.2019.1708830
- **Score**: 8.702

### 11. SCA: A Sine Cosine Algorithm for solving optimization problems

- **Year**: 2016 · **Citations**: 5357 · **Type**: journal-article · **API**: crossref
- **Authors**: Seyedali Mirjalili
- **Venue**: Knowledge-Based Systems
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, constraint_programming, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.knosys.2015.12.022
- **Link**: https://doi.org/10.1016/j.knosys.2015.12.022
- **Score**: 8.680

### 12. On the implementation of an interior-point filter line-search algorithm for large-scale nonlinear programming

- **Year**: 2006 · **Citations**: 8115 · **Type**: journal-article · **API**: crossref
- **Authors**: Andreas Wächter, Lorenz T. Biegler
- **Venue**: Mathematical Programming
- **Domains**: linear_programming, integer_programming, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, constraint_programming, graph_or, cutting_packing, or_foundations_survey
- **DOI**: https://doi.org/10.1007/s10107-004-0559-y
- **Link**: https://doi.org/10.1007/s10107-004-0559-y
- **Score**: 8.661

### 13. The Arithmetic Optimization Algorithm

- **Year**: 2021 · **Citations**: 2749 · **Type**: journal-article · **API**: crossref
- **Authors**: Laith Abualigah, Ali Diabat, Seyedali Mirjalili, Mohamed Abd Elaziz, Amir H. Gandomi
- **Venue**: Computer Methods in Applied Mechanics and Engineering
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.cma.2020.113609
- **Link**: https://doi.org/10.1016/j.cma.2020.113609
- **Score**: 8.597

### 14. Research electronic data capture (REDCap)—A metadata-driven methodology and workflow process for providing translational research informatics support

- **Year**: 2009 · **Citations**: 46766 · **Type**: journal-article · **API**: crossref
- **Authors**: Paul A. Harris, Robert Taylor, Robert Thielke, Jonathon Payne, Nathaniel Gonzalez, Jose G. Conde
- **Venue**: Journal of Biomedical Informatics
- **Domains**: dynamic_programming, or_foundations_survey
- **DOI**: https://doi.org/10.1016/j.jbi.2008.08.010
- **Link**: https://doi.org/10.1016/j.jbi.2008.08.010
- **Score**: 8.591

### 15. RAxML version 8: a tool for phylogenetic analysis and post-analysis of large phylogenies

- **Year**: 2014 · **Citations**: 30030 · **Type**: journal-article · **API**: crossref
- **Authors**: Alexandros Stamatakis
- **Venue**: Bioinformatics
- **Domains**: metaheuristics
- **DOI**: https://doi.org/10.1093/bioinformatics/btu033
- **Link**: https://doi.org/10.1093/bioinformatics/btu033
- **Abstract**: Abstract                   Motivation: Phylogenies are increasingly used in all fields of medical and biological research. Moreover, because of the next-generation sequencing revolution, datasets used for conducting phylogenetic analyses grow at an unprecedented pace. RAxML (Randomized Axelerated Ma…
- **Score**: 8.562

### 16. Taking the Human Out of the Loop: A Review of Bayesian Optimization

- **Year**: 2016 · **Citations**: 5059 · **Type**: journal-article · **API**: crossref
- **Authors**: Bobak Shahriari, Kevin Swersky, Ziyu Wang, Ryan P. Adams, Nando de Freitas
- **Venue**: Proceedings of the IEEE
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1109/jproc.2015.2494218
- **Link**: https://doi.org/10.1109/jproc.2015.2494218
- **Score**: 8.514

### 17. A powerful and efficient algorithm for numerical function optimization: artificial bee colony (ABC) algorithm

- **Year**: 2007 · **Citations**: 6492 · **Type**: journal-article · **API**: crossref
- **Authors**: Dervis Karaboga, Bahriye Basturk
- **Venue**: Journal of Global Optimization
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1007/s10898-007-9149-x
- **Link**: https://doi.org/10.1007/s10898-007-9149-x
- **Score**: 8.507

### 18. A fast and elitist multiobjective genetic algorithm: NSGA-II

- **Year**: 2002 · **Citations**: 42500 · **Type**: journal-article · **API**: crossref
- **Authors**: K. Deb, A. Pratap, S. Agarwal, T. Meyarivan
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: network_flows, nonlinear_convex, multiobjective, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1109/4235.996017
- **Link**: https://doi.org/10.1109/4235.996017
- **Score**: 8.494

### 19. G*Power 3: A flexible statistical power analysis program for the social, behavioral, and biomedical sciences

- **Year**: 2007 · **Citations**: 54633 · **Type**: journal-article · **API**: crossref
- **Authors**: Franz Faul, Edgar Erdfelder, Albert-Georg Lang, Axel Buchner
- **Venue**: Behavior Research Methods
- **Domains**: or_foundations_survey
- **DOI**: https://doi.org/10.3758/bf03193146
- **Link**: https://doi.org/10.3758/bf03193146
- **Score**: 8.474

### 20. Minimap2: pairwise alignment for nucleotide sequences

- **Year**: 2018 · **Citations**: 15403 · **Type**: journal-article · **API**: crossref
- **Authors**: Heng Li
- **Venue**: Bioinformatics
- **Domains**: or_foundations_survey
- **DOI**: https://doi.org/10.1093/bioinformatics/bty191
- **Link**: https://doi.org/10.1093/bioinformatics/bty191
- **Abstract**: Abstract                                   Motivation                   Recent advances in sequencing technologies promise ultra-long reads of ∼100 kb in average, full-length mRNA or cDNA reads in high throughput and genomic contigs over 100 Mb in length. Existing alignment programs are unable or in…
- **Score**: 8.465

### 21. A Singular Value Thresholding Algorithm for Matrix Completion

- **Year**: 2010 · **Citations**: 4665 · **Type**: journal-article · **API**: crossref
- **Authors**: Jian-Feng Cai, Emmanuel J. Candès, Zuowei Shen
- **Venue**: SIAM Journal on Optimization
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1137/080738970
- **Link**: https://doi.org/10.1137/080738970
- **Score**: 8.424

### 22. On hyperparameter optimization of machine learning algorithms: Theory and practice

- **Year**: 2020 · **Citations**: 2959 · **Type**: journal-article · **API**: crossref
- **Authors**: Li Yang, Abdallah Shami
- **Venue**: Neurocomputing
- **Domains**: combinatorial_optimization, scheduling, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.neucom.2020.07.061
- **Link**: https://doi.org/10.1016/j.neucom.2020.07.061
- **Score**: 8.327

### 23. Moth-flame optimization algorithm: A novel nature-inspired heuristic paradigm

- **Year**: 2015 · **Citations**: 4321 · **Type**: journal-article · **API**: crossref
- **Authors**: Seyedali Mirjalili
- **Venue**: Knowledge-Based Systems
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.knosys.2015.07.006
- **Link**: https://doi.org/10.1016/j.knosys.2015.07.006
- **Score**: 8.319

### 24. Particle swarm optimization algorithm: an overview

- **Year**: 2018 · **Citations**: 2996 · **Type**: journal-article · **API**: crossref
- **Authors**: Dongshu Wang, Dapei Tan, Lei Liu
- **Venue**: Soft Computing
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1007/s00500-016-2474-6
- **Link**: https://doi.org/10.1007/s00500-016-2474-6
- **Score**: 8.304

### 25. Long Short-Term Memory

- **Year**: 1997 · **Citations**: 84493 · **Type**: journal-article · **API**: crossref
- **Authors**: Sepp Hochreiter, Jürgen Schmidhuber
- **Venue**: Neural Computation
- **Domains**: ml_or_hybrid
- **DOI**: https://doi.org/10.1162/neco.1997.9.8.1735
- **Link**: https://doi.org/10.1162/neco.1997.9.8.1735
- **Abstract**: Learning to store information over extended time intervals by recurrent backpropagation takes a very long time, mostly because of insufficient, decaying error backflow. We briefly review Hochreiter's (1991) analysis of this problem, then address it by introducing a novel, efficient, gradient based m…
- **Score**: 8.297

### 26. Optimization by Simulated Annealing

- **Year**: 1983 · **Citations**: 33952 · **Type**: journal-article · **API**: crossref
- **Authors**: S. Kirkpatrick, C. D. Gelatt, M. P. Vecchi
- **Venue**: Science
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1126/science.220.4598.671
- **Link**: https://doi.org/10.1126/science.220.4598.671
- **Abstract**: There is a deep and useful connection between statistical mechanics (the behavior of systems with many degrees of freedom in thermal equilibrium at a finite temperature) and multivariate or combinatorial optimization (finding the minimum of a given function depending on many parameters). A detailed …
- **Score**: 8.269

### 27. Gapped BLAST and PSI-BLAST: a new generation of protein database search programs

- **Year**: 1997 · **Citations**: 60540 · **Type**: journal-article · **API**: crossref
- **Authors**: S. Altschul
- **Venue**: Nucleic Acids Research
- **Domains**: metaheuristics, column_generation_decomp, or_foundations_survey
- **DOI**: https://doi.org/10.1093/nar/25.17.3389
- **Link**: https://doi.org/10.1093/nar/25.17.3389
- **Score**: 8.267

### 28. Improved Optimization for the Robust and Accurate Linear Registration and Motion Correction of Brain Images

- **Year**: 2002 · **Citations**: 10844 · **Type**: journal-article · **API**: crossref
- **Authors**: Mark Jenkinson, Peter Bannister, Michael Brady, Stephen Smith
- **Venue**: NeuroImage
- **Domains**: linear_programming, integer_programming, combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid, or_foundations_survey
- **DOI**: https://doi.org/10.1006/nimg.2002.1132
- **Link**: https://doi.org/10.1006/nimg.2002.1132
- **Score**: 8.254

### 29. <i>Stan</i>
                    : A Probabilistic Programming Language

- **Year**: 2017 · **Citations**: 5830 · **Type**: journal-article · **API**: crossref
- **Authors**: Bob Carpenter, Andrew Gelman, Matthew D. Hoffman, Daniel Lee, Ben Goodrich, Michael Betancourt, Marcus Brubaker, Jiqiang Guo, Peter Li, Allen Riddell
- **Venue**: Journal of Statistical Software
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming, or_foundations_survey
- **DOI**: https://doi.org/10.18637/jss.v076.i01
- **Link**: https://doi.org/10.18637/jss.v076.i01
- **Score**: 8.249

### 30. Equilibrium optimizer: A novel optimization algorithm

- **Year**: 2020 · **Citations**: 2171 · **Type**: journal-article · **API**: crossref
- **Authors**: Afshin Faramarzi, Mohammad Heidarinejad, Brent Stephens, Seyedali Mirjalili
- **Venue**: Knowledge-Based Systems
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.knosys.2019.105190
- **Link**: https://doi.org/10.1016/j.knosys.2019.105190
- **Score**: 8.160

### 31. Aquila Optimizer: A novel meta-heuristic optimization algorithm

- **Year**: 2021 · **Citations**: 2084 · **Type**: journal-article · **API**: crossref
- **Authors**: Laith Abualigah, Dalia Yousri, Mohamed Abd Elaziz, Ahmed A. Ewees, Mohammed A.A. Al-qaness, Amir H. Gandomi
- **Venue**: Computers &amp; Industrial Engineering
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.cie.2021.107250
- **Link**: https://doi.org/10.1016/j.cie.2021.107250
- **Score**: 8.155

### 32. Particle Swarm Optimization Algorithm and Its Applications: A Systematic Review

- **Year**: 2022 · **Citations**: 1710 · **Type**: journal-article · **API**: crossref
- **Authors**: Ahmed G. Gad
- **Venue**: Archives of Computational Methods in Engineering
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1007/s11831-021-09694-4
- **Link**: https://doi.org/10.1007/s11831-021-09694-4
- **Abstract**: AbstractThroughout the centuries, nature has been a source of inspiration, with much still to learn from and discover about. Among many others, Swarm Intelligence (SI), a substantial branch of Artificial Intelligence, is built on the intelligent collective behavior of social swarms in nature. One of…
- **Score**: 8.132

### 33. On the limited memory BFGS method for large scale optimization

- **Year**: 1989 · **Citations**: 6680 · **Type**: journal-article · **API**: crossref
- **Authors**: Dong C. Liu, Jorge Nocedal
- **Venue**: Mathematical Programming
- **Domains**: linear_programming, integer_programming, combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, constraint_programming, ml_or_hybrid, or_foundations_survey
- **DOI**: https://doi.org/10.1007/bf01589116
- **Link**: https://doi.org/10.1007/bf01589116
- **Score**: 8.114

### 34. Global burden of 288 causes of death and life expectancy decomposition in 204 countries and territories and 811 subnational locations, 1990–2021: a systematic analysis for the Global Burden of Disease Study 2021

- **Year**: 2024 · **Citations**: 2541 · **Type**: journal-article · **API**: crossref
- **Authors**: Mohsen Naghavi, Kanyin Liane Ong, Amirali Aali, Hazim S Ababneh, Yohannes Habtegiorgis Abate, Cristiana Abbafati, Rouzbeh Abbasgholizadeh, Mohammadreza Abbasian
- **Venue**: The Lancet
- **Domains**: column_generation_decomp, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/s0140-6736(24)00367-2
- **Link**: https://doi.org/10.1016/s0140-6736(24)00367-2
- **Score**: 8.100

### 35. Software survey: VOSviewer, a computer program for bibliometric mapping

- **Year**: 2010 · **Citations**: 17419 · **Type**: journal-article · **API**: crossref
- **Authors**: Nees Jan van Eck, Ludo Waltman
- **Venue**: Scientometrics
- **Domains**: or_foundations_survey
- **DOI**: https://doi.org/10.1007/s11192-009-0146-3
- **Link**: https://doi.org/10.1007/s11192-009-0146-3
- **Score**: 8.098

### 36. A Limited Memory Algorithm for Bound Constrained Optimization

- **Year**: 1995 · **Citations**: 5013 · **Type**: journal-article · **API**: crossref
- **Authors**: Richard H. Byrd, Peihuang Lu, Jorge Nocedal, Ciyou Zhu
- **Venue**: SIAM Journal on Scientific Computing
- **Domains**: combinatorial_optimization, network_flows, scheduling, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1137/0916069
- **Link**: https://doi.org/10.1137/0916069
- **Score**: 7.989

### 37. Convergence Properties of the Nelder--Mead Simplex Method in Low Dimensions

- **Year**: 1998 · **Citations**: 5989 · **Type**: journal-article · **API**: crossref
- **Authors**: Jeffrey C. Lagarias, James A. Reeds, Margaret H. Wright, Paul E. Wright
- **Venue**: SIAM Journal on Optimization
- **Domains**: linear_programming, combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1137/s1052623496303470
- **Link**: https://doi.org/10.1137/s1052623496303470
- **Score**: 7.966

### 38. Instant neural graphics primitives with a multiresolution hash encoding

- **Year**: 2022 · **Citations**: 3857 · **Type**: journal-article · **API**: crossref
- **Authors**: Thomas Müller, Alex Evans, Christoph Schied, Alexander Keller
- **Venue**: ACM Transactions on Graphics
- **Domains**: graph_or, ml_or_hybrid
- **DOI**: https://doi.org/10.1145/3528223.3530127
- **Link**: https://doi.org/10.1145/3528223.3530127
- **Abstract**: Neural graphics primitives, parameterized by fully connected neural networks, can be costly to train and evaluate. We reduce this cost with a versatile new input encoding that permits the use of a smaller network without sacrificing quality, thus significantly reducing the number of floating point a…
- **Score**: 7.950

### 39. Dung beetle optimizer: a new meta-heuristic algorithm for global optimization

- **Year**: 2023 · **Citations**: 1589 · **Type**: journal-article · **API**: crossref
- **Authors**: Jiankai Xue, Bo Shen
- **Venue**: The Journal of Supercomputing
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1007/s11227-022-04959-6
- **Link**: https://doi.org/10.1007/s11227-022-04959-6
- **Score**: 7.942

### 40. A New Heuristic Optimization Algorithm: Harmony Search

- **Year**: 2001 · **Citations**: 5189 · **Type**: journal-article · **API**: crossref
- **Authors**: Zong Woo Geem, Joong Hoon Kim, G.V. Loganathan
- **Venue**: SIMULATION
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1177/003754970107600201
- **Link**: https://doi.org/10.1177/003754970107600201
- **Abstract**: Many optimization problems in various fields have been solved using diverse optimization al gorithms. Traditional optimization techniques such as linear programming (LP), non-linear programming (NLP), and dynamic program ming (DP) have had major roles in solving these problems. However, their drawba…
- **Score**: 7.904

### 41. MOEA/D: A Multiobjective Evolutionary Algorithm Based on Decomposition

- **Year**: 2007 · **Citations**: 9024 · **Type**: journal-article · **API**: crossref
- **Authors**: Qingfu Zhang, Hui Li
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: network_flows, nonlinear_convex, multiobjective, column_generation_decomp, constraint_programming, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1109/tevc.2007.892759
- **Link**: https://doi.org/10.1109/tevc.2007.892759
- **Score**: 7.889

### 42. Efficient Global Optimization of Expensive Black-Box Functions

- **Year**: 1998 · **Citations**: 6749 · **Type**: journal-article · **API**: crossref
- **Authors**: Donald R. Jones, Matthias Schonlau, William J. Welch
- **Venue**: Journal of Global Optimization
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1023/a:1008306431147
- **Link**: https://doi.org/10.1023/a:1008306431147
- **Score**: 7.879

### 43. PlatEMO: A MATLAB Platform for Evolutionary Multi-Objective Optimization [Educational Forum]

- **Year**: 2017 · **Citations**: 2644 · **Type**: journal-article · **API**: crossref
- **Authors**: Ye Tian, Ran Cheng, Xingyi Zhang, Yaochu Jin
- **Venue**: IEEE Computational Intelligence Magazine
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1109/mci.2017.2742868
- **Link**: https://doi.org/10.1109/mci.2017.2742868
- **Score**: 7.871

### 44. Fast unfolding of communities in large networks

- **Year**: 2008 · **Citations**: 16903 · **Type**: journal-article · **API**: crossref
- **Authors**: Vincent D Blondel, Jean-Loup Guillaume, Renaud Lambiotte, Etienne Lefebvre
- **Venue**: Journal of Statistical Mechanics: Theory and Experiment
- **Domains**: metaheuristics, game_theory_or, queuing_simulation
- **DOI**: https://doi.org/10.1088/1742-5468/2008/10/p10008
- **Link**: https://doi.org/10.1088/1742-5468/2008/10/p10008
- **Abstract**: We propose a simple method to extract the community structure of large networks. Our method is a heuristic method that is based on modularity optimization. It is shown to outperform all other known community detection methods in terms of computation time. Moreover, the quality of the communities det…
- **Score**: 7.869

### 45. Teaching–learning-based optimization: A novel method for constrained mechanical design optimization problems

- **Year**: 2011 · **Citations**: 4483 · **Type**: journal-article · **API**: crossref
- **Authors**: R.V. Rao, V.J. Savsani, D.P. Vakharia
- **Venue**: Computer-Aided Design
- **Domains**: combinatorial_optimization, scheduling, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.cad.2010.12.015
- **Link**: https://doi.org/10.1016/j.cad.2010.12.015
- **Score**: 7.855

### 46. Finite-Time Stability of Continuous Autonomous Systems

- **Year**: 2000 · **Citations**: 5150 · **Type**: journal-article · **API**: crossref
- **Authors**: Sanjay P. Bhat, Dennis S. Bernstein
- **Venue**: SIAM Journal on Control and Optimization
- **Domains**: combinatorial_optimization, tsp_routing, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1137/s0363012997321358
- **Link**: https://doi.org/10.1137/s0363012997321358
- **Score**: 7.855

### 47. Optimization of the Additive CHARMM All-Atom Protein Force Field Targeting Improved Sampling of the Backbone ϕ, ψ and Side-Chain χ<sub>1</sub> and χ<sub>2</sub> Dihedral Angles

- **Year**: 2012 · **Citations**: 4641 · **Type**: journal-article · **API**: crossref
- **Authors**: Robert B. Best, Xiao Zhu, Jihyun Shim, Pedro E. M. Lopes, Jeetain Mittal, Michael Feig, Alexander D. MacKerell
- **Venue**: Journal of Chemical Theory and Computation
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1021/ct300400x
- **Link**: https://doi.org/10.1021/ct300400x
- **Score**: 7.847

### 48. Benchmarking optimization software with performance profiles

- **Year**: 2002 · **Citations**: 3577 · **Type**: journal-article · **API**: crossref
- **Authors**: Elizabeth D. Dolan, Jorge J. Moré
- **Venue**: Mathematical Programming
- **Domains**: linear_programming, integer_programming, combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, constraint_programming, or_foundations_survey
- **DOI**: https://doi.org/10.1007/s101070100263
- **Link**: https://doi.org/10.1007/s101070100263
- **Score**: 7.835

### 49. No free lunch theorems for optimization

- **Year**: 1997 · **Citations**: 11754 · **Type**: journal-article · **API**: crossref
- **Authors**: D.H. Wolpert, W.G. Macready
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1109/4235.585893
- **Link**: https://doi.org/10.1109/4235.585893
- **Score**: 7.833

### 50. Molecular Optimization Enables over 13% Efficiency in Organic Solar Cells

- **Year**: 2017 · **Citations**: 2724 · **Type**: journal-article · **API**: crossref
- **Authors**: Wenchao Zhao, Sunsun Li, Huifeng Yao, Shaoqing Zhang, Yun Zhang, Bei Yang, Jianhui Hou
- **Venue**: Journal of the American Chemical Society
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1021/jacs.7b02677
- **Link**: https://doi.org/10.1021/jacs.7b02677
- **Score**: 7.826

### 51. Data-driven distributionally robust optimization using the Wasserstein metric: performance guarantees and tractable reformulations

- **Year**: 2018 · **Citations**: 1472 · **Type**: journal-article · **API**: crossref
- **Authors**: Peyman Mohajerin Esfahani, Daniel Kuhn
- **Venue**: Mathematical Programming
- **Domains**: linear_programming, integer_programming, combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, constraint_programming
- **DOI**: https://doi.org/10.1007/s10107-017-1172-1
- **Link**: https://doi.org/10.1007/s10107-017-1172-1
- **Score**: 7.814

### 52. Pymoo: Multi-Objective Optimization in Python

- **Year**: 2020 · **Citations**: 2116 · **Type**: journal-article · **API**: crossref
- **Authors**: Julian Blank, Kalyanmoy Deb
- **Venue**: IEEE Access
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1109/access.2020.2990567
- **Link**: https://doi.org/10.1109/access.2020.2990567
- **Score**: 7.808

### 53. RAxML-VI-HPC: maximum likelihood-based phylogenetic analyses with thousands of taxa and mixed models

- **Year**: 2006 · **Citations**: 13645 · **Type**: journal-article · **API**: crossref
- **Authors**: Alexandros Stamatakis
- **Venue**: Bioinformatics
- **Domains**: integer_programming, network_flows, constraint_programming, graph_or, ml_or_hybrid
- **DOI**: https://doi.org/10.1093/bioinformatics/btl446
- **Link**: https://doi.org/10.1093/bioinformatics/btl446
- **Abstract**: Abstract                Summary: RAxML-VI-HPC (randomized axelerated maximum likelihood for high performance computing) is a sequential and parallel program for inference of large phylogenies with maximum likelihood (ML). Low-level technical optimizations, a modification of the search algorithm, and…
- **Score**: 7.800

### 54. Salp Swarm Algorithm: A bio-inspired optimizer for engineering design problems

- **Year**: 2017 · **Citations**: 4753 · **Type**: journal-article · **API**: crossref
- **Authors**: Seyedali Mirjalili, Amir H. Gandomi, Seyedeh Zahra Mirjalili, Shahrzad Saremi, Hossam Faris, Seyed Mohammad Mirjalili
- **Venue**: Advances in Engineering Software
- **Domains**: network_flows, nonlinear_convex, game_theory_or, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.advengsoft.2017.07.002
- **Link**: https://doi.org/10.1016/j.advengsoft.2017.07.002
- **Score**: 7.781

### 55. Commentary: The Materials Project: A materials genome approach to accelerating materials innovation

- **Year**: 2013 · **Citations**: 12209 · **Type**: journal-article · **API**: crossref
- **Authors**: Anubhav Jain, Shyue Ping Ong, Geoffroy Hautier, Wei Chen, William Davidson Richards, Stephen Dacek, Shreyas Cholia, Dan Gunter, David Skinner, Gerbrand Ceder, K
- **Venue**: APL Materials
- **Domains**: scheduling
- **DOI**: https://doi.org/10.1063/1.4812323
- **Link**: https://doi.org/10.1063/1.4812323
- **Abstract**: Accelerating the discovery of advanced materials is essential for human welfare and sustainable, clean energy. In this paper, we introduce the Materials Project (www.materialsproject.org), a core program of the Materials Genome Initiative that uses high-throughput computing to uncover the properties…
- **Score**: 7.770

### 56. <i>Mercury 4.0</i>: from visualization to analysis, design and prediction

- **Year**: 2020 · **Citations**: 4943 · **Type**: journal-article · **API**: crossref
- **Authors**: Clare F. Macrae, Ioana Sovago, Simon J. Cottrell, Peter T. A. Galek, Patrick McCabe, Elna Pidcock, Michael Platings, Greg P. Shields, Joanna S. Stevens, Matthew
- **Venue**: Journal of Applied Crystallography
- **Domains**: game_theory_or
- **DOI**: https://doi.org/10.1107/s1600576719014092
- **Link**: https://doi.org/10.1107/s1600576719014092
- **Abstract**: The program Mercury, developed at the Cambridge Crystallographic Data Centre, was originally designed primarily as a crystal structure visualization tool. Over the years the fields and scientific communities of chemical crystallography and crystal engineering have developed to require more advanced …
- **Score**: 7.768

### 57. A novel metaheuristic method for solving constrained engineering optimization problems: Crow search algorithm

- **Year**: 2016 · **Citations**: 2024 · **Type**: journal-article · **API**: crossref
- **Authors**: Alireza Askarzadeh
- **Venue**: Computers &amp; Structures
- **Domains**: linear_programming, combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.compstruc.2016.03.001
- **Link**: https://doi.org/10.1016/j.compstruc.2016.03.001
- **Score**: 7.765

### 58. A fast and robust algorithm for Bader decomposition of charge density

- **Year**: 2006 · **Citations**: 10217 · **Type**: journal-article · **API**: crossref
- **Authors**: Graeme Henkelman, Andri Arnaldsson, Hannes Jónsson
- **Venue**: Computational Materials Science
- **Domains**: network_flows, stochastic_or, nonlinear_convex, column_generation_decomp, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.commatsci.2005.04.010
- **Link**: https://doi.org/10.1016/j.commatsci.2005.04.010
- **Score**: 7.759

### 59. Using SeDuMi 1.02, A Matlab toolbox for optimization over symmetric cones

- **Year**: 1999 · **Citations**: 5427 · **Type**: journal-article · **API**: crossref
- **Authors**: Jos F. Sturm
- **Venue**: Optimization Methods and Software
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1080/10556789908805766
- **Link**: https://doi.org/10.1080/10556789908805766
- **Score**: 7.759

### 60. Variational Mode Decomposition

- **Year**: 2014 · **Citations**: 8540 · **Type**: journal-article · **API**: crossref
- **Authors**: Konstantin Dragomiretskiy, Dominique Zosso
- **Venue**: IEEE Transactions on Signal Processing
- **Domains**: dynamic_programming, column_generation_decomp
- **DOI**: https://doi.org/10.1109/tsp.2013.2288675
- **Link**: https://doi.org/10.1109/tsp.2013.2288675
- **Score**: 7.743

### 61. <i>TOPAS</i> and <i>TOPAS-Academic</i>: an optimization program integrating computer algebra and crystallographic objects written in C++

- **Year**: 2018 · **Citations**: 2418 · **Type**: journal-article · **API**: crossref
- **Authors**: Alan A. Coelho
- **Venue**: Journal of Applied Crystallography
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1107/s1600576718000183
- **Link**: https://doi.org/10.1107/s1600576718000183
- **Abstract**: TOPAS and its academic variant TOPAS-Academic are nonlinear least-squares optimization programs written in the C++ programming language. This paper describes their functionality and architecture. The latter is of benefit to developers seeking to reduce development time. TOPAS allows linear and nonli…
- **Score**: 7.726

### 62. <i>WinGX</i>and<i>ORTEP for Windows</i>: an update

- **Year**: 2012 · **Citations**: 11364 · **Type**: journal-article · **API**: crossref
- **Authors**: Louis J. Farrugia
- **Venue**: Journal of Applied Crystallography
- **Domains**: tsp_routing
- **DOI**: https://doi.org/10.1107/s0021889812029111
- **Link**: https://doi.org/10.1107/s0021889812029111
- **Abstract**: TheWinGXsuite provides a complete set of programs for the treatment of small-molecule single-crystal diffraction data, from data reduction and processing, structure solution, model refinement and visualization, and metric analysis of molecular geometry and crystal packing, to final report preparatio…
- **Score**: 7.706

### 63. Response surface methodology (RSM) as a tool for optimization in analytical chemistry

- **Year**: 2008 · **Citations**: 5264 · **Type**: journal-article · **API**: crossref
- **Authors**: Marcos Almeida Bezerra, Ricardo Erthal Santelli, Eliane Padua Oliveira, Leonardo Silveira Villar, Luciane Amélia Escaleira
- **Venue**: Talanta
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.talanta.2008.05.019
- **Link**: https://doi.org/10.1016/j.talanta.2008.05.019
- **Score**: 7.704

### 64. MrBayes 3: Bayesian phylogenetic inference under mixed models

- **Year**: 2003 · **Citations**: 21944 · **Type**: journal-article · **API**: crossref
- **Authors**: Fredrik Ronquist, John P. Huelsenbeck
- **Venue**: Bioinformatics
- **Domains**: integer_programming, ml_or_hybrid
- **DOI**: https://doi.org/10.1093/bioinformatics/btg180
- **Link**: https://doi.org/10.1093/bioinformatics/btg180
- **Abstract**: Abstract                Summary: MrBayes 3 performs Bayesian phylogenetic analysis combining information from different data partitions or subsets evolving under different stochastic evolutionary models. This allows the user to analyze heterogeneous data sets consisting of different data types—e.g. …
- **Score**: 7.699

### 65. Arlequin suite ver 3.5: a new series of programs to perform population genetics analyses under Linux and Windows

- **Year**: 2010 · **Citations**: 14084 · **Type**: journal-article · **API**: crossref
- **Authors**: LAURENT EXCOFFIER, HEIDI E. L. LISCHER
- **Venue**: Molecular Ecology Resources
- **Domains**: tsp_routing
- **DOI**: https://doi.org/10.1111/j.1755-0998.2010.02847.x
- **Link**: https://doi.org/10.1111/j.1755-0998.2010.02847.x
- **Abstract**: AbstractWe present here a new version of the Arlequin program available under three different forms: a Windows graphical version (Winarl35), a console version of Arlequin (arlecore), and a specific console version to compute summary statistics (arlsumstat). The command‐line versions run under both L…
- **Score**: 7.658

### 66. <i>PRISMA2020</i>
                    : An R package and Shiny app for producing PRISMA 2020‐compliant flow diagrams, with interactivity for optimised digital transparency and Open Synthesis

- **Year**: 2022 · **Citations**: 2978 · **Type**: journal-article · **API**: crossref
- **Authors**: Neal R. Haddaway, Matthew J. Page, Chris C. Pritchard, Luke A. McGuinness
- **Venue**: Campbell Systematic Reviews
- **Domains**: network_flows
- **DOI**: https://doi.org/10.1002/cl2.1230
- **Link**: https://doi.org/10.1002/cl2.1230
- **Abstract**: Abstract                                        Background                     Reporting standards, such as PRISMA aim to ensure that the methods and results of systematic reviews are described in sufficient detail to allow full transparency. Flow diagrams in evidence syntheses allow the reader to r…
- **Score**: 7.619

### 67. Optimization Methods for Large-Scale Machine Learning

- **Year**: 2018 · **Citations**: 2123 · **Type**: journal-article · **API**: crossref
- **Authors**: Léon Bottou, Frank E. Curtis, Jorge Nocedal
- **Venue**: SIAM Review
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1137/16m1080173
- **Link**: https://doi.org/10.1137/16m1080173
- **Score**: 7.618

### 68. Particle Swarm Optimization: A Comprehensive Survey

- **Year**: 2022 · **Citations**: 1334 · **Type**: journal-article · **API**: crossref
- **Authors**: Tareq M. Shami, Ayman A. El-Saleh, Mohammed Alswaitti, Qasem Al-Tashi, Mhd Amen Summakieh, Seyedali Mirjalili
- **Venue**: IEEE Access
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1109/access.2022.3142859
- **Link**: https://doi.org/10.1109/access.2022.3142859
- **Score**: 7.609

### 69. Ant system: optimization by a colony of cooperating agents

- **Year**: 1996 · **Citations**: 8870 · **Type**: journal-article · **API**: crossref
- **Authors**: M. Dorigo, V. Maniezzo, A. Colorni
- **Venue**: IEEE Transactions on Systems, Man, and Cybernetics, Part B (Cybernetics)
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1109/3477.484436
- **Link**: https://doi.org/10.1109/3477.484436
- **Score**: 7.608

### 70. The empirical mode decomposition and the Hilbert spectrum for nonlinear and non-stationary time series analysis

- **Year**: 1998 · **Citations**: 19781 · **Type**: journal-article · **API**: crossref
- **Authors**: Norden E. Huang, Zheng Shen, Steven R. Long, Manli C. Wu, Hsing H. Shih, Quanan Zheng, Nai-Chyuan Yen, Chi Chao Tung, Henry H. Liu
- **Venue**: Proceedings of the Royal Society of London. Series A: Mathematical, Physical and Engineering Sciences
- **Domains**: tsp_routing, nonlinear_convex, column_generation_decomp
- **DOI**: https://doi.org/10.1098/rspa.1998.0193
- **Link**: https://doi.org/10.1098/rspa.1998.0193
- **Score**: 7.597

### 71. Dynamic programming algorithm optimization for spoken word recognition

- **Year**: 1978 · **Citations**: 5218 · **Type**: journal-article · **API**: crossref
- **Authors**: H. Sakoe, S. Chiba
- **Venue**: IEEE Transactions on Acoustics, Speech, and Signal Processing
- **Domains**: linear_programming, integer_programming, combinatorial_optimization, network_flows, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, constraint_programming, graph_or, cutting_packing, ml_or_hybrid, or_foundations_survey
- **DOI**: https://doi.org/10.1109/tassp.1978.1163055
- **Link**: https://doi.org/10.1109/tassp.1978.1163055
- **Score**: 7.595

### 72. Decoding by Linear Programming

- **Year**: 2005 · **Citations**: 5425 · **Type**: journal-article · **API**: crossref
- **Authors**: E.J. Candes, T. Tao
- **Venue**: IEEE Transactions on Information Theory
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, game_theory_or, queuing_simulation, constraint_programming, or_foundations_survey
- **DOI**: https://doi.org/10.1109/tit.2005.858979
- **Link**: https://doi.org/10.1109/tit.2005.858979
- **Score**: 7.582

### 73. RAxML-NG: a fast, scalable and user-friendly tool for maximum likelihood phylogenetic inference

- **Year**: 2019 · **Citations**: 4105 · **Type**: journal-article · **API**: crossref
- **Authors**: Alexey M Kozlov, Diego Darriba, Tomáš Flouri, Benoit Morel, Alexandros Stamatakis
- **Venue**: Bioinformatics
- **Domains**: network_flows, graph_or
- **DOI**: https://doi.org/10.1093/bioinformatics/btz305
- **Link**: https://doi.org/10.1093/bioinformatics/btz305
- **Abstract**: Abstract                                        Motivation                     Phylogenies are important for fundamental biological research, but also have numerous applications in biotechnology, agriculture and medicine. Finding the optimal tree under the popular maximum likelihood (ML) criterion i…
- **Score**: 7.581

### 74. CD-HIT: accelerated for clustering the next-generation sequencing data

- **Year**: 2012 · **Citations**: 10520 · **Type**: journal-article · **API**: crossref
- **Authors**: Limin Fu, Beifang Niu, Zhengwei Zhu, Sitao Wu, Weizhong Li
- **Venue**: Bioinformatics
- **Domains**: column_generation_decomp
- **DOI**: https://doi.org/10.1093/bioinformatics/bts565
- **Link**: https://doi.org/10.1093/bioinformatics/bts565
- **Abstract**: Abstract                   Summary: CD-HIT is a widely used program for clustering biological sequences to reduce sequence redundancy and improve the performance of other sequence analyses. In response to the rapid increase in the amount of sequencing data produced by the next-generation sequencing …
- **Score**: 7.577

### 75. African vultures optimization algorithm: A new nature-inspired metaheuristic algorithm for global optimization problems

- **Year**: 2021 · **Citations**: 1345 · **Type**: journal-article · **API**: crossref
- **Authors**: Benyamin Abdollahzadeh, Farhad Soleimanian Gharehchopogh, Seyedali Mirjalili
- **Venue**: Computers &amp; Industrial Engineering
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.cie.2021.107408
- **Link**: https://doi.org/10.1016/j.cie.2021.107408
- **Score**: 7.571

### 76. STRUCTURE HARVESTER: a website and program for visualizing STRUCTURE output and implementing the Evanno method

- **Year**: 2012 · **Citations**: 10418 · **Type**: journal-article · **API**: crossref
- **Authors**: Dent A. Earl, Bridgett M. vonHoldt
- **Venue**: Conservation Genetics Resources
- **Domains**: linear_programming
- **DOI**: https://doi.org/10.1007/s12686-011-9548-7
- **Link**: https://doi.org/10.1007/s12686-011-9548-7
- **Score**: 7.569

### 77. Ant colony optimization

- **Year**: 2006 · **Citations**: 4880 · **Type**: journal-article · **API**: crossref
- **Authors**: Marco Dorigo, Mauro Birattari, Thomas Stutzle
- **Venue**: IEEE Computational Intelligence Magazine
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1109/mci.2006.329691
- **Link**: https://doi.org/10.1109/mci.2006.329691
- **Score**: 7.550

### 78. Survey of multi-objective optimization methods for engineering

- **Year**: 2004 · **Citations**: 3822 · **Type**: journal-article · **API**: crossref
- **Authors**: R.T. Marler, J.S. Arora
- **Venue**: Structural and Multidisciplinary Optimization
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, or_foundations_survey
- **DOI**: https://doi.org/10.1007/s00158-003-0368-6
- **Link**: https://doi.org/10.1007/s00158-003-0368-6
- **Score**: 7.538

### 79. Measuring the efficiency of decision making units

- **Year**: 1978 · **Citations**: 21790 · **Type**: journal-article · **API**: crossref
- **Authors**: A. Charnes, W.W. Cooper, E. Rhodes
- **Venue**: European Journal of Operational Research
- **Domains**: dynamic_programming, or_foundations_survey
- **DOI**: https://doi.org/10.1016/0377-2217(78)90138-8
- **Link**: https://doi.org/10.1016/0377-2217(78)90138-8
- **Score**: 7.491

### 80. Particle swarm optimization

- **Year**: 2007 · **Citations**: 4096 · **Type**: journal-article · **API**: crossref
- **Authors**: Riccardo Poli, James Kennedy, Tim Blackwell
- **Venue**: Swarm Intelligence
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1007/s11721-007-0002-0
- **Link**: https://doi.org/10.1007/s11721-007-0002-0
- **Score**: 7.468

### 81. Muiltiobjective Optimization Using Nondominated Sorting in Genetic Algorithms

- **Year**: 1994 · **Citations**: 5686 · **Type**: journal-article · **API**: crossref
- **Authors**: N. Srinivas, Kalyanmoy Deb
- **Venue**: Evolutionary Computation
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1162/evco.1994.2.3.221
- **Link**: https://doi.org/10.1162/evco.1994.2.3.221
- **Abstract**: In trying to solve multiobjective optimization problems, many traditional methods scalarize the objective vector into a single objective. In those cases, the obtained solution is highly sensitive to the weight vector used in the scalarization process and demands that the user have knowledge about th…
- **Score**: 7.460

### 82. Marine Predators Algorithm: A nature-inspired metaheuristic

- **Year**: 2020 · **Citations**: 2243 · **Type**: journal-article · **API**: crossref
- **Authors**: Afshin Faramarzi, Mohammad Heidarinejad, Seyedali Mirjalili, Amir H. Gandomi
- **Venue**: Expert Systems with Applications
- **Domains**: network_flows, nonlinear_convex, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.eswa.2020.113377
- **Link**: https://doi.org/10.1016/j.eswa.2020.113377
- **Score**: 7.458

### 83. Machine learning for combinatorial optimization: A methodological tour d’horizon

- **Year**: 2021 · **Citations**: 1146 · **Type**: journal-article · **API**: crossref
- **Authors**: Yoshua Bengio, Andrea Lodi, Antoine Prouvost
- **Venue**: European Journal of Operational Research
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, ml_or_hybrid
- **DOI**: https://doi.org/10.1016/j.ejor.2020.07.063
- **Link**: https://doi.org/10.1016/j.ejor.2020.07.063
- **Score**: 7.430

### 84. Honey Badger Algorithm: New metaheuristic algorithm for solving optimization problems

- **Year**: 2022 · **Citations**: 1230 · **Type**: journal-article · **API**: crossref
- **Authors**: Fatma A. Hashim, Essam H. Houssein, Kashif Hussain, Mai S. Mabrouk, Walid Al-Atabany
- **Venue**: Mathematics and Computers in Simulation
- **Domains**: combinatorial_optimization, network_flows, nonlinear_convex, metaheuristics, multiobjective, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.matcom.2021.08.013
- **Link**: https://doi.org/10.1016/j.matcom.2021.08.013
- **Score**: 7.427

### 85. A theory for multiresolution signal decomposition: the wavelet representation

- **Year**: 1989 · **Citations**: 16390 · **Type**: journal-article · **API**: crossref
- **Authors**: S.G. Mallat
- **Venue**: IEEE Transactions on Pattern Analysis and Machine Intelligence
- **Domains**: scheduling, game_theory_or, queuing_simulation, column_generation_decomp, ml_or_hybrid
- **DOI**: https://doi.org/10.1109/34.192463
- **Link**: https://doi.org/10.1109/34.192463
- **Score**: 7.414

### 86. LSST: From Science Drivers to Reference Design and Anticipated Data Products

- **Year**: 2019 · **Citations**: 3487 · **Type**: journal-article · **API**: crossref
- **Authors**: Željko Ivezić, Steven M. Kahn, J. Anthony Tyson, Bob Abel, Emily Acosta, Robyn Allsman, David Alonso, Yusra AlSayyad, Scott F. Anderson, John Andrew, James Roge
- **Venue**: The Astrophysical Journal
- **Domains**: game_theory_or
- **DOI**: https://doi.org/10.3847/1538-4357/ab042c
- **Link**: https://doi.org/10.3847/1538-4357/ab042c
- **Abstract**: Abstract                We describe here the most ambitious survey currently planned in the optical, the Large Synoptic Survey Telescope (LSST). The LSST design is driven by four main science themes: probing dark energy and dark matter, taking an inventory of the solar system, exploring the transien…
- **Score**: 7.413

### 87. Butterfly optimization algorithm: a novel approach for global optimization

- **Year**: 2019 · **Citations**: 1584 · **Type**: journal-article · **API**: crossref
- **Authors**: Sankalap Arora, Satvir Singh
- **Venue**: Soft Computing
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1007/s00500-018-3102-4
- **Link**: https://doi.org/10.1007/s00500-018-3102-4
- **Score**: 7.407

### 88. Blockchain technology and its relationships to sustainable supply chain management

- **Year**: 2019 · **Citations**: 3423 · **Type**: journal-article · **API**: crossref
- **Authors**: Sara Saberi, Mahtab Kouhizadeh, Joseph Sarkis, Lejia Shen
- **Venue**: International Journal of Production Research
- **Domains**: inventory_supply_chain
- **DOI**: https://doi.org/10.1080/00207543.2018.1533261
- **Link**: https://doi.org/10.1080/00207543.2018.1533261
- **Score**: 7.398

### 89. Differential Evolution Algorithm With Strategy Adaptation for Global Numerical Optimization

- **Year**: 2009 · **Citations**: 3236 · **Type**: journal-article · **API**: crossref
- **Authors**: A.K. Qin, V.L. Huang, P.N. Suganthan
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1109/tevc.2008.927706
- **Link**: https://doi.org/10.1109/tevc.2008.927706
- **Score**: 7.394

### 90. Energy-Efficient UAV Communication With Trajectory Optimization

- **Year**: 2017 · **Citations**: 2040 · **Type**: journal-article · **API**: crossref
- **Authors**: Yong Zeng, Rui Zhang
- **Venue**: IEEE Transactions on Wireless Communications
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1109/twc.2017.2688328
- **Link**: https://doi.org/10.1109/twc.2017.2688328
- **Score**: 7.389

### 91. Fast model-based estimation of ancestry in unrelated individuals

- **Year**: 2009 · **Citations**: 9327 · **Type**: journal-article · **API**: crossref
- **Authors**: David H. Alexander, John Novembre, Kenneth Lange
- **Venue**: Genome Research
- **Domains**: inventory_supply_chain, constraint_programming
- **DOI**: https://doi.org/10.1101/gr.094052.109
- **Link**: https://doi.org/10.1101/gr.094052.109
- **Abstract**: Population stratification has long been recognized as a confounding factor in genetic association studies. Estimated ancestries, derived from multi-locus genotype data, can be used to perform a statistical correction for population stratification. One popular technique for estimation of ancestry is …
- **Score**: 7.385

### 92. ENSEMBLE EMPIRICAL MODE DECOMPOSITION: A NOISE-ASSISTED DATA ANALYSIS METHOD

- **Year**: 2009 · **Citations**: 7716 · **Type**: journal-article · **API**: crossref
- **Authors**: ZHAOHUA WU, NORDEN E. HUANG
- **Venue**: Advances in Adaptive Data Analysis
- **Domains**: linear_programming, column_generation_decomp
- **DOI**: https://doi.org/10.1142/s1793536909000047
- **Link**: https://doi.org/10.1142/s1793536909000047
- **Abstract**: A new Ensemble Empirical Mode Decomposition (EEMD) is presented. This new approach consists of sifting an ensemble of white noise-added signal (data) and treats the mean as the final true result. Finite, not infinitesimal, amplitude white noise is necessary to force the ensemble to exhaust all possi…
- **Score**: 7.384

### 93. MapReduce

- **Year**: 2008 · **Citations**: 11386 · **Type**: journal-article · **API**: crossref
- **Authors**: Jeffrey Dean, Sanjay Ghemawat
- **Venue**: Communications of the ACM
- **Domains**: metaheuristics
- **DOI**: https://doi.org/10.1145/1327452.1327492
- **Link**: https://doi.org/10.1145/1327452.1327492
- **Abstract**: MapReduce is a programming model and an associated implementation for processing and generating large datasets that is amenable to a broad variety of real-world tasks. Users specify the computation in terms of a             map             and a             reduce             function, and the under…
- **Score**: 7.376

### 94. Grasshopper Optimisation Algorithm: Theory and application

- **Year**: 2017 · **Citations**: 2524 · **Type**: journal-article · **API**: crossref
- **Authors**: Shahrzad Saremi, Seyedali Mirjalili, Andrew Lewis
- **Venue**: Advances in Engineering Software
- **Domains**: network_flows, nonlinear_convex, game_theory_or, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.advengsoft.2017.01.004
- **Link**: https://doi.org/10.1016/j.advengsoft.2017.01.004
- **Score**: 7.363

### 95. Optimization of parameters for semiempirical methods I. Method

- **Year**: 1989 · **Citations**: 6859 · **Type**: journal-article · **API**: crossref
- **Authors**: James J. P. Stewart
- **Venue**: Journal of Computational Chemistry
- **Domains**: linear_programming, combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1002/jcc.540100208
- **Link**: https://doi.org/10.1002/jcc.540100208
- **Abstract**: AbstractA new method for obtaining optimized parameters for semiempirical methods has been developed and applied to the modified neglect of diatomic overlap (MNDO) method. The method uses derivatives of calculated values for properties with respect to adjustable parameters to obtain the optimized va…
- **Score**: 7.361

### 96. Optimization of conditional value-at-risk

- **Year**: 2000 · **Citations**: 5185 · **Type**: journal-article · **API**: crossref
- **Authors**: R. Tyrrell Rockafellar, Stanislav Uryasev
- **Venue**: The Journal of Risk
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.21314/jor.2000.038
- **Link**: https://doi.org/10.21314/jor.2000.038
- **Score**: 7.359

### 97. OSQP: an operator splitting solver for quadratic programs

- **Year**: 2020 · **Citations**: 1034 · **Type**: journal-article · **API**: crossref
- **Authors**: Bartolomeo Stellato, Goran Banjac, Paul Goulart, Alberto Bemporad, Stephen Boyd
- **Venue**: Mathematical Programming Computation
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming
- **DOI**: https://doi.org/10.1007/s12532-020-00179-2
- **Link**: https://doi.org/10.1007/s12532-020-00179-2
- **Score**: 7.323

### 98. A general reinforcement learning algorithm that masters chess, shogi, and Go through self-play

- **Year**: 2018 · **Citations**: 2630 · **Type**: journal-article · **API**: crossref
- **Authors**: David Silver, Thomas Hubert, Julian Schrittwieser, Ioannis Antonoglou, Matthew Lai, Arthur Guez, Marc Lanctot, Laurent Sifre, Dharshan Kumaran, Thore Graepel, T
- **Venue**: Science
- **Domains**: network_flows, nonlinear_convex, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1126/science.aar6404
- **Link**: https://doi.org/10.1126/science.aar6404
- **Abstract**: One program to rule them all                                        Computers can beat humans at increasingly complex games, including chess and Go. However, these programs are typically constructed for a particular game, exploiting its properties, such as the symmetries of the board on which it is …
- **Score**: 7.296

### 99. Epigenetic programming by maternal behavior

- **Year**: 2004 · **Citations**: 4974 · **Type**: journal-article · **API**: crossref
- **Authors**: Ian C G Weaver, Nadia Cervoni, Frances A Champagne, Ana C D'Alessio, Shakti Sharma, Jonathan R Seckl, Sergiy Dymov, Moshe Szyf, Michael J Meaney
- **Venue**: Nature Neuroscience
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming, or_foundations_survey
- **DOI**: https://doi.org/10.1038/nn1276
- **Link**: https://doi.org/10.1038/nn1276
- **Score**: 7.277

### 100. Optimized sgRNA design to maximize activity and minimize off-target effects of CRISPR-Cas9

- **Year**: 2016 · **Citations**: 4630 · **Type**: journal-article · **API**: crossref
- **Authors**: John G Doench, Nicolo Fusi, Meagan Sullender, Mudra Hegde, Emma W Vaimberg, Katherine F Donovan, Ian Smith, Zuzana Tothova, Craig Wilen, Robert Orchard, Herbert
- **Venue**: Nature Biotechnology
- **Domains**: game_theory_or
- **DOI**: https://doi.org/10.1038/nbt.3437
- **Link**: https://doi.org/10.1038/nbt.3437
- **Score**: 7.263

### 101. Semidefinite Relaxation of Quadratic Optimization Problems

- **Year**: 2010 · **Citations**: 3428 · **Type**: journal-article · **API**: crossref
- **Authors**: Zhi-quan Luo, Wing-kin Ma, Anthony So, Yinyu Ye, Shuzhong Zhang
- **Venue**: IEEE Signal Processing Magazine
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1109/msp.2010.936019
- **Link**: https://doi.org/10.1109/msp.2010.936019
- **Score**: 7.262

### 102. Multi-objective grey wolf optimizer: A novel algorithm for multi-criterion optimization

- **Year**: 2016 · **Citations**: 1694 · **Type**: journal-article · **API**: crossref
- **Authors**: Seyedali Mirjalili, Shahrzad Saremi, Seyed Mohammad Mirjalili, Leandro dos S. Coelho
- **Venue**: Expert Systems with Applications
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.eswa.2015.10.039
- **Link**: https://doi.org/10.1016/j.eswa.2015.10.039
- **Score**: 7.251

### 103. Systematic optimization of long-range corrected hybrid density functionals

- **Year**: 2008 · **Citations**: 3743 · **Type**: journal-article · **API**: crossref
- **Authors**: Jeng-Da Chai, Martin Head-Gordon
- **Venue**: The Journal of Chemical Physics
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1063/1.2834918
- **Link**: https://doi.org/10.1063/1.2834918
- **Abstract**: A general scheme for systematically modeling long-range corrected (LC) hybrid density functionals is proposed. Our resulting two LC hybrid functionals are shown to be accurate in thermochemistry, kinetics, and noncovalent interactions, when compared with common hybrid density functionals. The qualit…
- **Score**: 7.251

### 104. Biogeography-Based Optimization

- **Year**: 2008 · **Citations**: 3741 · **Type**: journal-article · **API**: crossref
- **Authors**: D. Simon
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1109/tevc.2008.919004
- **Link**: https://doi.org/10.1109/tevc.2008.919004
- **Score**: 7.251

### 105. Non-fullerene acceptors with branched side chains and improved molecular packing to exceed 18% efficiency in organic solar cells

- **Year**: 2021 · **Citations**: 2145 · **Type**: journal-article · **API**: crossref
- **Authors**: Chao Li, Jiadong Zhou, Jiali Song, Jinqiu Xu, Huotian Zhang, Xuning Zhang, Jing Guo, Lei Zhu, Donghui Wei, Guangchao Han, Jie Min, Yuan Zhang
- **Venue**: Nature Energy
- **Domains**: cutting_packing
- **DOI**: https://doi.org/10.1038/s41560-021-00820-x
- **Link**: https://doi.org/10.1038/s41560-021-00820-x
- **Score**: 7.250

### 106. Machine Learning for Fluid Mechanics

- **Year**: 2020 · **Citations**: 2680 · **Type**: journal-article · **API**: crossref
- **Authors**: Steven L. Brunton, Bernd R. Noack, Petros Koumoutsakos
- **Venue**: Annual Review of Fluid Mechanics
- **Domains**: scheduling
- **DOI**: https://doi.org/10.1146/annurev-fluid-010719-060214
- **Link**: https://doi.org/10.1146/annurev-fluid-010719-060214
- **Abstract**: The field of fluid mechanics is rapidly advancing, driven by unprecedented volumes of data from experiments, field measurements, and large-scale simulations at multiple spatiotemporal scales. Machine learning (ML) offers a wealth of techniques to extract information from data that can be translated …
- **Score**: 7.242

### 107. Efficacy of Pembrolizumab in Patients With Noncolorectal High Microsatellite Instability/Mismatch Repair–Deficient Cancer: Results From the Phase II KEYNOTE-158 Study

- **Year**: 2020 · **Citations**: 2672 · **Type**: journal-article · **API**: crossref
- **Authors**: Aurelien Marabelle, Dung T. Le, Paolo A. Ascierto, Anna Maria Di Giacomo, Ana De Jesus-Acosta, Jean-Pierre Delord, Ravit Geva, Maya Gottfried, Nicolas Penel, Aa
- **Venue**: Journal of Clinical Oncology
- **Domains**: multiobjective
- **DOI**: https://doi.org/10.1200/jco.19.02105
- **Link**: https://doi.org/10.1200/jco.19.02105
- **Abstract**: PURPOSE                     Genomes of tumors that are deficient in DNA mismatch repair (dMMR) have high microsatellite instability (MSI-H) and harbor hundreds to thousands of somatic mutations that encode potential neoantigens. Such tumors are therefore likely to be immunogenic, triggering upregula…
- **Score**: 7.239

### 108. CHARMM‐GUI: A web‐based graphical user interface for CHARMM

- **Year**: 2008 · **Citations**: 9358 · **Type**: journal-article · **API**: crossref
- **Authors**: Sunhwan Jo, Taehoon Kim, Vidyashankara G. Iyer, Wonpil Im
- **Venue**: Journal of Computational Chemistry
- **Domains**: constraint_programming
- **DOI**: https://doi.org/10.1002/jcc.20945
- **Link**: https://doi.org/10.1002/jcc.20945
- **Abstract**: AbstractCHARMM is an academic research program used widely for macromolecular mechanics and dynamics with versatile analysis and manipulation tools of atomic coordinates and dynamics trajectories. CHARMM‐GUI, http://www.charmm‐gui.org, has been developed to provide a web‐based graphical user interfa…
- **Score**: 7.230

### 109. Probabilistic programming in Python using PyMC3

- **Year**: 2016 · **Citations**: 2096 · **Type**: journal-article · **API**: crossref
- **Authors**: John Salvatier, Thomas V. Wiecki, Christopher Fonnesbeck
- **Venue**: PeerJ Computer Science
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming
- **DOI**: https://doi.org/10.7717/peerj-cs.55
- **Link**: https://doi.org/10.7717/peerj-cs.55
- **Abstract**: Probabilistic programming allows for automatic Bayesian inference on user-defined probabilistic models. Recent advances in Markov chain Monte Carlo (MCMC) sampling allow inference on increasingly complex models. This class of MCMC, known as Hamiltonian Monte Carlo, requires gradient information whic…
- **Score**: 7.223

### 110. Understanding and Mitigating Gradient Flow Pathologies in Physics-Informed Neural Networks

- **Year**: 2021 · **Citations**: 1731 · **Type**: journal-article · **API**: crossref
- **Authors**: Sifan Wang, Yujun Teng, Paris Perdikaris
- **Venue**: SIAM Journal on Scientific Computing
- **Domains**: network_flows
- **DOI**: https://doi.org/10.1137/20m1318043
- **Link**: https://doi.org/10.1137/20m1318043
- **Score**: 7.222

### 111. Dragonfly algorithm: a new meta-heuristic optimization technique for solving single-objective, discrete, and multi-objective problems

- **Year**: 2016 · **Citations**: 2455 · **Type**: journal-article · **API**: crossref
- **Authors**: Seyedali Mirjalili
- **Venue**: Neural Computing and Applications
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective, queuing_simulation
- **DOI**: https://doi.org/10.1007/s00521-015-1920-1
- **Link**: https://doi.org/10.1007/s00521-015-1920-1
- **Score**: 7.221

### 112. Multi-Verse Optimizer: a nature-inspired algorithm for global optimization

- **Year**: 2016 · **Citations**: 2665 · **Type**: journal-article · **API**: crossref
- **Authors**: Seyedali Mirjalili, Seyed Mohammad Mirjalili, Abdolreza Hatamlou
- **Venue**: Neural Computing and Applications
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective
- **DOI**: https://doi.org/10.1007/s00521-015-1870-7
- **Link**: https://doi.org/10.1007/s00521-015-1870-7
- **Score**: 7.217

### 113. CHARMM: The biomolecular simulation program

- **Year**: 2009 · **Citations**: 8439 · **Type**: journal-article · **API**: crossref
- **Authors**: B. R. Brooks, C. L. Brooks, A. D. Mackerell, L. Nilsson, R. J. Petrella, B. Roux, Y. Won, G. Archontis, C. Bartels, S. Boresch, A. Caflisch, L. Caves
- **Venue**: Journal of Computational Chemistry
- **Domains**: queuing_simulation
- **DOI**: https://doi.org/10.1002/jcc.21287
- **Link**: https://doi.org/10.1002/jcc.21287
- **Abstract**: AbstractCHARMM (Chemistry at HARvard Molecular Mechanics) is a highly versatile and widely used molecular simulation program. It has been developed over the last three decades with a primary focus on molecules of biological interest, including proteins, peptides, lipids, nucleic acids, carbohydrates…
- **Score**: 7.211

### 114. Cd-hit: a fast program for clustering and comparing large sets of protein or nucleotide sequences

- **Year**: 2006 · **Citations**: 10512 · **Type**: journal-article · **API**: crossref
- **Authors**: Weizhong Li, Adam Godzik
- **Venue**: Bioinformatics
- **Domains**: metaheuristics
- **DOI**: https://doi.org/10.1093/bioinformatics/btl158
- **Link**: https://doi.org/10.1093/bioinformatics/btl158
- **Abstract**: Abstract                   Motivation: In 2001 and 2002, we published two papers (Bioinformatics, 17, 282–283, Bioinformatics, 18, 77–82) describing an ultrafast protein sequence clustering program called cd-hit. This program can efficiently cluster a huge protein database with millions of sequences…
- **Score**: 7.210

### 115. The promising future of microalgae: current status, challenges, and optimization of a sustainable and renewable industry for biofuels, feed, and other products

- **Year**: 2018 · **Citations**: 1793 · **Type**: journal-article · **API**: crossref
- **Authors**: Muhammad Imran Khan, Jin Hyuk Shin, Jong Deog Kim
- **Venue**: Microbial Cell Factories
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1186/s12934-018-0879-x
- **Link**: https://doi.org/10.1186/s12934-018-0879-x
- **Score**: 7.208

### 116. Multi-objective optimization using genetic algorithms: A tutorial

- **Year**: 2006 · **Citations**: 2835 · **Type**: journal-article · **API**: crossref
- **Authors**: Abdullah Konak, David W. Coit, Alice E. Smith
- **Venue**: Reliability Engineering &amp; System Safety
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1016/j.ress.2005.11.018
- **Link**: https://doi.org/10.1016/j.ress.2005.11.018
- **Score**: 7.204

### 117. Handling multiple objectives with particle swarm optimization

- **Year**: 2004 · **Citations**: 3903 · **Type**: journal-article · **API**: crossref
- **Authors**: C.A.C. Coello, G.T. Pulido, M.S. Lechuga
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1109/tevc.2004.826067
- **Link**: https://doi.org/10.1109/tevc.2004.826067
- **Score**: 7.203

### 118. An overview of clinical decision support systems: benefits, risks, and strategies for success

- **Year**: 2020 · **Citations**: 2495 · **Type**: journal-article · **API**: crossref
- **Authors**: Reed T. Sutton, David Pincock, Daniel C. Baumgart, Daniel C. Sadowski, Richard N. Fedorak, Karen I. Kroeker
- **Venue**: npj Digital Medicine
- **Domains**: dynamic_programming
- **DOI**: https://doi.org/10.1038/s41746-020-0221-y
- **Link**: https://doi.org/10.1038/s41746-020-0221-y
- **Abstract**: AbstractComputerized clinical decision support systems, or CDSS, represent a paradigm shift in healthcare today. CDSS are used to augment clinicians in their complex decision-making processes. Since their first use in the 1980s, CDSS have seen a rapid evolution. They are now commonly administered th…
- **Score**: 7.180

### 119. Optimal shape design as a material distribution problem

- **Year**: 1989 · **Citations**: 3838 · **Type**: journal-article · **API**: crossref
- **Authors**: M. P. Bendsøe
- **Venue**: Structural Optimization
- **Domains**: combinatorial_optimization, tsp_routing, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, constraint_programming, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1007/bf01650949
- **Link**: https://doi.org/10.1007/bf01650949
- **Score**: 7.173

### 120. The Impact of Enhancing Students’ Social and Emotional Learning: A Meta-Analysis of School-Based Universal Interventions

- **Year**: 2011 · **Citations**: 5884 · **Type**: journal-article · **API**: crossref
- **Authors**: Joseph A Durlak, Roger P Weissberg, Allison B Dymnicki, Rebecca D Taylor, Kriston B Schellinger
- **Venue**: Child Development
- **Domains**: constraint_programming, ml_or_hybrid
- **DOI**: https://doi.org/10.1111/j.1467-8624.2010.01564.x
- **Link**: https://doi.org/10.1111/j.1467-8624.2010.01564.x
- **Abstract**: Abstract                   This article presents findings from a meta-analysis of 213 school-based, universal social and emotional learning (SEL) programs involving 270,034 kindergarten through high school students. Compared to controls, SEL participants demonstrated significantly improved social an…
- **Score**: 7.162

### 121. A Reference Vector Guided Evolutionary Algorithm for Many-Objective Optimization

- **Year**: 2016 · **Citations**: 1634 · **Type**: journal-article · **API**: crossref
- **Authors**: Ran Cheng, Yaochu Jin, Markus Olhofer, Bernhard Sendhoff
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: combinatorial_optimization, network_flows, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1109/tevc.2016.2519378
- **Link**: https://doi.org/10.1109/tevc.2016.2519378
- **Score**: 7.152

### 122. tRNAscan-SE: A Program for Improved Detection of Transfer RNA Genes in Genomic Sequence

- **Year**: 1997 · **Citations**: 16089 · **Type**: journal-article · **API**: crossref
- **Authors**: Todd M. Lowe, Sean R. Eddy
- **Venue**: Nucleic Acids Research
- **Domains**: or_foundations_survey
- **DOI**: https://doi.org/10.1093/nar/25.5.955
- **Link**: https://doi.org/10.1093/nar/25.5.955
- **Score**: 7.150

### 123. Reptile Search Algorithm (RSA): A nature-inspired meta-heuristic optimizer

- **Year**: 2022 · **Citations**: 1357 · **Type**: journal-article · **API**: crossref
- **Authors**: Laith Abualigah, Mohamed Abd Elaziz, Putra Sumari, Zong Woo Geem, Amir H. Gandomi
- **Venue**: Expert Systems with Applications
- **Domains**: network_flows, nonlinear_convex, metaheuristics, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.eswa.2021.116158
- **Link**: https://doi.org/10.1016/j.eswa.2021.116158
- **Score**: 7.145

### 124. Clustered Federated Learning: Model-Agnostic Distributed Multitask Optimization Under Privacy Constraints

- **Year**: 2021 · **Citations**: 1122 · **Type**: journal-article · **API**: crossref
- **Authors**: Felix Sattler, Klaus-Robert Muller, Wojciech Samek
- **Venue**: IEEE Transactions on Neural Networks and Learning Systems
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective
- **DOI**: https://doi.org/10.1109/tnnls.2020.3015958
- **Link**: https://doi.org/10.1109/tnnls.2020.3015958
- **Score**: 7.142

### 125. Attention Based Spatial-Temporal Graph Convolutional Networks for Traffic Flow Forecasting

- **Year**: 2019 · **Citations**: 2432 · **Type**: journal-article · **API**: crossref
- **Authors**: Shengnan Guo, Youfang Lin, Ning Feng, Chao Song, Huaiyu Wan
- **Venue**: Proceedings of the AAAI Conference on Artificial Intelligence
- **Domains**: network_flows, graph_or
- **DOI**: https://doi.org/10.1609/aaai.v33i01.3301922
- **Link**: https://doi.org/10.1609/aaai.v33i01.3301922
- **Abstract**: Forecasting the traffic flows is a critical issue for researchers and practitioners in the field of transportation. However, it is very challenging since the traffic flows usually show high nonlinearities and complex patterns. Most existing traffic flow prediction methods, lacking abilities of model…
- **Score**: 7.139

### 126. Exact Matrix Completion via Convex Optimization

- **Year**: 2009 · **Citations**: 3436 · **Type**: journal-article · **API**: crossref
- **Authors**: Emmanuel J. Candès, Benjamin Recht
- **Venue**: Foundations of Computational Mathematics
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1007/s10208-009-9045-5
- **Link**: https://doi.org/10.1007/s10208-009-9045-5
- **Score**: 7.139

### 127. Fractional Programming for Communication Systems—Part I: Power Control and Beamforming

- **Year**: 2018 · **Citations**: 1845 · **Type**: journal-article · **API**: crossref
- **Authors**: Kaiming Shen, Wei Yu
- **Venue**: IEEE Transactions on Signal Processing
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming
- **DOI**: https://doi.org/10.1109/tsp.2018.2812733
- **Link**: https://doi.org/10.1109/tsp.2018.2812733
- **Score**: 7.132

### 128. Necroptosis, pyroptosis and apoptosis: an intricate game of cell death

- **Year**: 2021 · **Citations**: 2021 · **Type**: journal-article · **API**: crossref
- **Authors**: Damien Bertheloot, Eicke Latz, Bernardo S. Franklin
- **Venue**: Cellular &amp; Molecular Immunology
- **Domains**: game_theory_or
- **DOI**: https://doi.org/10.1038/s41423-020-00630-3
- **Link**: https://doi.org/10.1038/s41423-020-00630-3
- **Abstract**: AbstractCell death is a fundamental physiological process in all living organisms. Its roles extend from embryonic development, organ maintenance, and aging to the coordination of immune responses and autoimmunity. In recent years, our understanding of the mechanisms orchestrating cellular death and…
- **Score**: 7.128

### 129. The atomic simulation environment—a Python library for working with atoms

- **Year**: 2017 · **Citations**: 3464 · **Type**: journal-article · **API**: crossref
- **Authors**: Ask Hjorth Larsen, Jens Jørgen Mortensen, Jakob Blomqvist, Ivano E Castelli, Rune Christensen, Marcin Dułak, Jesper Friis, Michael N Groves, Bjørk Hammer, Cory 
- **Venue**: Journal of Physics: Condensed Matter
- **Domains**: queuing_simulation
- **DOI**: https://doi.org/10.1088/1361-648x/aa680e
- **Link**: https://doi.org/10.1088/1361-648x/aa680e
- **Abstract**: Abstract                   The atomic simulation environment (ASE) is a software package written in the Python programming language with the aim of setting up, steering, and analyzing atomistic simulations. In ASE, tasks are fully scripted in Python. The powerful syntax of Python combined with the N…
- **Score**: 7.122

### 130. From a literature review to a conceptual framework for sustainable supply chain management

- **Year**: 2008 · **Citations**: 4829 · **Type**: journal-article · **API**: crossref
- **Authors**: Stefan Seuring, Martin Müller
- **Venue**: Journal of Cleaner Production
- **Domains**: inventory_supply_chain
- **DOI**: https://doi.org/10.1016/j.jclepro.2008.04.020
- **Link**: https://doi.org/10.1016/j.jclepro.2008.04.020
- **Score**: 7.090

### 131. Distributed Subgradient Methods for Multi-Agent Optimization

- **Year**: 2009 · **Citations**: 3180 · **Type**: journal-article · **API**: crossref
- **Authors**: Angelia Nedic, Asuman Ozdaglar
- **Venue**: IEEE Transactions on Automatic Control
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1109/tac.2008.2009515
- **Link**: https://doi.org/10.1109/tac.2008.2009515
- **Score**: 7.081

### 132. Dynamic mode decomposition of numerical and experimental data

- **Year**: 2010 · **Citations**: 5210 · **Type**: journal-article · **API**: crossref
- **Authors**: PETER J. SCHMID
- **Venue**: Journal of Fluid Mechanics
- **Domains**: dynamic_programming, column_generation_decomp
- **DOI**: https://doi.org/10.1017/s0022112010001217
- **Link**: https://doi.org/10.1017/s0022112010001217
- **Abstract**: The description of coherent features of fluid flow is essential to our understanding of fluid-dynamical and transport processes. A method is introduced that is able to extract dynamic information from flow fields that are either generated by a (direct) numerical simulation or visualized/measured in …
- **Score**: 7.078

### 133. MODELTEST: testing the model of DNA substitution.

- **Year**: 1998 · **Citations**: 13462 · **Type**: journal-article · **API**: crossref
- **Authors**: D Posada, K A Crandall
- **Venue**: Bioinformatics
- **Domains**: inventory_supply_chain
- **DOI**: https://doi.org/10.1093/bioinformatics/14.9.817
- **Link**: https://doi.org/10.1093/bioinformatics/14.9.817
- **Abstract**: Abstract                SUMMARY: The program MODELTEST uses log likelihood scores to establish the model of DNA evolution that best fits the data. AVAILABILITY: The MODELTEST package, including the source code and some documentation is available at http://bioag.byu. edu/zoology/crandall_lab/modeltes…
- **Score**: 7.059

### 134. The Mythos of Model Interpretability

- **Year**: 2018 · **Citations**: 2512 · **Type**: journal-article · **API**: crossref
- **Authors**: Zachary C. Lipton
- **Venue**: Queue
- **Domains**: scheduling, inventory_supply_chain
- **DOI**: https://doi.org/10.1145/3236386.3241340
- **Link**: https://doi.org/10.1145/3236386.3241340
- **Abstract**: Supervised machine-learning models boast remarkable predictive capabilities. But can you trust your model? Will it work in deployment? What else can it tell you about the world?…
- **Score**: 7.058

### 135. Ant colony system: a cooperative learning approach to the traveling salesman problem

- **Year**: 1997 · **Citations**: 6045 · **Type**: journal-article · **API**: crossref
- **Authors**: M. Dorigo, L.M. Gambardella
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: tsp_routing, inventory_supply_chain, constraint_programming, graph_or, cutting_packing, ml_or_hybrid
- **DOI**: https://doi.org/10.1109/4235.585892
- **Link**: https://doi.org/10.1109/4235.585892
- **Score**: 7.043

### 136. An Adaptive Large Neighborhood Search Heuristic for the Pickup and Delivery Problem with Time Windows

- **Year**: 2006 · **Citations**: 2207 · **Type**: journal-article · **API**: crossref
- **Authors**: Stefan Ropke, David Pisinger
- **Venue**: Transportation Science
- **Domains**: tsp_routing, metaheuristics, inventory_supply_chain, constraint_programming, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1287/trsc.1050.0135
- **Link**: https://doi.org/10.1287/trsc.1050.0135
- **Abstract**: The pickup and delivery problem with time windows is the problem of serving a number of transportation requests using a limited amount of vehicles. Each request involves moving a number of goods from a pickup location to a delivery location. Our task is to construct routes that visit all locations s…
- **Score**: 7.041

### 137. The Byzantine Generals Problem

- **Year**: 1982 · **Citations**: 4386 · **Type**: journal-article · **API**: crossref
- **Authors**: Leslie Lamport, Robert Shostak, Marshall Pease
- **Venue**: ACM Transactions on Programming Languages and Systems
- **Domains**: linear_programming, integer_programming, tsp_routing, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, inventory_supply_chain, constraint_programming, graph_or, cutting_packing, or_foundations_survey
- **DOI**: https://doi.org/10.1145/357172.357176
- **Link**: https://doi.org/10.1145/357172.357176
- **Score**: 7.040

### 138. A Paravascular Pathway Facilitates CSF Flow Through the Brain Parenchyma and the Clearance of Interstitial Solutes, Including Amyloid β

- **Year**: 2012 · **Citations**: 5233 · **Type**: journal-article · **API**: crossref
- **Authors**: Jeffrey J. Iliff, Minghuan Wang, Yonghong Liao, Benjamin A. Plogg, Weiguo Peng, Georg A. Gundersen, Helene Benveniste, G. Edward Vates, Rashid Deane, Steven A. 
- **Venue**: Science Translational Medicine
- **Domains**: network_flows
- **DOI**: https://doi.org/10.1126/scitranslmed.3003748
- **Link**: https://doi.org/10.1126/scitranslmed.3003748
- **Abstract**: Cerebrospinal fluid flows through channels around brain blood vessels that are bounded by astrocytic endfeet, mediated by water transport through aquaporin-4.…
- **Score**: 7.039

### 139. The Amber biomolecular simulation programs

- **Year**: 2005 · **Citations**: 8773 · **Type**: journal-article · **API**: crossref
- **Authors**: David A. Case, Thomas E. Cheatham, Tom Darden, Holger Gohlke, Ray Luo, Kenneth M. Merz, Alexey Onufriev, Carlos Simmerling, Bing Wang, Robert J. Woods
- **Venue**: Journal of Computational Chemistry
- **Domains**: queuing_simulation
- **DOI**: https://doi.org/10.1002/jcc.20290
- **Link**: https://doi.org/10.1002/jcc.20290
- **Abstract**: AbstractWe describe the development, current features, and some directions for future development of the Amber package of computer programs. This package evolved from a program that was constructed in the late 1970s to do Assisted Model Building with Energy Refinement, and now contains a group of pr…
- **Score**: 7.030

### 140. Polymorphic transitions in single crystals: A new molecular dynamics method

- **Year**: 1981 · **Citations**: 19219 · **Type**: journal-article · **API**: crossref
- **Authors**: M. Parrinello, A. Rahman
- **Venue**: Journal of Applied Physics
- **Domains**: linear_programming
- **DOI**: https://doi.org/10.1063/1.328693
- **Link**: https://doi.org/10.1063/1.328693
- **Abstract**: A new Lagrangian formulation is introduced. It can be used to make molecular dynamics (MD) calculations on systems under the most general, externally applied, conditions of stress. In this formulation the MD cell shape and size can change according to dynamical equations given by this Lagrangian. Th…
- **Score**: 7.030

### 141. z-Tree: Zurich toolbox for ready-made economic experiments

- **Year**: 2007 · **Citations**: 7658 · **Type**: journal-article · **API**: crossref
- **Authors**: Urs Fischbacher
- **Venue**: Experimental Economics
- **Domains**: graph_or
- **DOI**: https://doi.org/10.1007/s10683-006-9159-4
- **Link**: https://doi.org/10.1007/s10683-006-9159-4
- **Abstract**: Abstractz-Tree (Zurich Toolbox for Ready-made Economic Experiments) is a software for developing and conducting economic experiments. The software is stable and allows programming almost any kind of experiments in a short time. In this article, I present the guiding principles behind the software de…
- **Score**: 7.029

### 142. LOBSTER: A tool to extract chemical bonding from plane‐wave based DFT

- **Year**: 2016 · **Citations**: 3463 · **Type**: journal-article · **API**: crossref
- **Authors**: Stefan Maintz, Volker L. Deringer, Andrei L. Tchougréeff, Richard Dronskowski
- **Venue**: Journal of Computational Chemistry
- **Domains**: constraint_programming
- **DOI**: https://doi.org/10.1002/jcc.24300
- **Link**: https://doi.org/10.1002/jcc.24300
- **Abstract**: The computer program LOBSTER (Local Orbital Basis Suite Towards Electronic‐Structure Reconstruction) enables chemical‐bonding analysis based on periodic plane‐wave (PAW) density‐functional theory (DFT) output and is applicable to a wide range of first‐principles simulations in solid‐state and materi…
- **Score**: 7.028

### 143. Surrogate Gradient Learning in Spiking Neural Networks: Bringing the Power of Gradient-Based Optimization to Spiking Neural Networks

- **Year**: 2019 · **Citations**: 1421 · **Type**: journal-article · **API**: crossref
- **Authors**: Emre O. Neftci, Hesham Mostafa, Friedemann Zenke
- **Venue**: IEEE Signal Processing Magazine
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1109/msp.2019.2931595
- **Link**: https://doi.org/10.1109/msp.2019.2931595
- **Score**: 7.015

### 144. Optimization of parameters for semiempirical methods V: Modification of NDDO approximations and application to 70 elements

- **Year**: 2007 · **Citations**: 3288 · **Type**: journal-article · **API**: crossref
- **Authors**: James J. P. Stewart
- **Venue**: Journal of Molecular Modeling
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1007/s00894-007-0233-4
- **Link**: https://doi.org/10.1007/s00894-007-0233-4
- **Score**: 7.007

### 145. MUSCLE: a multiple sequence alignment method with reduced time and space complexity

- **Year**: 2004 · **Citations**: 7802 · **Type**: journal-article · **API**: crossref
- **Authors**: Robert C Edgar
- **Venue**: BMC Bioinformatics
- **Domains**: linear_programming, tsp_routing
- **DOI**: https://doi.org/10.1186/1471-2105-5-113
- **Link**: https://doi.org/10.1186/1471-2105-5-113
- **Abstract**: Abstract                         Background                         In a previous paper, we introduced MUSCLE, a new program for creating multiple alignments of protein sequences, giving a brief summary of the algorithm and showing MUSCLE to achieve the highest scores reported to date on four alignm…
- **Score**: 7.001

### 146. The method of moving asymptotes—a new method for structural optimization

- **Year**: 1987 · **Citations**: 4900 · **Type**: journal-article · **API**: crossref
- **Authors**: Krister Svanberg
- **Venue**: International Journal for Numerical Methods in Engineering
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1002/nme.1620240207
- **Link**: https://doi.org/10.1002/nme.1620240207
- **Abstract**: AbstractA new method for non‐linear programming in general and structural optimization in particular is presented. In each step of the iterative process, a strictly convex approximating subproblem is generated and solved. The generation of these subproblems is controlled by so called ‘moving asympto…
- **Score**: 6.998

### 147. Comprehensive learning particle swarm optimizer for global optimization of multimodal functions

- **Year**: 2006 · **Citations**: 3347 · **Type**: journal-article · **API**: crossref
- **Authors**: J.J. Liang, A.K. Qin, P.N. Suganthan, S. Baskar
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1109/tevc.2005.857610
- **Link**: https://doi.org/10.1109/tevc.2005.857610
- **Score**: 6.975

### 148. The CCP4 suite: programs for protein crystallography

- **Year**: 1994 · **Citations**: 14099 · **Type**: journal-article · **API**: crossref
- **Authors**: Collaborative Computational Project, Number 4
- **Venue**: Acta Crystallographica Section D Biological Crystallography
- **Domains**: scheduling
- **DOI**: https://doi.org/10.1107/s0907444994003112
- **Link**: https://doi.org/10.1107/s0907444994003112
- **Score**: 6.969

### 149. A mixed-cation lead mixed-halide perovskite absorber for tandem solar cells

- **Year**: 2016 · **Citations**: 2930 · **Type**: journal-article · **API**: crossref
- **Authors**: David P. McMeekin, Golnaz Sadoughi, Waqaas Rehman, Giles E. Eperon, Michael Saliba, Maximilian T. Hörantner, Amir Haghighirad, Nobuya Sakai, Lars Korte, Bernd R
- **Venue**: Science
- **Domains**: integer_programming
- **DOI**: https://doi.org/10.1126/science.aad5845
- **Link**: https://doi.org/10.1126/science.aad5845
- **Abstract**: Perovskites for tandem solar cells                        Improving the performance of conventional single-crystalline silicon solar cells will help increase their adoption. The absorption of bluer light by an inexpensive overlying solar cell in a tandem arrangement would provide a step in the right…
- **Score**: 6.964

### 150. A slacks-based measure of efficiency in data envelopment analysis

- **Year**: 2001 · **Citations**: 5120 · **Type**: journal-article · **API**: crossref
- **Authors**: Kaoru Tone
- **Venue**: European Journal of Operational Research
- **Domains**: constraint_programming
- **DOI**: https://doi.org/10.1016/s0377-2217(99)00407-5
- **Link**: https://doi.org/10.1016/s0377-2217(99)00407-5
- **Score**: 6.954

### 151. Blockchain technology in supply chain operations: Applications, challenges and research opportunities

- **Year**: 2020 · **Citations**: 1348 · **Type**: journal-article · **API**: crossref
- **Authors**: Pankaj Dutta, Tsan-Ming Choi, Surabhi Somani, Richa Butala
- **Venue**: Transportation Research Part E: Logistics and Transportation Review
- **Domains**: inventory_supply_chain
- **DOI**: https://doi.org/10.1016/j.tre.2020.102067
- **Link**: https://doi.org/10.1016/j.tre.2020.102067
- **Score**: 6.951

### 152. Tensor Decomposition for Signal Processing and Machine Learning

- **Year**: 2017 · **Citations**: 1347 · **Type**: journal-article · **API**: crossref
- **Authors**: Nicholas D. Sidiropoulos, Lieven De Lathauwer, Xiao Fu, Kejun Huang, Evangelos E. Papalexakis, Christos Faloutsos
- **Venue**: IEEE Transactions on Signal Processing
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, column_generation_decomp
- **DOI**: https://doi.org/10.1109/tsp.2017.2690524
- **Link**: https://doi.org/10.1109/tsp.2017.2690524
- **Score**: 6.950

### 153. A First-Order Primal-Dual Algorithm for Convex Problems with Applications to Imaging

- **Year**: 2011 · **Citations**: 3405 · **Type**: journal-article · **API**: crossref
- **Authors**: Antonin Chambolle, Thomas Pock
- **Venue**: Journal of Mathematical Imaging and Vision
- **Domains**: network_flows, nonlinear_convex, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1007/s10851-010-0251-1
- **Link**: https://doi.org/10.1007/s10851-010-0251-1
- **Score**: 6.946

### 154. “Neural” computation of decisions in optimization problems

- **Year**: 1985 · **Citations**: 4777 · **Type**: journal-article · **API**: crossref
- **Authors**: J. J. Hopfield, D. W. Tank
- **Venue**: Biological Cybernetics
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1007/bf00339943
- **Link**: https://doi.org/10.1007/bf00339943
- **Score**: 6.945

### 155. Algorithms for the Vehicle Routing and Scheduling Problems with Time Window Constraints

- **Year**: 1987 · **Citations**: 3376 · **Type**: journal-article · **API**: crossref
- **Authors**: Marius M. Solomon
- **Venue**: Operations Research
- **Domains**: tsp_routing, scheduling, or_foundations_survey
- **DOI**: https://doi.org/10.1287/opre.35.2.254
- **Link**: https://doi.org/10.1287/opre.35.2.254
- **Abstract**: This paper considers the design and analysis of algorithms for vehicle routing and scheduling problems with time window constraints. Given the intrinsic difficulty of this problem class, approximation methods seem to offer the most promise for practical size problems. After describing a variety of h…
- **Score**: 6.940

### 156. Proximal Algorithms

- **Year**: 2014 · **Citations**: 2577 · **Type**: journal-article · **API**: crossref
- **Authors**: Neal Parikh, Stephen Boyd
- **Venue**: Foundations and Trends® in Optimization
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective
- **DOI**: https://doi.org/10.1561/2400000003
- **Link**: https://doi.org/10.1561/2400000003
- **Abstract**: This monograph is about a class of optimization algorithms called proximal algorithms. Much like Newton’s method is a standard tool for solving unconstrained smooth optimization problems of modest size, proximal algorithms can be viewed as an analogous tool for nonsmooth, constrained, large-scale, o…
- **Score**: 6.930

### 157. Robust principal component analysis?

- **Year**: 2011 · **Citations**: 4941 · **Type**: journal-article · **API**: crossref
- **Authors**: Emmanuel J. Candès, Xiaodong Li, Yi Ma, John Wright
- **Venue**: Journal of the ACM
- **Domains**: stochastic_or
- **DOI**: https://doi.org/10.1145/1970392.1970395
- **Link**: https://doi.org/10.1145/1970392.1970395
- **Abstract**: This article is about a curious phenomenon. Suppose we have a data matrix, which is the superposition of a low-rank component and a sparse component. Can we recover each component individually? We prove that under some suitable assumptions, it is possible to recover both the low-rank and the sparse …
- **Score**: 6.929

### 158. A review and evaluation of the state-of-the-art in PV solar power forecasting: Techniques and optimization

- **Year**: 2020 · **Citations**: 1146 · **Type**: journal-article · **API**: crossref
- **Authors**: R. Ahmed, V. Sreeram, Y. Mishra, M.D. Arif
- **Venue**: Renewable and Sustainable Energy Reviews
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective
- **DOI**: https://doi.org/10.1016/j.rser.2020.109792
- **Link**: https://doi.org/10.1016/j.rser.2020.109792
- **Score**: 6.921

### 159. Tunicate Swarm Algorithm: A new bio-inspired based metaheuristic paradigm for global optimization

- **Year**: 2020 · **Citations**: 1158 · **Type**: journal-article · **API**: crossref
- **Authors**: Satnam Kaur, Lalit K. Awasthi, A.L. Sangal, Gaurav Dhiman
- **Venue**: Engineering Applications of Artificial Intelligence
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1016/j.engappai.2020.103541
- **Link**: https://doi.org/10.1016/j.engappai.2020.103541
- **Score**: 6.920

### 160. Decomposition of the mean squared error and NSE performance criteria: Implications for improving hydrological modelling

- **Year**: 2009 · **Citations**: 5171 · **Type**: journal-article · **API**: crossref
- **Authors**: Hoshin V. Gupta, Harald Kling, Koray K. Yilmaz, Guillermo F. Martinez
- **Venue**: Journal of Hydrology
- **Domains**: column_generation_decomp
- **DOI**: https://doi.org/10.1016/j.jhydrol.2009.08.003
- **Link**: https://doi.org/10.1016/j.jhydrol.2009.08.003
- **Score**: 6.914

### 161. Robust decomposition of cell type mixtures in spatial transcriptomics

- **Year**: 2022 · **Citations**: 1342 · **Type**: journal-article · **API**: crossref
- **Authors**: Dylan M. Cable, Evan Murray, Luli S. Zou, Aleksandrina Goeva, Evan Z. Macosko, Fei Chen, Rafael A. Irizarry
- **Venue**: Nature Biotechnology
- **Domains**: stochastic_or, column_generation_decomp
- **DOI**: https://doi.org/10.1038/s41587-021-00830-w
- **Link**: https://doi.org/10.1038/s41587-021-00830-w
- **Score**: 6.905

### 162. The SWISS-MODEL workspace: a web-based environment for protein structure homology modelling

- **Year**: 2006 · **Citations**: 6016 · **Type**: journal-article · **API**: crossref
- **Authors**: Konstantin Arnold, Lorenza Bordoli, Jürgen Kopp, Torsten Schwede
- **Venue**: Bioinformatics
- **Domains**: inventory_supply_chain, constraint_programming
- **DOI**: https://doi.org/10.1093/bioinformatics/bti770
- **Link**: https://doi.org/10.1093/bioinformatics/bti770
- **Abstract**: Abstract                Motivation: Homology models of proteins are of great interest for planning and analysing biological experiments when no experimental three-dimensional structures are available. Building homology models requires specialized programs and up-to-date sequence and structural datab…
- **Score**: 6.903

### 163. Box-Behnken design: An alternative for the optimization of analytical methods

- **Year**: 2007 · **Citations**: 2834 · **Type**: journal-article · **API**: crossref
- **Authors**: S.L.C. Ferreira, R.E. Bruns, H.S. Ferreira, G.D. Matos, J.M. David, G.C. Brandão, E.G.P. da Silva, L.A. Portugal, P.S. dos Reis, A.S. Souza, W.N.L. dos Santos
- **Venue**: Analytica Chimica Acta
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1016/j.aca.2007.07.011
- **Link**: https://doi.org/10.1016/j.aca.2007.07.011
- **Score**: 6.898

### 164. How to make a decision: The analytic hierarchy process

- **Year**: 1990 · **Citations**: 7219 · **Type**: journal-article · **API**: crossref
- **Authors**: Thomas L. Saaty
- **Venue**: European Journal of Operational Research
- **Domains**: dynamic_programming
- **DOI**: https://doi.org/10.1016/0377-2217(90)90057-i
- **Link**: https://doi.org/10.1016/0377-2217(90)90057-i
- **Score**: 6.887

### 165. Event-Triggered Real-Time Scheduling of Stabilizing Control Tasks

- **Year**: 2007 · **Citations**: 4353 · **Type**: journal-article · **API**: crossref
- **Authors**: Paulo Tabuada
- **Venue**: IEEE Transactions on Automatic Control
- **Domains**: tsp_routing, scheduling, queuing_simulation
- **DOI**: https://doi.org/10.1109/tac.2007.904277
- **Link**: https://doi.org/10.1109/tac.2007.904277
- **Score**: 6.883

### 166. Topology optimization approaches

- **Year**: 2013 · **Citations**: 2639 · **Type**: journal-article · **API**: crossref
- **Authors**: Ole Sigmund, Kurt Maute
- **Venue**: Structural and Multidisciplinary Optimization
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective
- **DOI**: https://doi.org/10.1007/s00158-013-0978-6
- **Link**: https://doi.org/10.1007/s00158-013-0978-6
- **Score**: 6.878

### 167. An analysis of approximations for maximizing submodular set functions—I

- **Year**: 1978 · **Citations**: 3005 · **Type**: journal-article · **API**: crossref
- **Authors**: G. L. Nemhauser, L. A. Wolsey, M. L. Fisher
- **Venue**: Mathematical Programming
- **Domains**: linear_programming, integer_programming, combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming
- **DOI**: https://doi.org/10.1007/bf01588971
- **Link**: https://doi.org/10.1007/bf01588971
- **Score**: 6.878

### 168. The
                    <scp>M</scp>
                    icrobial
                    <scp>E</scp>
                    fficiency‐
                    <scp>M</scp>
                    atrix
                    <scp>S</scp>
                    tabilization (
                    <scp>MEMS</scp>
                    ) framework integrates plant litter decomposition with soil organic matter stabilization: do labile plant inputs form stable soil organic matter?

- **Year**: 2013 · **Citations**: 3222 · **Type**: journal-article · **API**: crossref
- **Authors**: M. Francesca Cotrufo, Matthew D. Wallenstein, Claudia M. Boot, Karolien Denef, Eldor Paul
- **Venue**: Global Change Biology
- **Domains**: column_generation_decomp
- **DOI**: https://doi.org/10.1111/gcb.12113
- **Link**: https://doi.org/10.1111/gcb.12113
- **Abstract**: Abstract                                        The decomposition and transformation of above‐ and below‐ground plant detritus (litter) is the main process by which soil organic matter (                     SOM                     ) is formed. Yet, research on litter decay and                     SO…
- **Score**: 6.874

### 169. Development of the Alcohol Use Disorders Identification Test (AUDIT): WHO Collaborative Project on Early Detection of Persons with Harmful Alcohol Consumption‐II

- **Year**: 1993 · **Citations**: 10577 · **Type**: journal-article · **API**: crossref
- **Authors**: JOHN B SAUNDERS, OLAF G. AASLAND, THOMAS F. BABOR, JUAN R. DE LA FUENTE, MARCUS GRANT
- **Venue**: Addiction
- **Domains**: scheduling, multiobjective
- **DOI**: https://doi.org/10.1111/j.1360-0443.1993.tb02093.x
- **Link**: https://doi.org/10.1111/j.1360-0443.1993.tb02093.x
- **Abstract**: AbstractThe Alcohol Use Disorders Identification Test (A UDIT) has been developed from a six‐country WHO collaborative project as a screening instrument for hazardous and harmful alcohol consumption. It is a 10‐item questionnaire which covers the domains of alcohol consumption, drinking behaviour, a…
- **Score**: 6.847

### 170. Future paths for integer programming and links to artificial intelligence

- **Year**: 1986 · **Citations**: 3049 · **Type**: journal-article · **API**: crossref
- **Authors**: Fred Glover
- **Venue**: Computers &amp; Operations Research
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming
- **DOI**: https://doi.org/10.1016/0305-0548(86)90048-1
- **Link**: https://doi.org/10.1016/0305-0548(86)90048-1
- **Score**: 6.835

### 171. A survey on routing protocols for wireless sensor networks

- **Year**: 2005 · **Citations**: 2351 · **Type**: journal-article · **API**: crossref
- **Authors**: Kemal Akkaya, Mohamed Younis
- **Venue**: Ad Hoc Networks
- **Domains**: tsp_routing
- **DOI**: https://doi.org/10.1016/j.adhoc.2003.09.010
- **Link**: https://doi.org/10.1016/j.adhoc.2003.09.010
- **Score**: 6.826

### 172. Snake Optimizer: A novel meta-heuristic optimization algorithm

- **Year**: 2022 · **Citations**: 1050 · **Type**: journal-article · **API**: crossref
- **Authors**: Fatma A. Hashim, Abdelazim G. Hussien
- **Venue**: Knowledge-Based Systems
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective
- **DOI**: https://doi.org/10.1016/j.knosys.2022.108320
- **Link**: https://doi.org/10.1016/j.knosys.2022.108320
- **Score**: 6.815

### 173. Evolutionary programming made faster

- **Year**: 1999 · **Citations**: 3297 · **Type**: journal-article · **API**: crossref
- **Authors**: Xin Yao, Yong Liu, Guangming Lin
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming, or_foundations_survey
- **DOI**: https://doi.org/10.1109/4235.771163
- **Link**: https://doi.org/10.1109/4235.771163
- **Score**: 6.811

### 174. Temperature sensitivity of soil carbon decomposition and feedbacks to climate change

- **Year**: 2006 · **Citations**: 5510 · **Type**: journal-article · **API**: crossref
- **Authors**: Eric A. Davidson, Ivan A. Janssens
- **Venue**: Nature
- **Domains**: column_generation_decomp
- **DOI**: https://doi.org/10.1038/nature04514
- **Link**: https://doi.org/10.1038/nature04514
- **Score**: 6.809

### 175. A discrete numerical model for granular assemblies

- **Year**: 1979 · **Citations**: 15248 · **Type**: journal-article · **API**: crossref
- **Authors**: P. A. Cundall, O. D. L. Strack
- **Venue**: Géotechnique
- **Domains**: inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1680/geot.1979.29.1.47
- **Link**: https://doi.org/10.1680/geot.1979.29.1.47
- **Abstract**: The distinct element method is a numerical model capable of describing the mechanical behaviour of assemblies of discs and spheres. The method is based on the use of an explicit numerical scheme in which the interaction of the particles is monitored contact by contact and the motion of the particles…
- **Score**: 6.806

### 176. Network information flow

- **Year**: 2000 · **Citations**: 6322 · **Type**: journal-article · **API**: crossref
- **Authors**: R. Ahlswede, Ning Cai, S.-Y.R. Li, R.W. Yeung
- **Venue**: IEEE Transactions on Information Theory
- **Domains**: network_flows, game_theory_or, queuing_simulation
- **DOI**: https://doi.org/10.1109/18.850663
- **Link**: https://doi.org/10.1109/18.850663
- **Score**: 6.799

### 177. Multiobjective evolutionary algorithms: a comparative case study and the strength Pareto approach

- **Year**: 1999 · **Citations**: 7222 · **Type**: journal-article · **API**: crossref
- **Authors**: E. Zitzler, L. Thiele
- **Venue**: IEEE Transactions on Evolutionary Computation
- **Domains**: multiobjective
- **DOI**: https://doi.org/10.1109/4235.797969
- **Link**: https://doi.org/10.1109/4235.797969
- **Score**: 6.799

### 178. Viability of intertwined supply networks: extending the supply chain resilience angles towards survivability. A position paper motivated by COVID-19 outbreak

- **Year**: 2020 · **Citations**: 1793 · **Type**: journal-article · **API**: crossref
- **Authors**: Dmitry Ivanov, Alexandre Dolgui
- **Venue**: International Journal of Production Research
- **Domains**: inventory_supply_chain
- **DOI**: https://doi.org/10.1080/00207543.2020.1750727
- **Link**: https://doi.org/10.1080/00207543.2020.1750727
- **Score**: 6.796

### 179. Atomic Decomposition by Basis Pursuit

- **Year**: 1998 · **Citations**: 4682 · **Type**: journal-article · **API**: crossref
- **Authors**: Scott Shaobing Chen, David L. Donoho, Michael A. Saunders
- **Venue**: SIAM Journal on Scientific Computing
- **Domains**: column_generation_decomp
- **DOI**: https://doi.org/10.1137/s1064827596304010
- **Link**: https://doi.org/10.1137/s1064827596304010
- **Score**: 6.795

### 180. CLUMPP: a cluster matching and permutation program for dealing with label switching and multimodality in analysis of population structure

- **Year**: 2007 · **Citations**: 5570 · **Type**: journal-article · **API**: crossref
- **Authors**: Mattias Jakobsson, Noah A. Rosenberg
- **Venue**: Bioinformatics
- **Domains**: graph_or
- **DOI**: https://doi.org/10.1093/bioinformatics/btm233
- **Link**: https://doi.org/10.1093/bioinformatics/btm233
- **Abstract**: Abstract                Motivation: Clustering of individuals into populations on the basis of multilocus genotypes is informative in a variety of settings. In population-genetic clustering algorithms, such as BAPS, STRUCTURE and TESS, individual multilocus genotypes are partitioned over a set of cl…
- **Score**: 6.795

### 181. Semidefinite Programming

- **Year**: 1996 · **Citations**: 3275 · **Type**: journal-article · **API**: crossref
- **Authors**: Lieven Vandenberghe, Stephen Boyd
- **Venue**: SIAM Review
- **Domains**: linear_programming, integer_programming, stochastic_or, dynamic_programming, nonlinear_convex, multiobjective, constraint_programming, or_foundations_survey
- **DOI**: https://doi.org/10.1137/1038003
- **Link**: https://doi.org/10.1137/1038003
- **Score**: 6.793

### 182. Laser powder-bed fusion additive manufacturing: Physics of complex melt flow and formation mechanisms of pores, spatter, and denudation zones

- **Year**: 2016 · **Citations**: 2578 · **Type**: journal-article · **API**: crossref
- **Authors**: Saad A. Khairallah, Andrew T. Anderson, Alexander Rubenchik, Wayne E. King
- **Venue**: Acta Materialia
- **Domains**: network_flows
- **DOI**: https://doi.org/10.1016/j.actamat.2016.02.014
- **Link**: https://doi.org/10.1016/j.actamat.2016.02.014
- **Score**: 6.790

### 183. Tensor-Train Decomposition

- **Year**: 2011 · **Citations**: 2213 · **Type**: journal-article · **API**: crossref
- **Authors**: I. V. Oseledets
- **Venue**: SIAM Journal on Scientific Computing
- **Domains**: column_generation_decomp
- **DOI**: https://doi.org/10.1137/090752286
- **Link**: https://doi.org/10.1137/090752286
- **Score**: 6.788

### 184. Constrained model predictive control: Stability and optimality

- **Year**: 2000 · **Citations**: 7145 · **Type**: journal-article · **API**: crossref
- **Authors**: D.Q. Mayne, J.B. Rawlings, C.V. Rao, P.O.M. Scokaert
- **Venue**: Automatica
- **Domains**: scheduling, inventory_supply_chain
- **DOI**: https://doi.org/10.1016/s0005-1098(99)00214-9
- **Link**: https://doi.org/10.1016/s0005-1098(99)00214-9
- **Score**: 6.785

### 185. Simultaneous Optimization of Several Response Variables

- **Year**: 1980 · **Citations**: 4213 · **Type**: journal-article · **API**: crossref
- **Authors**: George Derringer, Ronald Suich
- **Venue**: Journal of Quality Technology
- **Domains**: combinatorial_optimization, stochastic_or, dynamic_programming, nonlinear_convex, metaheuristics, multiobjective, game_theory_or, inventory_supply_chain, queuing_simulation, ml_or_hybrid
- **DOI**: https://doi.org/10.1080/00224065.1980.11980968
- **Link**: https://doi.org/10.1080/00224065.1980.11980968
- **Score**: 6.784

### 186. Optimization Approaches for the Traveling Salesman Problem with Drone

- **Year**: 2018 · **Citations**: 909 · **Type**: journal-article · **API**: crossref
- **Authors**: Niels Agatz, Paul Bouman, Marie Schmidt
- **Venue**: Transportation Science
- **Domains**: tsp_routing, inventory_supply_chain, constraint_programming, cutting_packing
- **DOI**: https://doi.org/10.1287/trsc.2017.0791
- **Link**: https://doi.org/10.1287/trsc.2017.0791
- **Abstract**: The fast and cost-efficient home delivery of goods ordered online is logistically challenging. Many companies are looking for new ways to cross the last mile to their customers. One technology-enabled opportunity that recently has received much attention is the use of drones to support deliveries. A…
- **Score**: 6.784

### 187. An Interior Trust Region Approach for Nonlinear Minimization Subject to Bounds

- **Year**: 1996 · **Citations**: 2672 · **Type**: journal-article · **API**: crossref
- **Authors**: Thomas F. Coleman, Yuying Li
- **Venue**: SIAM Journal on Optimization
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain
- **DOI**: https://doi.org/10.1137/0806023
- **Link**: https://doi.org/10.1137/0806023
- **Score**: 6.783

### 188. Adaptive Dynamic Programming for Control: A Survey and Recent Advances

- **Year**: 2021 · **Citations**: 672 · **Type**: journal-article · **API**: crossref
- **Authors**: Derong Liu, Shan Xue, Bo Zhao, Biao Luo, Qinglai Wei
- **Venue**: IEEE Transactions on Systems, Man, and Cybernetics: Systems
- **Domains**: linear_programming, integer_programming, stochastic_or, nonlinear_convex, multiobjective, constraint_programming
- **DOI**: https://doi.org/10.1109/tsmc.2020.3042876
- **Link**: https://doi.org/10.1109/tsmc.2020.3042876
- **Score**: 6.773

### 189. Hidden fluid mechanics: Learning velocity and pressure fields from flow visualizations

- **Year**: 2020 · **Citations**: 1888 · **Type**: journal-article · **API**: crossref
- **Authors**: Maziar Raissi, Alireza Yazdani, George Em Karniadakis
- **Venue**: Science
- **Domains**: network_flows
- **DOI**: https://doi.org/10.1126/science.aaw4741
- **Link**: https://doi.org/10.1126/science.aaw4741
- **Abstract**: Machine-learning fluid flow                        Quantifying fluid flow is relevant to disciplines ranging from geophysics to medicine. Flow can be experimentally visualized using, for example, smoke or contrast agents, but extracting velocity and pressure fields from this information is tricky. R…
- **Score**: 6.770

### 190. Beamforming Optimization for Wireless Network Aided by Intelligent Reflecting Surface With Discrete Phase Shifts

- **Year**: 2020 · **Citations**: 1177 · **Type**: journal-article · **API**: crossref
- **Authors**: Qingqing Wu, Rui Zhang
- **Venue**: IEEE Transactions on Communications
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective, queuing_simulation
- **DOI**: https://doi.org/10.1109/tcomm.2019.2958916
- **Link**: https://doi.org/10.1109/tcomm.2019.2958916
- **Score**: 6.764

### 191. Reinforcement learning for combinatorial optimization: A survey

- **Year**: 2021 · **Citations**: 613 · **Type**: journal-article · **API**: crossref
- **Authors**: Nina Mazyavkina, Sergey Sviridov, Sergei Ivanov, Evgeny Burnaev
- **Venue**: Computers &amp; Operations Research
- **Domains**: game_theory_or, or_foundations_survey
- **DOI**: https://doi.org/10.1016/j.cor.2021.105400
- **Link**: https://doi.org/10.1016/j.cor.2021.105400
- **Score**: 6.762

### 192. Archimedes optimization algorithm: a new metaheuristic algorithm for solving optimization problems

- **Year**: 2021 · **Citations**: 1037 · **Type**: journal-article · **API**: crossref
- **Authors**: Fatma A. Hashim, Kashif Hussain, Essam H. Houssein, Mai S. Mabrouk, Walid Al-Atabany
- **Venue**: Applied Intelligence
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective
- **DOI**: https://doi.org/10.1007/s10489-020-01893-z
- **Link**: https://doi.org/10.1007/s10489-020-01893-z
- **Score**: 6.743

### 193. A level set method for structural topology optimization

- **Year**: 2003 · **Citations**: 2850 · **Type**: journal-article · **API**: crossref
- **Authors**: Michael Yu Wang, Xiaoming Wang, Dongming Guo
- **Venue**: Computer Methods in Applied Mechanics and Engineering
- **Domains**: combinatorial_optimization, stochastic_or, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation
- **DOI**: https://doi.org/10.1016/s0045-7825(02)00559-5
- **Link**: https://doi.org/10.1016/s0045-7825(02)00559-5
- **Score**: 6.739

### 194. A review on Fenton process for organic wastewater treatment based on optimization perspective

- **Year**: 2019 · **Citations**: 1049 · **Type**: journal-article · **API**: crossref
- **Authors**: Meng-hui Zhang, Hui Dong, Liang Zhao, De-xi Wang, Di Meng
- **Venue**: Science of The Total Environment
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective
- **DOI**: https://doi.org/10.1016/j.scitotenv.2019.03.180
- **Link**: https://doi.org/10.1016/j.scitotenv.2019.03.180
- **Score**: 6.739

### 195. A global optimisation method for robust affine registration of brain images

- **Year**: 2001 · **Citations**: 6348 · **Type**: journal-article · **API**: crossref
- **Authors**: Mark Jenkinson, Stephen Smith
- **Venue**: Medical Image Analysis
- **Domains**: linear_programming, stochastic_or
- **DOI**: https://doi.org/10.1016/s1361-8415(01)00036-6
- **Link**: https://doi.org/10.1016/s1361-8415(01)00036-6
- **Score**: 6.736

### 196. Chimp optimization algorithm

- **Year**: 2020 · **Citations**: 1138 · **Type**: journal-article · **API**: crossref
- **Authors**: M. Khishe, M.R. Mosavi
- **Venue**: Expert Systems with Applications
- **Domains**: combinatorial_optimization, nonlinear_convex, metaheuristics, multiobjective, cutting_packing
- **DOI**: https://doi.org/10.1016/j.eswa.2020.113338
- **Link**: https://doi.org/10.1016/j.eswa.2020.113338
- **Score**: 6.735

### 197. HiC-Pro: an optimized and flexible pipeline for Hi-C data processing

- **Year**: 2015 · **Citations**: 2413 · **Type**: journal-article · **API**: crossref
- **Authors**: Nicolas Servant, Nelle Varoquaux, Bryan R. Lajoie, Eric Viara, Chong-Jian Chen, Jean-Philippe Vert, Edith Heard, Job Dekker, Emmanuel Barillot
- **Venue**: Genome Biology
- **Domains**: scheduling
- **DOI**: https://doi.org/10.1186/s13059-015-0831-x
- **Link**: https://doi.org/10.1186/s13059-015-0831-x
- **Score**: 6.655

### 198. The flying sidekick traveling salesman problem: Optimization of drone-assisted parcel delivery

- **Year**: 2015 · **Citations**: 1554 · **Type**: journal-article · **API**: crossref
- **Authors**: Chase C. Murray, Amanda G. Chu
- **Venue**: Transportation Research Part C: Emerging Technologies
- **Domains**: tsp_routing
- **DOI**: https://doi.org/10.1016/j.trc.2015.03.005
- **Link**: https://doi.org/10.1016/j.trc.2015.03.005
- **Score**: 6.604

### 199. Information Flow and Cooperative Control of Vehicle Formations

- **Year**: 2004 · **Citations**: 3884 · **Type**: journal-article · **API**: crossref
- **Authors**: J.A. Fax, R.M. Murray
- **Venue**: IEEE Transactions on Automatic Control
- **Domains**: network_flows, tsp_routing, or_foundations_survey
- **DOI**: https://doi.org/10.1109/tac.2004.834433
- **Link**: https://doi.org/10.1109/tac.2004.834433
- **Score**: 6.599

### 200. Thermodynamical approach to the traveling salesman problem: An efficient simulation algorithm

- **Year**: 1985 · **Citations**: 2489 · **Type**: journal-article · **API**: crossref
- **Authors**: V. Černý
- **Venue**: Journal of Optimization Theory and Applications
- **Domains**: combinatorial_optimization, tsp_routing, nonlinear_convex, metaheuristics, multiobjective, inventory_supply_chain, queuing_simulation, constraint_programming, graph_or, cutting_packing
- **DOI**: https://doi.org/10.1007/bf00940812
- **Link**: https://doi.org/10.1007/bf00940812
- **Score**: 6.585

## 局限（诚实说明）

1. 「约 2000 篇」指多源检索命中去重后的**候选池规模**，不是人工精读 2000 篇全文。
2. 引用数来自 Crossref `is-referenced-by-count` 等，常低于 Google Scholar。
3. 相关度为启发式；入库 RAG 前建议按域再人工抽检。
4. 清单偏**通用方法/经典+前沿**，不是某道竞赛题的最优解库。
