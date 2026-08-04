# r012_10_1007_s12532-020-00179-2_osqp_an_operator_splitting_solver_for_quadratic_


- kind: paper-mineru
- title: r012_10_1007_s12532-020-00179-2_osqp_an_operator_splitting_solver_for_quadratic_
- source: path:knowledge/inbox_pdf/or_fulltext/r012_10.1007_s12532-020-00179-2_osqp_an_operator_splitting_solver_for_quadratic_programs.pdf

- kind: paper-mineru
- source_pdf: knowledge/inbox_pdf/or_fulltext/r012_10.1007_s12532-020-00179-2_osqp_an_operator_splitting_solver_for_quadratic_programs.pdf
- preprocess_mode: offline_extract
- extract_backend: pypdf
- note: RAG text for Pi retrieve; not numeric authority.

---
OSQP: An Operator Splitting Solver for
Quadratic Programs
Bartolomeo Stellato, Goran Banjac, Paul Goulart,
Alberto Bemporad, and Stephen Boyd
February 13, 2020
Abstract
We present a general-purpose solver for convex quadratic programs based on the
alternating direction method of multipliers, employing a novel operator splitting tech-
nique that requires the solution of a quasi-deﬁnite linear system with the same co-
eﬃcient matrix at almost every iteration. Our algorithm is very robust, placing no
requirements on the problem data such as positive deﬁniteness of the objective func-
tion or linear independence of the constraint functions. It can be conﬁgured to be
division-free once an initial matrix factorization is carried out, making it suitable for
real-time applications in embedded systems. In addition, our technique is the ﬁrst op-
erator splitting method for quadratic programs able to reliably detect primal and dual
infeasible problems from the algorithm iterates. The method also supports factorization
caching and warm starting, making it particularly eﬃcient when solving parametrized
problems arising in ﬁnance, control, and machine learning. Our open-source C imple-
mentation OSQP has a small footprint, is library-free, and has been extensively tested
on many problem instances from a wide variety of application areas. It is typically ten
times faster than competing interior-point methods, and sometimes much more when
factorization caching or warm start is used. OSQP has already shown a large impact
with tens of thousands of users both in academia and in large corporations.
1 Introduction
1.1 The problem
Consider the following optimization problem
minimize (1 /2)xTPx +qTx
subject to Ax∈C , (1)
where x ∈ Rn is the decision variable. The objective function is deﬁned by a positive
semideﬁnite matrixP∈ Sn
+ and a vectorq∈ Rn, and the constraints by a matrixA∈ Rm×n
1
arXiv:1711.08013v4  [math.OC]  12 Feb 2020
and a nonempty, closed and convex set C ⊆Rm. We will refer to it as general (convex)
quadratic program.
If the setC takes the form
C = [l,u ] ={z∈ Rm|li≤zi≤ui, i = 1,...,m },
with li∈{−∞}∪ R and ui∈ R∪{ +∞}, we can write problem (1) as
minimize (1 /2)xTPx +qTx
subject to l≤Ax≤u, (2)
which we will refer to as a quadratic program (QP). Linear equality constraints can be
encoded in this way by setting li =ui for some or all of the elements in (l,u ). Note that any
linear program (LP) can be written in this form by setting P = 0. We will characterize the
size of (2) with the tuple ( n,m,N ) where N is the sum of the number of nonzero entries in
P and A, i.e., N = nnz(P ) + nnz(A).
Applications. Optimization problems of the form (1) arise in a huge variety of applica-
tions in engineering, ﬁnance, operations research and many other ﬁelds. Applications in
machine learning include support vector machines (SVM) [CV95], Lasso [Tib96, CWB08]
and Huber ﬁtting [Hub64, Hub81]. Financial applications of (1) include portfolio opti-
mization [CT06, Mar52, BMOW14, BBD +17] [BV04, §4.4.1]. In the ﬁeld of control engi-
neering, model predictive control (MPC) [RM09, GPM89] and moving horizon estimation
(MHE) [ABQ +99] techniques require the solution of a QP at each time instant. Several
signal processing problems also fall into the same class [BV04, §6.3.3][MB10]. In addition,
the numerical solution of QP subproblems is an essential component in nonconvex opti-
mization methods such as sequential quadratic programming (SQP) [NW06, Chap. 18] and
mixed-integer optimization using branch-and-bound algorithms [BKL +13, FL98].
1.2 Solution methods
Convex QPs have been studied since the 1950s [FW56], following from the seminal work on
LPs started by Kantorovich [Kan60]. Several solution methods for both LPs and QPs have
been proposed and improved upon throughout the years.
Active-set methods. Active-set methods were the ﬁrst algorithms popularized as solution
methods for QPs [Wol59], and were obtained from an extension of Dantzig’s simplex method
for solving LPs [Dan63]. Active-set algorithms select an active-set ( i.e., a set of binding
constraints) and then iteratively adapt it by adding and dropping constraints from the index
of active ones [NW06, §16.5]. New active constraints are added based on the cost function
gradient and the current dual variables. Active-set methods for QPs diﬀer from the simplex
method for LPs because the iterates are not necessarily vertices of the feasible region. These
methods can easily be warm started to reduce the number of active-set recalculations re-
quired. However, the major drawback of active-set methods is that the worst-case complexity
2
grows exponentially with the number of constraints, since it may be necessary to investigate
all possible active-sets before reaching the optimal one [KM70]. Modern implementations of
active-set methods for the solution of QPs can be found in many commercial solvers, such as
MOSEK [MOS17] and GUROBI [Gur16], and in the open-source solver qpOASES [FKP+14].
Interior-point methods. Interior-point algorithms gained popularity in the 1980s as a
method for solving LPs in polynomial time [Kar84, GMS +86]. In the 90s these techniques
were extended to general convex optimization problems, including QPs [NN94]. Interior-
point methods model the problem constraints as parametrized penalty functions, also re-
ferred to as barrier functions. At each iteration an unconstrained optimization problem is
solved for varying barrier function parameters until the optimum is achieved; see [BV04,
Chap. 11] and [NW06, §16.6] for details. Primal-dual interior-point methods, in particu-
lar the Mehrotra predictor-corrector [Meh92] method, became the algorithms of choice for
practical implementation [Wri97] because of their good performance across a wide range of
problems. However, interior-point methods are not easily warm started and do not scale well
for very large problems. Interior-point methods are currently the default algorithms in the
commercial solvers MOSEK [MOS17], GUROBI [Gur16] and CVXGEN [MB12] and in the
open-source solver OOQP [GW03].
First-order methods. First-order optimization methods for solving quadratic programs
date to the 1950s [FW56]. These methods iteratively compute an optimal solution using only
ﬁrst-order information about the cost function. Operator splitting techniques such as the
Douglas-Rachford splitting [LM79, DR56] are a particular class of ﬁrst-order methods which
model the optimization problem as the problem of ﬁnding a zero of the sum of monotone
operators.
In recent years, the operator splitting method known as the alternating direction method
of multipliers (ADMM) [GM76, GM75] has received particular attention because of its very
good practical convergence behavior; see [BPC +11] for a survey. ADMM can be seen as a
variant of the classical alternating projections algorithm [BB96] for ﬁnding a point in the
intersection of two convex sets, and can also be shown to be equivalent to the Douglas-
Rachford splitting [Gab83]. ADMM has been shown to reliably provide modest accuracy
solutions to QPs in a relatively small number of computationally inexpensive iterations. It
is therefore well suited to applications such as embedded optimization or large-scale opti-
mization, wherein high accuracy solutions are typically not required due to noise in the data
and arbitrariness of the cost function. ADMM steps are computationally very cheap and sim-
ple to implement, and thus ideal for embedded processors with limited computing resources
such as those found in embedded control systems [JGR +14, OSB13, SSS +16]. ADMM is
also compatible with distributed optimization architectures enabling the solution of very
large-scale problems [BPC +11].
A drawback of ﬁrst-order methods is that they are typically unable to detect primal
and/or dual infeasibility. In order to address this shortcoming, a homogeneous self-dual
embedding has been proposed in conjunction with ADMM for solving conic optimization
3
problems and implemented in the open-source solver SCS [OCPB16]. Although every QP can
be reformulated as a conic program, this reformulation is not eﬃcient from a computational
point of view. A further drawback of ADMM is that number of iterations required to converge
is highly dependent on the problem data and on the user’s choice of the algorithm’s step-
size parameters. Despite some recent theoretical results [GB17, BG18], it remains unclear
how to select those parameters to optimize the algorithm convergence rate. For this reason,
even though there are several beneﬁts in using ADMM techniques for solving optimization
problems, there exists no reliable general-purpose QP solver based on operator splitting
methods.
1.3 Our approach
In this work we present a new general-purpose QP solver based on ADMM that is able
to provide high accuracy solutions. The proposed algorithm is based on a novel splitting
requiring the solution of a quasi-deﬁnite linear system that is always solvable for any choice of
problem data. We therefore impose no constraints such as strict convexity of the cost function
or linear independence of the constraints. Since the linear system’s matrix coeﬃcients remain
the same at every iteration whenρ is ﬁxed, our algorithm requires only a single factorization
to solve the QP (2). Once this initial factorization is computed, we can ﬁx the linear system
matrix coeﬃcients to make the algorithm division-free. If we allow divisions, then we can
make occasional updates to the term ρ in this linear system to improve our algorithm’s
convergence. We ﬁnd that our algorithm typically updates these coeﬃcients very few times,
e.g., 1 or 2 in our experiments. In contrast to other ﬁrst-order methods, our approach is able
to return primal and dual solutions when the problem is solvable or to provide certiﬁcates
of primal and dual infeasibility without resorting to the homogeneous self-dual embedding.
To obtain high accuracy solutions, we perform solution polishing on the iterates obtained
from ADMM. By identifying the active constraints from the ﬁnal dual variable iterates, we
construct an ancillary equality-constrained QP whose solution is equivalent to that of the
original QP (1). This ancillary problem is then solved by computing the solution of a single
linear system of typically much lower dimensions than the one solved during the ADMM
iterations. If we identify the active constraints correctly, then the resulting solution of our
method has accuracy equal to or even better than interior-point methods.
Our algorithm can be eﬃciently warm started to reduce the number of iterations. More-
over, if the problem matrices do not change then the quasi-deﬁnite system factorization can
be reused across multiple solves greatly improving the computation time. This feature is
particularly useful when solving multiple instances of parametric QPs where only a few el-
ements of the problem data change. Examples illustrating the eﬀectiveness of the proposed
algorithm in parametric programs arising in embedded applications appear in [BSM +17].
We implemented our method in the open-source “Operator Splitting Quadratic Program”
(OSQP) solver. OSQP is written in C and can be compiled to be library free. OSQP is
robust against noisy and unreliable problem data, has a very small code footprint, and is
suitable for both embedded and large-scale applications. We have extensively tested our code
and carefully tuned its parameters by solving millions of QPs. We benchmarked our solver
4
against state-of-the-art interior-point and active-set solvers over a benchmark library of 1400
problems from 7 diﬀerent classes and over the hard QPs Maros-M´ esz´ aros test set [MM99].
Numerical results show that our algorithm is able to provide up to an order of magnitude
computational time improvements over existing commercial and open-source solvers in a
wide variety of applications. We also showed further time reductions from warm starting
and factorization caching.
2 Optimality conditions
We will ﬁnd it convenient to rewrite problem (1) by introducing an additional decision
variablez∈ Rm, to obtain the equivalent problem
minimize (1 /2)xTPx +qTx
subject to Ax =z
z∈C .
(3)
We can write the optimality conditions of problem (3) as [BGSB19, Lem. A.1] [RW98, Thm.
6.12]
Ax =z, (4)
Px +q +ATy = 0, (5)
z∈C , y ∈NC(z), (6)
where y∈ Rm is the Lagrange multiplier associated with the constraint Ax =z and NC(z)
denotes the normal cone ofC atz. If there exist x∈ Rn,z∈ Rm andy∈ Rm that satisfy the
conditions above, then we say that (x,z ) is a primal andy is a dual solution to problem (3).
We deﬁne the primal and dual residuals of problem (1) as
rprim =Ax−z, (7)
rdual =Px +q +ATy. (8)
Quadratic programs. In case of QPs of the form (2), condition (6) reduces to
l≤z≤u, y T
+(z−u) = 0, y T
−(z−l) = 0, (9)
where y+ = max(y, 0) and y− = min(y, 0).
2.1 Certiﬁcates of primal and dual infeasibility
From the theorem of strong alternatives [BV04,§5.8], [BGSB19, Prop. 3.1], exactly one of
the following sets is nonempty
P ={x∈ Rn|Ax∈C} , (10)
D =
{
y∈ Rm|ATy = 0, S C(y)< 0
}
, (11)
5
where SC is the support function of C, provided that some type of constraint qualiﬁcation
holds [BV04]. In other words, any variable y∈D serves as a certiﬁcate that problem (1) is
primal infeasible.
Quadratic programs. In case C = [l,u ], certifying primal infeasibility of (2) amounts to
ﬁnding a vector y∈ Rm such that
ATy = 0, u Ty+ +lTy− < 0. (12)
Similarly, it can be shown that a vector x∈ Rn satisfying
Px = 0, q Tx< 0, (Ax)i



