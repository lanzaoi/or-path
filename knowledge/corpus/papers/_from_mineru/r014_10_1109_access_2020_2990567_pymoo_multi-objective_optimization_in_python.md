# r014_10_1109_access_2020_2990567_pymoo_multi-objective_optimization_in_python


- kind: paper-mineru
- title: r014_10_1109_access_2020_2990567_pymoo_multi-objective_optimization_in_python
- source: path:knowledge/inbox_pdf/or_fulltext/r014_10.1109_access.2020.2990567_pymoo_multi-objective_optimization_in_python.pdf

- kind: paper-mineru
- source_pdf: knowledge/inbox_pdf/or_fulltext/r014_10.1109_access.2020.2990567_pymoo_multi-objective_optimization_in_python.pdf
- preprocess_mode: offline_extract
- extract_backend: pypdf
- note: RAG text for Pi retrieve; not numeric authority.

---
Received March 13, 2020, accepted March 30, 2020, date of publication April 27, 2020, date of current version May 22, 2020.
Digital Object Identifier 10.1 109/ACCESS.2020.2990567
Pymoo: Multi-Objective Optimization in Python
JULIAN BLANK
 AND KAL YANMOY DEB
 , (Fellow, IEEE)
Computer Science and Engineering, Michigan State University, East Lansing, MI 48824, USA
Corresponding author: Julian Blank (blankjul@egr.msu.edu)
This work was supported by Koenig Endowed Chair Grant at Michigan State University, East Lansing, USA.
ABSTRACT Python has become the programming language of choice for research and industry projects
related to data science, machine learning, and deep learning. Since optimization is an inherent part of these
research ﬁelds, more optimization related frameworks have arisen in the past few years. Only a few of them
support optimization of multiple conﬂicting objectives at a time, but do not provide comprehensive tools
for a complete multi-objective optimization task. To address this issue, we have developed pymoo, a multi-
objective optimization framework in Python. We provide a guide to getting started with our framework
by demonstrating the implementation of an exemplary constrained multi-objective optimization scenario.
Moreover, we give a high-level overview of the architecture of pymoo to show its capabilities followed by an
explanation of each module and its corresponding sub-modules. The implementations in our framework are
customizable and algorithms can be modiﬁed/extended by supplying custom operators. Moreover, a variety
of single, multi- and many-objective test problems are provided and gradients can be retrieved by automatic
differentiation out of the box. Also, pymoo addresses practical needs, such as the parallelization of function
evaluations, methods to visualize low and high-dimensional spaces, and tools for multi-criteria decision
making. For more information about pymoo, readers are encouraged to visit: https://pymoo.org.
INDEX TERMS Customization, genetic algorithm, multi-objective optimization, python.
I. INTRODUCTION
Optimization plays an essential role in many scientiﬁc areas,
such as engineering, data analytics, and deep learning. These
ﬁelds are fast-growing and their concepts are employed for
various purposes, for instance gaining insights from a large
data sets or ﬁtting accurate prediction models. Whenever an
algorithm has to handle a signiﬁcantly large amount of data,
an efﬁcient implementation in a suitable programming lan-
guage is important. Python [1] has become the programming
language of choice for the above mentioned research areas
over the last few years, not only because it is easy to use but
also good community support exists. Python is a high-level,
cross-platform, and interpreted programming language that
focuses on code readability. A large number of high-quality
libraries are available and support for any kind of scientiﬁc
computation is ensured. These characteristics make Python
an appropriate tool for many research and industry projects
where the investigations can be rather complex.
A fundamental principle of research is to ensure repro-
ducibility of studies and to provide access to materials
used in the research, whenever possible. In computer sci-
ence, this translates to a sketch of an algorithm and the
The associate editor coordinating the review of this manuscript and
approving it for publication was Halil Y etgin
 .
