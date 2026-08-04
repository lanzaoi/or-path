# r009_10_1016_j_ejor_2020_07_063_machine_learning_for_combinatorial_optimization_


- kind: paper-mineru
- title: r009_10_1016_j_ejor_2020_07_063_machine_learning_for_combinatorial_optimization_
- source: path:knowledge/inbox_pdf/or_fulltext/r009_10.1016_j.ejor.2020.07.063_machine_learning_for_combinatorial_optimization_a_methodolog.pdf

- kind: paper-mineru
- source_pdf: knowledge/inbox_pdf/or_fulltext/r009_10.1016_j.ejor.2020.07.063_machine_learning_for_combinatorial_optimization_a_methodolog.pdf
- preprocess_mode: offline_extract
- extract_backend: pypdf
- note: RAG text for Pi retrieve; not numeric authority.

---
arXiv:1811.06128v2  [cs.LG]  12 Mar 2020
Machine Learning for Combinatorial Optimization:
a Methodological Tour d’Horizon∗
Yoshua Bengio2,3, Andrea Lodi 1,3, and Antoine Prouvost 1,3
yoshua.bengio@mila.quebec
{andrea.lodi, antoine.prouvost }@polymtl.ca
1Canada Excellence Research Chair in Data Science for Decision
Making, ´Ecole Polytechnique de Montr´ eal
2Department of Computer Science and Operations Research,
Universit´ e de Montr´ eal
3Mila, Quebec Artiﬁcial Intelligence Institute
Abstract
This paper surveys the recent attempts, both from the machine
learning and operations research communities, at leveraging machin e
learning to solve combinatorial optimization problems. Given the hard
nature of these problems, state-of-the-art algorithms rely on h and-
crafted heuristics for making decisions that are otherwise too exp ensive
to compute or mathematically not well deﬁned. Thus, machine learn-
ing looks like a natural candidate to make such decisions in a more
principled and optimized way. We advocate for pushing further the
integration of machine learning and combinatorial optimization and
detail a methodology to do so. A main point of the paper is seeing
generic optimization problems as data points and inquiring what is
the relevant distribution of problems to use for learning on a given
task.
1 Introduction
Operations research, also referred to as prescriptive anal ytics, started in the
second world war as an initiative to use mathematics and comp uter science
∗ Accepted to the European Journal of Operations Research. c⃝ 2020. Licensed under
the Creative Commons cbnd
1
to assist military planners in their decisions (Fortun and S chweber, 1993).
Nowadays, it is widely used in the industry, including but no t limited to
transportation, supply chain, energy, ﬁnance, and schedul ing. In this pa-
per, we focus on discrete optimization problems formulated as integer con-
strained optimization, i.e., with integral or binary variables (called decision
variables). While not all such problems are hard to solve ( e.g., shortest
path problems), we concentrate on combinatorial optimizat ion (CO) prob-
lems (NP-hard). This is bad news, in the sense that, for those problems, it is
considered unlikely that an algorithm whose running time is polynomial in
the size of the input exists. However, in practice, CO algori thms can solve
instances with up to millions of decision variables and cons traints.
How is it possible to solve NP-hard problems in practical tim e? Let us
look at the example of the traveling salesman problem (TSP), a NP-hard
problem deﬁned on a graph where we are searching for a cycle of minimum
length visiting once and only once every node. A particular c ase is that of
the Euclidian TSP. In this version, each node is assigned coordinates in a
plane,1 and the cost on an edge connecting two nodes is the Euclidian d is-
tance between them. While theoretically as hard as the gener al TSP, good
approximate solution can be found more eﬃciently in the Eucl idian case
by leveraging the structure of the graph (Larson and Odoni, 1981, Chapter
6.4.7). Likewise, diverse types of problems are solved by le veraging their
special structure. Other algorithms, designed to be genera l, are found in
hindsight to be empirically more eﬃcient on particular prob lems types. The
scientiﬁc literature covers the rich set of techniques rese archers have devel-
oped to tackle diﬀerent CO problems. An expert will know how to further
reﬁne algorithm parameters to diﬀerent behaviors of the opti mization pro-
cess, thus extending this knowledge with unwritten intuiti on. These tech-
niques, and the parameters controlling them, have been coll ectively learned
by the community to perform on the inaccessible distributio n of problem in-
stances deemed valuable. The focus of this paper is on CO algo rithms that
automatically perform learning on a chosen implicit distri bution of prob-
lems. Incorporating machine learning (ML) components in th e algorithm
can achieve this.
Conversely, ML focuses on performing a task given some (ﬁnit e and usu-
ally noisy) data. It is well suited for natural signals for wh ich no clear
mathematical formulation emerges because the true data dis tribution is not
known analytically, such as when processing images, text, v oice or molecules,
or with recommender systems, social networks or ﬁnancial pr edictions. Most
1 Or more generally in a vector space of arbitrary dimension.
2
of the times, the learning problem has a statistical formula tion that is solved
through mathematical optimization. Recently, dramatic pr ogress has been
achieved with deep learning, an ML sub-ﬁeld building large p arametric ap-
proximators by composing simpler functions. Deep learning excels when
applied in high dimensional spaces with a large number of dat a points.
1.1 Motivation
From the CO point of view, machine learning can help improve a n algorithm
on a distribution of problem instances in two ways. On the one side, the
researcher assumes expert knowledge 2 about the optimization algorithm,
but wants to replace some heavy computations by a fast approx imation.
Learning can be used to build such approximations in a generi c way, i.e.,
without the need to derive new explicit algorithms. On the ot her side, ex-
pert knowledge may not be suﬃcient and some algorithmic deci sions may be
unsatisfactory. The goal is therefore to explore the space o f these decisions,
and learn out of this experience the best performing behavio r (policy), hope-
fully improving on the state of the art. Even though ML is appr oximate, we
will demonstrate through the examples surveyed in this pape r that this does
not systematically mean that incorporating learning will c ompromise over-
all theoretical guarantees. From the point of view of using M L to tackle a
combinatorial problem, CO can decompose the problem into sm aller, hope-
fully simpler, learning tasks. The CO structure therefore a cts as a relevant
prior for the model. It is also an opportunity to leverage the CO literature,
notably in terms of theoretical guarantees ( e.g., feasibility and optimality).
1.2 Setting
Imagine a delivery company in Montreal that needs to solve TS Ps. Every
day, the customers may vary, but usually, many are downtown a nd few on
top of the Mont Royal mountain. Furthermore, Montreal stree ts are laid on
a grid, making the distances close to the ℓ1 distance. How close? Not as
much as Phoenix, but certainly more than Paris. The company d oes not care
about solving all possible TSPs, but only theirs. Explicitly deﬁning what
makes a TSP a likely one for the company is tedious, does not sc ale, and it
is not clear how it can be leveraged when explicitly writing a n optimization
algorithm. We would like to automatically specialize TSP al gorithms for
this company.
2Theoretical and/or empirical.
3
The true probability distribution of likely TSPs in the Mont real scenario
is deﬁning the instances on which we would like our algorithm to perform
well. This is unknown, and cannot even be mathematically cha racterized
in an explicit way. Because we do not know what is in this distr ibution,
we can only learn an algorithm that performs well on a ﬁnite se t of TSPs
sampled from this distribution (for instance, a set of histo rical instances
collected by the company), thus implicitly incorporating t he desired infor-
mation about the distribution of instances. As a comparison , in traditional
ML tasks, the true distribution could be that of all possible images of cats,
while the training distribution is a ﬁnite set of such images . The challenge
in learning is that an algorithm that performs well on proble m instances
used for learning may not work properly on other instances fr om the true
probability distribution. For the company, this would mean the algorithm
only does well on past problems, but not on the future ones. To control this,
we monitor the performance of the learned algorithm over ano ther indepen-
dent set of unseen problem instances. Keeping the performances similar
between the instances used for learning and the unseen ones i s known in ML
as generalizing. Current ML algorithms can generalize to examples from
the same distribution, but tend to have more diﬃculty genera lizing out-of-
distribution (although this is a topic of intense research i n ML), and so we
may expect CO algorithms that leverage ML models to fail when evaluated
on unseen problem instances that are too far from what has bee n used for
training the ML predictor. As previously motivated, it is al so worth noting
that traditional CO algorithms might not even work consiste ntly across all
possible instances of a problem family, but rather tend to be more adapted
to particular structures of problems, e.g., Euclidean TSPs.
Finally, the implicit knowledge extracted by ML algorithms is comple-
mentary to the hard-won explicit expertise extracted throu gh CO research.
Rather, it aims to augment and automate the unwritten expert intuition
(or lack of) on various existing algorithms. Given that thes e problems are
highly structured, we believe it is relevant to augment solv ing algorithms
with machine learning – and especially deep learning to addr ess the high
dimensionality of such problems.
In the following, we survey the attempts in the literature to achieve such
automation and augmentation, and we present a methodologic al overview
of those approaches. In light of the current state of the ﬁeld , the literature
we survey is exploratory, i.e., we aim at highlighting promising research
directions in the use of ML within CO, instead of reporting on already
mature algorithms.
4
1.3 Outline
We have introduced the context and motivations for building combinatorial
optimization algorithms together with machine learning. T he remainder of
this paper is organized as follows. Section 2 provides minim al prerequisites in
combinatorial optimization, machine learning, deep learn ing, and reinforce-
ment learning necessary to fully grasp the content of the pap er. Section 3
surveys the recent literature and derives two distinctive, orthogonal, views:
Section 3.1 shows how machine learning policies can either b e learned by
imitating an expert or discovered through experience, whil e Section 3.2 dis-
cusses the interplay between the ML and CO components. Secti on 5 pushes
further the reﬂection on the use of ML for combinatorial opti mization and
brings to the fore some methodological points. In Section 6, we detail criti-
cal practical challenges of the ﬁeld. Finally, some conclus ions are drawn in
Section 7.
2 Preliminaries
In this section, we give a basic (sometimes rough) overview o f combinato-
rial optimization and machine learning, with the unique aim of introducing
concepts that are strictly required to understand the remai nder of the paper.
2.1 Combinatorial Optimization
Without loss of generality, a CO problem can be formulated as a constrained
min-optimization program. Constraints model natural or im posed restric-
tions of the problem, variables deﬁne the decisions to be mad e, while the
objective function, generally a cost to be minimized, deﬁne s the measure of
the quality of every feasible assignment of values to variab les. If the objec-
tive and constraints are linear, the problem is called a line ar programming
(LP) problem. If, in addition, some variables are also restr icted to only as-
sume integer values, then the problem is a mixed-integer lin ear programming
(MILP) problem.
The set of points that satisfy the constraints is the feasibl e region. Every
point in that set (often referred to as a feasible solution) y ields an upper
bound on the objective value of the optimal solution. Exact s olving is an
important aspect of the ﬁeld, hence a lot of attention is also given to ﬁnd
lower bounds to the optimal cost. The tighter the lower bound s, with respect
to the optimal solution value, the higher the chances that th e current al-
gorithmic approaches to tackle mixed-integer linear progr ammings (MILPs)
5
described in the following could be successful, i.e., eﬀective if not eﬃcient.
Linear and mixed-integer linear programming problems are t he workhorse
of CO because they can model a wide variety of problems and are the best
understood, i.e., there are reliable algorithms and software tools to solve
them. We give them special considerations in this paper but, of course,
they do not represent the entire CO, mixed-integer nonlinea r programming
being a rapidly expanding and very signiﬁcant area both in th eory and in
practical applications. With respect to complexity and sol ution methods,
LP is a polynomial problem, well solved, in theory and in prac tice, through
the simplex algorithm or interior points methods. Mixed-in teger linear pro-
gramming, on the other hand, is an NP-hard problem, which doe s not make
it hopeless. Indeed, it is easy to see that the complexity of M ILP is as-
sociated with the integrality requirement on (some of) the v ariables, which
makes the MILP feasible region nonconvex. However, droppin g the integral-
ity requirement (i) deﬁnes a proper relaxation of MILP ( i.e., an optimization
problem whose feasible region contains the MILP feasible re gion), which (ii)
happens to be an LP, i.e., polynomially solvable. This immediately suggests
the algorithmic line of attack that is used to solve MILP thro ugh a whole
ecosystem of branch-and-bound (B&B) techniques to perform implicit enu-
meration. Branch and bound implemements a divide-and-conq uer type of
algorithm representable by a search tree in which, at every n ode, an LP
relaxation of the problem (possibly augmented by branching decisions, see
below) is eﬃciently computed. If the relaxation is infeasib le, or if the solu-
tion of the relaxation is naturally (mixed-)integer, i.e., MILP feasible, the
node does not need to be expanded. Otherwise, there exists at least one vari-
able, among those supposed to be integer, taking a fractiona l value in the
LP solution and that variable can be chosen for branching (en umeration),
i.e., by restricting its value in such a way that two child nodes ar e created.
The two child nodes have disjoint feasible regions, none of w hich contains
the solution of the previous LP relaxation. We use Figure 1 to illustrate the
B&B algorithm for a minimization MILP. At the root node in the ﬁgure,
the variable x2 has a fractional value in the LP solution (not represented),
thus branching is done on the ﬂoor (here zero) and ceiling (he re one) of
this value. When an integer solution is found, we also get an u pper bound
(denoted as z) on the optimal solution value of the problem. At every node,
we can then compare the solution value of the relaxation (den oted as z)
with the minimum upper bound found so far, called the incumbe nt solution
value. If the latter is smaller than the former for a speciﬁc n ode, no better
(mixed-)integer solution can be found in the sub-tree origi nated by the node
itself, and it can be pruned.
6
InfeasiblePruned by bound
Integer solution
x2 ≥ 1x2 ≤ 0
x3 ≤ 0 x3 ≥ 1 x1 ≥ 1
x5 ≥ 1
x3 ≥ 1
x5 ≤ 0
x1 ≤ 0
x3 ≤ 0
z = 3:4
z = 5:7
z = z = 4
z = 3:8
Figure 1: A branch-and-bound tree for MILPs. The LP relaxati on is com-
puted at every node (only partially shown in the ﬁgure). Node s still open
for exploration are represented as blank.
All commercial and noncommercial MILP solvers enhance the a bove enu-
meration framework with the extensive use of cutting planes , i.e., valid linear
inequalities that are added to the original formulation (es pecially at the root
of the B&B tree) in the attempt of strengthening its LP relaxa tion. The
resulting framework, referred to as the branch-and-cut alg orithm, is then
further enhanced by additional algorithmic components, pr eprocessing and
primal heuristics being the most crucial ones. The reader is referred to
Wolsey (1998) and Conforti et al. (2014) for extensive textb ooks on MILP
and to Lodi (2009) for a detailed description of the algorith mic components
of the MILP solvers.
We end the section by noting that there is a vast literature de voted to
(primal) heuristics, i.e., algorithms designed to compute “good in practice”
solutions to CO problems without optimality guarantee. Alt hough a general
discussion on them is outside the scope here, those heuristi c methods play a
central role in CO and will be considered in speciﬁc contexts in the present
paper. The interested reader is referred to Fischetti and Lo di (2011) and
Gendreau and Potvin (2010).
2.2 Machine Learning
Supervised learning In supervised learning, a set of input (features) /
target pairs is provided and the task is to ﬁnd a function that for every input
has a predicted output as close as possible to the provided ta rget. Finding
such a function is called learning and is solved through an op timization
7
problem over a family of functions. The loss function, i.e., the measure of
discrepancy between the output and the target, can be chosen depending on
the task (regression, classiﬁcation, etc.) and on the optimization methods.
However, this approach is not enough because the problem has a statistical
nature. It is usually easy enough to achieve a good score on th e given
examples but one wants to achieve a good score on unseen examp les (test
data). This is known as generalization.
Mathematically speaking, let X and Y , following a joint probability
distribution P , be random variables representing the input features and th e
target. Let ℓ be the per sample loss function to minimize, and let {fθ |θ ∈
Rp} be the family of ML models (parametric in this case) to optimi ze over.
The supervised learning problem is framed as
min
θ∈Rp
EX,Y ∼P ℓ(Y, fθ(X)). (1)
For instance, fθ could be a linear model with weights θ that we wish to
learn. The loss function ℓ is task dependent ( e.g., classiﬁcation error) and
can sometimes be replaced by a surrogate one ( e.g., a diﬀerentiable one).
The probability distribution is unknown and inaccessible. For example, it
can be the probability distribution of all natural images. T herefore, it is
approximated by the empirical probability distribution ov er a ﬁnite dataset
Dtrain = {(xi, yi)}i and the optimization problem solved is
min
θ∈Rp
∑
(x,y )∈Dtrain
1
|Dtrain|ℓ(y, fθ(x)). (2)
A model is said to generalize, if low objective values of (2) t ranslate in
low objective values of (1). Because (1) remains inaccessib le, we estimate
the generalization error by evaluating the trained model on a separate test
dataset Dtest with ∑
(x,y )∈Dtest
1
|Dtest|ℓ(y, fθ(x)). (3)
If a model ( i.e., a family of functions) can represent many diﬀerent function s,
the model is said to have high capacity and is prone to overﬁtt ing: doing well
on the training data but not generalizing to the test data. Re gularization is
anything that can improve the test score at the expense of the training score
and is used to restrict the practical capacity of a model. On t he contrary,
if the capacity is too low, the model underﬁts and performs po orly on both
sets. The boundary between overﬁtting and underﬁtting can b e estimated
by changing the eﬀective capacity (the richness of the family of functions
8
reachable by training): below the critical capacity one und erﬁts and test
error decreases with increases in capacity, while above tha t critical capacity
one overﬁts and test error increases with increases in capac ity.
Selecting the best among various trained models cannot be do ne on the
test set. Selection is a form of optimization, and doing so on the test set
would bias the estimator in (2). This is a common form of data d redging, and
a mistake to be avoided. To perform model selection, a valida tion dataset
Dvalid is used to estimate the generalization error of diﬀerent ML mo dels is
necessary. Model selection can be done based on these estima tes, and the
ﬁnal unbiased generalization error of the selected model ca n be computed
on the test set. The validation set is therefore often used to select eﬀective
capacity, e.g., by changing the amount of training, the number of parameter s
θ, and the amount of regularization imposed to the model.
Unsupervised learning In unsupervised learning, one does not have tar-
gets for the task one wants to solve, but rather tries to captu re some char-
acteristics of the joint distribution of the observed rando m variables. The
variety of tasks include density estimation, dimensionali ty reduction, and
clustering. Because unsupervised learning has received so far little atten-
tion in conjunction with CO and its immediate use seems diﬃcu lt, we are not
discussing it any further. The reader is referred to Bishop ( 2006); Murphy
(2012); Goodfellow et al. (2016) for textbooks on machine le arning.
Reinforcement learning In reinforcement learning (RL), an agent in-
teracts with an environment through a markov decision proce ss (MDP), as
illustrated in Figure 2. At every time step, the agent is in a g iven state of
the environment and chooses an action according to its (poss ibly stochastic)
policy. As a result, it receives from the environment a rewar d and enters a
new state. The goal in RL is to train the agent to maximize the e xpected
sum of future rewards, called the return. For a given policy, the expected
return given a current state (resp. state and action pair) is known as the
value function (resp. state action value function). Value f unctions follow
the Bellman equation, hence the problem can be formulated as dynamic
programming, and solved approximately. The dynamics of the environment
need not be known by the agent and are learned directly or indi rectly, yield-
ing an exploration vs exploitation dilemma: choosing between exploring new
states for reﬁning the knowledge of the environment for poss ible long-term
improvements, or exploiting the best-known scenario learn ed so far (which
tends to be in already visited or predictable states).
9
π(ajs)
Environment
Agent
p(s0; rja; s)
ActionRewardState
AtRt+1St+1
Figure 2: The Markov decision process associated with reinf orcement learn-
ing, modiﬁed from Sutton and Barto (2018). The agent behavio r is deﬁned
by its policy π, while the environment evolution is deﬁned by the dynam-
ics p. Note that the reward is not necessary to deﬁne the evolution and is
provided only as a learning mechanism for the agent. Actions , states, and
rewards are random variables in the general framework.
The state should fully characterize the environment at ever y step, in the
sense that future states only depend on past states via the cu rrent state
(the Markov property). When this is not the case, similar met hods can
be applied but we say that the agent receives an observation of the state.
The Markov property no longer holds and the MDP is said to be pa rtially
observable.
Deﬁning a reward function is not always easy. Sometimes one w ould
like to deﬁne a very sparse reward, such as 1 when the agent sol ves the
problem, and 0 otherwise. Because of its underlying dynamic programming
process, RL is naturally able to credit states/actions that lead to future re-
wards. Nonetheless, the aforementioned setting is challen ging as it provides
no learning opportunity until the agent (randomly, or throu gh advanced ap-
proaches) solves the problem. Furthermore, when the policy is approximated
(for instance, by a linear function), the learning is not gua ranteed to con-
verge and may fall into local minima. For example, an autonom ous car may
decide not to drive anywhere for fear of hitting a pedestrian and receiving a
dramatic negative reward. These challenges are strongly re lated to the afore-
mentioned exploration dilemma. The reader is referred to Su tton and Barto
(2018) for an extensive textbook on reinforcement learning .
Deep learning Deep learning is a successful method for building para-
metric composable functions in high dimensional spaces. In the case of
the simplest neural network architecture, the feedforward neural network
10
(also called an multilayer perceptron (MLP)), the input dat a is successively
passed through a number of layers. For every layer, an aﬃne tr ansforma-
tion is applied on the input vector, followed by a non-linear scalar function
(named activation function) applied element-wise. The out put of a layer,
called intermediate activations, is passed on to the next la yer. All aﬃne
transformations are independent and represented in practi ce as diﬀerent
matrices of coeﬃcients. They are learned, i.e., optimized over, through
stochastic gradient descent (SGD), the optimization algor ithm used to min-
imize the selected loss function. The stochasticity comes f rom the limited
number of data points used to compute the loss before applyin g a gradient
update. In practice, gradients are computed using reverse m ode automatic
diﬀerentiation, a practical algorithm based on the chain rul e, also known as
back-propagation. Deep neural networks can be diﬃcult to op timize, and
a large variety of techniques have been developed to make the optimization
behave better, often by changing architectural designs of t he network. Be-
cause neural networks have dramatic capacities, i.e., they can essentially
match any dataset, thus being prone to overﬁtting, they are a lso heavily
regularized. Training them by SGD also regularizes them bec ause of the
noise in the gradient, making neural networks generally rob ust to overﬁt-
ting issues, even when they are very large and would overﬁt if trained with
more aggressive optimization. In addition, many hyper-par ameters exist
and diﬀerent combinations are evaluated (known as hyper-par ameters op-
timization). Deep learning also sets itself apart from more traditional ML
techniques by taking as inputs all available raw features of the data, e.g.,
all pixels of an image, while traditional ML typically requi res to engineer a
limited number of domain-speciﬁc features.
Deep learning researchers have developed diﬀerent techniqu es to tackle
this variety of structured data in a manner that can handle va riable-size
data structures, e.g., variable-length sequences. In this paragraph, and in
the next, we present such state-of-the-art techniques. The se are complex
topics, but lack of comprehension does not hinder the readin g of the paper.
At a high level, it is enough to comprehend that these are arch itectures
designed to handle diﬀerent structures of data. Their usage, and in par-
ticular the way they are learned, remains very similar to pla in feedforward
neural networks introduced above. The ﬁrst architectures p resented are the
recurrent neural networks (RNNs). These models can operate on sequence
data by sharing parameters across diﬀerent sequence steps. More precisely,
a same neural network block is successively applied at every step of the se-
quence, i.e., with the same architecture and parameter values at each tim e
step. The speciﬁcity of such a network is the presence of recu rrent layers:
11
layers that take as input both the activation vector of the pr evious layer and
its own activation vector on the preceding sequence step (ca lled a hidden
state vector), as illustrated in Figure 3.
x
h
o
V W
U
xt− 1
ht− 1
ot− 1
V
U
xt
ht
ot
V
U
xt+1
ht+1
ot+1
V
U
W WW
Figure 3: A vanilla RNN modiﬁed from Goodfellow et al. (2016) . On the
left, the black square indicates a one step delay. On the righ t, the same RNN
is shown unfolded. Three sets U , V , and W of parameters are represented
and re-used at every time step.
Another important size-invariant technique are attention mechanisms .
They can be used to process data where each data point corresp onds to a set.
In that context, parameter sharing is used to address the fac t that diﬀerent
sets need not to be of the same size. Attention is used to query information
about all elements in the set, and merge it for downstream pro cessing in
the neural network, as depicted in Figure 4. An aﬃnity functi on takes as
input the query (which represents any kind of contextual inf ormation which
informs where attention should be concentrated) and a repre sentation of
an element of the set (both are activation vectors) and outpu ts a scalar.
This is repeated over all elements in the set for the same quer y. Those
scalars are normalized (for instance with a softmax functio n) and used to
deﬁne a weighted sum of the representations of elements in th e set that
can, in turn, be used in the neural network making the query. T his form
of content-based soft attention was introduced by Bahdanau et al. (2015).
A general explanation of attention mechanisms is given by Va swani et al.
(2017). Attention can be used to build graph neural networks (GNNs),
i.e., neural networks able to process graph structured input dat a, as done
by Veliˇ ckovi´ c et al. (2018). In this architecture, every n ode attends over
the set of its neighbors. The process is repeated multiple ti mes to gather
12
information about nodes further away. GNNs can also be under stood as a
form of message passing (Gilmer et al., 2017).
f f f
sof tmax
∗ ∗ ∗
Σ
:::v1 v2 vp q
Figure 4: A vanilla attention mechanism where a query q is computed
against a set of values ( vi)i. An aﬃnity function f , such as a dot prod-
uct, is used on query and value pairs. If it includes some para meters, the
mechanism can be learned.
Deep learning and back-propagation can be used in supervise d, unsuper-
vised, or reinforcement learning. The reader is referred to Goodfellow et al.
(2016) for a machine learning textbook devoted to deep learn ing.
3 Recent approaches
We survey diﬀerent uses of ML to help solve combinatorial opti mization
problems and organize them along two orthogonal axes. First , in Section 3.1
we illustrate the two main motivations for using learning: a pproximation
and discovery of new policies. Then, in Section 3.2, we show e xamples of
diﬀerent ways to combine learned and traditional algorithmi c elements.
3.1 Learning methods
This section relates to the two motivations reported in Sect ion 1.1 for us-
ing ML in CO. In some works, the researcher assumes theoretic al and/or
13
empirical knowledge about the decisions to be made for a CO al gorithm,
but wants to alleviate the computational burden by approxim ating some of
those decisions with machine learning. On the contrary, we a re also moti-
vated by the fact that, sometimes, expert knowledge is not sa tisfactory and
the researcher wishes to ﬁnd better ways of making decisions . Thus, ML
can come into play to train a model through trial and error rei nforcement
learning.
We frame both these motivations in the state/action MDP fram ework
introduced in section 2.2, where the environment is the inte rnal state of the
algorithm. We care about learning algorithmic decisions ut ilized by a CO
algorithm and we call the function making the decision a policy, that, given
all available information, 3 returns (possibly stochastically) the action to be
taken. The policy is the function that we want to learn using M L and we
show in the following how the two motivations naturally yiel d two learning
settings. Note that the case where the length of the trajecto ry of the MDP
has value 1 is a common edge case (called the bandit setting) w here this
formulation can seem excessive, but it nonetheless helps co mparing methods.
In the case of using ML to approximate decisions, the policy i s often
learned by imitation learning , thanks to demonstrations, because the ex-
pected behavior is shown (demonstrated) to the ML model by an expert
(also called oracle, even though it is not necessarily optim al), as shown in
Figure 5. In this setting, the learner is not trained to optim ize a performance
measure, but to blindly mimic the expert.
Decision?
πexpert
^πml ^action
action
min distance
Figure 5: In the demonstration setting, the policy is traine d to reproduce
the action of an expert policy by minimizing some discrepanc y in the action
space.
In the case where one cares about discovering new policies, i.e., opti-
mizing an algorithmic decision function from the ground up, the policy may
be learned by reinforcement learning through experience, as shown in Fig-
3 A state if the information is suﬃcient to fully characterize the env ironment at that
time in a Markov decision process setting.
14
ure 6. Even though we present the learning problem under the f undamental
MDP of RL, this does not constrain one to use the major RL algor ithms
(approximate dynamic programming and policy gradients) to maximize the
expected sum of rewards. Alternative optimization methods , such as bandit
algorithms, genetic algorithms, direct/local search, can also be used to solve
the RL problem. 4
Decision?
^πml
^action reward
score
max return
Figure 6: When learning through a reward signal, no expert is involved;
only maximizing the expected sum of future rewards (the retu rn) matters.
It is critical to understand that in the imitation setting, t he policy is
learned through supervised targets provided by an expert fo r every action
(and without a reward), whereas in the experience setting, t he policy is
learned from a reward (possibly delayed) signal using RL (an d without an
expert). In imitation, the agent is taught what to do, whereas in RL, the
agent is encouraged to quickly accumulate rewards. The distinction between
these two settings is far more complex than the distinction m ade here. We
explore some of this complexity, including their strengths and weaknesses,
in Section 5.1.
In the following, few papers demonstrating the diﬀerent sett ings are
surveyed.
3.1.1 Demonstration
In Baltean-Lugojan et al. (2018), the authors use a neural ne twork to ap-
proximate the lower bound improvement generated by tighten ing the current
relaxation via cutting planes (cuts, for short). More preci sely, Baltean-Lugojan et al.
(2018) consider non-convex quadratic programming problem s and aim at
approximating the associated semideﬁnite programming (SD P) relaxation,
known to be strong but time-consuming, by a linear program. A straightfor-
ward way of doing that is to iteratively add (linear) cutting planes associated
with negative eigenvalues, especially considering small- size (square) subma-
trices of the original quadratic objective function. That a pproach has the
4 In general, identifying which algorithm will perform best i s an open research question
unlikely to have a simple answer, and is outside of the scope o f the methodology presented
here.
15
advantage of generating sparse cuts 5 but it is computationally challenging
because of the exponential number of those submatrices and b ecause of the
diﬃculty of ﬁnding the right metrics to select among the viol ated cuts. The
authors propose to solve SDPs to compute the bound improveme nt asso-
ciated with considering speciﬁc submatrices, which is also a proxy on the
quality of the cuts that could be separated from the same subm atrices. In
this context, supervised (imitation) learning is applied o ﬄine to approxi-
mate the objective value of the SDP problem associated with a submatrix
selection and, afterward, the model can be rapidly applied t o select the most
promising submatrices without the very signiﬁcant computa tional burden of
solving SDPs. Of course, the rational is that the most promis ing submatrices
correspond to the most promising cutting planes and Baltean -Lugojan et al.
(2018) train a model to estimate the objective of an SDP probl em only in
order to decide to add the most promising cutting planes. Hen ce, cutting
plane selection is the ultimate policy learned.
Another example of demonstration is found in the context of b ranch-
ing policies in B&B trees of MILPs. The choice of variables to branch on
can dramatically change the size of the B&B tree, hence the so lving time.
Among many heuristics, a well-performing approach is strong branching
(Applegate et al., 2007). Namely, for every branching decis ion to be made,
strong branching performs a one step look-ahead by tentativ ely branching
on many candidate variables, computes the LP relaxations to get the po-
tential lower bound improvements, and eventually branches on the variable
providing the best improvement. Even if not all variables ar e explored, and
the LP value can be approximated, this is still a computation ally expensive
strategy. For these reasons, Marcos Alvarez et al. (2014, 20 17) use a special
type of decision tree (a classical model in supervised learn ing) to approx-
imate strong branching decisions using supervised learnin g. Khalil et al.
(2016) propose a similar approach, where a linear model is le arned on the
ﬂy for every instance by using strong branching at the top of t he tree, and
eventually replacing it by its ML approximation. The linear approximator
of strong branching introduced in Marcos Alvarez et al. (201 6) is learned in
an active fashion: when the estimator is deemed unreliable, the algorithm
falls back to true strong branching and the results are then u sed for both
branching and learning. In all the branching algorithms pre sented here,
inputs to the ML model are engineered as a vector of ﬁxed lengt h with
static features descriptive of the instance, and dynamic fe atures providing
5 The reader is referred to Dey and Molinaro (2018) for a detail ed discussion on the
importance of sparse cutting planes in MILP.
16
information about the state of the B&B process. Gasse et al. ( 2019) use a
neural network to learn an oﬄine approximation to strong bra nching, but,
contrary to the aforementioned papers, the authors use a raw exhaustive
representation ( i.e., they do not discard nor aggregate any information) of
the sub-problem associated with the current branching node as input to
the ML model. Namely, an MILP sub-problem is represented as a bipar-
tite graph on variables and constraints, with edges represe nting non-zero
coeﬃcients in the constraint matrix. Each node is augmented with a set of
features to fully describe the sub-problem, and a GNN is used to build an
ML approximator able to process this type of structured data . Node selec-
tion, i.e., deciding on the next branching node to explore in a B&B tree,
is also a critical decision in MILP. He et al. (2014) learn a po licy to select
among the open branching nodes the one that contains the opti mal solution
in its sub-tree. The training algorithm is an online learnin g method col-
lecting expert behaviors throughout the entire learning ph ase. The reader
is referred to Lodi and Zarpellon (2017) for an extended surv ey on learning
and branching in MILPs.
Branch and bound is a technique not limited to MILP and can be u se
for general tree search. Hottung et al. (2017) build a tree se arch procedure
for the container pre-marshalling problem in which they aim to learn, not
only a branching policy (similar in principle to what has bee n discussed in
the previous paragraph), but also a value network to estimat e the value of
partial solutions and used for bounding. The authors levera ge a form of
convolutional neural network (CNN) 6 for both networks and train them in
a supervised fashion using pre-computed solutions of the pr oblem. The re-
sulting algorithm is heuristic due the approximations made while bounding.
As already mentioned at the beginning of Section 3.1, learni ng a policy
by demonstration is identical to supervised learning, wher e training pairs
of input state and target actions are provided by the expert. In the sim-
plest case, expert decisions are collected beforehand, but more advanced
methods can collect them online to increase stability as pre viously shown in
Marcos Alvarez et al. (2016) and He et al. (2014).
3.1.2 Experience
Considering the TSP on a graph, it is easy to devise a greedy he uristic that
builds a tour by sequentially picking the nodes among those t hat have not
been visited yet, hence deﬁning a permutation. If the criter ion for selecting
6 A type of neural network, usually used on image input, that le verages parameter
sharing to extract local information.
17
the next node is to take the closest one, then the heuristic is known as
the nearest neighbor. This simple heuristic has poor practi cal performance
and many other heuristics perform better empirically, i.e., build cheaper
tours. Selecting the nearest node is a fair intuition but tur ns out to be
far from satisfactory. Khalil et al. (2017a) suggest learni ng the criterion for
this selection. They build a greedy heuristic framework, wh ere the node
selection policy is learned using a GNN (Dai et al., 2016), a t ype of neural
network able to process input graphs of any ﬁnite size by a mec hanism of
message passing (Gilmer et al., 2017). For every node to sele ct, the authors
feed to the network the graph representation of the problem – augmented
with features indicating which of the nodes have already bee n visited –
and receive back an action value for every node. Action value s are used
to train the network through RL (Q-learning in particular) a nd the partial
tour length is used as a reward.
This example does not do justice to the rich TSP literature th at has
developed far more advanced algorithms performing orders o f magnitude
better than ML ones. Nevertheless, the point we are trying to highlight
here is that given a ﬁxed context, and a decision to be made, ML can be
used to discover new, potentially better performing polici es. Even on state-
of-the-art TSP algorithms ( i.e., when exact solving is taken to its limits),
many decisions are made in heuristic ways, e.g., cutting plane selection, thus
leaving room for ML to assist in making these decisions.
Once again, we stress that learning a policy by experience is well de-
scribed by the MDP framework of reinforcement learning, whe re an agent
maximizes the return (deﬁned in Section 2.2). By matching th e reward sig-
nal with the optimization objective, the goal of the learnin g agent becomes
to solve the problem, without assuming any expert knowledge . Some meth-
ods that were not presented as RL can also be cast in this MDP fo rmulation,
even if the optimization methods are not those of the RL commu nity. For
instance, part of the CO literature is dedicated to automati cally build spe-
cialized heuristics for diﬀerent problems. The heuristics a re build by orches-
trating a set of moves, or subroutines, from a pre-deﬁned dom ain-speciﬁc
collections. For instance, to tackle bipartite boolean qua dratic program-
ming problems, Karapetyan et al. (2017) represent this orch estration as a
Markov chain where the states are the subroutines. One Marko v chain is
parametrized by its transition probabilities. Mascia et al . (2014), on the
other hand, deﬁne valid succession of moves through a gramma r, where
words are moves and sentences correspond to heuristics. The authors intro-
duce a parametric space to represent sentences of a grammar. In both cases,
the setting is very close to the MDP of RL, but the parameters a re learned
18
though direct optimization of the performances of their ass ociated heuristic
through so-called automatic conﬁguration tools (usually based on genetic or
local search, and exploiting parallel computing). Note tha t the learning set-
ting is rather simple as the parameters do not adapt to the pro blem instance,
but are ﬁxed for various clusters. From the ML point of view, t his is equiva-
lent to a piece-wise constant regression. If more complex mo dels were to be
used, direct optimization may not scale adequately to obtai n good perfor-
mances. The same approach to building heuristics can be brou ght one level
up if, instead of orchestrating sets of moves, it arranges pr edeﬁned heuris-
tics. The resulting heuristic is then called a hyper-heuristic. ¨Ozcan et al.
(2012) build a hyper-heuristic for examination timetablin g by learning to
combine existing heuristics. They use a bandit algorithm, a stateless form
of RL (see Sutton and Barto, 2018, Chapter 2), to learn online a value func-
tion for each heuristic.
We close this section by noting that demonstration and exper ience are
not mutually exclusive and most learning tasks can be tackle d in both ways.
In the case of selecting the branching variables in an MILP br anch-and-
bound tree, one could adopt anyone of the two prior strategie s. On the one
hand, Marcos Alvarez et al. (2014, 2016, 2017); Khalil et al. (2016) estimate
that strong branching is an eﬀective branching strategy but c omputationally
too expensive and build a machine learning model to approxim ate it. On
the other hand, one could believe that no branching strategy is good enough
and try to learn one from the ground up, for instance through r einforcement
learning as suggested (but not implemented) in Khalil et al. (2016). An
intermediary approach is proposed by Liberto et al. (2016). The authors
recognize that, among traditional variable selection poli cies, the ones per-
forming well at the top of the B&B tree are not necessarily the same as
the ones performing well deeper down. Hence, the authors lea rn a model
to dynamically switch among predeﬁned policies during B&B b ased on the
current state of the tree. While this seems like a case of imit ation learning,
given that traditional branching policies can be thought of as experts, this
is actually not the case. In fact, the model is not learning from any expert,
but really learning to choose between pre-existing policie s. This is techni-
cally not a branching variable selection, but rather a branc hing heuristic
selection policy. Each sub-tree is represented by a vector o f handcrafted
features, and a clustering of these vectors is performed. Si milarly to what
was detailed in the previous paragraph about the work of Kara petyan et al.
(2017); Mascia et al. (2014), automatic conﬁguration tools are then used to
assign the best branching policy to each cluster. When branc hing at a given
19
node, the cluster the closest to the current sub-tree is retr ieved, and its
assigned policy is used.
3.2 Algorithmic structure
In this section, we survey how the learned policies (whether from demon-
stration or experience) are combined with traditional CO al gorithms, i.e.,
considering ML and explicit algorithms as building blocks, we survey how
they can be laid out in diﬀerent templates. The three followin g sections are
not necessarily disjoint nor exhaustive but are a natural wa y to look at the
literature.
3.2.1 End to end learning
A ﬁrst idea to leverage machine learning to solve discrete op timization prob-
lems is to train the ML model to output solutions directly fro m the input
instance, as shown in Figure 7.
SolutionMLProblem
deﬁnition
Figure 7: Machine learning acts alone to provide a solution t o the problem.
This approach has been explored recently, especially on Euc lidean TSPs.
To tackle the problem with deep learning, Vinyals et al. (201 5) introduce the
pointer network wherein an encoder, namely an RNN, is used to parse all
the TSP nodes in the input graph and produces an encoding (a ve ctor of
activations) for each of them. Afterward, a decoder, also an RNN, uses an
attention mechanism similar to Bahdanau et al. (2015) (Sect ion 2.2) over
the previously encoded nodes in the graph to produce a probab ility distri-
bution over these nodes (through the softmax layer previous ly illustrated in
Figure 4). Repeating this decoding step, it is possible for t he network to
output a permutation over its inputs (the TSP nodes). This me thod makes
it possible to use the network over diﬀerent input graph sizes . The authors
train the model through supervised learning with precomput ed TSP solu-
tions as targets. Bello et al. (2017) use a similar model and t rain it with
reinforcement learning using the tour length as a reward sig nal. They ad-
dress some limitations of supervised (imitation) learning , such as the need to
compute optimal (or at least high quality) TSP solutions (th e targets), that
in turn, may be ill-deﬁned when those solutions are not compu ted exactly,
20
or when multiple solutions exist. Kool and Welling (2018) in troduce more
prior knowledge in the model using a GNN instead of an RNN to pr ocess
the input. Emami and Ranka (2018) and Nowak et al. (2017) expl ore a dif-
ferent approach by directly approximating a double stochas tic matrix in the
output of the neural network to characterize the permutatio n. The work of
Khalil et al. (2017a), introduced in Section 3.1.2, can also be understood as
an end to end method to tackle the TSP, but we prefer to see it un der the
eye of Section 3.2.3. It is worth noting that tackling the TSP through ML is
not new. Earlier work from the nineties focused on Hopﬁeld ne ural networks
and self organizing neural networks, the interested reader is referred to the
survey of Smith (1999).
In another example, Larsen et al. (2018) train a neural netwo rk to pre-
dict the solution of a stochastic load planning problem for w hich a determin-
istic MILP formulation exists. Their main motivation is tha t the application
needs to make decisions at a tactical level, i.e., under incomplete informa-
tion, and machine learning is used to address the stochastic ity of the problem
arising from missing some of the state variables in the obser ved input. The
authors use operational solutions, i.e., solutions to the deterministic version
of the problem, and aggregate them to provide (tactical) sol ution targets to
the ML model. As explained in their paper, the highest level o f description
of the solution is its cost, whereas the lowest (operational ) is the knowledge
of values for all its variables. Then, the authors place them selves in the
middle and predict an aggregation of variables (tactical) t hat corresponds
to the stochastic version of their speciﬁc problem. Further more, the nature
of the application requires to output solutions in real time , which is not
possible either for the stochastic version of the load plann ing problem or its
deterministic variant when using state-of-the-art MILP so lvers. Then, ML
turns out to be suitable for obtaining accurate solutions wi th short com-
puting times because some of the complexity is addressed oﬄi ne, i.e., in
the learning phase, and the run-time (inference) phase is ex tremely quick.
Finally, note that in Larsen et al. (2018) an MLP, i.e., a feedforward neural
network, is used to process the input instance as a vector, he nce integrating
very little prior knowledge about the problem structure.
3.2.2 Learning to conﬁgure algorithms
In many cases, using only machine learning to tackle the prob lem may not
be the most suitable approach. Instead, ML can be applied to p rovide
additional pieces of information to a CO algorithm as illust rated in Figure 8.
For example, ML can provide a parametrization of the algorit hm (in a very
21
broad sense).
SolutionMLProblem
deﬁnition ORDecision
Figure 8: The machine learning model is used to augment an ope ration
research algorithm with valuable pieces of information.
Algorithm conﬁguration, detailed in Hoos (2012); Bischl et al. (2016),
is a well studied area that captures the setting presented he re. Complex
optimization algorithms usually have a set of parameters le ft constant dur-
ing optimization (in machine learning they are called hyper -parameters).
For instance, this can be the aggressiveness of the pre-solv ing operations
(usually controlled by a single parameter) of an MILP solver , or the learn-
ing rate / step size in gradient descent methods. Carefully s electing their
value can dramatically change the performance of the optimi zation algo-
rithm. Hence, the algorithm conﬁguration community starte d looking for
good default parameters. Then good default parameters for d iﬀerent cluster
of similar problem instances. From the ML point of view, the f ormer is a
constant regression, while the second is a piece-wise const ant nearest neigh-
bors regression. The natural continuation was to learn a reg ression mapping
problem instances to algorithm parameters.
In this context, Kruber et al. (2017) use machine learning on MILP in-
stances to estimate beforehand whether or not applying a Dan tzig-Wolf de-
composition will be eﬀective, i.e., will make the solving time faster. Decom-
position methods can be powerful but deciding if and how to ap ply them
depends on many ingredients of the instance and of its formul ation and there
is no clear cut way of optimally making such a decision. In the ir work, a
data point is represented as a ﬁxed length vector with featur es representing
instance and tentative decomposition statistics. In anoth er example, in the
context of mixed-integer quadratic programming, Bonami et al. (2018) use
machine learning to decide if linearizing the problem will s olve faster. When
the quadratic programming (QP) problem given by the relaxat ion is con-
vex, i.e., the quadratic objective matrix is semideﬁnite positive, o ne could
address the problem by a B&B algorithm that solves QP relaxat ions7 to
provide lower bounds. Even in this convex case, it is not clea r if QP B&B
7 Note that convex QPs can be solved in polynomial time.
22
would solve faster than linearizing the problem (by using Mc Cormick (1976)
inequalities) and solving an equivalent MILP. This is why ML is a great can-
didate here to ﬁll the knowledge gap. In both papers (Kruber e t al., 2017;
Bonami et al., 2018), the authors experiment with diﬀerent ML models, such
as support vector machines and random forests, as is good pra ctice when no
prior knowledge is embedded in the model.
The heuristic building framework used in Karapetyan et al. ( 2017) and
Mascia et al. (2014), already presented in Section 3.1.2, ca n be understood
under this eye. Indeed, it can be seen as a large parametric he uristic, conﬁg-
ured by the transition probabilities in the former case, and by the parameter
representing a sentence in the latter.
As previously stated, the parametrization of the CO algorit hm provided
by ML is to be understood in a very broad sense. For instance, i n the
case of radiation therapy for cancer treatment, Mahmood et a l. (2018) use
ML to produce candidate therapies that are afterward reﬁned by a CO
algorithm into a deliverable plan. Namely, a generative adv ersarial network
(GAN) is used to color CT scan images into a potential radiati on plan,
then, inverse optimization (Ahuja and Orlin, 2001) is appli ed on the result
to make the plan feasible (Chan et al., 2014). In general, GAN s are made
of two distinct networks: one (the generator) generates ima ges, and another
one (the discriminator) discriminates between the generat ed images and a
dataset of real images. Both are trained alternatively: the discriminator
through a usual supervised objective, while the generator i s trained to fool
the discriminator. In Mahmood et al. (2018), a particular ty pe of GAN
(conditional GAN) is used to provide coloring instead of ran dom images.
The interested reader is referred to Creswell et al. (2018) f or an overview on
GANs.
We end this section by noting that an ML model used for learnin g
some representation may in turn use as features pieces of inf ormation given
by another CO algorithm, such as the decomposition statisti cs used in
Kruber et al. (2017), or the LP information in Bonami et al. (2 018). More-
over, we remark that, in the satisﬁability context, the lear ning of the type of
algorithm to execute on a particular cluster of instances ha s been paired with
the learning of the parameters of the algorithm itself, see, e.g., Ans´ otegui et al.
(2017, 2019).
3.2.3 Machine learning alongside optimization algorithms
To generalize the context of the previous section to its full potential, one
can build CO algorithms that repeatedly call an ML model thro ughout their
23
execution, as illustrated in Figure 9. A master algorithm co ntrols the high-
level structure while frequently calling an ML model to assi st in lower level
decisions. The key diﬀerence between this approach and the ex amples dis-
cussed in the previous section is that the same ML model is used by the CO
algorithm to make the same type of decisions a number of times in the order
of the number of iterations of the algorithm. As in the previo us section,
nothing prevents one from applying additional steps before or after such an
algorithm.
SolutionORProblem
deﬁnition
ML
State Decision
Figure 9: The combinatorial optimization algorithm repeat edly queries the
same ML model to make decisions. The ML model takes as input th e current
state of the algorithm, which may include the problem deﬁnit ion.
This is clearly the context of the branch-and-bound tree for MILP, where
we already mentioned how the task of selecting the branching variable is ei-
ther too heuristic or too slow, and is therefore a good candid ate for learning
(Lodi and Zarpellon, 2017). In this case, the general algori thm remains
a branch-and-bound framework, with the same software archi tecture and
the same guarantees on lower and upper bounds, but the branch ing de-
cisions made at every node are left to be learned. Likewise, t he work of
Hottung et al. (2017) learning both a branching policy and value network
for heuristic tree search undeniably ﬁts in this context. An other important
aspect in solving MILPs is the use of primal heuristics, i.e., algorithms that
are applied in the B&B nodes to ﬁnd feasible solutions, witho ut guarantee
of success. On top of their obvious advantages, good solutio ns also give
tighter upper bounds (for minimization problems) on the sol ution value and
make more pruning of the tree possible. Heuristics depend on the branch-
ing node (as branching ﬁx some variables to speciﬁc values), so they need
24
to be run frequently. However, running them too often can slo w down the
exploration of the tree, especially if their outcome is nega tive, i.e., no better
upper bound is detected. Khalil et al. (2017b) build an ML mod el to predict
whether or not running a given heuristic will yield a better s olution than
the best one found so far and then greedily run that heuristic whenever the
outcome of the model is positive.
The approximation used by Baltean-Lugojan et al. (2018), al ready dis-
cussed in Section 3.2.1, is an example of predicting a high-l evel description
of the solution to an optimization problem, namely the objec tive value.
Nonetheless, the goal is to solve the original QP. Thus, the l earned model is
queried repeatedly to select promising cutting planes. The ML model is used
only to select promising cuts, but once selected, cuts are ad ded to the LP
relaxation, thus embedding the ML outcome into an exact algo rithm. This
approach highlights promising directions for this type of a lgorithm. The de-
cision learned is critical because adding the best cutting p lanes is necessary
for solving the problem fast (or fast enough, because in the p resence of NP-
hard problems, optimization may time out before any meaning ful solving).
At the same time, the approximate decision (often in the form of a proba-
bility) does not compromise the exactness of the algorithm: any cut added
is guaranteed to be valid. This setting leaves room for ML to t hrive, while
reducing the need for guarantees from the ML algorithms (an a ctive and dif-
ﬁcult area of research). In addition, note that, the approac h in Larsen et al.
(2018) is part of a master algorithm in which the ML is iterati vely invoked
to make booking decisions in real time. The work of Khalil et a l. (2017a),
presented in Section 3.1.2, also belongs to this setting, ev en if the resulting
algorithm is heuristic. Indeed, an ML model is asked to selec t the most rel-
evant node, while a master algorithm maintains the partial t our, computes
its length, etc. Because the master algorithm is very simple, it is possible
to see the contribution as an end-to-end method, as stated in Section 3.2.1,
but it can also be interpreted more generally as done here.
Presented in Section 3.1.2, and mentioned in the previous se ction, the
Markov Chain framework for building heuristics from Karape tyan et al.
(2017) can also be framed as repeated decisions. The transit ion matrix
can be queried and sampled from in order to transition from on e state to
another, i.e., to make the low level decisions of choosing the next move. Th e
three distinctions made in this Section 3.2 are general enou gh that they can
overlap. Here, the fact that the model operates on internal s tate transitions,
yet is learned globally, is what makes it hard to analyze.
Before ending this section, it is worth mentioning that lear ning recur-
rent algorithmic decisions is also used in the deep learning community, for
25
instance in the ﬁeld of meta-learning to decide how to apply g radient updates
in stochastic gradient descent (Andrychowicz et al., 2016; Li and Malik, 2017;
Wichrowska et al., 2017).
4 Learning objective
In the previous section, we have surveyed the existing liter ature by orthog-
onally grouping the main contributions of ML for CO into fami lies of ap-
proaches, sometimes with overlaps. In this section, we form ulate and study
the objective that drives the learning process.
4.1 Multi-instance formulation
In the following, we introduce an abstract learning formula tion (inspired
from Bischl et al. (2016)). How would an ML practitioner comp are opti-
mization algorithms? Let us deﬁne I to be a set of problem instances, and
P a probability distribution over I. These are the problems that we care
about, weighted by a probability distribution, reﬂecting t he fact that, in a
practical application, not all problems are as likely. In pr actice, I or P are
inaccessible, but we can observe some samples from P , as motivated in the
introduction with the Montreal delivery company. For a set o f algorithms
A, let m : I × A → R be a measure of the performance of an algorithm
on a problem instance (lower is better). This could be the obj ective value
of the best solution found, but could also incorporate eleme nts from opti-
mality bounds, absence of results, running times, and resou rce usage. To
compare a1, a 2 ∈ A , an ML practitioner would compare Ei∼P m(i, a1) and
Ei∼P m(i, a2), or equivalently
min
a∈{a1,a 2}
Ei∼P m(i, a). (4)
Because measuring these quantities is not tractable, one wi ll typically use
empirical estimates instead, by using a ﬁnite dataset Dtrain of independent
instances sampled from P
min
a∈{a1,a 2}
∑
i∈Dtrain
1
|Dtrain|m(i, a). (5)
This is intuitive and done in practice: collect a dataset of p roblem instances
and compare say, average running times. Of course, such expe ctation can
be computed for diﬀerent datasets (diﬀerent I’s and P ’s), and diﬀerent
measures (diﬀerent m’s).
26
This is already a learning problem. The more general one that we want
to solve through leaning is
min
a∈A
Ei∼P m(i, a). (6)
Instead of comparing between two algorithms, we may compare among an
uncountable, maybe non-parametric, space of algorithms. T o see how we
come up with so many algorithms, we have to look at the algorit hms in
Section 3, and think of the ML model space over which we learn a s deﬁning
parametrizing the algorithm space A. For instance, consider the case of
learning a branching policy π for B&B. If we deﬁne the policy to be a neural
network with a set of weights θ ∈ Rp, then we obtain a parametric B&B
algorithm a(πθ) and (6) becomes
min
θ∈Rp
Ei∼P m(i, a(πθ)). (7)
Unfortunately, solving this problem is hard. On the one hand , the per-
formance measure m is most often not diﬀerentiable and without closed form
expression. We discuss this in Section 4.2. On the other hand , computing
the expectation in (6) is intractable. As in (5), one can use a n empirical
distribution using a ﬁnite dataset, but that leads to generalization consid-
erations, as explained in Section 4.3.
Before we move on, let us introduce a new element to make (6) mo re
general. That formula suggests that, once given an instance , the outcome of
the performance measure is deterministic. That is unrealis tic for multiple
reasons. The performance measure could itself incorporate some source of
randomness due to external factors, for instance with runni ng times which
are hardware and system dependent. The algorithm could also incorporate
non negligible sources of randomness, if it is designed to be stochastic, or
if some operations are non deterministic, or to express the f act that the
algorithm should be robust to the choice of some external par ameters. Let
τ be that source of randomness, π ∈ Π the internal policy being learned,
and a(π, τ ) the resulting algorithm, then we can reformulate (6) as
min
π ∈Π
Ei∼P [ Eτ[ m(i, a (π, τ )) | i ] ] . (8)
In particular, when learning repeated decisions, as in Sect ion 3.2.3, this
source of randomness can be expressed along the trajectory f ollowed in the
MDP, using the dynamics of the environment p(s′, r|a, s) (see Figure 2).
The addition made in (8) will be useful for the discussion on g eneralization
in Section 4.3.
27
4.2 Surrogate objectives
In the previous section, we have formulated a proper learnin g objective.
Here, we try to relate that objective to the learning methods of Section 3.1,
namely, demonstration and experience. If the usual learnin g metrics of an
ML model, e.g., accuracy for classiﬁcation in supervised (imitation) lea rn-
ing, is improving, does it mean that the performance metric o f (6) is also
improving?
A straightforward approach for solving (8) is that of reinfo rcement learn-
ing (including direct optimization methods), as surveyed i n Section 3.1.2.
The objective from (6) can be optimized directly on experien ce data by
matching the total return to the performance measure. Somet imes, a single
ﬁnal reward can naturally be decoupled across the trajector y. For instance,
if the performance objective of a B&B variable selection pol icy is to min-
imize the number of opened nodes, then the policy can receive a reward
discouraging an increase in the number of nodes, hence givin g an incentive
to select variables that lead to pruning. However, that may n ot be always
possible, leaving only the option of delaying a single rewar d to the end of
the trajectory. This sparse reward setting is challenging f or RL algorithms,
and one might want to design a surrogate reward signal to enco urage in-
termediate accomplishments. This introduces some discrep ancies, and the
policy being optimized may learn a behavior not intended by t he algorithm
designer. There is a priori no relationship between two reward signals. One
needs to make use of their intuition to design surrogate sign als, e.g., min-
imizing the number of B&B nodes should lead to smaller running times.
Reward shaping is an active area of research in RL, yet it is of ten performed
by a number of engineering tricks.
In the case of learning a policy from a supervised signal from expert
demonstration, the performance measure m does not even appear in the
learning problem that is solved. In this context, the goal is to optimize
a policy π ∈ Π in the action space to mimic an expert policy πe (as ﬁrst
introduced with Figure 5)
min
π ∈Π
Ei∼P [ Es[ ℓ(π(s), πe(s)) | i, πe ] ] , (9)
where ℓ is a task dependent loss (classiﬁcation, regression, etc.). We have
emphasized that the state S is conditional, not only on the instance, but also
on the expert policy πe used to collect the data. Intuitively, the better the
ML model learns, i.e., the better the policy imitates the expert, the closer
the ﬁnal performance of the learned policy should be to the pe rformance of
the expert. Under some conditions, it is possible to relate t he performance
28
of the learned policy to the performance of the expert policy , but covering
this aspect is out of the scope of this paper. The opposite is n ot true, if
learning fails, the policy may still turn out to perform well (by encountering
an alternative good decision). Indeed, when making a decisi on with high
surrogate objective error, the learning will be fully penal ized when, in fact,
the decision could have good performances by the original me tric. For that
reason, it is capital to report the performance metrics. For example, we
surveyed in Section 3.2.2 the work of Bonami et al. (2018) whe re the authors
train a classiﬁer to predict if a mixed integer quadratic pro blem instance
should be linearized or not. The targets used for the learner are computed
optimally by solving the problem instance in both conﬁgurat ions. Simply
reporting the classiﬁcation accuracy is not enough. Indeed , this metric gives
no information on the impact a misclassiﬁcation has on runni ng times, the
metric used to compute the targets. In the binary classiﬁcat ion, a properly
classiﬁed example could also happen to have unsigniﬁcant di ﬀerence between
the running times of the two conﬁgurations. To alleviate thi s issue, the
authors also introduce a category where running times are no t signiﬁcatively
diﬀerent (and report the real running times). A continuous ex tension would
be to learn a regression of the solving time. However, learni ng this regression
now means that the ﬁnal algorithm needs to optimize over the s et of decisions
to ﬁnd the best one. In RL, this is analoguous to learning a val ue function
(see Section 2.2). Applying the same reasoning to repeated d ecisions is
better understood with the complete RL theory.
4.3 On generalization
In Section 4.1, we have claimed that the probability distrib ution in (6) is in-
accessible and needs to be replaced by the empirical probabi lity distribution
over a ﬁnite dataset Dtrain. The optimization problem solved is
min
a∈A
∑
i∈Dtrain
1
|Dtrain|m(i, a). (10)
As pointed out in Section 2.2, when optimizing over the empir ical probability
distribution, we risk having a low performance measure on th e ﬁnite number
of problem instances, regardless of the true probability distribution . In this
case, the generalization error is high because of the discrepancy between
the training performances and the true expected performanc es (overﬁtting).
To control this aspect, a validation set Dvalid is introduced to compare a
ﬁnite number of candidate algorithms based on estimates of g eneralization
29
performances, and a test set Dtest is used for estimating the generalization
performances of the selected algorithm.
In the following, we look more intuitively at generalizatio n in ML for
CO, and its consequences. To make it easier, let us recall diﬀe rent learning
scenarios. In the introduction, we have motivated the Montr eal delivery
company example, where the problems of interest are from an u nknown
probability distribution of Montreal TSPs. This is a very re stricted set of
problems, but enough to deliver value for this business. Muc h more ambi-
tious, we may want our policy learned on a ﬁnite set of instanc es to perform
well (generalize) to any “ real-world” MILP instance. This is of interest if
you are in the business of selling MILP solvers and want the br anching pol-
icy to perform well for as many of your clients as possible. In both cases,
generalization applies to the instances that are not known t o the algorithm
implementer. These are the only instances that we care about ; the one
used for training are already solved. The topic of probabili ty distribution of
instances also appears naturally in stochastic programmin g/optimization,
where uncertainty about the problem is modeled through prob ability dis-
tributions. Scenario generation, an essential way to solve this type of op-
timization programs, require sampling from this distribut ion and solving
the associated problem multiple times. Nair et al. (2018) ta ke advantage of
this repetitive process to learn an end-to-end model to solv e the problem.
Their model is composed of a local search and a local improvem ent policy
and is trained through RL. Here, generalization means that, during scenario
generation, the learned search beats other approaches, hen ce delivering an
overall faster stochastic programming algorithm. In short , learning without
generalization is pointless!
When the policy generalizes to other problem instances, it i s no longer
a problem if training requires additional computation for s olving problem
instances because, learning can be decoupled from solving a s it can be done
oﬄine. This setting is promising as it could give a policy to u se out of the
box for similar instances, while keeping the learning probl em to be han-
dled beforehand while remaining hopefully reasonable. Whe n the model
learned is a simple mapping, as is the case in Section 3.2.2, g eneralization to
new instances, as previously explained, can be easily under stood. However,
when learning sequential decisions, as in Section 3.2.3, th ere are intricate
levels of generalization. We said that we want the policy to g eneralize to
new instances, but the policy also needs to generalize to int ernal states of
the algorithm for a single instance, even if the model can be l earned from
complete optimization trajectories, as formulated by (8). Indeed, complex
algorithms can have unexpected sources of randomness, even if they are de-
30
signed to be deterministic. For instance, a numerical appro ximation may
perform diﬀerently if the version of some underlying numeric al library is
changed or because of asynchronous computing, such as when u sing Graph-
ical Processing Units (Nagarajan et al., 2019). Furthermor e, even if we can
achieve perfect replicability, we do not want the branching policy to break
if some other parameters of the solver are set (slightly) diﬀe rently. At the
very least, we want the policy to be robust to the choice of the random seed
present in many algorithms, including MILP solvers. These p arameters can
therefore be modeled as random variables. Because of these n ested levels
of generalization, one appealing way to think about the trai ning data from
multiple instances is like separate tasks of a multi-task le arning setting. The
diﬀerent tasks have underlying aspects in common, and they ma y also have
their own peculiar quirks. One way to learn a single policy th at generalizes
within a distribution of instances is to take advantage of th ese commonali-
ties. Generalization in RL remains a challenging topic, pro bably because of
the fuzzy distinction between a multi-task setting, and a la rge environment
encompassing all of the tasks.
Choosing how ambitious one should be in deﬁning the characte ristics of
the distribution is a hard question. For instance, if the Mon treal company
expands its business to other cities, should they be conside red as separate
distributions, and learn one branching policy per city, or o nly a single one?
Maybe one per continent? Generalization to a larger variety of instances is
challenging and requires more advanced and expensive learn ing algorithms.
Learning an array of ML models for diﬀerent distributions aso ciated with
a same task means of course more models to train, maintain, an d deploy.
The same goes with traditional CO algorithms, an MILP solver on its own
is not the best performing algorithm to solve TSPs, but it wor ks across
all MILP problems. It is too early to provide insights about h ow broad
the considered distributions should be, given the limited l iterature in the
ﬁeld. For scholars generating synthetic distributions, tw o intuitive axes of
investigation are “ structure” and “ size”. A TSP and a scheduling problem
seem to have fairly diﬀerent structure, and one can think of tw o planar
euclidean TSPs to be way more similar. Still, two of these TSP s can have
dramatically diﬀerent sizes (number of nodes). For instance , Gasse et al.
(2019) assess their methodology independently on three dis tributions. Each
training dataset has a speciﬁc problem structure (set cover ing, combinatorial
auction, and capacitated facility location), and a ﬁxed pro blem size. The
problem instance generators used are state-of-art and repr esentative of real-
world instances. Nonetheless, when they evaluate their lea rned algorithm,
the authors push the test distributions to larger sizes. The idea behind
31
this is to gauge if the model learned is able to generalize to a larger, more
practical, distribution, or only perform well on the restri cted distribution of
problems of the same size. The answer is largely aﬃrmative.
4.4 Single instance learning
An edge case that we have not much discussed yet is the single i nstance
learning framework. This might be the case for instance for p lanning the
design of a single factory. The factory would only be built on ce, with very
peculiar requirements, and the planners are not interested to relate this
to other problems. In this case, one can make as many runs (epi sodes)
and as many calls to a potential expert or simulator as one wan ts, but
ultimately one only cares about solving this one instance. L earning a policy
for a single instance should require a simpler ML model, whic h could thus
require less training examples. Nonetheless, in the single instance case, one
learns the policy from scratch at every new instance, actual ly incorporating
learning (not learned models but really the learning proces s itself) into the
end algorithm. This means starting the timer at the beginnin g of learning
and competing with other solvers to get the solution the fast est (or get the
best results within a time limit). This is an edge scenario th at can only
be employed in the setting of the Section 3.2.3, where ML is em bedded
inside a CO algorithm; otherwise there would be only one training ex ample!
There is therefore no notion of generalization to other prob lem instances, so
(6) is not the learning problem being solved. Nonetheless, t he model still
needs to generalize to unseen states of the algorithm. Indeed, if the model
was learned from all states of the algorithm that are needed t o solve the
problem, then the problem is already solved at training time and learning is
therefore fruitless. This is the methodology followed by Kh alil et al. (2016),
introduced in Section 3.1.1, to learn an instance-speciﬁc b ranching policy.
The policy is learned from strong-branching at the top of the B&B tree, but
needs to generalize to the state of the algorithm at the botto m of the tree,
where it is used. However, as for all CO algorithms, a fair com parison to
another algorithm can only be done on an independent dataset of instances,
as in (4). This is because through human trials and errors, th e data used
when building the algorithm leaks into the design of the algo rithm, even
without explicit learning components.
32
4.5 Fine tuning and meta-learning
A compromise between instance-speciﬁc learning and learni ng a generic pol-
icy is what we typically have in multi-task learning: some pa rameters are
shared across tasks and some are speciﬁc to each task. A commo n way to do
that (in the transfer learning scenario) is to start from a ge neric policy and
then adapt it to the particular instance by a form of ﬁne-tuning procedure:
training proceeds in two stages, ﬁrst training the generic p olicy across many
instances from the same distribution, and then continuing t raining on the
examples associated with a given instance on which we are hop ing to get
more specialized and accurate predictions.
Machine learning advances in the areas of meta-learning and transfer
learning are particularly interesting to consider here. Me ta-learning con-
siders two levels of optimization: the inner loop trains the parameters of a
model on the training set in a way that depends on meta-parame ters, which
are themselves optimized in an outer loop ( i.e., obtaining a gradient for each
completed inner-loop training or update). When the outer lo op’s objective
function is performance on a validation set, we end up traini ng a system so
that it will generalize well. This can be a successful strate gy for generalizing
from very few examples if we have access to many such training tasks. It
is related to transfer learning, where we want that what has b een learned
in one or many tasks helps improve generalization on another . These ap-
proaches can help rapidly adapt to a new problem, which would be useful
in the context of solving many MILP instances, seen as many re lated tasks.
To stay with the branching example on MILPs, one may not want t he
policy to perform well out of the box on new instances (from th e given
distribution). Instead, one may want to learn a policy oﬄine that can be
adapted to a new instance in a few training steps, every time i t is given one.
Similar topics have been explored in the context of automati c conﬁguration
tools. Fitzgerald et al. (2014) study the automatic conﬁgur ation in the life-
long learning context (a form of sequential transfer learni ng). The automatic
conﬁguration algorithm is augmented with a set of previous c onﬁgurations
that are prioritized on any new problem instance. A score reﬂ ecting past
performances is kept along every conﬁguration. It is design ed to retain con-
ﬁgurations that performed well in the past, while letting ne w ones a chance
to be properly evaluated. The automatic conﬁguration optim ization algo-
rithm used by Lindauer and Hutter (2018) requires training a n empirical
cost model mapping the Cartesian product of parameter conﬁg urations and
problem instances to expected algorithmic performance. Su ch a model is
usually learned for every cluster of problem instance that r equires conﬁg-
33
uring. Instead, when presented with a new cluster, the autho rs combine
the previously learned cost models and the new one to build an ensemble
model. As done by Fitzgerald et al. (2014), the authors also b uild a set of
previous conﬁgurations to prioritize, using an empirical c ost model to ﬁll
the missing data. This setting, which is more general than no t performing
any adaptation of the policy, has potential for better gener alization. Once
again, the scale on which this is applied can vary depending o n ambition.
One can transfer on very similar instances, or learn a policy that transfers
to a vast range of instances.
Meta-learning algorithms were ﬁrst introduced in the 1990s (Bengio et al.,
1991; Schmidhuber, 1992; Thrun and Pratt, 1998) and have sin ce then be-
come particularly popular in ML, including, but not limited to, learning
a gradient update rule (Hochreiter et al., 2001; Andrychowi cz et al., 2016),
few shot learning (Ravi and Larochelle, 2017), and multi-ta sk RL (Finn et al.,
2017).
4.6 Other metrics
Other metrics from the process of learning itself are also re levant, such as
how fast the learning process is, the sample complexity (num ber of examples
required to properly ﬁt the model), etc. As opposed to the metrics suggested
earlier in this section, these metrics provide us with infor mation not about
ﬁnal performance, but about oﬄine computation or the number of train-
ing examples required to obtain the desired policy. This inf ormation is, of
course, useful to calibrate the eﬀort in integrating ML into C O algorithms.
5 Methodology
In the previous section, we have detailed the theoretical le arning framework
of using ML in CO algorithms. Here, we provide some additiona l discussion
broadening some previously made claims.
5.1 Demonstration and experience
In order to learn a policy, we have highlighted two methodolo gies: demon-
stration, where the expected behavior is shown by an expert o r oracle (some-
times at a considerable computational cost), and experienc e, where the pol-
icy is learned through trial and error with a reward signal.
In the demonstration setting, the performance of the learne d policy is
bounded by the expert, which is a limitation when the expert i s not op-
34
timal. More precisely, without a reward signal, the imitati on policy can
only hope to marginally outperform the expert (for example b ecause the
learner can reduce the variance of the answers across simila rly-performing
experts). The better the learning, the closer the performan ce of the learner
to the expert’s. This means that imitation alone should be us ed only if it
is signiﬁcantly faster than the expert to compute the policy . Furthermore,
the performance of the learned policy may not generalize wel l to unseen
examples and small variations of the task and may be unstable due to accu-
mulation of errors. This is because in (9), the data was colle cted according
to the expert policy πe, but when run over multiple repeated decisions, the
distribution of states becomes that of the learned policy. S ome downsides of
supervised (imitation) learning can be overcome with more a dvanced algo-
rithms, including active methods to query the expert as an or acle to improve
behavior in uncertain states. The part of imitation learnin g presented here
is limited compared to the current literature in ML.
On the contrary, with a reward, the algorithm learns to optim ize for
that signal and can potentially outperform any expert, at th e cost of a much
longer training time. Learning from a reward signal (experi ence) is also more
ﬂexible when multiple decisions are (almost) equally good i n comparison
with an expert that would favor one (arbitrary) decision. Ex perience is not
without ﬂaws. In the case where policies are approximated ( e.g., with a
neural network), the learning process may get stuck around p oor solutions
if exploration is not suﬃcient or solutions which do not gene ralize well are
found. Furthermore, it may not always be straightforward to deﬁne a reward
signal. For instance, sparse rewards may be augmented using reward shaping
or a curriculum in order to value intermediate accomplishme nts (see Section
2.2).
Often, it is a good idea to start learning from demonstration s by an
expert, then reﬁne the policy using experience and a reward s ignal. This
is what was done in the original AlphaGo paper (Silver et al., 2016), where
human knowledge is combined with reinforcement learning. T he reader is
referred to Hussein et al. (2017) for a survey on imitation le arning covering
most of the discussion in this section.
5.2 Partial observability
We mentioned in section 2.2 that sometimes the states of an MD P are not
fully observed and the Markov property does not hold, i.e., the probability
of the next observation, conditioned on the current observa tion and action,
is not equal to the probability of the next observation, cond itioned on all
35
past observations and actions. An immediate example of this can be found
in any environment simulating physics: a single frame/imag e of such an
environment is not suﬃcient to grasp notions such as velocit y and is therefore
not suﬃcient to properly estimate the future trajectory of o bjects. It turns
out that, on real applications, partial observability is cl oser to the norm than
to the exception, either because one does not have access to a true state of
the environment, or because it is not computationally tract able to represent
and needs to be approximated. A straightforward way to tackl e the problem
is to compress all previous observations using an RNN. This c an be applied
in the imitation learning setting, as well as in RL, for insta nce by learning
a recurrent policy (Wierstra et al., 2010).
How does this apply in the case where we want to learn a policy f unction
making decisions for a CO algorithm? On the one hand, one has f ull access
to the state of the algorithm because it is represented in exa ct mathematical
concepts, such as constraints, cuts, solutions, B&B tree, etc. On the other
hand, these states can be exponentially large. This is an iss ue in terms of
computations and generalization. Indeed, if one does want t o solve problems
quickly, one needs to have a policy that is also fast to comput e, especially
if it is called frequently as is the case for, say, branching d ecisions. Further-
more, considering too high-dimensional states is also a sta tistical problem
for learning, as it may dramatically increase the required n umber of samples,
decrease the learning speed, or fail altogether. Hence, it i s necessary to keep
these aspects in mind while experimenting with diﬀerent repr esentations of
the data.
5.3 Exactness and approximation
In the diﬀerent examples we have surveyed, ML is used in both ex act
and heuristic frameworks, for example Baltean-Lugojan et a l. (2018) and
Larsen et al. (2018), respectively. Getting the output of an ML model to
respect advanced types of constraints is a hard task. In orde r to build exact
algorithms with ML components, it is necessary to apply the M L where all
possible decisions are valid. Using only ML as surveyed in Se ction 3.2.1
cannot give any optimality guarantee, and only weak feasibi lity guaran-
tees (see Section 6.1). However, applying ML to select or par ametrize a
CO algorithm as in Section 3.2.2 will keep exactness if all po ssible choices
that ML discriminate lead to complete algorithms. Finally, in the case of
repeated interactions between ML and CO surveyed in Section 3.2.3, all
possible decisions must be valid. For instance, in the case o f MILPs, this in-
cludes branching among fractional variables of the LP relaxation, selecting
36
the node to explore among open branching nodes (He et al., 2014), deciding
on the frequency to run heuristics on the B&B nodes (Khalil et al., 2017b),
selecting cutting planes among valid inequalities (Baltean-Lugojan et al.,
2018), removing previous cutting planes if they are not original constraints
or branching decision , etc. A counter-example can be found in the work of
Hottung et al. (2017), presented in Section 3.1.1. In their b ranch-an-bound
framework, bounding is performed by an approximate ML model that can
overestimate lower bounds, resulting in invalid pruning. T he resulting algo-
rithm is therefore not an exact one.
6 Challenges
In this section, we are reviewing some of the algorithmic con cepts previously
introduced by taking the viewpoint of their associated chal lenges.
6.1 Feasibility
In Section 3.2.1, we pointed out how ML can be used to directly output
solutions to optimization problems. Rather than learning t he solution, it
would be more precise to say that the algorithm is learning a heuristic. As
already repeatedly noted, the learned algorithm does not gi ve any guar-
antee in terms of optimality, but it is even more critical tha t feasibility is
not guaranteed either. Indeed, we do not know how far the outp ut of the
heuristic is from the optimal solution, or if it even respect s the constraints
of the problem. This can be the case for every heuristic and th e issue can
be mitigated by using the heuristic within an exact optimiza tion algorithm
(such as branch and bound).
Finding feasible solutions is not an easy problem (theoreti cally NP-hard
for MILPs), but it is even more challenging in ML, especially by using neu-
ral networks. Indeed, trained with gradient descent, neura l architectures
must be designed carefully in order not to break diﬀerentiabi lity. For in-
stance, both pointer networks (Vinyals et al., 2015) and the Sinkhorn layer
(Emami and Ranka, 2018) are complex architectures used to ma ke a network
output a permutation, a constraint easy to satisfy when writ ing a classical
CO heuristic.
6.2 Modelling
In ML, in general, and in deep learning, in particular, we kno w some good
prior for some given problems. For instance, we know that a CN N is an
37
architecture that will learn and generalize more easily tha n others on image
data. The problems studied in CO are diﬀerent from the ones cur rently being
addressed in ML, where most successful applications target natural signals.
The architectures used to learn good policies in combinator ial optimization
might be very diﬀerent from what is currently used with deep le arning.
This might also be true in more subtle or unexpected ways: it i s conceivable
that, in turn, the optimization components of deep learning algorithms (say,
modiﬁcations to SGD) could be diﬀerent when deep learning is a pplied to
the CO context.
Current deep learning already provides many techniques and architec-
tures for tackling problems of interest in CO. As pointed out in section 2.2,
techniques such as parameter sharing made it possible for ne ural networks to
process sequences of variable length with RNNs or, more rece ntly, to process
graph structured data through GNNs. Processing graph data i s of uttermost
importance in CO because many problems are formulated (repr esented) on
graphs. For a very general example, Selsam et al. (2018) repr esent a satis-
ﬁability problem using a bipartite graph on variables and cl auses. This can
generalize to MILPs, where the constraint matrix can be repr esented as the
adjacency matrix of a bipartite graph on variables and const raints, as done
in Gasse et al. (2019).
6.3 Scaling
Scaling to larger problems can be a challenge. If a model trai ned on instances
up to some size, say TSPs up to size ﬁfty nodes, is evaluated on larger in-
stances, say TSPs of size a hundred, ﬁve hundred nodes, etc, the challenge
exists in terms of generalization, as mentioned in Section 4 .3. Indeed, all
of the papers tackling TSP through ML and attempting to solve larger in-
stances see degrading performance as size increases much be yond the sizes
seen during training (Vinyals et al., 2015; Bello et al., 201 7; Khalil et al.,
2017a; Kool and Welling, 2018). To tackle this issue, one may try to learn
on larger instances, but this may turn out to be a computation al and gener-
alization issue. Except for very simple ML models and strong assumptions
about the data distribution, it is impossible to know the com putational
complexity and the sample complexity, i.e. the number of obs ervations that
learning requires, because one is unaware of the exact probl em one is trying
to solve, i.e., the true data generating distribution.
38
6.4 Data generation
Collecting data (for example instances of optimization pro blems) is a sub-
tle task. Larsen et al. (2018) claim that “ sampling from historical data is
appropriate when attempting to mimic a behavior reﬂected in such data ”.
In other words, given an external process on which we observe instances of
an optimization problem, we can collect data to train some po licy needed
for optimization, and expect the policy to generalize on fut ure instances of
this application. A practical example would be a business th at frequently
encounters optimization problems related to their activit ies, such as the
Montreal delivery company example used in the introduction .
In other cases, i.e., when we are not targeting a speciﬁc application for
which we would have historical data, how can we proactively t rain a policy
for problems that we do not yet know of? As partially discusse d in Sec-
tion 4.3, we ﬁrst need to deﬁne to which family of instances we want to gen-
eralize over. For instance, we might decide to learn a cuttin g plane selection
policy for Euclidian TSP problems. Even so, it remains a comp lex eﬀort to
generate problems that capture the essence of real applicat ions. Moreover,
CO problems are high dimensional, highly structured, and tr oublesome to vi-
sualize. The sole exercise of generating graphs is already a complicated one!
The topic has nonetheless received some interest. Smith-Mi les and Bowly
(2015) claim that the conﬁdence we can put in an algorithm “ depends on
how carefully we select test instances ”, but note however that too often,
a new algorithm is claimed “ to be superior by showing that it outperforms
previous approaches on a set of well-studied instances ”. The authors pro-
pose a problem instance generating method that consists of: deﬁning an
instance feature space, visualizing it in two dimensions (u sing dimensional-
ity reduction techniques such as principal component analy sis), and using an
evolutionary algorithm to drive the instance generation to ward a pre-deﬁned
sub-space. The authors argue that the method is successful i f the easy and
hard instances can be easily separated in the reduced instan ce space. The
methodology is then fruitfully applied to graph-based prob lems, but would
require redeﬁning evolution primitives in order to be appli ed to other type
of problems. On the contrary, Malitsky et al. (2016) propose a method to
generate problem instances from the same probability distr ibution, in that
case, the one of “ industrial” boolean satisﬁability problem instances. The
authors use a large neighborhood search, using destruction and reparation
primitives, to search for new instances. Some instance feat ures are com-
puted to classify whether the new instances fall under the sa me cluster as
the target one.
39
Deciding how to represent the data is also not an easy task, bu t can
have a dramatic impact on learning. For instance, how does on e properly
represent a B&B node, or even the whole B&B tree? These repres entations
need to be expressive enough for learning, but at the same tim e, concise
enough to be used frequently without excessive computation s.
7 Conclusions
We have surveyed and highlighted how machine learning can be used to
build combinatorial optimization algorithms that are part ially learned. We
have suggested that imitation learning alone can be valuabl e if the policy
learned is signiﬁcantly faster to compute than the original one provided
by an expert, in this case a combinatorial optimization algo rithm. On the
contrary, models trained with a reward signal have the poten tial to outper-
form current policies, given enough training and a supervis ed initialization.
Training a policy that generalizes to unseen problems is a ch allenge, this is
why we believe learning should occur on a distribution small enough that
the policy could fully exploit the structure of the problem a nd give better
results. We believe end-to-end machine learning approache s to combinato-
rial optimization can be improved by using machine learning in combination
with current combinatorial optimization algorithms to ben eﬁt from the the-
oretical guarantees and state-of-the-art algorithms alre ady available.
Other than performance incentives, there is also interest i n using ma-
chine learning as a modelling tool for discrete optimizatio n, as done by
Lombardi and Milano (2018), or to extract intuition and know ledge about
algorithms as mentioned in Bonami et al. (2018); Khalil et al . (2017a).
Although most of the approaches we discussed in this paper ar e still at
an exploratory level of deployment, at least in terms of thei r use in general-
purpose (commercial) solvers, we strongly believe that thi s is just the be-
ginning of a new era for combinatorial optimization algorit hms.
Acknowledgments
The authors are grateful to Emma Frejinger, Simon Lacoste-J ulien, Ja-
son Jo, Laurent Charlin, Matteo Fischetti, R´ emi Leblond, M ichela Milano,
S´ ebastien Lachapelle, Eric Larsen, Pierre Bonami, Martin a Fischetti, Elias
Khalil, Bistra Dilkina, Sebastian Pokutta, Marco L¨ ubbeck e, Andrea Tra-
montani, Dimitris Bertsimas and the entire CERC team for end less discus-
sions on the subject and for reading and commenting a prelimi nary version
40
of the paper.
References
Ahuja, R. K. and Orlin, J. B. (2001). Inverse Optimization. Operations
Research, 49(5):771–783.
Andrychowicz, M., Denil, M., G´ omez, S., Hoﬀman, M. W., Pfau, D., Schaul,
T., Shillingford, B., and de Freitas, N. (2016). Learning to learn by gra-
dient descent by gradient descent. In Lee, D. D., Sugiyama, M ., Luxburg,
U. V., Guyon, I., and Garnett, R., editors, Advances in Neural Informa-
tion Processing Systems 29 , pages 3981–3989. Curran Associates, Inc.
Ans´ otegui, C., Heymann, B., Pon, J., Sellmann, M., and Tierney, K. (2019).
Hyper-Reactive Tabu Search for MaxSAT. In Battiti, R., Brun ato, M.,
Kotsireas, I., and Pardalos, P. M., editors, Learning and Intelligent Op-
timization, Lecture Notes in Computer Science, pages 309–325. Springe r
International Publishing.
Ans´ otegui, C., Pon, J., Sellmann, M., and Tierney, K. (2017 ). Reactive
Dialectic Search Portfolios for MaxSAT. In Thirty-First AAAI Conference
on Artiﬁcial Intelligence .
Applegate, D., Bixby, R., Chv´ atal, V., and Cook, W. (2007). The traveling
salesman problem. A computational study . Princeton University Press.
Bahdanau, D., Cho, K., and Bengio, Y. (2015). Neural machine translation
by jointly learning to align and translate. In ICLR’2015, arXiv:1409.0473.
Baltean-Lugojan, R., Misener, R., Bonami, P., and Tramonta ni, A. (2018).
Strong sparse cut selection via trained neural nets for quad ratic semidef-
inite outer-approximations. Technical report, Imperial C ollege, London.
Bello, I., Pham, H., Le, Q. V., Norouzi, M., and Bengio, S. (20 17). Neural
Combinatorial Optimization with Reinforcement Learning. In Interna-
tional Conference on Learning Representations .
Bengio, Y., Bengio, S., Cloutier, J., and Gecsei, J. (1991). Learning a
synaptic learning rule. In IJCNN, pages II–A969.
Bischl, B., Kerschke, P., Kotthoﬀ, L., Lindauer, M., Malitsk y, Y., Fr´ echette,
A., Hoos, H., Hutter, F., Leyton-Brown, K., Tierney, K., and Vanschoren,
41
J. (2016). ASlib: A benchmark library for algorithm selecti on. Artiﬁcial
Intelligence, 237:41–58.
Bishop, C. M. (2006). Pattern Recognition and Machine Learning . springer.
Bonami, P., Lodi, A., and Zarpellon, G. (2018). Learning a Cl assiﬁcation
of Mixed-Integer Quadratic Programming Problems. In Integration of
Constraint Programming, Artiﬁcial Intelligence, and Operat ions Research,
Lecture Notes in Computer Science, pages 595–604. Springer , Cham.
Chan, T. C. Y., Craig, T., Lee, T., and Sharpe, M. B. (2014). Ge neralized
Inverse Multiobjective Optimization with Application to C ancer Therapy.
Operations Research, 62(3):680–695.
Conforti, M., Conrnu´ ejols, G., and Zambelli, G. (2014). Integer Program-
ming. Springer.
Creswell, A., White, T., Dumoulin, V., Arulkumaran, K., Sen gupta, B., and
Bharath, A. A. (2018). Generative Adversarial Networks: An Overview.
IEEE Signal Processing Magazine , 35(1):53–65.
Dai, H., Dai, B., and Song, L. (2016). Discriminative Embedd ings of Latent
Variable Models for Structured Data. In Balcan, M. F. and Wei nberger,
K. Q., editors, Proceedings of The 33rd International Conference on Ma-
chine Learning, volume 48 of Proceedings of Machine Learning Research ,
pages 2702–2711, New York, New York, USA. PMLR.
Dey, S. and Molinaro, M. (2018). Theoretical challenges tow ards cutting-
plane selection. Mathematical Programming, 170:237–266.
Emami, P. and Ranka, S. (2018). Learning Permutations with S inkhorn
Policy Gradient. arXiv:1805.07010 [cs, stat] .
Finn, C., Abbeel, P., and Levine, S. (2017). Model-Agnostic Meta-Learning
for Fast Adaptation of Deep Networks. In Precup, D. and Teh, Y . W., edi-
tors, Proceedings of the 34th International Conference on Machine L earn-
ing, volume 70 of Proceedings of Machine Learning Research, pages 1126–
1135, International Convention Centre, Sydney, Australia . PMLR.
Fischetti, M. and Lodi, A. (2011). Heuristics in Mixed Integer Programming,
volume 3, pages 2199–2204. Wiley Online Library.
Fitzgerald, T., Malitsky, Y., O’Sullivan, B., and Tierney, K. (2014). ReACT:
Real-Time Algorithm Conﬁguration through Tournaments. In Seventh
Annual Symposium on Combinatorial Search .
42
Fortun, M. and Schweber, S. S. (1993). Scientists and the leg acy of world
war ii: The case of operations research (or). Social Studies of Science ,
23(4):595–642.
Gasse, M., Ch´ etelat, D., Ferroni, N., Charlin, L., and Lodi , A. (2019). Ex-
act combinatorial optimization with graph convolutional n eural networks.
arXiv preprint arXiv:1906.01629 .
Gendreau, M. and Potvin, J.-Y., editors (2010). Handbook of metaheuristics,
volume 2. Springer.
Gilmer, J., Schoenholz, S. S., Riley, P. F., Vinyals, O., and Dahl, G. E.
(2017). Neural Message Passing for Quantum Chemistry. In Pr ecup, D.
and Teh, Y. W., editors, Proceedings of the 34th International Confer-
ence on Machine Learning , volume 70 of Proceedings of Machine Learn-
ing Research, pages 1263–1272, International Convention Centre, Sydne y,
Australia. PMLR.
Goodfellow, I., Bengio, Y., and Courville, A. (2016). Deep Learning. MIT
press.
He, H., Daume III, H., and Eisner, J. M. (2014). Learning to Se arch in
Branch and Bound Algorithms. In Ghahramani, Z., Welling, M. , Cortes,
C., Lawrence, N. D., and Weinberger, K. Q., editors, Advances in Neural
Information Processing Systems 27 , pages 3293–3301. Curran Associates,
Inc.
Hochreiter, S., Younger, A. S., and Conwell, P. R. (2001). Le arning to
learn using gradient descent. In Dorﬀner, G., Bischof, H., an d Hornik, K.,
editors, Artiﬁcial Neural Networks — ICANN 2001 , pages 87–94, Berlin,
Heidelberg. Springer Berlin Heidelberg.
Hoos, H. H. (2012). Automated Algorithm Conﬁguration and Pa rameter
Tuning. In Hamadi, Y., Monfroy, E., and Saubion, F., editors , Au-
tonomous Search , pages 37–71. Springer Berlin Heidelberg, Berlin, Hei-
delberg.
Hottung, A., Tanaka, S., and Tierney, K. (2017). Deep Learni ng As-
sisted Heuristic Tree Search for the Container Pre-marshal ling Problem.
arXiv:1709.09972 [cs] . arXiv: 1709.09972.
Hussein, A., Gaber, M. M., Elyan, E., and Jayne, C. (2017). Im itation
Learning: A Survey of Learning Methods. ACM Computing Surveys ,
50(2):21:1–21:35.
43
Karapetyan, D., Punnen, A. P., and Parkes, A. J. (2017). Mark ov Chain
methods for the Bipartite Boolean Quadratic Programming Pr oblem. Eu-
ropean Journal of Operational Research , 260(2):494–506.
Khalil, E., Dai, H., Zhang, Y., Dilkina, B., and Song, L. (201 7a). Learn-
ing Combinatorial Optimization Algorithms over Graphs. In Guyon, I.,
Luxburg, U. V., Bengio, S., Wallach, H., Fergus, R., Vishwan athan, S.,
and Garnett, R., editors, Advances in Neural Information Processing Sys-
tems 30 , pages 6348–6358. Curran Associates, Inc.
Khalil, E. B., Bodic, P. L., Song, L., Nemhauser, G., and Dilk ina, B. (2016).
Learning to Branch in Mixed Integer Programming. In Proceedings of
the Thirtieth AAAI Conference on Artiﬁcial Intelligence , AAAI’16, pages
724–731, Phoenix, Arizona. AAAI Press.
Khalil, E. B., Dilkina, B., Nemhauser, G. L., Ahmed, S., and S hao, Y.
(2017b). Learning to Run Heuristics in Tree Search. In Proceedings of
the Twenty-Sixth International Joint Conference on Artiﬁcial Intelligence,
IJCAI-17, pages 659–666.
Kool, W. W. M. and Welling, M. (2018). Attention Solves Your T SP, Ap-
proximately. arXiv:1803.08475 [cs, stat] .
Kruber, M., L¨ ubbecke, M. E., and Parmentier, A. (2017). Lea rning When
to Use a Decomposition. In Integration of AI and OR Techniques in
Constraint Programming, Lecture Notes in Computer Science, pages 202–
210. Springer, Cham.
Larsen, E., Lachapelle, S., Bengio, Y., Frejinger, E., Laco ste-Julien,
S., and Lodi, A. (2018). Predicting Solution Summaries to In teger
Linear Programs under Imperfect Information with Machine L earning.
arXiv:1807.11876 [cs, stat] .
Larson, R. C. and Odoni, A. R. (1981). Urban operations research. Number
Monograph.
Li, K. and Malik, J. (2017). Learning to Optimize Neural Nets .
arXiv:1703.00441 [cs, math, stat] .
Liberto, G. D., Kadioglu, S., Leo, K., and Malitsky, Y. (2016 ). DASH:
Dynamic Approach for Switching Heuristics. European Journal of Oper-
ational Research, 248(3):943–953.
44
Lindauer, M. and Hutter, F. (2018). Warmstarting of Model-B ased Algo-
rithm Conﬁguration. In Thirty-Second AAAI Conference on Artiﬁcial
Intelligence.
Lodi, A. (2009). MIP computation. In J¨ unger, M., Liebling, T., Naddef, D.,
Nemhauser, G., Pulleyblank, W., Reinelt, G., Rinaldi, G., a nd Wolsey,
L., editors, 50 Years of Integer Programming 1958-2008 , pages 619–645.
Springer-Verlag.
Lodi, A. and Zarpellon, G. (2017). On learning and branching : A survey.
TOP, 25(2):207–236.
Lombardi, M. and Milano, M. (2018). Boosting Combinatorial Problem
Modeling with Machine Learning. In Proceedings of the Twenty-Seventh
International Joint Conference on Artiﬁcial Intelligence, IJCA I-18, pages
5472–5478. International Joint Conferences on Artiﬁcial I ntelligence Or-
ganization.
Mahmood, R., Babier, A., McNiven, A., Diamant, A., and Chan, T. C. Y.
(2018). Automated Treatment Planning in Radiation Therapy using Gen-
erative Adversarial Networks. In Proceedings of Machine Learning for
Health Care, volume 85 of Proceedings of Machine Learning Research .
Malitsky, Y., Merschformann, M., O’Sullivan, B., and Tiern ey, K. (2016).
Structure-Preserving Instance Generation. In Festa, P., S ellmann, M.,
and Vanschoren, J., editors, Learning and Intelligent Optimization , Lec-
ture Notes in Computer Science, pages 123–140. Springer Int ernational
Publishing.
Marcos Alvarez, A., Louveaux, Q., and Wehenkel, L. (2014). A supervised
machine learning approach to variable branching in branch- and-bound.
Technical report, Universit´ e de Li` ege.
Marcos Alvarez, A., Louveaux, Q., and Wehenkel, L. (2017). A Machine
Learning-Based Approximation of Strong Branching. INFORMS Journal
on Computing , 29(1):185–195.
Marcos Alvarez, A., Wehenkel, L., and Louveaux, Q. (2016). O nline Learn-
ing for Strong Branching Approximation in Branch-and-Boun d. Technical
report, Universit´ e de Li` ege.
Mascia, F., L´ opez-Ib´ a˜ nez, M., Dubois-Lacoste, J., and St¨ utzle, T. (2014).
Grammar-based generation of stochastic local search heuri stics through
45
automatic algorithm conﬁguration tools. Computers & Operations Re-
search, 51:190–199.
McCormick, G. P. (1976). Computability of global solutions to factorable
nonconvex programs: Part I — Convex underestimating proble ms. Math-
ematical Programming, 10(1):147–175.
Murphy, K. P. (2012). Machine Learning: A Probabilistic Perspective . MIT
press.
Nagarajan, P., Warnell, G., and Stone, P. (2019). Determini stic implemen-
tations for reproducibility in deep reinforcement learnin g. In AAAI 2019
Workshop on Reproducible AI .
Nair, V., Dvijotham, D., Dunning, I., and Vinyals, O. (2018) . Learning fast
optimizers for contextual stochastic integer programs. In Conference on
Uncertainty in Artiﬁcal Intelligence , pages 591–600.
Nowak, A., Villar, S., Bandeira, A. S., and Bruna, J. (2017). A Note on
Learning Algorithms for Quadratic Assignment with Graph Ne ural Net-
works. arXiv:1706.07450 [cs, stat] .
Ravi, S. and Larochelle, H. (2017). Optimization as a model f or few-shot
learning. In International Conference on Learning Representations .
Schmidhuber, J. (1992). Learning to control fast-weight me mories: An alter-
native to dynamic recurrent networks. Neural Computation, 4(1):131–139.
Selsam, D., Lamm, M., B¨ unz, B., Liang, P., de Moura, L., and D ill,
D. L. (2018). Learning a SAT Solver from Single-Bit Supervis ion.
arXiv:1802.03685 [cs] .
Silver, D., Huang, A., Maddison, C. J., Guez, A., Sifre, L., v an den Driess-
che, G., Schrittwieser, J., Antonoglou, I., Panneershelva m, V., Lanctot,
M., Dieleman, S., Grewe, D., Nham, J., Kalchbrenner, N., Sut skever, I.,
Lillicrap, T., Leach, M., Kavukcuoglu, K., Graepel, T., and Hassabis, D.
(2016). Mastering the game of Go with deep neural networks an d tree
search. Nature, 529(7587):484–489.
Smith, K. A. (1999). Neural Networks for Combinatorial Opti mization:
A Review of More Than a Decade of Research. INFORMS Journal on
Computing, 11(1):15–34.
46
Smith-Miles, K. and Bowly, S. (2015). Generating new test in stances by
evolving in instance space. Computers & Operations Research , 63:102–
113.
Sutton, R. S. and Barto, A. G. (2018). Reinforcement Learning: An Intro-
duction. MIT press Cambridge, second edition.
Thrun, S. and Pratt, L. Y., editors (1998). Learning to Learn . Kluwer
Academic.
Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N.,
Kaiser, L., and Polosukhin, I. (2017). Attention is All you N eed. In Guyon,
I., Luxburg, U. V., Bengio, S., Wallach, H., Fergus, R., Vish wanathan,
S., and Garnett, R., editors, Advances in Neural Information Processing
Systems 30 , pages 5998–6008. Curran Associates, Inc.
Veliˇ ckovi´ c, P., Cucurull, G., Casanova, A., Romero, A., Li` o, P., and Bengio,
Y. (2018). Graph attention networks. In International Conference on
Learning Representations.
Vinyals, O., Fortunato, M., and Jaitly, N. (2015). Pointer N etworks. In
Cortes, C., Lawrence, N. D., Lee, D. D., Sugiyama, M., and Gar nett, R.,
editors, Advances in Neural Information Processing Systems 28 , pages
2692–2700. Curran Associates, Inc.
Wichrowska, O., Maheswaranathan, N., Hoﬀman, M. W., Colmena rejo,
S. G., Denil, M., de Freitas, N., and Sohl-Dickstein, J. (201 7). Learned
Optimizers that Scale and Generalize. In Precup, D. and Teh, Y. W., edi-
tors, Proceedings of the 34th International Conference on Machine L earn-
ing, volume 70 of Proceedings of Machine Learning Research, pages 3751–
3760, International Convention Centre, Sydney, Australia . PMLR.
Wierstra, D., F¨ orster, A., Peters, J., and Schmidhuber, J. (2010). Recurrent
policy gradients. Logic Journal of the IGPL , 18(5):620–634.
Wolsey, L. A. (1998). Integer Programming. Wiley.
¨Ozcan, E., Misir, M., Ochoa, G., and Burke, E. K. (2012). A Rei nforcement
Learning: Great-Deluge Hyper-Heuristic for Examination T imetabling.
Modeling, Analysis, and Applications in Metaheuristic Comp uting: Ad-
vancements and Trends , pages 34–55.
47