= 0 li,ui∈ R
≥ 0 ui = +∞, li∈ R
≤ 0 li =−∞, ui∈ R
(13)
is a certiﬁcate of dual infeasibility for problem (2); see [BGSB19, Prop. 3.1] for more details.
3 Solution with ADMM
Our method solves problem (3) using ADMM [BPC +11]. By introducing auxiliary variables
˜x∈ Rn and ˜z∈ Rm, we can rewrite problem (3) as
minimize (1 /2)˜xTP ˜x +qT ˜x +IAx=z(˜x, ˜z) +IC(z)
subject to (˜x, ˜z) = (x,z ), (14)
whereIAx=z andIC are the indicator functions given by
IAx=z(x,z ) =
{
0 Ax =z
+∞ otherwise, IC(z) =
{
0 z∈C
+∞ otherwise.
An iteration of ADMM for solving problem (14) consists of the following steps:
(˜xk+1, ˜zk+1)← argmin
(˜x,˜z):A˜x=˜z
(1/2)˜xTP ˜x +qT ˜x + (σ/2)∥˜x−xk +σ−1wk∥2
2
+ (ρ/2)∥˜z−zk +ρ−1yk∥2
2
(15)
xk+1←α˜xk+1 + (1−α)xk +σ−1wk (16)
zk+1← Π
(
α˜zk+1 + (1−α)zk +ρ−1yk)
(17)
wk+1←wk +σ
(
α˜xk+1 + (1−α)xk−xk+1)
(18)
yk+1←yk +ρ
(
α˜zk+1 + (1−α)zk−zk+1)
(19)
where σ >0 and ρ >0 are the step-size parameters, α∈ (0, 2) is the relaxation parameter,
and Π denotes the Euclidean projection onto C. The introduction of the splitting variable ˜x
ensures that the subproblem in (15) is always solvable for any P∈ Sn
+ which can also be 0
for LPs. Note that all the derivations hold also for σ and ρ being positive deﬁnite diagonal
matrices. The iterates wk and yk are associated with the dual variables of the equality
constraints ˜x =x and ˜z =z, respectively. Observe from steps (16) and (18) that wk+1 = 0
for all k≥ 0, and consequently the w-iterate and the step (18) can be disregarded.
6
3.1 Solving the linear system
Evaluating the ADMM step (15) involves solving the equality constrained QP
minimize (1 /2)˜xTP ˜x +qT ˜x +(σ/2)∥˜x−xk∥2
2 +(ρ/2)∥˜z−zk +ρ−1yk∥2
2
subject to A˜x = ˜z. (20)
The optimality conditions for this equality constrained QP are
P ˜xk+1 +q +σ(˜xk+1−xk) +ATνk+1 = 0, (21)
ρ(˜zk+1−zk) +yk−νk+1 = 0, (22)
A˜xk+1− ˜zk+1 = 0, (23)
where νk+1∈ Rm is the Lagrange multiplier associated with the constraint Ax = z. By
eliminating the variable ˜zk+1 from (22), the above linear system reduces to
[P +σI A T
A −ρ−1I
][ ˜xk+1
νk+1
]
=
[ σxk−q
zk−ρ−1yk
]
, (24)
with ˜zk+1 recoverable as
˜zk+1 =zk +ρ−1(νk+1−yk).
We will refer to the coeﬃcient matrix in (24) as the KKT matrix. This matrix always has
full rank thanks to the positive parameters σ and ρ introduced in our splitting, so (24)
always has a unique solution for any matrices P∈ Sn
+ and A∈ Rm×n. In other words, we
do not impose any additional assumptions on the problem data such as strong convexity of
the objective function or linear independence of the constraints as was done in [GTSJ15,
RDC14b, RDC14a].
Direct method. A direct method for solving the linear system (24) computes its solution
by ﬁrst factoring the KKT matrix and then performing forward and backward substitution.
Since the KKT matrix remains the same for every iteration of ADMM, we only need to
perform the factorization once prior to the ﬁrst iteration and cache the factors so that we can
reuse them in subsequent iterations. This approach is very eﬃcient when the factorization
cost is considerably higher than the cost of forward and backward substitutions, so that
each iteration is computed quickly. Note that if ρ orσ change, the KKT matrix needs to be
factored again.
Our particular choice of splitting results in a KKT matrix that is quasi-deﬁnite,i.e., it can
be written as a 2-by-2 block-symmetric matrix where the (1, 1)-block is positive deﬁnite, and
the (2, 2)-block is negative deﬁnite. It therefore always has a well deﬁnedLDLT factorization,
withL being a lower triangular matrix with unit diagonal elements andD a diagonal matrix
with nonzero diagonal elements [Van95]. Note that once the factorization is carried out,
computing the solution of (24) can be made division-free by storing D−1 instead of D.
When the KKT matrix is sparse and quasi-deﬁnite, eﬃcient algorithms can be used for
computing a suitable permutation matrix P for which the factorization of PKP T results in
7
a sparse factor L [ADD04, Dav06] without regard for the actual nonzero values appearing in
the KKT matrix. The LDLT factorization consists of two steps. In the ﬁrst step we compute
the sparsity pattern of the factor L. This step is referred to as the symbolic factorization
and requires only the sparsity pattern of the KKT matrix. In the second step, referred to as
the numerical factorization, we determine the values of nonzero elements in L and D. Note
that we do not need to update the symbolic factorization if the nonzero entries of the KKT
matrix change but the sparsity pattern remains the same.
Indirect method. With large-scale QPs, factoring linear system (24) might be prohibitive.
In these cases it might be more convenient to use an indirect method by solving instead the
linear system (
P +σI +ρATA
)
˜xk+1 =σxk−q +AT (ρzk−yk)
obtained by eliminating νk+1 from (24). We then compute ˜ zk+1 as ˜zk+1 = A˜xk+1. Note
that the coeﬃcient matrix in the above linear system is always positive deﬁnite. The linear
system can therefore be solved with an iterative scheme such as the conjugate gradient
method [GVL96, NW06]. When the linear system is solved up to some predeﬁned accuracy,
we terminate the method. We can also warm start the method using the linear system
solution at the previous iteration of ADMM to speed up its convergence. In contrast to
direct methods, the complexity of indirect methods does not change if we update ρ and σ
since there is no factorization required. This allows for more updates to take place without
any overhead.
3.2 Final algorithm
By simplifying the ADMM iterations according to the previous discussion, we obtain Algo-
rithm 1. Steps 4, 5, 6 and 7 of Algorithm 1 are very easy to evaluate since they involve
only vector addition and subtraction, scalar-vector multiplication and projection onto a box.
Moreover, they are component-wise separable and can be easily parallelized. The most com-
putationally expensive part is solving the linear system in Step 3, which can be performed
as discussed in Section 3.1.
Algorithm 1
1: given initial values x0, z0, y0 and parameters ρ> 0, σ >0, α∈ (0, 2)
2: repeat
3: (˜xk+1,νk+1)← solve linear system
[P +σI A T
A −ρ−1I
][ ˜xk+1
νk+1
]
=
[ σxk−q
zk−ρ−1yk
]
4: ˜zk+1←zk +ρ−1(νk+1−yk)
5: xk+1←α˜xk+1 + (1−α)xk
6: zk+1← Π
(
α˜zk+1 + (1−α)zk +ρ−1yk)
7: yk+1←yk +ρ
(
α˜zk+1 + (1−α)zk−zk+1)
8: until termination criterion is satisﬁed
8
3.3 Convergence and infeasibility detection
We show in this section that the proposed algorithm generates a sequence of iterates
(xk,zk,yk) that in the limit satisfy the optimality conditions (4)–(6) when problem (1) is
solvable, or provides a certiﬁcate of primal or dual infeasibility otherwise.
If we denote the argument of the projection operator in step 6 of Algorithm 1 by vk+1,
then we can express zk and yk as
zk = Π(vk) and yk =ρ
(
vk− Π(vk)
)
. (25)
Observe from (25) that iterates zk and yk satisfy optimality condition (6) for all k > 0
by construction [BC11, Prop. 6.46]. Therefore, it only remains to show that optimality
conditions (4)–(5) are satisﬁed in the limit.
As shown in [BGSB19, Prop. 5.3], if problem (2) is solvable, then Algorithm 1 produces
a convergent sequence of iterates (xk,zk,yk) so that
lim
k→∞
rk
prim = 0,
lim
k→∞
rk
dual = 0,
where rk
prim and rk
dual correspond to the residuals deﬁned in (7) and (8) respectively.
On the other hand, if problem (2) is primal and/or dual infeasible, then the sequence of
iterates (xk,zk,yk) generated by Algorithm 1 does not converge. However, the sequence
(δxk,δz k,δy k) = (xk−xk−1,zk−zk−1,yk−yk−1)
always converges and can be used to certify infeasibility of the problem. According to
[BGSB19, Thm. 5.1], if the problem is primal infeasible, then δy = limk→∞δyk satisﬁes
conditions (12), whereas δx = limk→∞δxk satisﬁes conditions (13) if it is dual infeasible.
3.4 Termination criteria
We can deﬁne termination criteria for Algorithm 1 so that the iterations stop when either
a primal-dual solution or a certiﬁcate of primal or dual infeasibility is found up to some
predeﬁned accuracy.
A reasonable termination criterion for detecting optimality is that the norms of the
residuals rk
prim and rk
dual are smaller than some tolerance levels εprim > 0 and εdual > 0
[BPC+11], i.e.,
∥rk
prim∥∞≤εprim, ∥rk
dual∥∞≤εdual. (26)
We set the tolerance levels as
εprim =εabs +εrel max{∥Axk∥∞,∥zk∥∞}
εdual =εabs +εrel max{∥Pxk∥∞,∥ATyk∥∞,∥q∥∞},
where εabs > 0 and εrel > 0 are absolute and relative tolerances, respectively.
9
Quadratic programs infeasibility. IfC = [l,u ], we check the following conditions for primal
infeasibility
ATδyk
∞≤εpinf∥δyk∥∞, u T (δyk)+ +lT (δyk)−≤εpinf∥δyk∥∞,
where εpinf > 0 is some tolerance level. Similarly, we deﬁne the following criterion for
detecting dual infeasibility
∥Pδxk∥∞≤εdinf∥δxk∥∞, q Tδxk≤εdinf∥δxk∥∞,
(Aδxk)i



∈ [−εdinf,ε dinf]∥δxk∥∞ ui,li∈ R
≥−εdinf∥δxk∥∞ ui = +∞
≤εdinf∥δxk∥∞ li =−∞,
for i = 1,...,m where εdinf > 0 is some tolerance level. Note that ∥δxk∥∞ and∥δyk∥∞
appear in the right-hand sides to avoid division when considering normalized vectors δxk
and δyk in the termination criteria.
4 Solution polishing
Operator splitting methods are typically used for obtaining solution of an optimization prob-
lem with a low or medium accuracy. However, even if a solution is not very accurate we can
often guess which constraints are active from an approximate primal-dual solution. When
dealing with QPs of the form (2), we can obtain high accuracy solutions from the ﬁnal
ADMM iterates by solving one additional system of equations.
Given a dual solution y of the problem, we deﬁne the sets of lower- and upper-active
constraints
L ={i∈{ 1,...,m }| yi < 0},
U ={i∈{ 1,...,m }| yi > 0}.
According to (9) we have that zL =lL and zU =uU, where lL denotes the vector composed
of elements ofl corresponding to the indices inL. Similarly, we will denote byAL the matrix
composed of rows of A corresponding to the indices in L.
If the sets of active constraints are known a priori, then a primal-dual solution ( x,y,z )
can be found by solving the following linear system


P A T
L AT
U
AL
AU




x
yL
yU

 =


−q
lL
uU

, (27)
yi = 0, i /∈ (L∪U ), (28)
z =Ax. (29)
10
We can then apply the aforementioned procedure to obtain a candidate solution (x,y,z ).
If (x,y,z ) satisﬁes the optimality conditions (4)–(6), then our guess is correct and ( x,y,z )
is a primal-dual solution of problem (3). This approach is referred to as solution polishing.
Note that the dimension of the linear system (27) is usually much smaller than the KKT
system in Section 3.1 because the number of active constraints at optimality is less than or
equal to n for non-degenerate QPs.
However, the linear system (27) is not necessarily solvable even if the sets of active
constraintsL andU have been correctly identiﬁed. This can happen, e.g., if the solution is
degenerate, i.e., if it has one or more redundant active constraints. We make the solution
polishing procedure more robust by solving instead the following linear system


P +δI A T
L AT
U
AL −δI
AU −δI




ˆx
ˆyL
ˆyU

 =


−q
lL
uU

, (30)
whereδ >0 is a regularization parameter with value δ≈ 10−6. Since the regularized matrix
in (30) is quasi-deﬁnite, the linear system (30) is always solvable.
By using regularization, we actually solve a perturbed linear system and thus introduce
a small error to the polished solution. If we denote by K and (K + ∆K) the coeﬃcient
matrices in (27) and (30), respectively, then we can represent the two linear systems as
Kt =g and (K + ∆K)ˆt =g. To compensate for this error, we apply an iterative reﬁnement
procedure [Wil63], i.e., we iteratively solve
(K + ∆K)∆ˆtk =g−Kˆtk (31)
and update ˆtk+1 = ˆtk + ∆ˆtk. The sequence {ˆtk} converges to the true solution t, provided
that it exists. Observe that, compared to solving the linear system (30), iterative reﬁne-
ment requires only a backward- and a forward-solve, and does not require another matrix
factorization. Since the iterative reﬁnement iterations converge very quickly in practice, we
just run them for a ﬁxed number of passes without imposing any termination condition to
satisfy. Note that this is the same strategy used in commercial linear system solvers using
iterative reﬁnement [Int17].
5 Preconditioning and parameter selection
A known weakness of ﬁrst-order methods is their inability to deal eﬀectively with ill-
conditioned problems, and their convergence rate can vary signiﬁcantly when data are badly
scaled. In this section we describe how to precondition the data and choose the optimal
parameters to speed up the convergence of our algorithm.
5.1 Preconditioning
Preconditioning is a common heuristic aiming to reduce the number of iterations in ﬁrst-
order methods [NW06, Chap. 5],[GTSJ15, Ben02, PC11, GB15, GB17]. The optimal choice
11
of preconditioners has been studied for at least two decades and remains an active area of
research [Kel95, Chap. 2],[Gre97, Chap. 10]. For example, the optimal diagonal precon-
ditioner required to minimize the condition number of a matrix can be found exactly by
solving a semideﬁnite program [BEGFB94]. However, this computation is typically more
complicated than solving the original QP, and is therefore unlikely to be worth the eﬀort
since preconditioning is only a heuristic to minimize the number of iterations.
In order to keep the preconditioning procedure simple, we instead make use of a simple
heuristic called matrix equilibration [Bra10, TJ14, FB18, DB17]. Our goal is to rescale
the problem data to reduce the condition number of the symmetric matrix M ∈ Sn+m
representing the problem data, deﬁned as
M =
[P A T
A 0
]
. (32)
In particular, we use symmetric matrix equilibration by computing the diagonal matrix S∈
Sn+m
++ to decrease the condition number of SMS . We can write matrix S as
S =
[D
E
]
, (33)
where D∈ Sn
++ and E∈ Sm
++ are both diagonal. In addition, we would like to normalize
the cost function to prevent the dual variables from being too large. We can achieve this by
multiplying the cost function by the scalar c> 0.
Preconditioning eﬀectively modiﬁes problem (1) into the following
minimize (1 /2)¯xT ¯P ¯x + ¯qT ¯x
subject to ¯A¯x∈ ¯C, (34)
where ¯x = D−1x, ¯P = cDPD , ¯q = cDq, ¯A = EAD and ¯C ={Ez ∈ Rm| z∈C} . The
dual variables of the new problem are ¯y =cE−1y. Note that when C = [l,u ] the Euclidean
projection onto ¯C = [El,Eu ] is as easy to evaluate as the projection onto C.
The main idea of the equilibration procedure is to scale the rows of matrix M so that
they all have equal ℓp norm. It is possible to show that ﬁnding such a scaling matrix S can
be cast as a convex optimization problem [BHT04]. However, it is computationally more
convenient to solve this problem with heuristic iterative methods, rather than continuous
optimization algorithms such as interior-point methods. We refer the reader to [Bra10] for
more details on matrix equilibration.
Ruiz equilibration. In this work we apply a variation of the Ruiz equilibration [Rui01].
This technique was originally proposed to equilibrate square matrices showing fast linear
convergence superior to other methods such as the Sinkhorn-Knopp equilibration [SK67].
Ruiz equilibration converges in few tens of iterations even in cases when Sinkhorn-Knopp
equilibration takes thousands of iterations [KRU14]. The steps are outlined in Algorithm 2
and diﬀer from the original Ruiz algorithm by adding a cost scaling step that takes into
12
Algorithm 2 Modiﬁed Ruiz equilibration
initialize c = 1, S =I, δ = 0, ¯P =P, ¯q =q, ¯A =A, ¯C =C
while∥1−δ∥∞ >ε equil do
for i = 1,...,n +m do
δi← 1/
√
∥Mi∥∞ ⊿ Mequilibration
¯P, ¯q, ¯A, ¯C← Scale ¯P, ¯q, ¯A, ¯C using diag(δ)
γ← 1/ max{mean(∥ ¯Pi∥∞),∥¯q∥∞} ⊿ Cost scaling
¯P←γ ¯P, ¯q←γ¯q
S← diag(δ)S,c←γc
return S,c
account very large values of the cost. The ﬁrst part is the usual Ruiz equilibration step.
SinceM is symmetric, we focus only on the columns Mi and apply the scaling to both sides
ofM. At each iteration, we compute the∞-norm of each column and normalize that column
by the inverse of its square root. The second part is a cost scaling step. The scalar γ is the
current cost normalization coeﬃcient taking into account the maximum between the average
norm of the columns of ¯P and the norm of ¯q. We normalize problem data ¯P , ¯q, ¯A, ¯l, ¯u in
place at each iteration using the current values of δ and γ.
Unscaled termination criteria. Although we rescale our problem in the form (34), we
would still like to apply the stopping criteria deﬁned in Section 3.4 to an unscaled version of
our problem. The primal and dual residuals in (26) can be rewritten in terms of the scaled
problem as
rk
prim =E−1¯rk
prim =E−1( ¯A¯xk− ¯zk), r k
dual =c−1D−1¯rk
dual =c−1D−1( ¯P ¯xk + ¯q + ¯AT ¯yk),
and the tolerances levels as
εprim =εabs +εrel max{∥E−1 ¯A¯xk∥∞,∥E−1¯zk∥∞}
εdual =εabs +εrelc−1 max{∥D−1 ¯P ¯xk∥∞,∥D−1 ¯AT ¯yk∥∞,∥D−1¯q∥∞}.
Quadratic programs infeasibility. WhenC = [l,u ], the primal infeasibility conditions be-
come D−1 ¯ATδ¯yk
∞≤εpinf∥Eδ ¯yk∥∞, ¯uT (δ¯yk)+ + ¯lT (δ¯yk)−≤εpinf∥Eδ ¯yk∥∞,
where the primal infeasibility certiﬁcate is c−1Eδ ¯yk. The dual infeasibility criteria are
∥D−1 ¯Pδ ¯xk∥∞≤cεdinf∥Dδ¯xk∥∞, ¯qTδ¯xk≤cεdinf∥Dδ¯xk∥∞,
(E−1 ¯Aδ¯xk)i



∈ [−εdinf,ε dinf]∥Dδ¯xk∥∞ ui,li∈ R
≥−εdinf∥Dδ¯xk∥∞ ui = +∞
≤εdinf∥Dδ¯xk∥∞ li =−∞,
where the dual infeasibility certiﬁcate is Dδ¯xk.
13
5.2 Parameter selection
The choice of parameters (ρ,σ,α ) in Algorithm 1 is a key factor in determining the number
of iterations required to ﬁnd an optimal solution. Unfortunately, it is still an open research
question how to select the optimal ADMM parameters, see [GTSJ15, NLR+15, GB17]. After
extensive numerical testing on millions of problem instances and a wide range of dimensions,
we chose the algorithm parameters as follows for QPs.
Choosing σ and α. The parameterσ is a regularization term which is used to ensure that
a unique solution of (15) will always exist, even when P has one or more zero eigenvalues.
After scaling P in order to minimize its condition number, we choose σ as small as possible
to preserve numerical stability without slowing down the algorithm. We set the default value
as σ = 10−6. The relaxation parameter α in the range [1 .5, 1.8] has empirically shown to
improve the convergence rate [Eck94, EF98]. In the proposed method, we set the default
value of α = 1.6.
Choosing ρ. The most crucial parameter is the step-size ρ. Numerical testing showed that
having diﬀerent values of ρ for diﬀerent constraints, can greatly improve the performance.
For this reason, without altering the algorithm steps, we chose ρ∈ Sm
++ being a positive
deﬁnite diagonal matrix with diﬀerent elements ρi.
For a speciﬁc QP, if we know the active and inactive constraints, then we can rewrite it
simply as an equality constrained QP. In this case the optimal ρ is deﬁned as ρi =∞ for
the active constraints and ρi = 0 for the inactive constraints, therefore reducing the linear
system (24) to the optimality conditions of the equivalent equality constrained QP (after
settingσ = 0). Unfortunately, it is impossible to know a priori whether any given constraint
is active or inactive at optimality, so we must instead adopt some heuristics. We deﬁne ρ as
follows
ρ = diag(ρ1,...,ρ m), ρ i =
{
¯ρ l i̸=ui
103¯ρ l i =ui,
where ¯ρ > 0. In this way we assign a high value to the step-size related to the equality
constraints since they will be active at the optimum. Having a ﬁxed value of ¯ ρ cannot
provide fast convergence for diﬀerent kind of problems since the optimal solution and the
active constraints vary greatly. To compensate for this issue, we adopt an adaptive scheme
which updates ¯ρ during the iterations based on the ratio between primal and dual residuals.
The idea of introducing “feedback” in the algorithm steps makes ADMM more robust to bad
scaling in the data; see [HYW00, BPC +11, Woh17]. Contrary to the adaptation approaches
in the literature where the update increases or decreases the value of the step-size by a ﬁxed
amount, we adopt the following rule
¯ρk+1← ¯ρk
√
∥¯rk
prim∥∞/ max{∥ ¯A¯xk∥∞,∥¯zk∥∞}
∥¯rk
dual∥∞/ max{∥ ¯P ¯xk∥∞,∥ ¯AT ¯yk∥∞,∥¯q∥∞}.
14
In other words we update ¯ρk using the square root of the ratio between the scaled residuals
normalized by the magnitudes of the relative part of the tolerances. We set the initial value as
¯ρ0 = 0.1. In our benchmarks, if ¯ρ0 does not already give a low number of ADMM iterations,
it gets usually tuned with a maximum of 1 or 2 updates. The adaptation causes the KKT
matrix in (24) to change and, if the linear system solver solution method is direct, it requires
a new numerical factorization. We do not require a new symbolic factorization because
the sparsity pattern of the KKT matrix does not change. Since the numerical factorization
can be costly, we perform the adaptation only when it is really necessary. In particular, we
allow an update if the accumulated iterations time is greater than a certain percentage of the
factorization time (nominally 40%) and if the new parameter is suﬃciently diﬀerent than the
current one, i.e., 5 times larger or smaller. Note that in the case of an indirect method this
rule allows for more frequent changes of ρ since there is no need to factor the KKT matrix
and the update is numerically much cheaper. Note that the convergence of the ADMM
algorithm is hard to prove in general if the ρ updates happen at each iteration. However, if
we assume that the updates stop after a ﬁxed number of iterations the convergence results
hold [BPC+11, Section 3.4.1].
6 Parametric programs
In application domains such as control, statistics, ﬁnance, and SQP, problem (1) is solved
repeatedly for varying data. For these problems, usually referred to as parametric programs,
we can speed up the repeated OSQP calls by re-using the computations across multiple
solves.
We make the distinction between cases in which only the vectors or all data in (1) change
between subsequent problem instances. We assume that the problem dimensions n and m
and the sparsity patterns of P and A are ﬁxed.
Vectors as parameters. If the vectors q, l, and u are the only parameters that vary, then
the KKT coeﬃcient matrix in Algorithm 1 does not change across diﬀerent instances of
the parametric program. Thus, if a direct method is used, we perform and store its fac-
torization only once before the ﬁrst solution and reuse it across all subsequent iterations.
Since the matrix factorization is the computationally most expensive step of the algorithm,
this approach reduces signiﬁcantly the amount of time OSQP takes to solve subsequent
problems. This class of problems arises very frequently in many applications including
linear MPC and MHE [RM09, ABQ +99], Lasso [Tib96, CWB08], and portfolio optimiza-
tion [BMOW14, Mar52].
Matrices and vectors as parameters. We separately consider the case in which the values
(but not the locations) of the nonzero entries of matrices P and A are updated. In this
case, in a direct method, we need to refactor the matrix in Algorithm 1. However, since
the sparsity pattern does not change we need only to recompute the numerical factorization
while reusing the symbolic factorization from the previous solution. This results in a modest
15
reduction in the computation time. This class of problems encompasses several applications
such as nonlinear MPC and MHE [DFH09] and sequential quadratic programming [NW06].
Warm starting. In contrast to interior-point methods, OSQP is easily initialized by pro-
viding an initial guess of both the primal and dual solutions to the QP. This approach
is known as warm starting and is particularly eﬀective when the subsequent QP solutions
do not vary signiﬁcantly, which is the case for most parametric programs applications. We
can warm start the ADMM iterates from the previous OSQP solution ( x⋆,y⋆) by setting
(x0,z 0,y 0)← (x⋆,Ax⋆,y⋆). Note that we can warm-start the ρ estimation described in Sec-
tion 7 to exploit the ratio between the primal and dual residuals to speed up convergence in
subsequent solves.
7 OSQP
We have implemented our proposed approach in the “Operator Splitting Quadratic Program”
(OSQP) solver, an open-source software package in the C language. OSQP can solve any
QP of the form (2) and makes no assumptions about the problem data other than convexity.
OSQP is available online at
https://osqp.org.
Users can call OSQP from C, C ++, Fortran, Python, Matlab, R, Julia, Ruby and Rust, and
via parsers such as CVXPY [DB16, AVDB18], JuMP [DHL17], and YALMIP [L ¨04].
To exploit the data sparsity pattern, OSQP accepts matrices in Compressed-Sparse-
Column (CSC) format [Dav06]. We implemented the linear system solution described in
Section 3.1 as an object-oriented interface to easily switch between eﬃcient algorithms. At
present, OSQP ships with the open-source QDLDL direct solver which is our independent
implementation based on [Dav05], and also supports dynamic loading of more advanced
algorithms such as the MKL Pardiso direct solver [Int17]. We plan to add iterative indirect
solvers and other direct solvers in future versions.
The default values for the OSQP termination tolerances described in Section 3.4 are
εabs =εrel = 10−3, ε pinf =εdinf = 10−4.
The default step-size parameter σ and the relaxation parameter α are set to
σ = 10−6, α = 1.6,
while ρ is automatically chosen by default as described in Section 5.2, with optional user
override. We set the default ﬁxed number of iterative reﬁnement steps to 3.
OSQP reports the total computation time divided by the time required to perform pre-
processing operations such as scaling or matrix factorization and the time to carry out the
ADMM iterations. If the solver is called multiple times reusing the same matrix factoriza-
tion, it will report only the ADMM solve time as total computation time. For more details
we refer the reader to the solver documentation on the OSQP project website.
16
8 Numerical examples
We benchmarked OSQP against the open-source interior-point solver ECOS [DCB13], the
open-source active-set solver qpOASES [FKP+14], and the commercial interior-point solvers
GUROBI [Gur16] and MOSEK [MOS17]. We executed every benchmark comparing diﬀerent
solvers with both low accuracy, i.e., εabs =εrel = 10−3, and high accuracy, i.e., εabs =εrel =
10−5. We set GUROBI, ECOS, MOSEK and OSQP primal and dual feasibility tolerances
to our low and high accuracy tolerances. Since qpOASES is an active-set method and does
not allow the user to tune primal nor dual feasibility tolerances, we set it to its default
termination settings. In addition, the maximum time we allow each solver to run is 1000 sec
and no limit on the maximum number of iterations. Note that the use of maximum time
limits with no bounds on the number of iterations is the default setting in commercial solvers
such as MOSEK. For every solver we leave all the other settings to the internal defaults.
In general it is hard to compare the solution accuracies because all the solvers, especially
commercial ones, use an internal problem scaling and verify that the termination conditions
are satisﬁed against their scaled version of the problem. In contrast, OSQP allows the option
to check the termination conditions against the internally scaled or the original problem.
Therefore, to make the benchmark fair, we say that the primal-dual solution (x⋆,y⋆) returned
by each solver is optimal if the following optimality conditions are satisﬁed with tolerances
deﬁned above with low and high accuracy modes,
∥(Ax⋆−u)+ + (Ax⋆−l)−∥∞≤εprim, ∥Px⋆ +q +ATy⋆∥∞≤εdual,
where εprim and εdual are deﬁned in Section 3.4. If the primal-dual solution returned by a
solver does not satisfy the optimality conditions deﬁned above, we consider it a failure. Note
that we decided not to include checks on the complementary slackness satisfaction because
interior-point solvers satisﬁed them with diﬀerent metrics and scalings, therefore failing very
often. In contrast OSQP always satisﬁes complementary slackness conditions with machine
precision by construction.
In addition, we used the direct single-threaded linear system solver QDLDL [GSB18]
based on [ADD04, Dav05] and very simple linear algebra where other solvers such as
GUROBI and MOSEK use advanced multi-threaded linear system solvers and custom linear
algebra.
All the experiments were carried out on the MIT SuperCloud facility in collaboration
with the Lincoln Laboratory [RKB +18] with 16 Intel Xeon E5-2650 cores. The code for all
the numerical examples is available online at [SB19].
Shifted geometric mean. As in most common benchmarks [Mit], we make use of the
normalized shifted geometric mean to compare the timings of the various solvers. Given the
time required by solver s to solve problem p tp,s, we deﬁne the shifted geometric mean as
gs = n
√∏
p
(tp,s +k)−k,
17
where n is the number of problem instances considered and k = 1 is the shift [Mit]. The
normalized shifted geometric mean is therefore
rs =gs/ min
s
gs.
This value shows the factor at which a speciﬁc solver is slower than the fastest one with
scaled value of 1.00. If solver s fails at solving problem p, we set the time as the maximum
allowed, i.e., tp,s = 1000 sec. Note that to avoid memory overﬂows in the product, we
compute in practice the shifted geometric mean as elngs.
Performance proﬁles. We also make use of the performance proﬁles [DM02] to compare
the solver timings. We deﬁne the performance ratio
up,s =tp,s/ min
s
tp,s.
The performance proﬁle plots the function fs : R↦→ [0, 1] deﬁned as
fs(τ) = 1
n
∑
p
I≤τ(up,s),
whereI≤τ(up,s) = 1 ifup,s≤τ or 0 otherwise. The value fs(τ) corresponds to the fraction of
problems solved within τ times from the best solver. Note that while we cannot necessarily
assess the performance of one solver relative to another with performance proﬁles, they still
represent a viable choice to benchmark the performance of a solver with respect to the best
one [GS16].
8.1 Benchmark problems
We considered QPs in the form (2) from 7 problem classes ranging from standard random
programs to applications in the areas of control, portfolio optimization and machine learning.
For each problem class, we generated 10 diﬀerent instances for 20 dimensions giving a total of
1400 problem instances. All instances were obtained from either real data or from non-trivial
random data. Note that the random QPs and random equality constrained QPs problem
classes might not closely correspond to a real-world application. However, they have a typical
number of nonzero elements appearing in practice. We described generation for each class in
Appendix A. Throughout all the problem classes, n ranges between 101 and 104,m between
102 and 105, and the number of nonzeros N between 102 and 108.
Results. We show in Figures 1 and 2 the OSQP and GUROBI computation times across all
the problem classes for low and high accuracy solutions respectively. OSQP is competitive
or even faster than GUROBI for several problem classes. Results are shown in Table 1
and Figure 3. OSQP shows the best performance across these benchmarks with MOSEK
performing better at lower accuracy and GUROBI at higher accuracy. ECOS is generally
18
Table 1: Benchmark problems comparison with timings as shifted geometric mean and
failure rates.
OSQP GUROBI MOSEK ECOS qpOASES
Shifted geometric
means
Low accuracy 1 .000 4 .285 2 .522 28 .847 149 .932
High accuracy 1 .000 1 .886 6 .234 52 .718 66 .254
Failure rates [%] Low accuracy 0 .000 1 .429 0 .071 20 .714 31 .857
High accuracy 0 .000 1 .429 11 .000 45 .571 31 .714
Table 2: Benchmark problems OSQP statistics.
Median Max
Setup/solve time [%] Low accuracy 60 .23 1550 .19
High accuracy 29 .65 1373 .18
Polish time increase [%] Low accuracy 19 .20 876 .80
High accuracy 10 .63 1408 .83
Number of ρ updates Low accuracy 1 3
High accuracy 1 5
Mean
Polish success [%] Low accuracy 42 .79
High accuracy 83 .21
slower than the other interior-point solvers but faster than qpOASES that shows issues with
many constraints. Table 2 contains the OSQP statistics for this benchmark class. Because
of the good convergence behavior of OSQP on these problems, the setup time is signiﬁcant
compared to the solve time, especially at low accuracy. Solution polishing increases the
solution time by a median of 10 to 20 percent due to the additional factorization used. The
worst-case time increase is very high and happens for the problems that converge in very few
iterations. Note that with high accuracy, polishing succeeds in 83% of test cases while on
low accuracy it succeeds in only 42% of cases. The number of ρ updates is in general very
low, usually requiring just more matrix factorization to adjust, with up to 5 refactorisations
used in the worst case when solving with high accuracy.
8.2 SuiteSparse matrix collection least squares problems
We considered 30 least squares problem in the form Ax≈ b from the SuiteSparse Matrix
Collection library [DH11]. Using the Lasso and Huber problem setups from Appendix A we
formulate 60 QPs that we solve with OSQP, GUROBI and MOSEK. We excluded ECOS
because its interior-point algorithm showed numerical issues for several problems of the test
set. We also excluded qpOASES because it is not designed for large linear systems.
19
Table 3: SuiteSparse matrix problems comparison with timings as shifted geometric mean
and failure rates.
OSQP GUROBI MOSEK
Shifted geometric
means
Low accuracy 1 .000 1 .630 1 .745
High accuracy 1 .000 1 .489 4 .498
Failure rates [%] Low accuracy 0 .000 14 .286 12 .500
High accuracy 1 .786 16 .071 33 .929
Table 4: SuiteSparse problems OSQP statistics.
Median Max
Setup/solve time [%] Low accuracy 71 .37 2910 .37
High accuracy 48 .03 1451 .56
Polish time increase [%] Low accuracy 32 .27 178 .23
High accuracy 22 .68 115 .77
Number of ρ updates Low accuracy 0 2
High accuracy 1 3
Mean
Polish success [%] Low accuracy 67 .86
High accuracy 78 .18
Results. Results are shown in Table 3 and Figure 4. OSQP shows the best performance
with GUROBI slightly slower and MOSEK third. The failure rates for GUROBI and MOSEK
are higher because the reported solution does not satisfy the optimality conditions of the
original problem. We display the OSQP statistics in Table 4. The setup phase takes a
signiﬁcant amount of time compared to the solve phase, especially when OSQP converges
in a few iterations. This happens because the large problem dimensions result in a large
initial factorization time. Polish time is in general 22 to 32% of the total solution time.
However, the success is usually reliable, succeeding 78% of the times with very high quality
solutions. The number of matrix refactorizations required due to ρ updates is very low in
these examples, with a maximum of 2 or 3 even for high accuracy.
8.3 Maros-M´ esz´ aros problems
We considered the Maros-M´ esz´ aros test set [MM99] of hard QPs. We compared the OSQP
solver against GUROBI and MOSEK against all the problems in the set. We decided to
exclude ECOS because its interior-point algorithm showed numerical issues for several prob-
lems of the test set. We also excluded qpOASES because it could not solve most of the
problems since it is not suited for large QPs – it is based on an active-set method with dense
20
Table 5: Maros-M´ esz´ aros problems comparison with timings as shifted geometric mean
and failure rates.
OSQP GUROBI MOSEK
Shifted geometric
means
Low accuracy 1 .464 1 .000 6 .121
High accuracy 5 .247 1 .000 14 .897
Failure rates [%] Low accuracy 1 .449 2 .174 14 .493
High accuracy 10 .145 2 .899 30 .435
Table 6: Maros-M´ esz´ aros problems OSQP statistics.
Median Max
Setup/solve time [%] Low accuracy 31 .59 643 .29
High accuracy 2 .89 326 .11
Polish time increase [%] Low accuracy 9 .49 127 .55
High accuracy 1 .55 76 .36
Number of ρ updates Low accuracy 1 70
High accuracy 2 2498
Mean
Polish success [%] Low accuracy 30 .15
High accuracy 37 .90
linear algebra.
Results. Results are shown in Table 5 and Figure 5. GUROBI shows the best performance
and OSQP, while slower, is still competitive on both low and high accuracy tests. MOSEK
remains the slowest in every case. Table 6 shows the statistics relative to OSQP. Since these
hard problems require a larger number of iterations to converge, the setup time overhead
compared to the solution time is in general lower than the other benchmark sets. Moreover,
since the problems are badly scaled and degenerate, the polishing strategy rarely succeeds.
However, the median time increase from the polish step is less than 10% of the total com-
putation time for both low and high accuracy modes. Note that the number of ρ updates
is usually very low with a median of 1 or 2. However, there are some worst-case problems
when it is very high because the bad scaling causes issues in our ρ estimation. However,
from our data we have seen that in more than 95% of the cases the number of ρ updates is
less than 5.
21
8.4 Warm start and factorization caching
To show the beneﬁts of warm starting and factorization caching, we solved a sequence of
QPs using OSQP with the data varying according to some parameters. Since we are not
comparing OSQP with other high accuracy solvers in these benchmarks, we use its default
settings with accuracy 10−3.
Lasso regularization path. We solved a Lasso problem described in Appendix A.5 with
varying λ in order to choose a regressor with good validation set performance. We solved
one problem instance with n = 50, 100, 150, 200 features, m = 100n data points, and λ
logarithmically spaced taking 100 values between λmax =∥ATb∥∞ and 0.01λmax.
Since the parameters only enter linearly in the cost, we can reuse the matrix factorization
and enable warm starting to reduce the computation time as discussed in Section 6.
Model predictive control. In MPC, we solve the optimal control problem described in
Appendix A.3 at each time step to compute an optimal input sequence over the horizon.
Then, we apply only the ﬁrst input to the system and propagate the state to the next time
step. The whole procedure is repeated with an updated initial state xinit. We solved the
control problem with nx = 20, 40, 60, 80 states, nu = nx/2 inputs, horizon T = 10 and 100
simulation steps. The initial state of the simulation is uniformly distributed and constrained
to be within the feasible region, i.e., xinit∼U (−0.5x, 0.5x).
Since the parameters only enter linearly in the constraints bounds, we can reuse the
matrix factorization and enable warm starting to reduce the computation time as discussed
in Section 6.
Portfolio back test. Consider the portfolio optimization problem in Appendix A.4 with
n = 10k assets and k = 100, 200, 300, 400 factors.
We run a 4 years back test to compute the optimal assets investment depending on
varying expected returns and factor models [BBD +17]. We solved 240 QPs per year giving
a total of 960 QPs. Each month we solved 20 QPs corresponding to the trading days.
Every day, we updated the expected returns µ by randomly generating another vector with
µi∼ 0.9ˆµi +N (0, 0.1), where ˆµi comes from the previous expected returns. The risk model
was updated every month by updating the nonzero elements of D andF according to Dii∼
0.9 ˆDii +U[0, 0.1
√
k] and Fij∼ 0.9 ˆFij +N (0, 0.1) where ˆDii and ˆFij come from the previous
risk model.
As discussed in Section 6, we exploited the following computations during the QP updates
to reduce the computation times. Since µ only enters in the linear part of the objective, we
can reuse the matrix factorization and enable warm starting. Since the sparsity patterns of
D andF do not change during the monthly updates, we can reuse the symbolic factorization
and exploit warm starting to speed up the computations.
Results. We show the results in Table 7. For the Lasso problem we see more than 10-
fold improvement in time and between 8 and 11 times reduction in number of iterations
22
Table 7: OSQP parametric problem results with warm start (ws) and without warm start
(no ws) in terms of time in seconds and number of iterations for diﬀerent leading problem
dimensions of Lasso, MPC and Portfolio classes.
Problem dim. Timeno ws Timews
Time
improv. Iterno ws Iterws
Iter
improv.
Lasso
50 0 .225 0 .012 19 .353 210 .250 25 .750 8 .165
100 0 .423 0 .040 10 .556 224 .000 25 .750 8 .699
150 1 .022 0 .086 11 .886 235 .500 25 .750 9 .146
200 2 .089 0 .149 13 .986 281 .750 26 .000 10.837
MPC
20 0 .007 0 .002 4 .021 89 .500 32 .750 2 .733
40 0 .014 0 .005 2 .691 29 .000 27 .250 1 .064
60 0 .035 0 .013 2 .673 33 .750 33 .000 1 .023
80 0 .067 0 .022 3 .079 32 .000 31 .750 1 .008
Portfolio
100 0 .177 0 .030 5 .817 93 .333 25 .417 3 .672
200 0 .416 0 .061 6 .871 86 .875 25 .391 3 .422
300 0 .646 0 .097 6 .635 80 .521 25 .521 3 .155
400 0 .976 0 .139 7 .003 76 .458 26 .094 2 .930
depending on the dimension. For the MPC problem the number of iterations does not
signiﬁcantly decrease because the number of iterations is already low in cold-start. However
we get from 2.6 to 4-fold time improvement from factorization caching. OSQP shows from
5.8 to 7 times reduction in time for the portfolio problem and from 2.9 to 3.6 times reduction
in number of iterations.
9 Conclusions
We presented a novel general-purpose QP solver based on ADMM. Our method uses a
new splitting requiring the solution of a quasi-deﬁnite linear system that is always solvable
independently from the problem data. We impose no assumptions on the problem data other
than convexity, resulting in a general-purpose and very robust algorithm.
For the ﬁrst time, we propose a ﬁrst-order QP solution method able to provide primal and
dual infeasibility certiﬁcates if the problem is unsolvable without resorting to homogeneous
self-dual embedding or additional complexity in the iterations.
In contrast to other ﬁrst-order methods, our solver can provide high-quality solutions by
performing solution polishing. After guessing which constraints are active, we compute the
solutions of an additional small equality constrained QP by solving a linear system. If the
constraints are identiﬁed correctly, the returned solution has accuracy equal or higher than
interior-point methods.
The proposed method is easily warm started to reduce the number of iterations. If the
problem matrices do not change, the linear system matrix factorization can be cached and
23
reused across multiple solves greatly improving the computation time. This technique can be
extremely eﬀective, especially when solving parametric QPs where only part of the problem
data change.
We have implemented our algorithm in the open-source OSQP solver written in C and
interfaced with multiple other languages and parsers. OSQP is based on sparse linear algebra
and is able to exploit the structure of QPs arising in diﬀerent application areas. OSQP is
robust against noisy and unreliable data and, after the ﬁrst factorization is computed, can be
compiled to be library-free and division-free, making it suitable for embedded applications.
Thanks to its simple and parallelizable iterations, OSQP can handle large-scale problems
with millions of nonzeros.
We extensively benchmarked the OSQP solver with problems arising in several appli-
cation domains including ﬁnance, control and machine learning. In addition, we bench-
marked it against the hard problems from the Maros-M´ esz´ aros test set [MM99] and Lasso
and Huber ﬁtting problems generated with sparse matrices from the SuiteSparse Matrix
Collection [DH11]. Timing and failure rate results showed great improvements over state-
of-the-art academic and commercial QP solvers.
OSQP has already a large userbase with tens of thousands of users both from top academic
institutions and large corporations.
A Problem classes
In this section we describe the random problem classes used in the benchmarks and derive
formulations with explicit linear equalities and inequalities that can be directly written in
the form Ax∈C withC = [l,u ].
A.1 Random QP
Consider the following QP
minimize (1 /2)xTPx +qTx
subject to l≤Ax≤u.
Problem instances. The number of variables and constraints in our problem instances are
n and m = 10n. We generated random matrix P =MMT +αI where M∈ Rn×n and 15%
nonzero elementsMij∼N (0, 1). We add the regularization αI withα = 10−2 to ensure that
the problem is not unbounded. We set the elements of A∈ Rm×n asAij∼N (0, 1) with only
15% being nonzero. The linear part of the cost is normally distributed, i.e., qi∼N (0, 1).
We generated the constraint bounds as ui∼U (0, 1), li∼−U (0, 1).
24
A.2 Equality constrained QP
Consider the following equality constrained QP
minimize (1 /2)xTPx +qTx
subject to Ax =b.
This problem can be rewritten as (1) by setting l =u =b.
Problem instances. The number of variables and constraints in our problem instances are
n and m =⌊n/2⌋.
We generated random matrix P = MMT +αI where M ∈ Rn×n and 15% nonzero
elements Mij∼N (0, 1). We add the regularization αI with α = 10−2 to ensure that the
problem is not unbounded. We set the elements of A∈ Rm×n as Aij∼N (0, 1) with only
15% being nonzero. The vectors are all normally distributed, i.e., qi,bi∼N (0, 1).
Iterative reﬁnement interpretation. Solution of the above problem can be found directly
by solving the following linear system
[P A T
A 0
][x
ν
]
=
[−q
b
]
. (35)
If we apply the ADMM iterations (15)–(19) for solving the above problem, and by setting
α = 1 and y0 =b, the algorithm boils down to the following iteration
[xk+1
νk+1
]
=
[xk
νk
]
+
[P +σI A T
A −ρ−1I
]−1([−q
b
]
−
[P A T
A 0
][xk
νk
])
,
which is equivalent to (31) with g = (−q,b ) and ˆtk = (xk,νk). This means that Algo-
rithm 1 applied to solve an equality constrained QP is equivalent to applying iterative re-
ﬁnement [Wil63, DER89] to solve the KKT system (35). Note that the perturbation matrix
in this case is
∆K =
[σI
−ρ−1I
]
,
which justiﬁes using a low value of σ and a high value of ρ for equality constraints.
A.3 Optimal control
We consider the problem of controlling a constrained linear time-invariant dynamical system.
To achieve this, we formulate the following optimization problem [BBM17]
minimize xT
TQTxT +∑T−1
t=0 xT
tQxt +uT
tRut
subject to xt+1 =Axt +But
xt∈X ,ut∈U
x0 =xinit.
(36)
25
The states xt∈ Rnx and the inputs uk∈ Rnu are subject to polyhedral constraints deﬁned
by the setsX andU. The horizon length is T and the initial state is xinit∈ Rnx. Matrices
Q∈ Snx
+ and R∈ Snu
++ deﬁne the state and input costs at each stage of the horizon, and
QT∈ Snx
+ deﬁnes the ﬁnal stage cost.
By deﬁning the new variable z = (x0,...,x T,u 0,...,u T−1), problem (36) can be written
as a sparse QP of the form (2) with a total of nx(T + 1) +nuT variables.
Problem instances. We deﬁned the linear systems with n = nx states and nu = 0.5nx
inputs. We set the horizon length to T = 10. We generated the dynamics as A =I + ∆ with
∆ij∼N (0, 0.01). We chose only stable dynamics by enforcing the norm of the eigenvalues
of A to be less than 1. The input action is modeled as B with Bij∼N (0, 1).
The state cost is deﬁned as Q = diag(q) where qi∼U (0, 10) and 70% nonzero elements
in q. We chose the input cost as R = 0.1I. The terminal cost QT is chosen as the optimal
cost for the linear quadratic regulator (LQR) applied to A,B,Q,R by solving a discrete
algebraic Riccati equation (DARE) [BBM17]. We generated input and state constraints as
X ={xt∈ Rnx|−x≤xt≤x}, U ={ut∈ Rnu|−u≤ut≤u},
where xi ∼ U(1, 2) and ui ∼ U(0, 0.1). The initial state is uniformly distributed with
xinit∼U (−0.5x, 0.5x).
A.4 Portfolio optimization
Portfolio optimization is a problem arising in ﬁnance that seeks to allocate assets in a way
that maximizes the risk adjusted return [BMOW14, Mar52, BBD +17], [BV04,§4.4.1],
maximize µTx−γ(xT Σx)
subject to 1Tx = 1
x≥ 0,
where the variable x∈ Rn represents the portfolio, µ∈ Rn the vector of expected returns,
γ >0 the risk aversion parameter, and Σ ∈ Sn
+ the risk model covariance matrix. The risk
model is usually assumed to be the sum of a diagonal and a rank k <n matrix
Σ =FF T +D,
where F∈ Rn×k is the factor loading matrix and D∈ Rn×n is a diagonal matrix describing
the asset-speciﬁc risk.
We introduce a new variable y = FTx and solve the resulting problem in variables x
and y
minimize xTDx +yTy−γ−1µTx
subject to y =FTx
1Tx = 1
x≥ 0,
(37)
Note that the Hessian of the objective in (37) is a diagonal matrix. Also, observe that FF T
does not appear in problem (37).
26
Problem instances. We generated portfolio problems for increasing number of factors k
and number of assets n = 100k. The elements of matrix F were chosen as Fij∼N (0, 1)
with 50% nonzero elements. The diagonal matrix D is chosen as Dii∼U [0,
√
k]. The mean
return was generated as µi∼N (0, 1). We set γ = 1.
A.5 Lasso
The least absolute shrinkage and selection operator (Lasso) is a well known linear regression
technique obtained by adding an ℓ1 regularization term in the objective [Tib96, CWB08]. It
can be formulated as
minimize ∥Ax−b∥2
2 +λ∥x∥1,
where x∈ Rn is the vector of parameters and A∈ Rm×n is the data matrix and λ is the
weighting parameter.
We convert this problem to the following QP
minimize yTy +λ1Tt
subject to y =Ax−b
−t≤x≤t,
where y∈ Rm and t∈ Rn are two newly introduced variables.
Problem instances. The elements of matrix A are generated as Aij∼N (0, 1) with 15%
nonzero elements. To construct the vector b, we generated the true sparse vector v∈ Rn to
be learned
vi∼
{
0 with probability p = 0.5
N (0, 1/n) otherwise .
Then we let b = Av +ε where ε is the noise generated as εi∼N (0, 1). We generated the
instances with varying n features and m = 100n data points. The parameter λ is chosen as
(1/5)∥ATb∥∞ since∥ATb∥∞ is the critical value above which the solution of the problem is
x = 0.
A.6 Huber ﬁtting
Huber ﬁtting or the robust least-squares problem performs linear regression under the as-
sumption that there are outliers in the data [Hub64, Hub81]. The ﬁtting problem is written
as
minimize ∑m
i=1φhub(aT
ix−bi), (38)
with the Huber penalty function φhub : R→ R deﬁned as
φhub(u) =
{
u2 |u|≤ M
M(2|u|− M) |u|>M.
27
Problem (38) is equivalent to the following QP [MM00, Eq. (24)]
minimize uTu + 2M 1T (r +s)
subject to Ax−b−u =r−s
r≥ 0
s≥ 0.
Problem instances. We generate the elements of A as Aij∼N (0, 1) with 15% nonzero
elements. To construct b∈ Rm we ﬁrst generate a vector v∈ Rn as vi∼N (0, 1/n) and a
noise vector ε∈ Rm with elements
εi∼
{
N (0, 1/4) with probability p = 0.95
U[0, 10] otherwise .
We then set b =Av +ε. For each instance we choose m = 100n and M = 1.
A.7 Support vector machine
Support vector machine problem seeks an aﬃne function that approximately classiﬁes the
two sets of points [CV95]. The problem can be stated as
minimize xTx +λ∑m
i=1 max(0,biaT
ix + 1),
where bi∈{− 1, +1} is a set label, and ai is a vector of features for the i-th point. The
problem can be equivalently represented as the following QP
minimize xTx +λ1Tt
subject to t≥ diag(b)Ax + 1
t≥ 0,
where diag(b) denotes the diagonal matrix with elements of b on its diagonal.
Problem instances. We choose the vector b so that
bi =
{
+1 i≤m/2
−1 otherwise ,
and the elements of A as
Aij∼
{
N (+1/n, 1/n) i≤m/2
N (−1/n, 1/n) otherwise ,
with 15% nonzeros per case.
28
102 103 104 105 106 107 10810−4
10−1
102
Computation time [s]
Random QP
102 103 104 105 106 107 10810−4
10−1
102
Eq QP
102 103 104 105 106 107 10810−4
10−1
102
Computation time [s]
Portfolio
102 103 104 105 106 107 10810−4
10−1
102
Lasso
102 103 104 105 106 107 10810−4
10−1
102
Problem dimension N
Computation time [s]
SVM
102 103 104 105 106 107 10810−4
10−1
102
Problem dimension N
Huber
GUROBI OSQP
102 103 104 105 106 107 10810−4
10−1
102
Problem dimension N
Computation time [s]
Control
Figure 1: Computation time vs problem dimension for OSQP and GUROBI for low accu-
racy mode.
29
102 103 104 105 106 107 10810−4
10−1
102
Computation time [s]
Random QP
102 103 104 105 106 107 10810−4
10−1
102
Eq QP
102 103 104 105 106 107 10810−4
10−1
102
Computation time [s]
Portfolio
102 103 104 105 106 107 10810−4
10−1
102
Lasso
102 103 104 105 106 107 10810−4
10−1
102
Problem dimension N
Computation time [s]
SVM
102 103 104 105 106 107 10810−4
10−1
102
Problem dimension N
Huber
GUROBI OSQP
102 103 104 105 106 107 10810−4
10−1
102
Problem dimension N
Computation time [s]
Control
Figure 2: Computation time vs problem dimension for OSQP and GUROBI for high
accuracy mode.
30
1 10 100 1,000 10,0000
0.2
0.4
0.6
0.8
1
Performance ratio τ
Ratio of problems solved
Low accuracy
OSQP
GUROBI
MOSEK
ECOS
qpOASES
1 10 100 1,000 10,0000
0.2
0.4
0.6
0.8
1
Performance ratio τ
Ratio of problems solved
High accuracy
OSQP
GUROBI
MOSEK
ECOS
qpOASES
Figure 3: Benchmark problems comparison with performance proﬁles.
References
[ABQ+99] F. Allg¨ ower, T. A. Badgwell, J. S. Qin, J. B. Rawlings, and S. J. Wright.
Nonlinear Predictive Control and Moving Horizon Estimation – An Introductory
Overview, pages 391–449. Springer London, London, 1999.
[ADD04] P. R. Amestoy, T. A. Davis, and I. S. Duﬀ. Algorithm 837: AMD, an approxi-
mate minimum degree ordering algorithm. ACM Transactions on Mathematical
Software, 30(3):381–388, 2004.
[AVDB18] A. Agrawal, R. Verschueren, S. Diamond, and S. Boyd. A rewriting system for
convex optimization problems. Journal of Control and Decision , 5(1):42–60,
2018.
[BB96] H. H. Bauschke and J. M. Borwein. On projection algorithms for solving convex
feasibility problems. SIAM Review, 38(3):367–426, 1996.
31
1 10 100 1,000 10,0000
0.2
0.4
0.6
0.8
1
Performance ratio τ
Ratio of problems solved
Low accuracy
OSQP
GUROBI
MOSEK
1 10 100 1,000 10,0000
0.2
0.4
0.6
0.8
1
Performance ratio τ
Ratio of problems solved
High accuracy
OSQP
GUROBI
MOSEK
Figure 4: SuiteSparse matrix problems comparison with performance proﬁles.
[BBD+17] S. Boyd, E. Busseti, S. Diamond, R. N. Kahn, K. Koh, P. Nystrup, and J. Speth.
Multi-period trading via convex optimization. Foundations and Trends in Op-
timization, 3(1):1–76, 2017.
[BBM17] F. Borrelli, A. Bemporad, and M. Morari. Predictive Control for Linear and
Hybrid Systems. Cambridge University Press, 2017.
[BC11] H. H. Bauschke and P. L. Combettes. Convex Analysis and Monotone Operator
Theory in Hilbert Spaces. Springer, 1st edition, 2011.
[BEGFB94] S. Boyd, L. El Ghaoui, E. Feron, and V. Balakrishnan. Linear Matrix In-
equalities in System and Control Theory . Society for Industrial and Applied
Mathematics, 1994.
[Ben02] M. Benzi. Preconditioning techniques for large linear systems: a survey. Journal
of Computational Physics , 182(2):418 – 477, 2002.
32
1 10 100 1,000 10,0000
0.2
0.4
0.6
0.8
1
Performance ratio τ
Ratio of problems solved
Low accuracy
OSQP
GUROBI
MOSEK
1 10 100 1,000 10,0000
0.2
0.4
0.6
0.8
1
Performance ratio τ
Ratio of problems solved
High accuracy
OSQP
GUROBI
MOSEK
Figure 5: Maros-M´ esz´ aros problems comparison with performance proﬁles.
[BG18] G. Banjac and P. Goulart. Tight global linear convergence rate bounds for oper-
ator splitting methods. IEEE Transactions on Automatic Control, 63(12):4126–
4139, 2018.
[BGSB19] G. Banjac, P. Goulart, B. Stellato, and S. Boyd. Infeasibility detection in the
alternating direction method of multipliers for convex optimization. Journal of
Optimization Theory and Applications , 183(2):490–519, 2019.
[BHT04] H. Balakrishnan, I. Hwang, and C. J. Tomlin. Polynomial approximation algo-
rithms for belief matrix maintenance in identity management. In IEEE Con-
ference on Decision and Control (CDC) , pages 4874–4879, 2004.
[BKL+13] P. Belotti, C. Kirches, S. Leyﬀer, J. Linderoth, J. Luedtke, and A. Mahajan.
Mixed-integer nonlinear optimization. Acta Numerica, 22:1–131, April 2013.
33
[BMOW14] S. Boyd, M. T. Mueller, B. O’Donoghue, and Y. Wang. Performance bounds
and suboptimal policies for multiperiod investment. Foundations and Trends
in Optimization, 1(1):1–72, 2014.
[BPC+11] S. Boyd, N. Parikh, E. Chu, B. Peleato, and J. Eckstein. Distributed optimiza-
tion and statistical learning via the alternating direction method of multipliers.
Foundations and Trends in Machine Learning , 3(1):1–122, 2011.
[Bra10] A. Bradley. Algorithms for the equilibration of matrices and their application to
limited-memory quasi-Newton methods. PhD thesis, Stanford University, 2010.
[BSM+17] G. Banjac, B. Stellato, N. Moehle, P. Goulart, A. Bemporad, and S. Boyd.
Embedded code generation using the OSQP solver. In IEEE Conference on
Decision and Control (CDC) , 2017.
[BV04] S. Boyd and L. Vandenberghe. Convex Optimization . Cambridge University
Press, 2004.
[CT06] G. Cornuejols and R. T¨ ut¨ unc¨ u.Optimization Methods in Finance. Mathematics,
Finance and Risk. Cambridge University Press, 2006.
[CV95] C. Cortes and V. Vapnik. Support-vector networks. Machine Learning ,
20(3):273–297, 1995.
[CWB08] E. J. Cand´ es, M. B. Wakin, and S. Boyd. Enhancing sparsity by reweighted
ℓ1 minimization. Journal of Fourier Analysis and Applications , 14(5):877–905,
2008.
[Dan63] G. B. Dantzig. Linear programming and extensions. Princeton University Press
Princeton, N.J., 1963.
[Dav05] T. A. Davis. Algorithm 849: a concise sparse Cholesky factorization package.
ACM Transactions on Mathematical Software , 31(4):587–591, 2005.
[Dav06] T. A. Davis. Direct Methods for Sparse Linear Systems . Society for Industrial
and Applied Mathematics, 2006.
[DB16] S. Diamond and S. Boyd. CVXPY: A Python-embedded modeling language for
convex optimization. Journal of Machine Learning Research, 17(83):1–5, 2016.
[DB17] S. Diamond and S. Boyd. Stochastic matrix-free equilibration. Journal of
Optimization Theory and Applications , 172(2):436–454, February 2017.
[DCB13] A. Domahidi, E. Chu, and S. Boyd. ECOS: An SOCP solver for embedded
systems. In European Control Conference (ECC), pages 3071–3076, 2013.
[DER89] I. S. Duﬀ, A. M. Erisman, and J. K. Reid. Direct methods for sparse matrices .
Oxford University Press, London, 1989.
34
[DFH09] M. Diehl, H. J. Ferreau, and N. Haverbeke. Eﬃcient Numerical Methods for
Nonlinear MPC and Moving Horizon Estimation , pages 391–417. Springer
Berlin Heidelberg, Berlin, Heidelberg, 2009.
[DH11] T. A. Davis and Y. Hu. The University of Florida Sparse Matrix Collection.
ACM Trans. Math. Softw. , 38(1):1:1–1:25, December 2011.
[DHL17] I. Dunning, J. Huchette, and M. Lubin. JuMP: A modeling language for math-
ematical optimization. SIAM Review, 59(2):295–320, 2017.
[DM02] Elizabeth D. Dolan and Jorge J. Mor´ e. Benchmarking optimization software
with performance proﬁles. Mathematical Programming, 91(2):201–213, January
2002.
[DR56] J. Douglas and H. H. Rachford. On the numerical solution of heat conduc-
tion problems in two and three space variables. Transactions of the American
Mathematical Society, 82(2):421–439, 1956.
[Eck94] J. Eckstein. Parallel alternating direction multiplier decomposition of convex
programs. Journal of Optimization Theory and Applications, 80(1):39–62, 1994.
[EF98] J. Eckstein and M. C. Ferris. Operator-splitting methods for monotone aﬃne
variational inequalities, with a parallel application to optimal control. IN-
FORMS Journal on Computing , 10(2):218–235, 1998.
[FB18] C. Fougner and S. Boyd. Parameter Selection and Preconditioning for a Graph
Form Solver, pages 41–61. Springer International Publishing, 2018.
[FKP+14] H. J. Ferreau, C. Kirches, A. Potschka, H. G. Bock, and M. Diehl. qpOASES:
a parametric active-set algorithm for quadratic programming. Mathematical
Programming Computation, 6(4):327–363, 2014.
[FL98] R. Fletcher and S. Leyﬀer. Numerical experience with lower bounds for MIQP
branch-and-bound. SIAM Journal on Optimization , 8(2):604–616, 1998.
[FW56] M. Frank and P. Wolfe. An algorithm for quadratic programming. Naval Re-
search Logistics Quarterly, 3(1-2):95–110, 1956.
[Gab83] D. Gabay. Chapter IX Applications of the method of multipliers to variational
inequalities. Studies in Mathematics and Its Applications , 15:299 – 331, 1983.
[GB15] P. Giselsson and S. Boyd. Metric selection in fast dual forward–backward split-
ting. Automatica, 62:1–10, 2015.
[GB17] P. Giselsson and S. Boyd. Linear convergence and metric selection for Douglas-
Rachford splitting and ADMM. IEEE Transactions on Automatic Control ,
62(2):532–544, February 2017.
35
[GM75] R. Glowinski and A. Marroco. Sur l’approximation, par ´ el´ ements ﬁnis d’ordre
un, et la r´ esolution, par p´ enalisation-dualit´ e d’une classe de probl` emes de dirich-
let non lin´ eaires. ESAIM: Mathematical Modelling and Numerical Analysis -
Mod´ elisation Math´ ematique et Analyse Num´ erique, 9(R2):41–76, 1975.
[GM76] D. Gabay and B. Mercier. A dual algorithm for the solution of nonlinear vari-
ational problems via ﬁnite element approximation. Computers & Mathematics
with Applications, 2(1):17 – 40, 1976.
[GMS+86] P. E. Gill, W. Murray, M. A. Saunders, J. A. Tomlin, and M. H. Wright. On
projected Newton barrier methods for linear programming and an equivalence
to Karmarkar’s projective method. Mathematical Programming, 36(2):183–209,
1986.
[GPM89] C. E. Garca, D. M. Prett, and M. Morari. Model predictive control: Theory
and practicea survey. Automatica, 25(3):335 – 348, 1989.
[Gre97] A. Greenbaum. Iterative Methods for Solving Linear Systems . Society for In-
dustrial and Applied Mathematics, 1997.
[GS16] N. Gould and J. Scott. A note on performance proﬁles for benchmarking soft-
ware. ACM Trans. Math. Softw. , 43(2):15:1–15:5, August 2016.
[GSB18] P. Goulart, B. Stellato, and G. Banjac. QDLDL. https://github.com/
oxfordcontrol/qdldl, 2018.
[GTSJ15] E. Ghadimi, A. Teixeira, I. Shames, and M. Johansson. Optimal parameter
selection for the alternating direction method of multipliers (ADMM): quadratic
problems. IEEE Transactions on Automatic Control , 60(3):644–658, 2015.
[Gur16] Gurobi Optimization Inc. Gurobi optimizer reference manual.
http://www.gurobi.com, 2016.
[GVL96] G. H. Golub and C. F. Van Loan. Matrix Computations (3rd Ed.) . Johns
Hopkins University Press, Baltimore, MD, USA, 1996.
[GW03] E. M. Gertz and S. J. Wright. Object-oriented software for quadratic program-
ming. ACM Trans. Math. Softw. , 29(1):58–81, March 2003.
[Hub64] P. J. Huber. Robust estimation of a location parameter. The Annals of Math-
ematical Statistics, 35(1):73–101, 1964.
[Hub81] P. J. Huber. Robust Statistics. John Wiley & Sons, 1981.
[HYW00] B. S. He, H. Yang, and S. L. Wang. Alternating direction method with self-
adaptive penalty parameters for monotone variational inequalities. Journal of
Optimization Theory and Applications , 106(2):337–356, 2000.
36
[Int17] Intel Corporation. Intel Math Kernel Library. User’s Guide , 2017.
[JGR+14] J. L. Jerez, P. J. Goulart, S. Richter, G. A. Constantinides, E. C. Kerrigan,
and M. Morari. Embedded online optimization for model predictive control at
megahertz rates. IEEE Transactions on Automatic Control , 59(12):3238–3251,
December 2014.
[Kan60] L. Kantorovich. Mathematical methods of organizing and planning production.
Management Science, 6(4):366–422, 1960. English translation.
[Kar84] N. Karmarkar. A new polynomial-time algorithm for linear programming. Com-
binatorica, 4(4):373–395, 1984.
[Kel95] C. Kelley. Iterative Methods for Linear and Nonlinear Equations . Society for
Industrial and Applied Mathematics, 1995.
[KM70] V. Klee and G. Minty. How good is the simplex algorithm. Technical report,
Department of Mathematics, University of Washington, 1970.
[KRU14] P. A. Knight, D. Ruiz, and B. U¸ car. A symmetry preserving algorithm for
matrix scaling. SIAM Journal on Matrix Analysis and Applications , 35(3):931–
955, 2014.
[L¨04] J. L¨ ofberg. YALMIP: a toolbox for modeling and optimization in MATLAB.
In IEEE International Conference on Robotics and Automation, pages 284–289,
2004.
[LM79] P. L. Lions and B. Mercier. Splitting algorithms for the sum of two nonlinear
operators. SIAM Journal on Numerical Analysis , 16(6):964–979, 1979.
[Mar52] H. Markowitz. Portfolio selection. The Journal of Finance , 7(1):77–91, 1952.
[MB10] J. Mattingley and S. Boyd. Real-time convex optimization in signal processing.
IEEE Signal Processing Magazine , 27(3):50–61, May 2010.
[MB12] J. Mattingley and S. Boyd. CVXGEN: A code generator for embedded convex
optimization. Optimization and Engineering , 13(1):1–27, 2012.
[Meh92] S. Mehrotra. On the implementation of a primal-dual interior point method.
SIAM Journal on Optimization , 2(4):575–601, 1992.
[Mit] H. Mittelmann. Benchmarks for optimization software. http://plato.asu.
edu/bench.html. Accessed: 2019-09-08.
[MM99] I. Maros and C. M´ esz´ aros. A repository of convex quadratic programming
problems. Optimization Methods and Software , 11(1-4):671–681, 1999.
37
[MM00] O. L. Mangasarian and D. R. Musicant. Robust linear and support vector
regression. IEEE Transactions on Pattern Analysis and Machine Intelligence ,
22(9):950–955, 2000.
[MOS17] MOSEK ApS. The MOSEK optimization toolbox for MATLAB manual. Version
8.0 (Revision 57). , 2017.
[NLR+15] R. Nishihara, L. Lessard, B. Recht, A. Packard, and M. I. Jordan. A general
analysis of the convergence of ADMM. In International Conference on Machine
Learning (ICML), pages 343–352, 2015.
[NN94] Y. Nesterov and A. Nemirovskii. Interior-Point Polynomial Algorithms in Con-
vex Programming. Society for Industrial and Applied Mathematics, 1994.
[NW06] J. Nocedal and S. J. Wright. Numerical optimization. Springer Series in Oper-
ations Research and Financial Engineering. Springer, Berlin, 2006.
[OCPB16] B. O’Donoghue, E. Chu, N. Parikh, and S. Boyd. Conic optimization via oper-
ator splitting and homogeneous self-dual embedding. Journal of Optimization
Theory and Applications, 169(3):1042–1068, June 2016.
[OSB13] B. O’Donoghue, G. Stathopoulos, and S. Boyd. A splitting method for optimal
control. IEEE Transactions on Control Systems Technology , 21(6):2432–2442,
November 2013.
[PC11] T. Pock and A. Chambolle. Diagonal preconditioning for ﬁrst order primal-
dual algorithms in convex optimization. In 2011 International Conference on
Computer Vision, pages 1762–1769, November 2011.
[RDC14a] A. U. Raghunathan and S. Di Cairano. ADMM for convex quadratic programs:
Q-linear convergence and infeasibility detection. arXiv:1411.7288, 2014.
[RDC14b] A. U. Raghunathan and S. Di Cairano. Infeasibility detection in alternating
direction method of multipliers for convex quadratic programs. In IEEE Con-
ference on Decision and Control (CDC) , pages 5819–5824, 2014.
[RKB+18] A. Reuther, J. Kepner, C. Byun, S. Samsi, W. Arcand, D. Bestor, B. Berg-
eron, V. Gadepally, M. Houle, M. Hubbell, M. Jones, A. Klein, L. Milechin,
J. Mullen, A. Prout, A. Rosa, C. Yee, and P. Michaleas. Interactive super-
computing on 40,000 cores for machine learning and data analysis. In 2018
IEEE High Performance extreme Computing Conference (HPEC) , pages 1–6,
Sep. 2018.
[RM09] J. B. Rawlings and D. Q. Mayne. Model Predictive Control: Theory and Design.
Nob Hill Publishing, 2009.
38
[Rui01] D. Ruiz. A scaling algorithm to equilibrate both rows and columns norms in ma-
trices. Technical Report RAL-TR-2001-034, Rutherford Appleton Laboratory,
Oxon, UL, 2001.
[RW98] R. T. Rockafellar and R. J.-B Wets. Variational analysis. Grundlehren der
mathematischen Wissenschaften. Springer, 1998.
[SB19] B. Stellato and G. Banjac. Benchmark examples for the OSQP solver.
https://github.com/oxfordcontrol/osqp_benchmarks, 2019.
[SK67] R. Sinkhorn and P. Knopp. Concerning nonnegative matrices and doubly
stochastic matrices. Paciﬁc Journal of Mathematics , 21(2):343–348, 1967.
[SSS+16] G. Stathopoulos, H. Shukla, A. Szucs, Y. Pu, and C. N. Jones. Operator
splitting methods in control. Foundations and Trends in Systems and Control ,
3(3):249–362, 2016.
[Tib96] R. Tibshirani. Regression shrinkage and selection via the lasso. Journal of the
Royal Statistical Society: Series B , 58(1):267–288, 1996.
[TJ14] R. Takapoui and H. Javadi. Preconditioning via diagonal scaling. EE364b:
Convex Optimization II Class Project , 2014.
[Van95] R. Vanderbei. Symmetric quasi-deﬁnite matrices. SIAM Journal on Optimiza-
tion, 5(1):100–113, 1995.
[Wil63] J. H. Wilkinson. Rounding Errors in Algebraic Processes. Prentice Hall, Engle-
wood Cliﬀs, NJ, 1963.
[Woh17] B. Wohlberg. ADMM penalty parameter selection by residual balancing.
arXiv:1704.06209v1, 2017.
[Wol59] P. Wolfe. The simplex method for quadratic programming. Econometrica,
27(3):382–398, 1959.
[Wri97] S. Wright. Primal-Dual Interior-Point Methods . Society for Industrial and
Applied Mathematics, Philadelphia, 1997.
39