implementation itself. However, the implementation of opti-
mization algorithms can be challenging and speciﬁcally
benchmarking is time-consuming. Having access to either a
good collection of different source codes or a comprehensive
library is time-saving and avoids an error-prone implementa-
tion from scratch.
To address this need for multi-objective optimization in
Python, we introduce pymoo. The goal of our framework
is not only to provide state of the art optimization algo-
rithms, but also to cover different aspects related to the
optimization process itself. We have implemented single,
multi and many-objective test problems which can be used
as a test-bed for algorithms. In addition to the objective and
constraint values of test problems, gradient information can
be retrieved through automatic differentiation [2]. Moreover,
a parallelized evaluation of solutions can be implemented
through vectorized computations, multi-threaded execution,
and distributed computing. Further, pymoo provides imple-
mentations of performance indicators to measure the qual-
ity of results obtained by a multi-objective optimization
algorithm. Tools for an explorative analysis through visu-
alization of lower and higher-dimensional data are avail-
able and multi-criteria decision making methods guide the
selection of a single solution from a solution set based on
preferences.
VOLUME 8, 2020 This work is licensed under a Creative Commons Attribution 4.0 License. For more information, see https://creativecommons.org/licenses/by/4.0/ 89497
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
Our framework is designed to be extendable through of its
modular implementation. For instance, a genetic algorithm is
assembled in a plug-and-play manner by making use of spe-
ciﬁc sub-modules, such as initial sampling, mating selection,
crossover, mutation and survival selection. Each sub-module
takes care of an aspect independently and, therefore, variants
of algorithms can be initiated by passing different combina-
tions of sub-modules. This concept allows end-users to incor-
porate domain knowledge through custom implementations.
For example, in an evolutionary algorithm a biased initial
sampling module created with the knowledge of domain
experts can guide the initial search.
Furthermore, we like to mention that our framework is
well-documented with a large number of available code-
snippets. We created a starter’s guide for users to become
familiar with our framework and to demonstrate its capa-
bilities. As an example, it shows the optimization results
of a bi-objective optimization problem with two constraints.
An extract from the guide will be presented in this paper.
Moreover, we provide an explanation of each algorithm and
source code to run it on a suitable optimization problem in our
software documentation. Additionally, we show a deﬁnition
of test problems and provide a plot of their ﬁtness landscapes.
The framework documentation is built using Sphinx [3] and
correctness of modules is ensured by automatic unit test-
ing [4]. Most algorithms have been developed in collabo-
ration with the second author and have been benchmarked
extensively against the original implementations.
In the remainder of this paper, we ﬁrst present related exist-
ing optimization frameworks in Python and in other program-
ming languages. Then, we provide a guide to getting started
with pymoo in Section III which covers the most important
steps of our proposed framework. In Section IV we illustrate
the framework architecture and the corresponding modules,
such as problems, algorithms and related analytics. Each of
the modules is then discussed separately in Sections V to VII.
Finally, concluding remarks are presented in Section VIII.
II. RELATED WORKS
In the last decades, various optimization frameworks in
diverse programming languages were developed. However,
some of them only partially cover multi-objective optimiza-
tion. In general, the choice of a suitable framework for
an optimization task is a multi-objective problem itself.
Moreover, some criteria are rather subjective, for instance,
the usability and extendibility of a framework and, therefore,
the assessment regarding criteria as well as the decision mak-
ing process differ from user to user. For example, one might
have decided on a programming language ﬁrst, either because
of personal preference or a project constraint, and then search
for a suitable framework. One might give more importance to
the overall features of a framework, for example paralleliza-
tion or visualization, over the programming language itself.
An overview of some existing multi-objective optimization
frameworks in Python is listed in Table 1, each of which is
described in the following.
TABLE 1. Multi-objective optimization frameworks in Python.
Recently, the well-known multi-objective optimization
framework jMetal [5] developed in Java [6] has been ported
to a Python version, namely jMetalPy [7]. The authors aim
to further extend it and to make use of the full feature set
of Python, for instance, data analysis and data visualization.
In addition to traditional optimization algorithms, jMetalPy
also offers methods for dynamic optimization. Moreover,
the post analysis of performance metrics of an experiment
with several independent runs is automated.
Parallel Global Multiobjective Optimizer, PyGMO [8],
is an optimization library for the easy distribution of massive
optimization tasks over multiple CPUs. It uses the gener-
alized island-model paradigm for the coarse grained paral-
lelization of optimization algorithms and, therefore, allows
users to develop asynchronous and distributed algorithms.
Platypus [9] is a multi-objective optimization framework
that offers implementations of state-of-the art algorithms.
It enables users to create an experiment with various algo-
rithms and provides post-analysis methods based on metrics
and visualization.
A Distributed Evolutionary Algorithms in Python
(DEAP) [10] is novel evolutionary computation framework
for rapid prototyping and testing of ideas. Even though,
DEAP does not focus on multi-objective optimization, how-
ever, due to the modularity and extendibility of the framework
multi-objective algorithms can be developed. Moreover, par-
allelization and load-balancing tasks are supported out of the
box.
Inspyred [11] is a framework for creating bio-inspired
computational intelligence algorithms in Python which is
not focused on multi-objective algorithms directly, but on
evolutionary computation in general. However, an example
for NSGA-II [12] is provided and other multi-objective algo-
rithms can be implemented through the modular implemen-
tation of the framework.
If the search for frameworks is not limited to Python, other
popular frameworks should be considered: PlatEMO [13]
in Matlab, MOEA [14] and jMetal [5] in Java, jMetal-
Cpp [15] and PaGMO [16] in C++. Of course this is not
an exhaustive list and readers may search for other available
options.
89498 VOLUME 8, 2020
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
III. GETTING STARTED 1
In the following, we provide a starter’s guide for pymoo.
It covers the most important steps in an optimization scenario
starting with the installation of the framework, deﬁning an
optimization problem, and the optimization procedure itself.
A. INSTALLATION
Our framework pymoo is available on PyPI [17] which is a
central repository to make Python software package easily
accessible. The framework can be installed by using the
package manager:
$ pip install -U pymoo
Some components are available in Python and additionally
in Cython [18]. Cython allows developers to annotate existing
Python code which is translated to C or C++ programming
languages. The translated ﬁles are compiled to a binary exe-
cutable and can be used to speed up computations. During
the installation of pymoo, attempts are made for compilation,
however, if unsuccessful due to the lack of a suitable compiler
or other reasons, the pure Python version is installed. We
would like to emphasize that the compilation is optional
and all features are available without it. More detail about
the compilation and troubleshooting can be found in our
installation guide online.
B. PROBLEM DEFINITION
In general, multi-objective optimization has several objective
functions with subject to inequality and equality constraints
to optimize [19]. The goal is to ﬁnd a set of solutions (variable
vectors) that satisfy all constraints and are as good as possible
regarding all its objectives values. The problem deﬁnition in
its general form is given by:
min fm(x) m= 1,.., M,
s.t. gj(x)≤ 0, j= 1,.., J,
hk (x)= 0, k= 1,.., K,
xL
i ≤ xi≤ xU
i , i= 1,.., N.
(1)
The formulation above deﬁnes a multi-objective optimiza-
tion problem with N variables, M objectives, J inequality, and
K equality constraints. Moreover, for each variable xi, lower
and upper variable boundaries ( xL
i and xU
i ) are also deﬁned.
In the following, we illustrate a bi-objective optimization
problem with two constraints.
min f1(x)= (x2
1+ x2
2 ),
max f2(x)=− (x1− 1)2− x2
2,
s.t. g1(x)= 2 (x1− 0.1) (x1− 0.9)≤ 0,
g2(x)= 20 (x1− 0.4) (x1− 0.6)≥ 0,
− 2≤ x1≤ 2,
− 2≤ x2≤ 2.
(2)
1ALL SOURCE CODES IN THIS PAPER ARE RELA TED TOPYMOO
VERSION 0.4.0. A GETTING STARTED GUIDE FOR UPCOMING VER-
SIONS CAN BE FOUND A T HTTPS://PYMOO.ORG.
It consists of two objectives ( M = 2) where f1(x) is
minimized and f2(x) maximized. The optimization is with
subject to two inequality constraints ( J = 2) where g1(x)
is formulated as a less-than-equal-to and g2(x) as a greater-
than-equal-to constraint. The problem is deﬁned with respect
to two variables ( N = 2), x1 and x2, which both are in the
range [−2, 2]. The problem does not contain any equality
constraints (K= 0). Contour plots of the objective functions
are shown in Figure 1. The contours of the objective function
f1(x) are represented by solid lines and f2(x) by dashed lines.
Constraints g1(x) and g2(x) are parabolas which intersect
the x1-axis at (0 .1, 0.9) and (0 .4, 0.6). The Pareto-optimal
set is marked by a thick orange line. Through the combi-
nation of both constraints the Pareto-set is split into two
parts. Analytically, the Pareto-optimal set is given by PS=
{(x1, x2)| (0.1≤ x1≤ 0.4)∨ (0.6≤ x1≤ 0.9)∧ x2= 0}
and the efﬁcient-front by f2= (√f1− 1)2 where f1 is deﬁned
in [0.01, 0.16] and [0.36, 0.81].
FIGURE 1. Contour plot of the test problem (Equation 2).
In the following, we provide an example implementation
of the problem formulation above using pymoo. We assume
the reader is familiar with Python and has a fundamental
knowledge of NumPy [20] which is utilized to deal with
vector and matrix computations.
In pymoo, we consider pure minimization problems for
optimization in all our modules. However, without loss of
generality an objective which is supposed to be maximized,
can be multiplied by −1 and be minimized [19]. There-
fore, we minimize −f2(x) instead of maximizing f2(x) in
our optimization problem. Furthermore, all constraint func-
tions need to be formulated as a less-than-equal-to constraint.
For this reason, g2(x) needs to be multiplied by −1 to ﬂip
the≥ to a ≤ relation. We recommend the normalization
of constraints to give equal importance to each of them.
For g1(x), the constant ‘resource’ value of the constraint is
2· (−0.1)· (−0.9)= 0.18 and for g2(x) it is 20 · (−0.4)·
(−0.6) = 4.8, respectively. We achieve normalization of
constraints by dividing g1(x) and g2(x) by the corresponding
constant [21].
VOLUME 8, 2020 89499
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
Finally, the optimization problem to be optimized using
pymoo is deﬁned by:
min f1(x)= (x2
1+ x2
2 ),
min f2(x)= (x1− 1)2+ x2
2,
s.t. g1(x)= 2 (x1− 0.1) (x1− 0.9)/ 0.18≤ 0,
g2(x)=− 20 (x1− 0.4) (x1− 0.6)/ 4.8≤ 0,
− 2≤ x1≤ 2,
− 2≤ x2≤ 2.
(3)
Next, the derived problem formulation is implemented
in Python. Each optimization problem in pymoo has to
inherit from the Problem class. First, by calling the
super() function the problem properties such as the num-
ber of variables ( n_var), objectives ( n_obj) and con-
straints (n_constr) are initialized. Furthermore, lower (xl)
and upper variables boundaries (xu) are supplied as a NumPy
array. Additionally, the evaluation function _evaluate
needs to be overwritten from the superclass. The method
takes a two-dimensional NumPy array x with n rows and
m columns as an input. Each row represents an individual
and each column an optimization variable. After doing the
necessary calculations, the objective values are added to the
dictionary out with the key F and the constraints with key G.
As mentioned above, pymoo utilizes NumPy [20] for most
of its computations. To be able to retrieve gradients through
automatic differentiation we are using a wrapper around
NumPy called Autograd [22]. Note that this is not obligatory
for a problem deﬁnition.
C. ALGORITHM INITIALIZATION
Next, we need to initialize a method to optimize the prob-
lem. In pymoo, an algorithm object needs to be created for
optimization. For each of the algorithms an API documenta-
tion is available and through supplying different parameters,
algorithms can be customized in a plug-and-play manner.
In general, the choice of a suitable algorithm for optimization
problems is a challenge itself. Whenever problem character-
istics are known beforehand we recommended using those
through customized operators. However, in our case the opti-
mization problem is rather simple, but the aspect of having
two objectives and two constraints should be considered.
For this reason, we decided to use NSGA-II [12] with its
default conﬁguration with minor modiﬁcations. We chose
a population size of 40, but instead of generating the same
number of offsprings, we create only 10 in each generation.
This is a steady-state variant of NSGA-II and it is likely to
improve the convergence property for rather simple optimiza-
tion problems without much difﬁculties, such as the existence
of local Pareto-fronts. Moreover, we enable a duplicate check
which makes sure that the mating produces offsprings which
are different with respect to themselves and also from the
existing population regarding their variable vectors. To illus-
trate the customization aspect, we listed the other unmodiﬁed
default operators in the code-snippet below. The constructor
of NSGA2 is called with the supplied parameters and returns
an initialized algorithm object.
D. OPTIMIZATION
Next, we use the initialized algorithm object to optimize the
deﬁned problem. Therefore, the minimize function with
both instances problem and algorithm as parameters
is called. Moreover, we supply the termination criterion of
running the algorithm for 40 generations which will result
in 40+ 40× 10= 440 function evaluations. In addition,
we deﬁne a random seed to ensure reproducibility and enable
the verbose ﬂag to see printouts for each generation.
The method returns a Result object which contains the
non-dominated set of solutions found by the algorithm.
The optimization results are illustrated in Figure 2 where
the design space is shown in Figure 2a and in the objective
space in Figure 2b. The solid line represents the analyti-
cally derived Pareto set and front in the corresponding space
and the circles solutions found by the algorithm. It can be
observed that the algorithm was able to converge and a set
of nearly-optimal solutions was obtained. Some additional
post-processing steps and more details about other aspects of
89500 VOLUME 8, 2020
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
FIGURE 2. Result of the getting started optimization.
the optimization procedure can be found in the remainder of
this paper and in our software documentation.
The starters guide showed the steps starting from the instal-
lation up to solving an optimization problem. The investiga-
tion of a constrained bi-objective problem demonstrated the
basic procedure in an optimization scenario.
IV. ARCHITECTURE
Software architecture is fundamentally important to keep
source code organized. On the one hand, it helps developers
and users to get an overview of existing classes, and on the
other hand, it allows ﬂexibility and extendibility by adding
new modules. Figure 3 visualizes the architecture of pymoo.
The ﬁrst level of abstraction consists of the optimization
problems, algorithms and analytics. Each of the modules can
be categorized into more detail and consists of multiple sub-
modules.
(i) Problems: Optimization problems in our framework
are categorized into single, multi, and many-objective
test problems. Gradients are available through automatic
differentiation and parallelization can be implemented
by using a variety of techniques.
(ii) Optimization: Since most of the algorithms are based
on evolutionary computations, operators such as sam-
pling, mating selection, crossover and mutation have
to be chosen or implemented. Furthermore, because
many problems in practice have one or more con-
straints, a methodology for handling those must be
incorporated. Some algorithms are based on decom-
position which splits the multi-objective problem into
many single-objective problems. Moreover, when the
algorithm is used to solve the problem, a termination
criterion must be deﬁned either explicitly or implicitly
by the implementation of the algorithm.
(iii) Analytics: During and after an optimization run analyt-
ics support the understanding of data. First, intuitively
the design space, objective space, or other metrics can
be explored through visualization. Moreover, to measure
the convergence and/or diversity of a Pareto-optimal set
performance indicators can be used. For real-parameter
problems, recently proposed theoretical KKT proxim-
ity metric [23] computation procedure is included in
pymoo to compute the proximity of a solution to the
true Pareto-optimal front, despite not knowing its exact
location. To support the decision making process either
through ﬁnding points close to the area of interest in
FIGURE 3. Architecture of pymoo.
VOLUME 8, 2020 89501
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
the objective space or high trade-off solutions. This can
be applied either during an optimization run to mimic
interactive optimization or as a post analysis.
In the remainder of the paper, we will discuss each of the
modules mentioned in more detail.
V. PROBLEMS
It is common practice for researchers to evaluate the perfor-
mance of algorithms on a variety of test problems. Since we
know no single-best algorithm for all arbitrary optimization
problems exist [24], this helps to identify problem classes
where the algorithm is suitable. Therefore, a collection of
test problems with different numbers of variables, objectives
or constraints and alternating complexity becomes handy
for algorithm development. Moreover, in a multi-objective
context, test problems with different Pareto-front shapes or
varying variable density close to the optimal region are of
interest.
A. IMPLEMENTATIONS
In our framework, we categorize test problems regarding
the number of objectives: single-objective (1 objective),
multi-objective (2 or 3 objectives) and many-objective (more
than 3 objectives). Test problems implemented in pymoo are
listed in Table 2. For each problem the number of variables,
objectives, and constraints are indicated. If the test problem
is scalable to any of the parameters, we label the problem
with (s). If the problem is scalable, but a default number was
original proposed we indicate that with surrounding brackets.
In case the category does not apply, for example because
we refer to a test problem family with several functions,
we use (·).
The implementations in pymoo let end-users deﬁne what
values of the corresponding problem should be returned.
On an implementation level, the evaluate function of a
Problem instance takes a list return_value_of which
contains the type of values being returned. By default the
objective values “F” and if the problem has constraints the
constraint violation “CV” are included. The constraint func-
tion values can be returned independently by adding “G”.
This gives developers the ﬂexibility to receive the values that
are needed for their methods.
B. GRADIENTS
All our test problems are implemented using Autograd [22].
Therefore, automatic differentiation is supported out of the
box. We have shown in Section III how a new optimization
problem is deﬁned.
If gradients are desired to be calculated the preﬁx
“d” needs to be added to the corresponding value of
the return_value_of list. For instance to ask for the
objective values and its gradients return_value_of =
[“F”, “dF”] .
Let us consider the problem we have implemented shown
in Equation 3. The derivation of the objective functions F
TABLE 2. Multi-objective optimization test problems.
with respect to each variable is given by:
∇F=
[ 2 x1 2 x2
2(x1− 1) 2 x2
]
. (4)
The gradients at the point [0.1, 0.2] are calculated by:
returns the following output
It can easily be veriﬁed that the values are matching with
the analytic gradient derivation. The gradients for the con-
straint functions can be calculated accordingly by adding
“dG” to the return_value_of list.
89502 VOLUME 8, 2020
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
C. PARALLELIZATION
If evaluation functions are computationally expensive,
a serialized evaluation of a set of solutions can become the
bottleneck of the overall optimization procedure. For this rea-
son, parallelization is desired for an use of existing computa-
tional resources more efﬁciently and distribute long-running
calculations. In pymoo, the evaluation function receives a set
of solutions if the algorithm is utilizing a population. This
empowers the user to implement any kind of parallelization
as long as the objective values for all solutions are written
as an output when the evaluation function terminates. In our
framework, a couple of possibilities to implement paralleliza-
tion exist:
(i) V ectorized Evaluation: A common technique to par-
allelize evaluations is to use matrices where each row
represents a solution. Therefore, a vectorized evaluation
refers to a column which includes the variables of all
solutions. By using vectors the objective values of all
solutions are calculated at once. The code-snippet of the
example problem in Section III shows such an imple-
mentation using NumPy [20]. To run calculations on a
GPU, implementing support for PyTorch [25] tensors
can be done with little overhead given suitable hardware
and correctly installed drivers.
(ii) Threaded Loop-wise Evaluation: If the function eval-
uation should occur independently, a for loop can be
used to set the values. By default the evaluation is serial-
ized and no calculations occur in parallel. By providing
a keyword to the evaluation function, pymoo spawns a
thread for each evaluation and manages those by using
the default thread pool implementation in Python. This
behaviour can be implemented out of the box and the
number of parallel threads can be modiﬁed.
(iii) Distributed Evaluation: If the evaluation should not
be limited to a single machine, the evaluation itself can
be distributed to several workers or a whole cluster.
We recommend using Dask [26] which enables dis-
tributed computations on different levels. For instance,
the matrix operation itself can be distributed or a whole
function can be outsourced. Similar to the loop wise
evaluation each individual can be evaluate element-wise
by sending it to a worker.
VI. OPTIMIZATION MODULE
The optimization module provides different kinds of
sub-modules to be used in algorithms. Some of them are more
of a generic nature, such as decomposition and termination
criterion, and others are more related to evolutionary com-
puting. By assembling those modules together algorithms are
built.
A. ALGORITHMS
Available algorithm implementations in pymoo are listed
in Table 3. Compared to other optimization frameworks
the list of algorithms may look rather short, however,
TABLE 3. Multi-objective optimization algorithms.
each algorithm is customizable and variants can be initial-
ized with different parameters. For instance, a Steady-State
NSGA-II [27] can be initialized by setting the number of
offspring to 1. This can be achieved by supplying this as a
parameter in the initialization method as shown in Section III.
Moreover, it is worth mentioning that many-objective algo-
rithms, such as NSGA-III or MOEAD, require reference
directions to be provided. The reference directions are com-
monly desired to be uniform or to have a bias towards a
region of interest. Our framework offers an implementation
of the Das and Dennis method [28] for a ﬁxed number of
points (ﬁxed with respect to a parameter often referred to
as partition number ) and a recently proposed Riesz-Energy
based method which creates a well-spaced point set for an
arbitrary number of points and is capable of introducing a
bias towards preferred regions in the objective space [29].
B. OPERATORS
The following evolutionary operators are available:
(i) Sampling: The initial population is mostly based on
sampling. In some cases it is created through domain
knowledge and/or some solutions are already evalu-
ated, they can directly be used as an initial population.
Otherwise, it can be sampled randomly for real, inte-
ger, or binary variables. Additionally, Latin-Hypercube
Sampling [41] can be used for real variables.
(ii) Crossover: A variety of crossover operators for different
type of variables are implemented. In Figure 4 some of
them are presented. Figures 4a to 4d help to visualize
the information exchange in a crossover with two par-
ents being involved. Each row represents an offspring
and each column a variable. The corresponding boxes
indicate whether the values of the offspring are inherited
from the ﬁrst or from the second parent. For one and
two-point crossovers it can be observed that either one
or two cuts in the variable sequence exist. Contrarily,
the Uniform Crossover (UX) does not have any clear
pattern, because each variable is chosen randomly either
from the ﬁrst or from the second parent. For the Half
Uniform Crossover (HUX) half of the variables, which
VOLUME 8, 2020 89503
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
FIGURE 4. Illustration of some crossover operators for different variables
types.
are different, are exchanged. For the purpose of illus-
tration, we have created two parents that have different
values in 10 different positions. For real variables, Sim-
ulated Binary Crossover [42] is known to be an efﬁcient
crossover. It mimics the crossover of binary encoded
variables. In Figure 4e the probability distribution when
the parents x1= 0.2 and x2= 0.8 where xi∈ [0, 1] with
η= 0.8 are recombined is shown. Analogously, in case
of integer variables we subtract 0 .5 from the lower and
add (0.5−ϵ) to the upper bound before applying the
crossover and round to the nearest integer afterwards
(see Figure 4f).
(iii) Mutation: For real and integer variables Polynomial
Mutation [19], [43] and for binary variables Bitﬂip
mutation [44] is provided.
Different problems require different type of operators.
In practice, if a problem is supposed to be solved repeatedly
and routinely, it makes sense to customize the evolution-
ary operators to improve the convergence of the algorithm.
Moreover, for custom variable types, for instance trees or
mixed variables [45], custom operators [46] can be imple-
mented easily and called by algorithm class. Our software
documentation contains examples for custom modules,
operators and variable types.
C. TERMINATION CRITERION
For every algorithm it must be determined when it should
terminate a run. This can be simply based on a
predeﬁned number of function evaluations, iterations, or a
more advanced criterion, such as the change of a performance
metric over time. For example, we have implemented a ter-
mination criterion based on the variable and objective space
difference between generations. To make the termination
criterion more robust the last k generations are considered.
The largest movement from a solution to its closest neighbour
is tracked across generation and whenever it is below a certain
threshold, the algorithm is considered to have converged.
Analogously, the movement in the objective space can also be
used. In the objective space, however, normalization is more
challenging and has to be addressed carefully. The default
termination criterion for multi-objective problems in pymoo
keeps track of the boundary points in the objective space and
uses them, when they have settled down, for normalization.
More details about the proposed termination criterion can be
found in [47].
D. DECOMPOSITION
Decomposition transforms multi-objective problems into
many single-objective optimization problems [48]. Such a
technique can be either embedded in a multi-objective algo-
rithm and solved simultaneously or independently using a
single-objective optimizer. Some decomposition methods are
based on the lp-metrics with different p values. For instance,
a naive but frequently used decomposition approach is the
Weighted-Sum Method ( p= 1), which is known to be not
able to converge to the non-convex part of a Pareto-front [19].
Moreover, instead of summing values, Tchebysheff Method
(p = ∞) considers only the maximum value of the dif-
ference between the ideal point and a solution. Similarly,
the Achievement Scalarization Function (ASF) [49] and
a modiﬁed version Augmented Achievement Scalarization
Function (AASF) [50] use the maximum of all differences.
Furthermore, Penalty Boundary Intersection (PBI) [40] is
calculated by a weighted sum of the norm of the projection of
a point onto the reference direction and the perpendicular dis-
tance. Also it is worth to note that normalization is essential
for any kind of decomposition. All decomposition techniques
mentioned above are implemented in pymoo.
VII. ANALYTICS
A. PERFORMANCE INDICATORS
For single-objective optimization algorithms the com-
parison regarding performance is rather simple because
each optimization run results in a single best solution.
In multi-objective optimization, however, each run returns
a non-dominated set of solutions. To compare sets of solu-
tions, various performance indicators have been proposed in
the past [51]. In pymoo most commonly used performance
indicators are described:
(i) GD/IGD: Given the Pareto-front PF the deviation
between the non-dominated set S found by the algo-
rithm and the optimum can be measured. Following this
principle, Generational Distance (GD) indicator [52]
89504 VOLUME 8, 2020
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
calculates the average Euclidean distance in the objec-
tive space from each solution in S to the closest solution
in PF. This measures the convergence of S, but does
not indicate whether a good diversity on the Pareto-
front has been reached. Similarly, Inverted Generational
Distance (IGD) indicator [52] measures the average
Euclidean distance in the objective space from each
solution in PF to the closest solution in S. The Pareto-
front as a whole needs to be covered by solutions from
S to minimize the performance metric. Thus, lower the
GD and IGD values, the better is the set. However, IGD
is known to be not Pareto compliant [53].
(ii) GD+/IGD+: A variation of GD and IGD has been
proposed in [53]. The Euclidean distance is replaced by
a distance measure that takes the dominance relation into
account. The authors show that IGD+ is weakly Pareto
compliant.
(iii) Hypervolume: Moreover, the dominated portion of the
objective space can be used to measure the quality of
non-dominated solutions [54]. The higher the hypervol-
ume, the better is the set. Instead of the Pareto-front a
reference point needs to be provided. It has been shown
that Hypervolume is Pareto compliant [55]. Because the
performance metric becomes computationally expen-
sive in higher dimensional spaces the exact measure
becomes intractable. However, we plan to include some
proposed approximation methods in the near future.
Performance indicators are used to compare existing algo-
rithms. Moreover, the development of new algorithms can be
driven by the goodness of different metrics itself.
B. VISUALIZATION
The visualization of intermediate steps or the ﬁnal result is
inevitable. In multi and many-objective optimization, visual-
ization of the objective space is of interest so that trade-off
information among solutions can be easily experienced from
the plots. Depending on the dimension of the objective space,
different types of plots are suitable to represent a single
or a set of solutions. In pymoo the implemented visualiza-
tions wrap around the well-known plotting library in Python
Matplotlib [56]. Keyword arguments provided by Matplotlib
itself are still available which allows to modify for instance
the color, thickness, opacity of lines, points or other shapes.
Therefore, all visualization techniques are customizable and
extendable.
For 2 or 3 objectives, scatter plots (see Figure 5a and 5b)
can give a good intuition about the solution set. Trade-offs
can be observed by considering the distance between two
points. It might be desired to normalize each objective to
make sure a comparison between values is based on relative
and not absolute values. Pairwise Scatter Plots (see Figure 5c)
visualize more than 3 objectives by showing each pair of axes
independently. The diagonal is used to label the correspond-
ing objectives.
Also, high-dimensional data can be illustrated by Parallel
Coordinate Plots (PCP) as shown in Figure 5d. All axes are
plotted vertically and represent an objective. Each solution is
illustrated by a line from the left to the right. The intersec-
tion of a line and an axis indicate the value of the solution
regarding the corresponding objective. For the purpose of
comparison solution(s) can be highlighted by varying color
and opacity.
Moreover, a common practice is to project the higher
dimensional objective values onto the 2D plane using a trans-
formation function. Radviz (Figure 5e) visualizes all points
in a circle and the objective axes are uniformly positioned
around on the perimeter. Considering a minimization problem
and a set of non-dominated solutions, an extreme point very
close to an axis represents the worst solution for that corre-
sponding objective, but is comparably ‘‘good’’ in one or many
other objectives. Similarly, Star Coordinate Plots (Figure 5f)
illustrate the objective space, except that the transformation
function allows solutions outside of the circle.
Heatmaps (Figure 5g) are used to represent the goodness
of solutions through colors. Each row represents a solution
and each column a variable. We leave the choice to the
end-user of what color map to use and whether light or dark
colors illustrate better or worse solutions. Also, solutions can
be sorted lexicographically by their corresponding objective
values.
Instead of visualizing a set of solutions, one solution can
be illustrated at a time. The Petal Diagram (Figure 5h) is a
pie diagram where the objective value is represented by each
piece’s diameter. Colors are used to further distinguish the
pieces. Finally, the Spider-Web or Radar Diagram (Figure 5i)
shows the objectives values as a point on an axis. The ideal
and nadir point [19] is represented by the inner and outer
polygon. By deﬁnition, the solution lies in between those two
extremes. If the objective space ranges are scaled differently,
normalization for the purpose of plotting can be enabled and
the diagram becomes symmetric. New and emerging methods
for visualizing more than three-dimensional efﬁcient solu-
tions, such as 2.5-dimensional PaletteViz plots [57], would
be implemented in the future.
C. DECISION MAKING
In practice, after obtaining a set of non-dominated solu-
tions a single solution has to be chosen for implementation.
pymoo provides a few ‘‘a posteriori’’ approaches for decision
making [19].
(i) Compromise Programming: One way of making a
decision is to compute value of a scalarized and
aggregated function and select one solution based
on minimum or maximum value of the function.
In pymoo a number of scalarization functions described
in Section VI-D can be used to come to a decision
regarding desired weights of objectives.
(ii) Pseudo-Weights: However, a more intuitive way
to chose a solution out of a Pareto-front is the
pseudo-weight vector approach proposed in [19]. The
pseudo weight wi for the i-th objective function is
VOLUME 8, 2020 89505
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
FIGURE 5. Different visualization methods coded in pymoo.
calculated by:
wi= (f max
i − fi(x))/ (f max
i − f min
i )
∑M
m=1(f maxm − fm(x))/ (f maxm − f minm )
. (5)
The normalized distance to the worst solution regarding
each objective i is calculated. It is interesting to note that
for non-convex Pareto-fronts, the pseudo weight does
not correspond to the result of an optimization using
the weighted-sum method. A solution having the closest
pseudo-weight to a target preference vector of objectives
(f1 being preferred twice as important as f2 results in a
target preference vector of (0.667, 0.333)) can be chosen
as the preferred solution from the efﬁcient set.
(iii) High Trade-Off Solutions: Furthermore, high trade-off
solutions are usually of interest, but not straightfor-
ward to detect in higher-dimensional objective spaces.
We have implemented the procedure proposed in [65].
It was described to be embedded in an algorithm to guide
the search; we, however, use it for post-processing. The
metric for each solution pairxi and xj in a non-dominated
set is given by:
T (xi, xj)=
∑M
i=1 max[0, fm(xj)− fm(xi)]
∑M
i=1 max[0, fm(xi)− fm(xj)]
, (6)
where the numerator represents the aggregated sacriﬁce
and the denominator the aggregated gain. The trade-off
measureµ(xi, S) for each solution xi with respect to a
set of neighboring solutions S is obtained by:
µ(xi, S)= min
xj∈S
T (xi, xj) (7)
It ﬁnds the minimum T (xi, xj) from xi to all other
solutions xj ∈ S. Instead of calculating the metric
with respect to all others, we provide the option to
only consider the k closest neighbors in the objective
89506 VOLUME 8, 2020
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
space to reduce the computational complexity. Based
on circumstances, the ‘min’ operator can be replaced
with ‘average’, or ‘max’, or any other suitable operator.
Thereafter, the solution having the maximum µ can
be chosen as the preferred solution, meaning that this
solution causes a maximum sacriﬁce in one of the
objective values for a unit gain in another objective value
for it be the most valuable solution for implementation.
The above methods are algorithmic, but requires an user
interaction to choose a single preferred solution. However,
in real practice, a more problem speciﬁc decision-making
method must be used, such as an interaction EMO method
suggested elsewhere [66]. We emphasize here the fact
that multi-objective frameworks should include methods for
multi-criteria decision making and support end-user further
in choosing a solution out of a trade-off solution set.
VIII. CONCLUDING REMARKS
This paper has introduced pymoo, a multi-objective opti-
mization framework in Python. We have walked through
our framework beginning with the installation up to the
optimization of a constrained bi-objective optimization prob-
lem. Moreover, we have presented the overall architecture of
the framework consisting of three core modules: Problems,
Optimization, and Analytics. Each module has been
described in depth and illustrative examples have been pro-
vided. We have shown that our framework covers various
aspects of multi-objective optimization including the visu-
alization of high-dimensional spaces and multi-criteria deci-
sion making to ﬁnally select a solution out of the obtained
solution set. One distinguishing feature of our framework
with other existing ones is that we have provided a few
options for various key aspects of a multi-objective opti-
mization task, providing standard evolutionary operators
for optimization, standard performance metrics for evalu-
ating a run, standard visualization techniques for showcas-
ing obtained trade-off solutions, and a few approaches for
decision-making. Most such implementations were originally
suggested and developed by the second author and his collab-
orators for more than 25 years. Hence, we consider that the
implementations of all such ideas are authentic and error-free.
Thus, the results from the proposed framework should stay as
benchmark results of implemented procedures.
However, the framework can be deﬁnitely extended to
make it more comprehensive and we are constantly adding
new capabilities based on practicalities learned from our col-
laboration with industries. In the future, we plan to implement
more optimization algorithms and test problems to provide
more choices to end-users. Also, we aim to implement some
methods from the classical literature on single-objective opti-
mization which can also be used for multi-objective opti-
mization through decomposition or embedded as a local
search. So far, we have provided a few basic performance
metrics. We plan to extend this by creating a module that
runs a list of algorithms on test problems automatically and
provides a statistics of different performance indicators.
Furthermore, we like to mention that any kind of con-
tribution is more than welcome. We see our framework as
a collaborative collection from and to the multi-objective
optimization community. By adding a method or algorithm to
pymoo the community can beneﬁt from a growing compre-
hensive framework and it can help researchers to advertise
their methods. Interested researchers are welcome to con-
tact the authors. In general, different kinds of contributions
are possible and more information can be found online.
Moreover, we would like to mention that even though we
try to keep our framework as bug-free as possible, in case
of exceptions during the execution or doubt of correctness,
please contact us directly or use our issue tracker.
REFERENCES
[1] G. Rossum, ‘‘Python reference manual,’’ CWI, Amsterdam, The
Netherlands, Tech. Rep. 10.5555/869369, 1995. [Online]. Available:
https://dl.acm.org/doi/book/10.5555/869369
[2] M. Bücker, G. Corliss, P . Hovland, U. Naumann, and B. Norris, Auto-
matic Differentiation: Applications, Theory, and Implementations (Lec-
ture Notes in Computational Science and Engineering). Berlin, Germany:
Springer-V erlag, 2006.
[3] G. Brandl. (2019). Sphinx Documentation . [Online]. Available:
https://www.sphinx-doc.org/
[4] A. Pajankar, Python Unit Test Automation: Practical Techniques for Python
Developers and Testers, 1st ed. Berkely, CA, USA: Apress, 2017.
[5] J. J. Durillo and A. J. Nebro, ‘‘JMetal: A java framework for multi-
objective optimization,’’ Adv. Eng. Softw. , vol. 42, no. 10, pp. 760–771,
Oct. 2011. [Online]. Available: http://www.sciencedirect.com/science/
article/pii/S0965997811001219
[6] J. Gosling, B. Joy, G. L. Steele, G. Bracha, and A. Buckley, The Java
Language Speciﬁcation, Java SE 8 Edition , 1st ed. Reading, MA, USA:
Addison-Wesley, 2014.
[7] A. Benítez-Hidalgo, A. J. Nebro, J. García-Nieto, I. Oregi, and
J. Del Ser, ‘‘JMetalPy: A Python framework for multi-objective
optimization with metaheuristics,’’ Swarm Evol. Comput. , vol. 51,
Dec. 2019, Art. no. 100598. [Online]. Available: http://www.sciencedirect.
com/science/article/pii/S2210650219301397
[8] D. Izzo, ‘‘PyGMO and PyKEP: Open source tools for massively parallel
optimization in astrodynamics (the case of interplanetary trajectory
optimization),’’ in 5th Int. Conf. Astrodyn. Tools Techn. (ICATT) , 2012.
[Online]. Available: http://www.esa.int/gsp/ACT/doc/MAD/pub/ACT-
RPR-MAD-2012-(ICA TT)PyKEP-PaGMO-SOCIS.pdf
[9] D. Hadka. Platypus: Multiobjective Optimization in Python . Accessed:
May 16, 2019. [Online]. Available: https://platypus.readthedocs.io
[10] F.-A. Fortin, F.-M. De Rainville, M.-A. Gardner, M. Parizeau, and
C. Gagné, ‘‘DEAP: Evolutionary algorithms made easy,’’ J. Mach. Learn.
Res., vol. 13, pp. 2171–2175, Jul. 2012.
[11] A. Garrett. Inspyred: Python Library for Bio-Inspired Computational Intel-
ligence. Accessed: May 16, 2019. [Online]. Available: https://github.com/
aarongarrett/inspyred
[12] K. Deb, A. Pratap, S. Agarwal, and T. Meyarivan, ‘‘A fast and elitist
multiobjective genetic algorithm: NSGA-II,’’ IEEE Trans. Evol. Comput.,
vol. 6, no. 2, pp. 182–197, Apr. 2002, doi: 10.1109/4235.996017.
[13] Y . Tian, R. Cheng, X. Zhang, and Y . Jin, ‘‘PlatEMO: A MA TLAB platform
for evolutionary multi-objective optimization [Educational Forum],’’IEEE
Comput. Intell. Mag., vol. 12, no. 4, pp. 73–87, Nov. 2017.
[14] D. Hadka. MOEA Framework: A Free and Open Source Java Framework
for Multiobjective Optimization. Accessed: May 16, 2019. [Online]. Avail-
able: http://moeaframework.org
[15] E. López-Camacho, M. J. García Godoy, A. J. Nebro, and
J. F. Aldana-Montes, ‘‘JMetalCpp: Optimizing molecular docking
problems with a C++ Metaheuristic framework,’’ Bioinformatics, vol. 30,
no. 3, pp. 437–438, Feb. 2014, doi: 10.1093/bioinformatics/btt679.
[16] F. Biscani, D. Izzo, and C. H. Y am, ‘‘A global optimisation toolbox for mas-
sively parallel engineering optimisation,’’ Apr. 2010, arXiv:1004.3824.
[Online]. Available: http://arxiv.org/abs/1004.3824
[17] PS Foundation. PyPI: The Python Package Index. Accessed: May 20, 2019.
[Online]. Available: https://pypi.org
VOLUME 8, 2020 89507
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
[18] S. Behnel, R. Bradshaw, C. Citro, L. Dalcin, D. S. Seljebotn, and K. Smith,
‘‘Cython: The best of both worlds,’’ Comput. Sci. Eng. , vol. 13, no. 2,
pp. 31–39, Mar. 2011.
[19] K. Deb, Multi-Objective Optimization Using Evolutionary Algorithms .
New Y ork, NY , USA: Wiley, 2001.
[20] T. Oliphant, NumPy: A Guide to NumPy . USA: Trelgol
Publishing, 2006. Accessed: May 16, 2019. [Online]. Available:
https://web.mit.edu/dvp/Public/numpybook.pdf
[21] K. Deb and R. Datta, ‘‘A bi-objective constrained optimization algorithm
using a hybrid evolutionary and penalty function approach,’’ Eng. Optim.,
vol. 45, no. 5, pp. 503–527, May 2013.
[22] D. Maclaurin, D. Duvenaud, and R. P . Adams, ‘‘Autograd: Effortless
gradients in numpy,’’ in Proc. ICML AutoML Workshop , 2015. [Online].
Available: https://bib/maclaurin/maclaurinautograd/automl-short.pdf,
https://indico.lal.in2p3.fr/event/2914/session/1/contribution/6/3/
material/paper/0.pdf, and https://github.com/HIPS/autograd
[23] K. Deb and M. Abouhawwash, ‘‘An optimality theory based proximity
measure for set based multi-objective optimization,’’ IEEE Trans. Evol.
Comput., vol. 20, no. 4, pp. 515–528, Sep. 2016.
[24] D. H. Wolpert and W. G. Macready, ‘‘No free lunch theorems for optimiza-
tion,’’IEEE Trans. Evol. Comput., vol. 1, no. 1, pp. 67–82, Apr. 1997, doi:
10.1109/4235.585893.
[25] A. Paszke, S. Gross, S. Chintala, G. Chanan, E. Y ang, Z. DeVito,
Z. Lin, A. Desmaison, L. Antiga, and A. Lerer, ‘‘Automatic
differentiation in pytorch,’’ Tech. Rep., 2017. [Online]. Available:
https://github.com/pytorch/pytorch/blob/master/CITA TION
[26] Dask Development Team. (2016). Dask: Library for Dynamic Task
Scheduling. [Online]. Available: https://dask.org
[27] S. Mishra, S. Mondal, and S. Saha, ‘‘Fast implementation of steady-
state NSGA-II,’’ in Proc. IEEE Congr . Evol. Comput. (CEC) , Jul. 2016,
pp. 3777–3784.
[28] I. Das and J. E. Dennis, ‘‘Normal-boundary intersection: A new
method for generating the Pareto surface in nonlinear multicriteria
optimization problems,’’ SIAM J. Optim. , vol. 8, no. 3, pp. 631–657,
Aug. 1998.
[29] J. Blank, K. Deb, Y . Dhebar, S. Bandaru, and H. Seada, ‘‘Generating
well-spaced points on a unit simplex for evolutionary many-objective
optimization,’’ IEEE Trans. Evol. Comput. , early access, May 6, 2020.
[Online]. Available: https://ieeexplore.ieee.org/document/9086772, doi:
10.1109/TEVC.2020.2992387.
[30] J. C. Bean, ‘‘Genetic algorithms and random keys for sequencing and
optimization,’’ ORSA J. Comput. , vol. 6, no. 2, pp. 154–160, May 1994,
doi: 10.1287/ijoc.6.2.154.
[31] K. Price, R. M. Storn, and J. A. Lampinen, Differential Evolution: A
Practical Approach to Global Optimization (Natural Computing Series).
Berlin, Germany: Springer-V erlag, 2005.
[32] J. A. Nelder and R. Mead, ‘‘A simplex method for function min-
imization,’’ Comput. J. , vol. 7, no. 4, pp. 308–313, Jan. 1965, doi:
10.1093/comjnl/7.4.308.
[33] N. Hansen, The CMA Evolution Strategy: A Comparing Review . Berlin,
Germany: Springer, 2006, pp. 75–102, doi: 10.1007/3-540-32494-1_4.
[34] K. Deb and J. Sundar, ‘‘Reference point based multi-objective optimiza-
tion using evolutionary algorithms,’’ in Proc. 8th Annu. Conf. Genetic
Evol. Comput. (GECCO) , New Y ork, NY , USA, 2006, pp. 635–642, doi:
10.1145/1143997.1144112.
[35] K. Deb and H. Jain, ‘‘An evolutionary many-objective optimization algo-
rithm using reference-point-based nondominated sorting approach, part
I: Solving problems with box constraints,’’ IEEE Trans. Evol. Comput. ,
vol. 18, no. 4, pp. 577–601, Aug. 2014.
[36] H. Jain and K. Deb, ‘‘An evolutionary many-objective optimization algo-
rithm using reference-point based nondominated sorting approach, part II:
Handling constraints and extending to an adaptive approach,’’IEEE Trans.
Evol. Comput., vol. 18, no. 4, pp. 602–622, Aug. 2014.
[37] J. Blank, K. Deb, and P . C. Roy, ‘‘Investigating the normalization pro-
cedure of NSGA-III,’’ in Evolutionary Multi-Criterion Optimization ,
K. Deb, E. Goodman, C. A. Coello Coello, K. Klamroth, K. Miettinen,
S. Mostaghim, and P . Reed, Eds. Cham, Switzerland: Springer, 2019,
pp. 229–240.
[38] H. Seada and K. Deb, ‘‘A uniﬁed evolutionary optimization procedure
for single, multiple, and many objectives,’’ IEEE Trans. Evol. Comput. ,
vol. 20, no. 3, pp. 358–369, Jun. 2016.
[39] Y . V esikar, K. Deb, and J. Blank, ‘‘Reference point based NSGA-III for
preferred solutions,’’ in Proc. IEEE Symp. Ser . Comput. Intell. (SSCI) ,
Nov. 2018, pp. 1587–1594.
[40] Q. Zhang and H. Li, ‘‘A multi-objective evolutionary algorithm based on
decomposition,’’ IEEE Trans. Evol. Comput. , vol. 11, no. 6, pp. 712–731,
Dec. 2007.
[41] M. D. McKay, R. J. Beckman, and W. J. Conover, ‘‘A comparison of
three methods for selecting values of input variables in the analysis of
output from a computer code,’’ Technometrics, vol. 42, no. 1, pp. 55–61,
Feb. 2000, doi: 10.2307/1271432.
[42] K. Deb, K. Sindhya, and T. Okabe, ‘‘Self-adaptive simulated binary
crossover for real-parameter optimization,’’ in Proc. 9th Annu. Conf.
Genetic Evol. Comput. (GECCO) , New Y ork, NY , USA, 2007,
pp. 1187–1194, doi: 10.1145/1276958.1277190.
[43] K. Deb and D. Deb, ‘‘Analysing mutation schemes for real-parameter
genetic algorithms,’’ Int. J. Artif. Intell. Soft Comput. , vol. 4, no. 1,
pp. 1–28, 2014.
[44] D. E. Goldberg, Genetic Algorithms for Search, Optimization, and
Machine Learning. Reading, MA, USA: Addison-Wesley, 1989.
[45] K. Deb and M. Goyal, ‘‘A ﬂexible optimization procedure for mechanical
component design based on genetic adaptive search,’’ J. Mech. Design ,
vol. 120, no. 2, pp. 162–164, Jun. 1998.
[46] K. Deb and C. Myburgh, ‘‘A population-based fast algorithm for a billion-
dimensional resource allocation problem with integer variables,’’ Eur . J.
Oper . Res., vol. 261, no. 2, pp. 460–474, Sep. 2017.
[47] J. Blank and K. Deb, ‘‘A running performance metric and termination cri-
terion for evaluating evolutionary multi- and many-objective optimization
algorithms,’’ in Proc. IEEE World Congr . Comput. Intell. (WCCI), 2020.
[48] A. Santiago, H. J. F. Huacuja, B. Dorronsoro, J. E. Pecero, C. G. Santillan,
J. J. G. Barbosa, and J. C. S. Monterrubio, A Survey of Decomposition
Methods for Multi-Objective Optimization . Cham, Switzerland: Springer,
2014, pp. 453–465, doi: 10.1007/978-3-319-05170-3_31.
[49] A. P . Wierzbicki, ‘‘The use of reference objectives in multiobjective opti-
mization,’’ in Multiple Criteria Decision Making Theory and Application .
Cham, Switzerland: Springer, 1980, pp. 468–486.
[50] A. P . Wierzbicki, ‘‘A mathematical basis for satisﬁcing decision mak-
ing,’’ Math. Model., vol. 3, no. 5, pp. 391–405, 1982. [Online]. Available:
http://www.sciencedirect.com/science/article/pii/0270025582900380
[51] J. Knowles and D. Corne, ‘‘On metrics for comparing non-dominated sets,’’
in Proc. Congr . Evol. Comput. Conf. (CEC), 2002, pp. 711–716.
[52] D. A. V . V eldhuizen and D. A. V . V eldhuizen, ‘‘Multiobjective evo-
lutionary algorithms: Classiﬁcations, analyses, and new innovations,’’
Evol. Comput., Air Force Inst. Technol., Dayton, OH, USA, Tech. Rep.
AFIT/DS/ENG/99-01, 1999.
[53] H. Ishibuchi, H. Masuda, Y . Tanigaki, and Y . Nojima, ‘‘Modiﬁed dis-
tance calculation in generational distance and inverted generational dis-
tance,’’ in Evolutionary Multi-Criterion Optimization , A. Gaspar-Cunha,
C. H. Antunes, and C. C. Coello, Eds. Cham, Switzerland: Springer, 2015,
pp. 110–125.
[54] E. Zitzler and L. Thiele, ‘‘Multiobjective optimization using evo-
lutionary algorithms—A comparative case study,’’ in Proc. 5th Int.
Conf. Parallel Problem Solving from Nature (PPSN), V . London,
UK, U.K.: Springer-V erlag, 1998, pp. 292–304. [Online]. Available:
http://dl.acm.org/citation.cfm?id=645824.668610
[55] E. Zitzler, D. Brockhoff, and L. Thiele, ‘‘The hypervolume indicator
revisited: On the design of Pareto-compliant indicators via weighted inte-
gration,’’ in Proc. 4th Int. Conf. Evol. Multi-Criterion Optim. (EMO) ,
Berlin, Germany: Springer-V erlag, 2007, pp. 862–876. [Online]. Avail-
able: http://dl.acm.org/citation.cfm?id=1762545.1762618
[56] J. D. Hunter, ‘‘Matplotlib: A 2D graphics environment,’’ Comput. Sci. Eng.,
vol. 9, no. 3, pp. 90–95, 2007.
[57] A. K. A. Talukder and K. Deb, ‘‘PaletteViz: A visualization method for
functional understanding of high-dimensional Pareto-optimal data-sets to
aid multi-criteria decision making,’’ IEEE Comput. Intell. Mag. , vol. 15,
no. 2, pp. 36–48, May 2020.
[58] J. M. Chambers and B. Kleiner, ‘‘10 graphical techniques for multivariate
data and for clustering,’’ Tech. Rep., 1982.
[59] E. J. Wegman, ‘‘Hyperdimensional data analysis using parallel coordi-
nates,’’ J. Amer . Stat. Assoc., vol. 85, no. 411, pp. 664–675, Sep. 1990.
[60] P . Hoffman, G. Grinstein, and D. Pinkney, ‘‘Dimensional anchors: A
graphic primitive for multidimensional multivariate information visualiza-
tions,’’ inProc. Workshop New Paradigms Inf. Vis. Manipulation Conjunct
8th ACM Int. Conf. Inf. Knowl. Manage. (NPIVM) , New Y ork, NY , USA,
1999, pp. 9–16.
[61] E. Kandogan, ‘‘Star coordinates: A multi-dimensional visualization tech-
nique with uniform treatment of dimensions,’’ in Proc. IEEE Inf. Vis.
Symp., Late Breaking Hot Topics, Oct. 2000, pp. 9–12.
89508 VOLUME 8, 2020
J. Blank, K. Deb: Pymoo: Multi-Objective Optimization in Python
[62] A. Pryke, S. Mostaghim, and A. Nazemi, ‘‘Heatmap visualization of popu-
lation based multi objective algorithms,’’ in Evolutionary Multi-Criterion
Optimization, S. Obayashi, K. Deb, C. Poloni, T. Hiroyasu, and T. Murata,
Eds. Berlin, Germany: Springer, 2007, pp. 361–375.
[63] Y . S. Tan and N. M. Fraser, ‘‘The modiﬁed star graph and the petal diagram:
Two new visual aids for discrete alternative multicriteria decision making,’’
J. Multi-Criteria Decis. Anal. , vol. 7, no. 1, pp. 20–33, Jan. 1998.
[64] E. Kasanen, R. Östermark, and M. Zeleny, ‘‘Gestalt system of holis-
tic graphics: New management support view of MCDM,’’ Comput. OR ,
vol. 18, no. 2, pp. 233–239, 1991, doi: 10.1016/0305-0548(91)90093-7.
[65] L. Rachmawati and D. Srinivasan, ‘‘Multiobjective evolutionary algorithm
with controllable focus on the knees of the Pareto front,’’IEEE Trans. Evol.
Comput., vol. 13, no. 4, pp. 810–824, Aug. 2009.
[66] K. Deb, A. Sinha, P . J. Korhonen, and J. Wallenius, ‘‘An interactive
evolutionary multiobjective optimization method based on progressively
approximated value functions,’’IEEE Trans. Evol. Comput., vol. 14, no. 5,
pp. 723–739, Oct. 2010.
JULIAN BLANK received the B.Sc. degree in
business information systems and the M.Sc. degree
in computer science from Otto von Guericke Uni-
versity, Germany, in 2010 and 2016, respectively.
He is currently pursuing the Ph.D. degree in com-
puter science with Michigan State University, East
Lansing, MI, USA. He was a Visiting Scholar for
six months with the Michigan State University,
in 2015. His current research interests include
multi-objective optimization, evolutionary compu-
tation, surrogate-assisted optimization, and machine learning.
KAL YANMOY DEB (Fellow, IEEE) received
the bachelor’s degree in mechanical engineering
from IIT Kharagpur, India, and the master’s and
Ph.D. degrees from the University of Alabama,
Tuscaloosa, AL, USA, in 1989 and 1991,
respectively.
He is currently the Koenig Endowed Chair
Professor with the Department of Electrical and
Computer Engineering, Michigan State Univer-
sity, East Lansing, MI, USA. He is also largely
known for his seminal research in evolutionary multi-criterion optimization.
He has authored two text books on optimization and published more than
535 international journal and conference research papers to date. His current
research interests include evolutionary optimization and its application in
design, AI, and machine learning. He is one of the top cited EC researchers
with more than 140 000 Google Scholar citations.
Dr. Deb is a Fellow of ASME. He was a recipient of the Shanti Swarup
Bhatnagar Prize in Engineering Sciences, in 2005, the Edgeworth-Pareto
Award, in 2008, the CajAstur Mamdani Prize, in 2011, the Distinguished
Alumni Award from IIT Kharagpur, in 2011, the Infosys Prize, in 2012,
the TW AS Prize in Engineering Sciences, in 2012, the Lifetime Achievement
Award from Clarivate Analytics, in 2017, the IEEE CIS EC Pioneer Award,
in 2018, and the Thomson Citation Laureate Award from Thompson Reuters.
http://www.coin-lab.org.
VOLUME 8, 2020 89509
