# r005_10_1007_s10107-017-1172-1_data-driven_distributionally_robust_optimization_


- kind: paper-mineru
- title: r005_10_1007_s10107-017-1172-1_data-driven_distributionally_robust_optimization_
- source: path:knowledge/inbox_pdf/or_fulltext/r005_10.1007_s10107-017-1172-1_data-driven_distributionally_robust_optimization_using_the_w.pdf

- kind: paper-mineru
- source_pdf: knowledge/inbox_pdf/or_fulltext/r005_10.1007_s10107-017-1172-1_data-driven_distributionally_robust_optimization_using_the_w.pdf
- preprocess_mode: offline_extract
- extract_backend: pypdf
- note: RAG text for Pi retrieve; not numeric authority.

---
Math. Program., Ser. A (2018) 171:115–166
https://doi.org/10.1007/s10107-017-1172-1
FULL LENGTH PAPER
Data-driven distributionally robust optimization using
the Wasserstein metric: performance guarantees
and tractable reformulations
Peyman Mohajerin Esfahani 1 · Daniel Kuhn2
Received: 9 May 2015 / Accepted: 16 June 2017 / Published online: 7 July 2017
© The Author(s) 2017. This article is an open access publication
Abstract We consider stochastic programs where the distribution of the uncertain
parameters is only observable through a ﬁnite training dataset. Using the Wasserstein
metric, we construct a ball in the space of (multivariate and non-discrete) probability
distributions centered at the uniform distribution on the training samples, and we seek
decisions that perform best in view of the worst-case distribution within this Wasser-
stein ball. The state-of-the-art methods for solving the resulting distributionally robust
optimization problems rely on global optimization techniques, which quickly become
computationally excruciating. In this paper we demonstrate that, under mild assump-
tions, the distributionally robust optimization problems over Wasserstein balls can
in fact be reformulated as ﬁnite convex programs—in many interesting cases even
as tractable linear programs. Leveraging recent measure concentration results, we
also show that their solutions enjoy powerful ﬁnite-sample performance guarantees.
Our theoretical results are exempliﬁed in mean-risk portfolio optimization as well as
uncertainty quantiﬁcation.
Mathematics Subject Classiﬁcation 90C15 Stochastic programming ·
90C25 Convex programming · 90C47 Minimax problems
1 Introduction
Stochastic programming is a powerful modeling paradigm for optimization under
uncertainty. The goal of a generic single-stage stochastic program is to ﬁnd a decision
B Peyman Mohajerin Esfahani
P .MohajerinEsfahani@tudelft.nl
Daniel Kuhn
daniel.kuhn@epﬂ.ch
1 Delft Center for Systems and Control, TU Delft, Delft, The Netherlands
2 Risk Analytics and Optimization Chair, EPFL, Lausanne, Switzerland
123
116 P . Mohajerin Esfahani, D. Kuhn
x ∈ Rn that minimizes an expected cost EP[h(x,ξ) ], where the expectation is taken
with respect to the distribution P of the continuous random vector ξ ∈ Rm . However,
classical stochastic programming is challenged by the large-scale decision problems
encountered in today’s increasingly interconnected world. First, the distribution P is
never observable but must be inferred from data. However, if we calibrate a stochastic
program to a given dataset and evaluate its optimal decision on a different dataset,
then the resulting out-of-sample performance is often disappointing—even if the two
datasets are generated from the same distribution. This phenomenon is termed the
optimizer’s curseand is reminiscent of overﬁtting effects in statistics [ 48]. Second, in
order to evaluate the objective function of a stochastic program for a ﬁxed decision x,
we need to compute a multivariate integral, which is #P-hard even ifh(x,ξ) constitutes
the positive part of an afﬁne function, while ξ is uniformly distributed on the unit
hypercube [24, Corollary 1].
Distributionally robust optimization is an alternative modeling paradigm, where
the objective is to ﬁnd a decision x that minimizes the worst-case expected cost
sup
Q∈P EQ[h(x,ξ) ]. Here, the worst-case is taken over an ambiguity set P, that
is, a family of distributions characterized through certain known properties of the
unknown data-generating distribution P. Distributionally robust optimization prob-
lems have been studied since Scarf’s [ 43] seminal treatise on the ambiguity-averse
newsvendor problem in 1958, but the ﬁeld has gained thrust only with the advent
of modern robust optimization techniques in the last decade [ 3,9]. Distributionally
robust optimization has the following striking beneﬁts. First, adopting a worst-case
approach regularizes the optimization problem and thereby mitigates the optimizer’s
curse characteristic for stochastic programming. Second, distributionally robust mod-
els are often tractable even though the corresponding stochastic model with the true
data-generating distribution (which is generically continuous) are # P-hard. So even
if the data-generating distribution was known, the corresponding stochastic program
could not be solved efﬁciently.
The ambiguity set P is a key ingredient of any distributionally robust optimization
model. A good ambiguity set should be rich enough to contain the true data-generating
distribution with high conﬁdence. On the other hand, the ambiguity set should be
small enough to exclude pathological distributions, which would incentivize overly
conservative decisions. The ambiguity set should also be easy to parameterize from
data, and—ideally—it should facilitate a tractable reformulation of the distributionally
robust optimization problem as a structured mathematical program that can be solved
with off-the-shelf optimization software.
Distributionally robust optimization models where ξ has ﬁnitely many realizations
a r er e v i e w e di n[2,7,39]. This paper focuses on situations where ξ can have a con-
tinuum of realizations. In this setting, the existing literature has studied three types
of ambiguity sets. Moment ambiguity sets contain all distributions that satisfy cer-
tain moment constraints, see for example [ 18,22,51] or the references therein. An
attractive alternative is to deﬁne the ambiguity set as a ball in the space of probability
distributions by using a probability distance function such as the Prohorov metric [20],
the Kullback–Leibler divergence [25,27], or the Wasserstein metric [38,52] etc. Such
metric-based ambiguity sets contain all distributions that are close to anominal or most
likely distribution with respect to the prescribed probability metric. By adjusting the
123
Data-driven distributionally robust optimization using the… 117
radius of the ambiguity set, the modeler can thus control the degree of conservatism of
the underlying optimization problem. If the radius drops to zero, then the ambiguity
set shrinks to a singleton that contains only the nominal distribution, in which case the
distributionally robust problem reduces to an ambiguity-free stochastic program. In
addition, ambiguity sets can also be deﬁned as conﬁdence regions of goodness-of-ﬁt
tests [7].
In this paper we study distributionally robust optimization problems with aWasser-
stein ambiguity set centered at the uniform distribution ˆP
N on N independent and
identically distributed training samples. The Wasserstein distance of two distributions
Q
1 and Q2 can be viewed as the minimum transportation cost for moving the proba-
bility mass from Q1 to Q2, and the Wasserstein ambiguity set contains all (continuous
or discrete) distributions that are sufﬁciently close to the (discrete) empirical distribu-
tionˆPN with respect to the Wasserstein metric. Modern measure concentration results
from statistics guarantee that the unknown data-generating distribution P belongs to
the Wasserstein ambiguity set around ˆPN with conﬁdence 1 − β if its radius is a
sublinearly growing function of log(1/β)/ N [11,21]. The optimal value of the distri-
butionally robust problem thus provides an upper conﬁdence bound on the achievable
out-of-sample cost.
While Wasserstein ambiguity sets offer powerful out-of-sample performance guar-
antees and enable the decision maker to control the model’s conservativeness,
moment-based ambiguity sets appear to display better tractability properties. Specif-
ically, there is growing evidence that distributionally robust models with moment
ambiguity sets are more tractable than the corresponding stochastic models because
the intractable high-dimensional integrals in the objective function are replaced with
tractable (generalized) moment problems [ 18,22,51]. In contrast, distributionally
robust models with Wasserstein ambiguity sets are believed to be harder than their
stochastic counterparts [ 36]. Indeed, the state-of-the-art method for computing the
worst-case expectation over a Wasserstein ambiguity set P relies on global opti-
mization techniques. Exploiting the fact that the extreme points of P are discrete
distributions with a ﬁxed number of atoms [ 52], one may reformulate the original
worst-case expectation problem as a ﬁnite-dimensional non-convex program, which
can be solved via “difference of convex programming” methods, see [52]o r[ 36, Sec-
tion 7.1]. However, the computational effort is reported to be considerable, and there is
no guarantee to ﬁnd the global optimum. Nevertheless, tractability results are available
for special cases. Speciﬁcally, the worst case of a convex law-invariant risk measure
with respect to a Wasserstein ambiguity set P reduces to the sum of the nominal risk
and a regularization term whenever h(x,ξ) is afﬁne in ξ and P does not include any
support constraints [ 53]. Moreover, while this paper was under review we became
aware of the PhD thesis [ 54], which reformulates a distributionally robust two-stage
unit commitment problem over a Wasserstein ambiguity set as a semi-inﬁnite linear
program, which is subsequently solved using a Benders decomposition algorithm.
The main contribution of this paper is to demonstrate that the worst-case expectation
over a Wasserstein ambiguity set can in fact be computed efﬁciently via convex opti-
mization techniques for numerous loss functions of practical interest. Furthermore, we
propose an efﬁcient procedure for constructing an extremal distribution that attains the
worst-case expectation—provided that such a distribution exists. Otherwise, we con-
123
118 P . Mohajerin Esfahani, D. Kuhn
struct a sequence of distributions that attain the worst-case expectation asymptotically.
As a by-product, our analysis shows that many interesting distributionally robust opti-
mization problems with Wasserstein ambiguity sets can be solved in polynomial time.
We also investigate the out-of-sample performance of the resulting optimal decisions—
both theoretically and experimentally—and analyze its dependence on the number of
training samples. We highlight the following main contributions of this paper.
• We prove that the worst-case expectation of an uncertain loss ℓ(ξ) over a Wasser-
stein ambiguity set coincides with the optimal value of a ﬁnite-dimensional convex
program if ℓ(ξ) constitutes a pointwise maximum of ﬁnitely many concave func-
tions. Generalizations to convex functions or to sums of maxima of concave
functions are also discussed. We conclude that worst-case expectations can be
computed efﬁciently to high precision via modern convex optimization algorithms.
• We describe a supplementary ﬁnite-dimensional convex program whose optimal
(near-optimal) solutions can be used to construct exact (approximate) extremal
distributions for the inﬁnite-dimensional worst-case expectation problem.
• We show that the worst-case expectation reduces to the optimal value of an explicit
linear program if the 1-norm or the∞-norm is used in the deﬁnition of the Wasser-
stein metric and if ℓ(ξ) belongs to any of the following function classes: (1) a
pointwise maximum or minimum of afﬁne functions; (2) the indicator function of
a closed polytope or the indicator function of the complement of an open polytope;
(3) the optimal value of a parametric linear program whose cost or right-hand side
coefﬁcients depend linearly on ξ .
• Using recent measure concentration results from statistics, we demonstrate that the
optimal value of a distributionally robust optimization problem over a Wasserstein
ambiguity set provides an upper conﬁdence bound on the out-of-sample cost of the
worst-case optimal decision. We validate this theoretical performance guarantee
in numerical tests.
If the uncertain parameter vectorξ is conﬁned to a ﬁxed ﬁnite subset of R
m , then the
worst-case expectation problems over Wasserstein ambiguity sets simplify substan-
tially and can often be reformulated as tractable conic programs by leveraging ideas
from robust optimization. An elegant second-order conic reformulation has been dis-
covered, for instance, in the context of distributionally robust regression analysis [32],
and a comprehensive list of tractable reformulations of distributionally robust risk
constraints for various risk measures is provided in [ 39]. Our paper extends these
tractability results to the practically relevant case where ξ has uncountably many pos-
sible realizations—without resorting to space tessellation or discretization techniques
that are prone to the curse of dimensionality.
When ℓ(ξ) is linear and the distribution of ξ ranges over a Wasserstein ambiguity
set without support constraints, one can derive a concise closed-form expression for
the worst-case risk of ℓ(ξ) for various convex risk measures [ 53]. However, these
analytical solutions come at the expense of a loss of generality. We believe that the
results of this paper may pave the way towards an efﬁcient computational procedure for
evaluating the worst-case risk of ℓ(ξ) in more general settings where the loss function
may be non-linear and ξ may be subject to support constraints.
123
Data-driven distributionally robust optimization using the… 119
Among all metric-based ambiguity sets studied to date, the Kullback–Leibler ambi-
guity set has attracted most attention from the robust optimization community. It has
ﬁrst been used in ﬁnancial portfolio optimization to capture the distributional uncer-
tainty of asset returns with a Gaussian nominal distribution [ 19]. Subsequent work
has focused on Kullback–Leibler ambiguity sets for discrete distributions with a ﬁxed
support, which offer additional modeling ﬂexibility without sacriﬁcing computational
tractability [ 2,14]. It is also known that distributionally robust chance constraints
involving a generic Kullback–Leibler ambiguity set are equivalent to the respective
classical chance constraints under the nominal distribution but with a rescaled viola-
tion probability [26,27]. Moreover, closed-form counterparts of distributionally robust
expectation constraints with Kullback–Leibler ambiguity sets have been derived in
[25].
However, Kullback–Leibler ambiguity sets typically fail to represent conﬁdence
sets for the unknown distribution P. To see this, assume that P is absolutely continu-
ous with respect to the Lebesgue measure and that the ambiguity set is centered at the
discrete empirical distributionˆP
N . Then, any distribution in a Kullback–Leibler ambi-
guity set aroundˆPN must assign positive probability mass to each training sample.
As P has a density function, it must therefore reside outside of the Kullback–Leibler
ambiguity set irrespective of the training samples. Thus, Kullback–Leibler ambiguity
sets aroundˆPN contain P with probability 0. In contrast, Wasserstein ambiguity sets
centered atˆPN contain discrete as well as continuous distributions and, if properly
calibrated, represent meaningful conﬁdence sets for P. We will exploit this property
in Sect. 3 to derive ﬁnite-sample guarantees. A comparison and critical assessment of
various metric-based ambiguity sets is provided in [ 45]. Speciﬁcally, it is shown that
worst-case expectations over Kullback–Leibler and other divergence-based ambiguity
sets are law invariant. In contrast, worst-case expectations over Wasserstein ambiguity
sets are not. The law invariance can be exploited to evaluate worst-case expectations
via the sample average approximation.
The models proposed in this paper fall within the scope of data-driven distribu-
tionally robust optimization [ 7,16,20,23]. Closest in spirit to our work is the robust
sample average approximation [7], which seeks decisions that are robust with respect
to the ambiguity set of all distributions that pass a prescribed statistical hypothesis
test. Indeed, the distributions within the Wasserstein ambiguity set could be viewed
as those that pass a multivariate goodness-of-ﬁt test in light of the available training
samples. This amounts to interpreting the Wasserstein distance between the empiri-
cal distributionˆP
N and a given hypothesis Q as a test statistic and the radius of the
Wasserstein ambiguity set as a threshold that needs to be chosen in view of the test’s
desired signiﬁcance level β. The Wasserstein distance has already been used in tests
for normality [ 17] and to devise nonparametric homogeneity tests [ 40].
The rest of the paper proceeds as follows. Section 2 sketches a generic framework
for data-driven distributionally robust optimization, while Sect. 3 introduces our spe-
ciﬁc approach based on Wasserstein ambiguity sets and establishes its out-of-sample
performance guarantees. In Sect. 4 we demonstrate that many worst-case expectation
problems over Wasserstein ambiguity sets can be reduced to ﬁnite-dimensional convex
programs, and we develop a systematic procedure for constructing worst-case distri-
butions. Explicit linear programming reformulations of distributionally robust single
123
120 P . Mohajerin Esfahani, D. Kuhn
and two-stage stochastic programs as well as uncertainty quantiﬁcation problems are
derived in Sect. 5. Section 6 extends the scope of the basic approach to broader classes
of objective functions, and Sect. 7 reports on numerical results.
Notation We denote by R+ the non-negative and by R:=R∪{−∞,∞} the extended
reals. Throughout this paper, we adopt the conventions of extended arithmetics,
whereby ∞· 0 = 0 ·∞ = 0/0 = 0 and ∞−∞ = − ∞+∞ = 1/0 =∞ .
The inner product of two vectors a, b ∈ Rm is denoted by
⟨
a, b
⟩
:=a⊺b.G i v e na
norm ∥·∥ on Rm , the dual norm is deﬁned through ∥z∥∗:= sup∥ξ∥≤1
⟨
z,ξ
⟩
. A function
f : Rm → R is proper if f (ξ) < +∞ for at least one ξ and f (ξ) > −∞ for every ξ
in Rm . The conjugate of f is deﬁned as f ∗(z):= supξ∈Rm
⟨
z,ξ
⟩
− f (ξ) . Note that con-
jugacy preserves properness. For a set /Xi1⊆ Rm , the indicator function 1/Xi1is deﬁned
through 1/Xi1(ξ) = 1i f ξ ∈ /Xi1; = 0 otherwise. Similarly, the characteristic function
χ/Xi1is deﬁned via χ/Xi1(ξ) = 0i f ξ ∈ /Xi1; =∞ otherwise. The support function of /Xi1is
deﬁned as σ/Xi1(z):= supξ∈/Xi1
⟨
z,ξ
⟩
. It coincides with the conjugate of χ/Xi1. We denote by
δξ the Dirac distribution concentrating unit mass at ξ ∈ Rm . The product of two prob-
ability distributions P1 and P2 on /Xi11 and /Xi12, respectively, is the distributionP1 ⊗ P2
on /Xi11 × /Xi12.T h e N -fold product of a distribution P on /Xi1is denoted by PN , which
represents a distribution on the Cartesian product space /Xi1N . Finally, we set the expec-
tation of ℓ: /Xi1→ R under P to EP[ℓ(ξ)]= EP[
max{ℓ(ξ),0}
]
+ EP[
min{ℓ(ξ),0}
]
,
which is well-deﬁned by the conventions of extended arithmetics.
2 Data-driven stochastic programming
Consider the stochastic program
J⋆:= inf
x∈X
{
EP[
h(x,ξ)
]
=
∫
/Xi1
h(x,ξ) P(dξ)
}
(1)
with feasible setX ⊆ Rn , uncertainty set/Xi1⊆ Rm and loss functionh : Rn×Rm → R.
The loss function depends both on the decision vector x ∈ Rn and the random vector
ξ ∈ Rm , whose distribution P is supported on /Xi1. Problem ( 1) can be viewed as the
ﬁrst-stage problem of a two-stage stochastic program, where h(x,ξ) represents the
optimal value of a subordinate second-stage problem [ 46]. Alternatively, problem (1)
may also be interpreted as a generic learning problem in the spirit of [ 49].
Unfortunately, in most situations of practical interest, the distribution P is not
precisely known, and therefore we miss essential information to solve problem ( 1)
exactly. However, P is often partially observable through a ﬁnite set of N indepen-
dent samples, e.g., past realizations of the random vector ξ . We denote the training
dataset comprising these samples byˆ/Xi1N :={ˆξi}i≤N ⊆ /Xi1. We emphasize that—before
its revelation—the dataset ˆ/Xi1N can be viewed as a random object governed by the
distribution PN supported on /Xi1N .
A data-driven solution for problem ( 1) is a feasible decisionˆxN ∈ X that is con-
structed from the training datasetˆ/Xi1N . Throughout this paper, we notationally suppress
the dependence ofˆxN on the training samples in order to avoid clutter. Instead, we
reserve the superscript ‘ˆ’ for objects that depend on the training data and thus con-
stitute random objects governed by the product distribution PN .T h e out-of-sample
123
Data-driven distributionally robust optimization using the… 121
performance ofˆxN is deﬁned as EP[
h(ˆxN ,ξ)
]
and can thus be viewed as the expected
cost ofˆxN under a new sample ξ that is independent of the training dataset. As P is
unknown, however, the exact out-of-sample performance cannot be evaluated in prac-
tice, and the best we can hope for is to establish performance guarantees in the form
of tight bounds. The feasibility of ˆx
N in ( 1) implies J⋆ ≤ EP[
h(ˆxN ,ξ)
]
, but this
lower bound is again of limited use as J⋆ is unknown and as our primary concern is to
bound the costs from above. Thus, we seek data-driven solutionsˆxN with performance
guarantees of the type
PN
{
ˆ/Xi1N : EP[
h(ˆxN ,ξ)
]
≤ˆJN
}
≥ 1 − β, (2)
whereˆJN constitutes an upper bound that may depend on the training dataset, and
β ∈ (0, 1) is a signiﬁcance parameter with respect to the distribution PN , which
governs bothˆxN andˆJN . Hereafter we refer to ˆJN as a certiﬁcate for the out-of-
sample performance ofˆxN and to the probability on the left-hand side of ( 2) as its
reliability. Our ideal goal is to ﬁnd a data-driven solution with the lowest possible
out-of-sample performance. This is impossible, however, as P is unknown, and the
out-of-sample performance cannot be computed. We thus pursue the more modest
but achievable goal to ﬁnd a data-driven solution with a low certiﬁcate and a high
reliability.
A natural approach to generate data-driven solutionsˆx
N is to approximate P with
the discrete empirical probability distribution
ˆPN := 1
N
N∑
i=1
δˆξi , (3)
that is, the uniform distribution on ˆ/Xi1N . This amounts to approximating the original
stochastic program ( 1) with the sample-average approximation (SAA) problem
ˆJSAA:= inf
x∈X
{
EˆPN
[
h(x,ξ)
]
= 1
N
N∑
i=1
h(x,ˆξi)
}
. (4)
If the feasible set X is compact and the loss function is uniformly continuous in x
across all ξ ∈ /Xi1, then the optimal value and optimal solutions of the SAA problem
(4) converge almost surely to their counterparts of the true problem ( 1)a s N tends to
inﬁnity [ 46, Theorem 5.3]. Even though ﬁnite sample performance guarantees of the
type (2) can be obtained under additional assumptions such as Lipschitz continuity of
the loss function (see e.g., [ 47, Theorem 1]), the SAA problem has been conceived
primarily for situations where the distribution P is known and additional samples can
be acquired cheaply via random number generation. However, the optimal solutions
of the SAA problem tend to display a poor out-of-sample performance in situations
where N is small and where the acquisition of additional samples would be costly.
In this paper we address problem ( 1) with an alternative approach that explicitly
accounts for our ignorance of the true data-generating distribution P, and that offers
123
122 P . Mohajerin Esfahani, D. Kuhn
attractive performance guarantees even when the acquisition of additional samples
from P is impossible or expensive. Speciﬁcally, we use ˆ/Xi1N to design an ambiguity
setˆPN containing all distributions that could have generated the training samples
with high conﬁdence. This ambiguity set enables us to deﬁne the certiﬁcate ˆJN as
the optimal value of a distributionally robust optimization problem that minimize the
worst-case expected cost.
ˆJN := inf
x∈X
sup
Q∈ˆPN
EQ[
h(x,ξ)
]
(5)
Following [38], we constructˆPN as a ball around the empirical distribution ( 3) with
respect to the Wasserstein metric. In the remainder of the paper we will demonstrate
that the optimal value ˆJ
N as well as any optimal solution ˆxN (if it exists) of the
distributionally robust problem ( 5) satisfy the following conditions.
(i) Finite sample guarantee: For a carefully chosen size of the ambiguity set, the
certiﬁcateˆJN provides a 1 − β conﬁdence bound of the type ( 2) on the out-of-
sample performance ofˆxN .
(ii) Asymptotic consistency: As N tends to inﬁnity, the certiﬁcate ˆJN and the data-
driven solutionˆxN converge—in a sense to be made precise below—to the
optimal value J⋆ and an optimizer x⋆ of the stochastic program (1), respectively.
(iii) Tractability: For many loss functions h(x,ξ) and sets X, the distributionally
robust problem (5) is computationally tractable and admits a reformulation rem-
iniscent of the SAA problem ( 4).
Conditions (i–iii) have been identiﬁed in [ 7] as desirable properties of data-driven
solutions for stochastic programs. Precise statements of these conditions will be pro-
vided in the remainder. In Sect. 3 we will use the Wasserstein metric to construct
ambiguity sets of the typeˆP
N satisfying the conditions (i) and (ii). In Sect. 4, we will
demonstrate that these ambiguity sets also fulﬁll the tractability condition (iii). We
see this last result as the main contribution of this paper because the state-of-the-art
method for solving distributionally robust problems over Wasserstein ambiguity sets
relies on global optimization algorithms [ 36].
3 Wasserstein metric and measure concentration
Probability metrics represent distance functions on the space of probability distri-
butions. One of the most widely used examples is the Wasserstein metric, which is
deﬁned on the space M(/Xi1)of all probability distributions Q supported on /Xi1with
E
Q[
∥ξ∥
]
=
∫
/Xi1∥ξ∥Q(dξ) < ∞.
Deﬁnition 3.1 (Wasserstein metric [29]) The Wasserstein metric dW : M(/Xi1)×
M(/Xi1)→ R+ is deﬁned via
dW
(
Q1, Q2
)
:= inf
{∫
/Xi12
∥ξ1 − ξ2∥/Pi1(dξ1, dξ2) : /Pi1is a joint distribution of ξ1 and ξ2
with marginals Q1 and Q2, respectively
}
for all distributions Q1, Q2 ∈ M(/Xi1), where∥·∥ represents an arbitrary norm onRm .
123
Data-driven distributionally robust optimization using the… 123
The decision variable /Pi1can be viewed as a transportation plan for moving a mass
distribution described by Q1 to another one described by Q2. Thus, the Wasserstein
distance between Q1 and Q2 represents the cost of an optimal mass transportation plan,
where the norm ∥·∥ encodes the transportation costs. We remark that a generalized p-
Wasserstein metric for p ≥ 1 is obtained by setting the transportation cost between ξ1
and ξ2 to ∥ξ1 −ξ2∥p. In this paper, however, we focus exclusively on the 1-Wasserstein
metric of Deﬁnition 3.1, which is sometimes also referred to as the Kantorovich metric.
We will sometimes also need the following dual representation of the Wasserstein
metric.
Theorem 3.2 (Kantorovich–Rubinstein [29]) For any distributionsQ1, Q2 ∈ M(/Xi1)
we have
dW
(
Q1, Q2
)
= sup
f ∈L
{∫
/Xi1
f (ξ) Q1(dξ) −
∫
/Xi1
f (ξ) Q2(dξ)
}
,
where L denotes the space of all Lipschitz functions with | f (ξ) − f (ξ′)|≤∥ ξ − ξ′∥
for all ξ,ξ ′∈ /Xi1.
Kantorovich and Rubinstein [ 29] originally established this result for distribu-
tions with bounded support. A modern proof for unbounded distributions is due to
Villani [50, Remark 6.5, p. 107]. The optimization problems in Deﬁnition 3.1 and
Theorem 3.2, which provide two equivalent characterizations of the Wasserstein met-
ric, constitute a primal-dual pair of inﬁnite-dimensional linear programs. The dual
representation implies that two distributions Q1 and Q2 are close to each other with
respect to the Wasserstein metric if and only if all functions with uniformly bounded
slopes have similar integrals underQ
1 and Q2. Theorem 3.2 also demonstrates that the
Wasserstein metric is a special instance of an integral probability metric (see e.g. [33])
and that its generating function class coincides with a family of Lipschitz continuous
functions.
In the remainder we will examine the ambiguity set
B
ε(ˆPN ):=
{
Q ∈ M(/Xi1): dW
(ˆPN , Q
)
≤ ε
}
, (6)
which can be viewed as the Wasserstein ball of radius ε centered at the empirical dis-
tributionˆPN . Under a common light tail assumption on the unknown data-generating
distribution P, this ambiguity set offers attractive performance guarantees in the spirit
of Sect. 2.
Assumption 3.3 (Light-tailed distribution) There exists an exponent a > 1 such that
A:=EP[
exp(∥ξ∥a)
]
=
∫
/Xi1
exp(∥ξ∥a) P(dξ) < ∞.
Assumption 3.3 essentially requires the tail of the distribution P to decay at an
exponential rate. Note that this assumption trivially holds if /Xi1is compact. Heavy-
tailed distributions that fail to meet Assumption 3.3 are difﬁcult to handle even in the
123
124 P . Mohajerin Esfahani, D. Kuhn
context of the classical sample average approximation. Indeed, under a heavy-tailed
distribution the sample average of the loss corresponding to any ﬁxed decision x ∈ X
may not even converge to the expected loss; see e.g. [13,15]. The following modern
measure concentration result provides the basis for establishing powerful ﬁnite sample
guarantees.
Theorem 3.4 (Measure concentration [21, Theorem 2]) If Assumption 3.3 holds, we
have
PN
{
dW
(
P,ˆPN
)
≥ ε
}
≤
{ c1 exp
(
−c2 Nεmax{m,2})
if ε ≤ 1,
c1 exp
(
−c2 Nεa)
if ε> 1, (7)
for all N ≥ 1,m ̸= 2, and ε> 0, where c1, c2 are positive constants that only depend
on a, A, and m. 1
Theorem 3.4 provides an a priori estimate of the probability that the unknown
data-generating distribution P resides outside of the Wasserstein ball Bε(ˆPN ). Thus,
we can use Theorem 3.4 to estimate the radius of the smallest Wasserstein ball that
contains P with conﬁdence 1 − β for some prescribed β ∈ (0, 1). Indeed, equating
the right-hand side of ( 7)t o β and solving for ε yields
εN (β):=
⎧
⎪⎨
⎪⎩
(
log(c1β−1)
c2 N
) 1/max{m,2}
if N ≥ log(c1β−1)
c2 ,
(
log(c1β−1)
c2 N
) 1/a
if N < log(c1β−1)
c2 .
(8)
Note that the Wasserstein ball with radius εN (β) can thus be viewed as a conﬁdence
set for the unknown true distribution as in statistical testing; see also [ 7].
Theorem 3.5 (Finite sample guarantee) Suppose that Assumption 3.3 holds and that
β ∈ (0, 1). Assume also thatˆJN andˆxN represent the optimal value and an optimizer
of the distributionally robust program(5) with ambiguity setˆPN = BεN (β)(ˆPN ). Then,
the ﬁnite sample guarantee (2) holds.
Proof The claim follows immediately from Theorem 3.4, which ensures via the def-
inition of εN (β) in ( 8) that PN {P ∈ BεN (β)(ˆPN )}≥ 1 − β. Thus, EP[h(ˆxN ,ξ) ]≤
supQ∈ˆPN EQ[h(ˆxN ,ξ) ]=ˆJN with probability 1 − β. ⊓⊔
It is clear from ( 8) that for any ﬁxed β> 0, the radius εN (β) tends to 0 as N
increases. Moreover, one can show that if βN converges to zero at a carefully chosen
rate, then the solution of the distributionally robust optimization problem ( 5) with
ambiguity setˆPN = BεN (βN )(ˆPN ) converges to the solution of the original stochastic
program (1)a s N tends to inﬁnity. The following theorem formalizes this statement.
1 A similar but slightly more complicated inequality also holds for the special case m = 2; see [ 21,
Theorem 2] for details.
123
Data-driven distributionally robust optimization using the… 125
Theorem 3.6 (Asymptotic consistency) Suppose that Assumption 3.3 holds and that
βN ∈ (0, 1),N ∈ N, satisﬁes∑∞
N=1 βN < ∞ and limN→∞ εN (βN ) = 0.2 Assume
also thatˆJN andˆxN represent the optimal value and an optimizer of the distributionally
robust program (5) with ambiguity setˆPN = BεN (βN )(ˆPN ),N ∈ N.
(i) If h (x,ξ) is upper semicontinuous in ξ and there exists L ≥ 0 with |h(x,ξ) |≤
L(1 +∥ξ∥) for all x ∈ X and ξ ∈ /Xi1, then P∞-almost surely we haveˆJN ↓ J⋆
as N →∞ where J ⋆ is the optimal value of (1).
(ii) If the assumptions of assertion (i) hold, X is closed, and h (x,ξ) is lower semi-
continuous in x for every ξ ∈ /Xi1, then any accumulation point of {ˆxN }N∈N is
P∞-almost surely an optimal solution for (1).
The proof of Theorem 3.6 will rely on the following technical lemma.
Lemma 3.7 (Convergence of distributions) If Assumption 3.3 holds andβN ∈ (0, 1),
N ∈ N, satisﬁes∑∞
N=1 βN < ∞ and limN→∞ εN (βN ) = 0, then, any sequence
ˆQN ∈ BεN (βN )(ˆPN ),N ∈ N, whereˆQN may depend on the training data, converges
under the Wasserstein metric (and thus weakly) toP almost surely with respect toP∞,
that is,
P∞
{
lim
N→∞
dW
(
P,ˆQN
)
= 0
}
= 1.
Proof AsˆQN ∈ BδN (ˆPN ), the triangle inequality for the Wasserstein metric ensures
that
dW
(
P,ˆQN
)
≤ dW
(
P,ˆPN
)
+ dW
(ˆPN ,ˆQN
)
≤ dW
(
P,ˆPN
)
+ εN (βN ).
Moreover, Theorem 3.4 implies that PN {dW
(
P,ˆPN
)
≤ εN (βN )}≥ 1 − βN , and
thus we have PN {dW
(
P,ˆQN
)
≤ 2εN (βN )}≥ 1 − βN .A s∑∞
N=1 βN < ∞,t h e
Borel–Cantelli Lemma [ 28, Theorem 2.18] further implies that
P∞{
dW
(
P,ˆQN
)
≤ εN (βN ) for all sufﬁciently large N
}
= 1.
Finally, as limN→∞ εN (βN ) = 0, we conclude that lim N→∞ dW
(
P,ˆQN
)
= 0a l m o s t
surely. Note that convergence with respect to the Wasserstein metric implies weak
convergence [10]. ⊓⊔
Proof of Theorem 3.6 AsˆxN ∈ X,w eh a v e J⋆ ≤ EP[h(ˆxN ,ξ) ]. Moreover, Theo-
rem 3.5 implies that
PN
{
J⋆ ≤ EP[h(ˆxN ,ξ) ]≤ˆJN
}
≥ PN{
P ∈ BεN (βN )(ˆPN )
}
≥ 1 − βN ,
2 A possible choice is βN = exp(−
√
N).
123
126 P . Mohajerin Esfahani, D. Kuhn
for all N ∈ N.A s∑∞
N=1 βN < ∞, the Borel–Cantelli Lemma further implies that
P∞
{
J⋆ ≤ EP[h(ˆxN ,ξ) ]≤ˆJN for all sufﬁciently large N
}
= 1.
To prove assertion (i), it thus remains to be shown that lim sup N→∞ˆJN ≤ J⋆ with
probability 1. Ash(x,ξ) is upper semicontinuous and grows at most linearly inξ , there
exists a non-increasing sequence of functions hk(x,ξ) , k ∈ N, such that h(x,ξ) =
limk→∞ hk(x,ξ) , and hk(x,ξ) is Lipschitz continuous in ξ for any ﬁxed x ∈ X and
k ∈ N with Lipschitz constant Lk ≥ 0; see Lemma A.1 in the appendix. Next, choose
any δ> 0, ﬁx a δ-optimal decision xδ ∈ X for ( 1) with EP[h(xδ,ξ) ]≤ J⋆ + δ, and
for every N ∈ N letˆQN ∈ˆPN be a δ-optimal distribution corresponding to xδ with
sup
Q∈ˆPN
EQ[h(xδ,ξ) ]≤ EQN [h(xδ,ξ) ]+ δ.
Then, we have
lim sup
N→∞
ˆJN ≤ lim sup
N→∞
sup
Q∈ˆPN
EQ[h(xδ,ξ) ]
≤ lim sup
N→∞
EˆQN [h(xδ,ξ) ]+ δ
≤ lim
k→∞
lim sup
N→∞
EˆQN [hk(xδ,ξ) ]+ δ
≤ lim
k→∞
lim sup
N→∞
(
EP[hk(xδ,ξ) ]+ Lk dW
(
P,ˆQN
))
+ δ
= lim
k→∞
EP[hk(xδ,ξ) ]+ δ, P∞-almost surely
= EP[h(xδ,ξ) ]+ δ ≤ J⋆+ 2δ,
where the second inequality holds because hk(x,ξ) converges from above to h(x,ξ) ,
and the third inequality follows from Theorem 3.2. Moreover, the almost sure equality
holds due to Lemma 3.7, and the last equality follows from the Monotone Conver-
gence Theorem [ 30, Theorem 5.5], which applies because |EP[hk(xδ,ξ) ]| < ∞.
Indeed, recall that P has an exponentially decaying tail due to Assumption 3.3 and
that hk(xδ,ξ) is Lipschitz continuous in ξ .A s δ> 0 was chosen arbitrarily, we thus
conclude that lim sup N→∞ˆJN ≤ J⋆.
To prove assertion (ii), ﬁx an arbitrary realization of the stochastic process{ˆξN }N∈N
such that J⋆ = limN→∞ˆJN and J⋆ ≤ EP[h(ˆxN ,ξ) ]≤ ˆJN for all sufﬁciently large
N . From the proof of assertion (i) we know that these two conditions are satisﬁed
P∞-almost surely. Using these assumptions, one easily veriﬁes that
lim inf
N→∞
EP[h(ˆxN ,ξ) ]≤ lim
N→∞
ˆJN = J⋆. (9)
Next, let x⋆ be an accumulation point of the sequence {ˆxN }N∈N, and note that x⋆ ∈ X
as X is closed. By passing to a subsequence, if necessary, we may assume without loss
of generality that x⋆ = limN→∞ˆxN . Thus,
123
Data-driven distributionally robust optimization using the… 127
J⋆ ≤ EP[h(x⋆,ξ) ]≤ EP[lim inf
N→∞
h(ˆxN ,ξ) ]≤ lim inf
N→∞
EP[h(ˆxN ,ξ) ]≤ J⋆,
where the ﬁrst inequality exploits that x⋆ ∈ X, the second inequality follows from the
lower semicontinuity of h(x,ξ) in x, the third inequality holds due to Fatou’s lemma
(which applies because h(x,ξ) grows at most linearly in ξ ), and the last inequality
follows from ( 9). Therefore, we have EP[h(x⋆,ξ) ]= J⋆. ⊓⊔
In the following we show that all assumptions of Theorem 3.6 are necessary for
asymptotic convergence, that is, relaxing any of these conditions can invalidate the
convergence result.
Example 1 (Necessity of regularity conditions)
(1) Upper semicontinuity of ξ ↦→ h(x,ξ) in Theorem 3.6 (i):
Set /Xi1=[ 0, 1], P = δ0 and h(x,ξ) = 1(0,1](ξ) , whereby J⋆ = 0. As P
concentrates unit mass at 0, we have ˆPN = δ0 = P irrespective of N ∈ N.
For any ε> 0, the Dirac distribution δε thus resides within the Wasserstein ball
Bε(ˆPN ). Hence,ˆJN fails to converge to J⋆ for ε → 0 because
ˆJN ≥ Eδε [h(x,ξ) ]= h(x,ε) = 1, ∀ε> 0.
(2) Linear growth of ξ ↦→ h(x,ξ) in Theorem 3.6 (i):
Set /Xi1= R, P = δ0 and h(x,ξ) = ξ 2, which implies that J⋆ = 0. Note that for
any ρ>ε , the two-point distribution Qρ = (1 − ε
ρ )δ0 + ε
ρ δρ is contained in the
Wasserstein ball Bε(ˆPN ) of radius ε> 0. Hence,ˆJN fails to converge to J⋆ for
ε → 0 because
ˆJN ≥ sup
ρ>ε
EQρ [h(x,ξ) ]= sup
ρ>ε
ερ =∞ , ∀ε> 0.
(3) Lower semicontinuity of x ↦→ h(x,ξ) in Theorem 3.6 (ii):
Set X =[ 0, 1] and h(x,ξ) = 1[0.5,1](x), whereby J⋆ = 0 irrespective of P.
As the objective is independent of ξ , the distributionally robust optimization
problem ( 5) is equivalent to ( 1). Then,ˆxN = N−1
2N is a sequence of minimizers
for (5) whose accumulation point x⋆ = 1
2 fails to be optimal in ( 1).
A convergence result akin to Theorem 3.6 for goodness-of-ﬁt-based ambiguity
sets is discussed in [ 7, Section 4]. This result is complementary to Theorem 3.6.
Indeed, Theorem 3.6(i) requires h(x,ξ) to be upper semicontinuous in ξ , which is
a necessary condition in our setting (see Example 1) that is absent in [ 7]. Moreover,
Theorem 3.6(ii) only requires h(x,ξ) to be lower semicontinuous in x, while [7]a s k s
for equicontinuity of this mapping. This stronger requirement provides a stronger
result, that is, the almost sure convergence of sup
Q∈ˆPN EQ[h(x,ξ) ] to EP[h(x,ξ) ]
uniformly in x on any compact subset of X.
Theorems 3.5 and 3.6 indicate that a careful a priori design of the Wasserstein ball
results in attractive ﬁnite sample and asymptotic guarantees for the distributionally
robust solutions. In practice, however, setting the Wasserstein radius to εN (β) yields
over-conservative solutions for the following reasons:
123
128 P . Mohajerin Esfahani, D. Kuhn
• Even though the constants c1 and c2 in ( 8) can be computed based on the proof
of [ 21, Theorem 2], the resulting Wasserstein ball is larger than necessary, i.e.,
P /∈ BεN (β)(ˆPN ) with probability ≪ β.
• Even if P /∈ BεN (β)(ˆPN ), the optimal valueˆJN of ( 5) may still provide an upper
bound on J⋆.
• The formula for εN (β) in ( 8) is independent of the training data. Allowing for
random Wasserstein radii, however, results in a more efﬁcient use of the available
training data.
While Theorems 3.5 and 3.6 provide strong theoretical justiﬁcation for using
Wasserstein ambiguity sets, in practice, it is prudent to calibrate the Wasserstein radius
via bootstrapping or cross-validation instead of using the conservative a priori bound
ε
N (β); see Sect. 7.2 for further details. A similar approach has been advocated in [ 7]
to determine the sizes of ambiguity sets that are constructed via goodness-of-ﬁt tests.
So far we have seen that the Wasserstein metric allows us to construct ambiguity sets
with favorable asymptotic and ﬁnite sample guarantees. In the remainder of the paper
we will further demonstrate that the distributionally robust optimization problem ( 5)
with a Wasserstein ambiguity set ( 6) is not signiﬁcantly harder to solve than the
corresponding SAA problem ( 4).
4 Solving worst-case expectation problems
We now demonstrate that the inner worst-case expectation problem in ( 5) over the
Wasserstein ambiguity set ( 6) can be reformulated as a ﬁnite convex program for
many loss functions h(x,ξ) of practical interest. For ease of notation, throughout this
section we suppress the dependence on the decision variable x. Thus, we examine a
generic worst-case expectation problem
sup
Q∈Bε(ˆPN )
EQ[
ℓ(ξ)
]
(10)
involving a decision-independent loss functionℓ(ξ):= maxk≤K ℓk(ξ) , which is deﬁned
as the pointwise maximum of more elementary measurable functions ℓk : Rm → R,
k ≤ K . The focus on loss functions representable as pointwise maxima is non-
restrictive unless we impose some structure on the functions ℓk . Many tractability
results in the remainder of this paper are predicated on the following convexity assump-
tion.
Assumption 4.1 (Convexity) The uncertainty set /Xi1⊆ R
m is convex and closed, and
the negative constituent functions −ℓk are proper, convex, and lower semicontinuous
for all k ≤ K . Moreover, we assume that ℓk is not identically −∞ on /Xi1for all ≤ K .
Assumption 4.1 essentially stipulates that ℓ(ξ) can be written as a maximum of
concave functions. As we will showcase in Sect. 5, this mild restriction does not sacri-
ﬁce much modeling power. Moreover, generalizations of this setting will be discussed
in Sect. 6. We proceed as follows. Sect. 4.1 addresses the reduction of ( 10) to a ﬁnite
convex program, while Sect. 4.2 describes a technique for constructing worst-case
distributions.
123
Data-driven distributionally robust optimization using the… 129
4.1 Reduction to a ﬁnite convex program
The worst-case expectation problem (10) constitutes an inﬁnite-dimensional optimiza-
tion problem over probability distributions and thus appears to be intractable. However,
we will now demonstrate that (10) can be re-expressed as a ﬁnite-dimensional convex
program by leveraging tools from robust optimization.
Theorem 4.2 (Convex reduction) If the convexity Assumption4.1 holds, then for any
ε ≥ 0 the worst-case expectation (10) equals the optimal value of the ﬁnite convex
program
⎧
⎪⎪
⎪
⎨
⎪⎪
⎪
⎩
inf
λ,si ,zik ,νik
λε + 1
N
N∑
i=1
si
s.t. [−ℓk]∗(zik − νik ) + σ/Xi1(νik ) −
⟨
zik ,ˆξi
⟩
≤ si ∀i ≤ N, ∀k ≤ K
∥zik ∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K.
(11)
Recall that [−ℓk]∗(zik − νik ) denotes the conjugate of −ℓk evaluated at zik − νik
and ∥zik ∥∗ the dual norm of zik . Moreover, χ/Xi1represents the characteristic function
of /Xi1and σ/Xi1its conjugate, that is, the support function of /Xi1.
Proof of Theorem 4.2 By using Deﬁnition 3.1 we can re-express the worst-case expec-
tation (10)a s
sup
Q∈Bε(ˆPN )
EQ[
ℓ(ξ)
]
=
⎧
⎪⎪⎪⎪
⎪
⎨
⎪⎪⎪⎪
⎪
⎩
sup
/Pi1,Q
∫
/Xi1ℓ(ξ)Q(dξ)
s.t.
∫
/Xi12 ∥ξ − ξ′∥/Pi1(dξ, dξ′) ≤ ε
{
/Pi1is a joint distribution of ξ and ξ′
with marginals Q andˆPN , respectively
=
⎧
⎪⎪
⎪
⎨
⎪⎪⎪⎩
sup
Qi ∈M(/Xi1)
1
N
N∑
i=1
∫
/Xi1ℓ(ξ)Qi(dξ)
s.t. 1
N
N∑
i=1
∫
/Xi1∥ξ −ˆξi∥Qi(dξ) ≤ ε.
The second equality follows from the law of total probability, which asserts that any
joint probability distribution /Pi1of ξ and ξ′ can be constructed from the marginal
distributionˆPN of ξ′and the conditional distributions Qi of ξ given ξ′=ˆξi , i ≤ N ,
that is, we may write /Pi1= 1
N
∑N
i=1 δˆξi ⊗ Qi . The resulting optimization problem
represents a generalized moment problem in the distributions Qi , i ≤ N .U s i n ga
standard duality argument, we obtain
123
130 P . Mohajerin Esfahani, D. Kuhn
sup
Q∈Bε(ˆPN )
EQ[
ℓ(ξ)
]
= sup
Qi ∈M(/Xi1)
inf
λ≥0
1
N
N∑
i=1
∫
/Xi1
ℓ(ξ)Qi(dξ)
+λ
(
ε − 1
N
N∑
i=1
∫
/Xi1
∥ξ −ˆξi∥Qi(dξ)
)
≤ inf
λ≥0
sup
Qi ∈M(/Xi1)
λε + 1
N
N∑
i=1
∫
/Xi1
(
ℓ(ξ)− λ∥ξ −ˆξi∥
)
Qi(dξ)
(12a)
= inf
λ≥0
λε + 1
N
N∑
i=1
sup
ξ∈/Xi1
(
ℓ(ξ)− λ∥ξ −ˆξi∥
)
, (12b)
where (12a) follows from the max-min inequality, and (12b) follows from the fact that
M(/Xi1)contains all the Dirac distributions supported on /Xi1. Introducing epigraphical
auxiliary variables si , i ≤ N , allows us to reformulate ( 12b)a s
⎧
⎪⎪⎪⎪
⎪
⎨
⎪⎪⎪⎪
⎪
⎩
inf
λ,si
λε + 1
N
N∑
i=1
si
s.t. sup
ξ∈/Xi1
(
ℓ(ξ)− λ∥ξ −ˆξi∥
)
≤ si ∀i ≤ N
λ ≥ 0
(12c)
=
⎧
⎪⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎩
inf
λ,si
λε + 1
N
N∑
i=1
si
s.t. sup
ξ∈/Xi1
(
ℓk(ξ) − max
∥zik ∥∗≤λ
⟨
zik ,ξ −ˆξi
⟩)
≤ si ∀i ≤ N, ∀k ≤ K
λ ≥ 0
(12d)
≤
⎧
⎪⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎩
inf
λ,si
λε + 1
N
N∑
i=1
si
s.t. min
∥zik ∥∗≤λ
sup
ξ∈/Xi1
(
ℓk(ξ) −
⟨
zik ,ξ −ˆξi
⟩)
≤ si ∀i ≤ N, ∀k ≤ K
λ ≥ 0.
(12e)
Equality (12d) exploits the deﬁnition of the dual norm and the decomposability ofℓ(ξ)
into its constituents ℓk(ξ) , k ≤ K . Interchanging the maximization over zik with the
minus sign (thereby converting the maximization to a minimization) and then with the
maximization over ξ leads to a restriction of the feasible set of ( 12d). The resulting
upper bound ( 12e) can be re-expressed as
123
Data-driven distributionally robust optimization using the… 131
⎧
⎪⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎩
inf
λ,si ,zik
λε + 1
N
N∑
i=1
si
s.t. sup
ξ∈/Xi1
(
ℓk(ξ) −
⟨
zik ,ξ
⟩)
+
⟨
zik ,ˆξi
⟩
≤ si ∀i ≤ N, ∀k ≤ K
∥zik ∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K
=
⎧
⎪⎪
⎪
⎨
⎪⎪
⎪
⎩
inf
λ,si ,zik
λε + 1
N
N∑
i=1
si
s.t. [−ℓk + χ/Xi1]∗(zik ) −
⟨
zik ,ˆξi
⟩
≤ si ∀i ≤ N, ∀k ≤ K
∥zik ∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K,
(12f)
where ( 12f) follows from the deﬁnition of conjugacy, our conventions of extended
arithmetic, and the substitution of zik with −zik . Note that ( 12f) is already a ﬁnite
convex program.
Next, we show that Assumption 4.1 reduces the inequalities ( 12a) and ( 12e)t o
equalities. Under Assumption 4.1, the inequality ( 12a) is in fact an equality for any
ε> 0 by virtue of an extended version of a well-known strong duality result for
moment problems [44, Proposition 3.4]. One can show that ( 12a) continues to hold as
an equality even for ε = 0, in which case the Wasserstein ambiguity set (6) reduces to
the singleton {ˆPN }, while ( 10) reduces to the sample average 1
N
∑N
i=1 ℓ(ˆξi). Indeed,
for ε = 0 the variable λ in ( 12b) can be increased indeﬁnitely at no penalty. As
ℓ(ξ) constitutes a pointwise maximum of upper semicontinuous concave functions,
an elementary but tedious argument shows that (12b) converges to the sample average
1
N
∑N
i=1 ℓ(ˆξi) as λ tends to inﬁnity.
The inequality ( 12e) also reduces to an equality under Assumption 4.1 thanks to
the classical minimax theorem [ 4, Proposition 5.5.4], which applies because the set
{zik ∈ Rm :∥ zik ∥∗ ≤ λ} is compact for any ﬁnite λ ≥ 0. Thus, the optimal values of
(10) and ( 12f) coincide.
Assumption 4.1 further implies that the function −ℓk + χ/Xi1is proper, convex and
lower semicontinuous. Properness holds because ℓk is not identically −∞ on /Xi1.
By Rockafellar and Wets [ 42, Theorem 11.23(a), p. 493], its conjugate essentially
coincides with the epi-addition (also known as inf-convolution) of the conjugates of
the functions −ℓk and σ/Xi1. Thus,
[−ℓk + χ/Xi1]∗(zik ) = infνik
(
[−ℓk]∗(zik − νik ) +[ χ/Xi1]∗(νik )
)
= cl
[
infνik
(
[−ℓk]∗(zik − νik ) + σ/Xi1(νik )
)]
,
where cl[·] denotes the closure operator that maps any function to its largest lower
semicontinuous minorant. As cl [ f (ξ)]≤ 0 if and only if f (ξ) ≤ 0 for any function
f , we may conclude that ( 12f) is indeed equivalent to ( 11) under Assumption 4.1. ⊓⊔
Note that the semi-inﬁnite inequality in ( 12c) generalizes the nonlinear uncertain
constraints studied in [ 1] because it involves an additional norm term and as the loss
function ℓ(ξ) is not necessarily concave under Assumption 4.1.A si n[ 1], however,
123
132 P . Mohajerin Esfahani, D. Kuhn
the semi-inﬁnite constraint admits a robust counterpart that involves the conjugate of
the loss function and the support function of the uncertainty set.
From the proof of Theorem 4.2 it is immediately clear that the worst-case expec-
tation ( 10) is conservatively approximated by the optimal value of the ﬁnite convex
program ( 12f)e v e ni fA s s u m p t i o n4.1 fails to hold. In this case the sum −ℓk + χ/Xi1
in ( 12f) must be evaluated under our conventions of extended arithmetics, whereby
∞−∞=∞ . These observations are formalized in the following corollary.
Corollary 4.3 [Approximate convex reduction] For anyε ≥ 0, the worst-case expec-
tation (10) is smaller or equal to the optimal value of the ﬁnite convex program(12f).
4.2 Extremal distributions
Stress test experiments are instrumental to assess the quality of candidate decisions
in stochastic optimization. Meaningful stress tests require a good understanding of
the extremal distributions from within the Wasserstein ball that achieve the worst-
case expectation ( 10) for various loss functions. We now show that such extremal
distributions can be constructed systematically from the solution of a convex program
akin to ( 11).
Theorem 4.4 (Worst-case distributions) If Assumption 4.1 holds, then the worst-case
expectation (10) coincides with the optimal value of the ﬁnite convex program
⎧
⎪⎪
⎪
⎪
⎪
⎪
⎪⎪⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪⎪⎩
sup
αik ,qik
1
N
N∑
i=1
K∑
k=1
αik ℓk
(ˆξi − qik
αik
)
s.t. 1
N
N∑
i=1
K∑
k=1
∥qik ∥≤ ε
K∑
k=1
αik = 1 ∀i ≤ N
αik ≥ 0 ∀i ≤ N, ∀k ≤ K
ˆξi − qik
αik ∈ /Xi1 ∀i ≤ N, ∀k ≤ K
(13)
irrespective ofε ≥ 0. Let
{
αik (r), qik (r)
}
r∈N be a sequence of feasible decisions whose
objective values converge to the supremum of (13). Then, the discrete probability
distributions
Qr := 1
N
N∑
i=1
K∑
k=1
αik (r)δξik (r) with ξik (r):=ˆξi − qik (r)
αik (r)
belong to the Wasserstein ballBε(ˆPN ) and attain the supremum of(10) asymptotically,
i.e.,
sup
Q∈Bε(ˆPN )
EQ[
ℓ(ξ)
]
= limr→∞ EQr
[
ℓ(ξ)
]
= lim
k→∞
1
N
N∑
i=1
K∑
k=1
αik (r)ℓ
(
ξik (r)
)
.
123
Data-driven distributionally robust optimization using the… 133
We highlight that all fractions in (13) must again be evaluated under our conventions
of extended arithmetics. Speciﬁcally, if αik = 0 and qik ̸= 0, then qik /αik has at least
one component equal to+∞ or −∞, which implies thatˆξi −qik /αik /∈ /Xi1. In contrast,
if αik = 0 and qik = 0, thenˆξi − qik /αik =ˆξi ∈ /Xi1. Moreover, the ik -th component
in the objective function of ( 13) evaluates to 0 whenever αik = 0 regardless of qik .
The proof of Theorem 4.4 is based on the following technical lemma.
Lemma 4.5 Deﬁne F : Rm × R+ → R through F (q,α) = infz∈Rm
⟨
z, q − αˆξ
⟩
+
α f ∗(z) for some proper, convex, and lower semicontinuous function f: Rm → R and
reference pointˆξ ∈ Rm . Then, F coincides with the (extended) perspective function
of the mapping q ↦→− f (ˆξ − q), that is,
F(q,α) =
{ −α f
(ˆξ − q/α
)
if α> 0,
−χ{0}(q) if α = 0.
Proof By construction, we have F(q, 0) = infz∈Rm
⟨
z, q
⟩
=− χ{0}(q).F o rα> 0, on
the other hand, the deﬁnition of conjugacy implies that
F(q,α) =− [α f ∗]∗(αˆξ − q) =− α[ f ∗]∗(ˆξ − q/α
)
.
The claim then follows because [ f ∗]∗ = f for any proper, convex, and lower semi-
continuous function f [4, Proposition 1.6.1(c)]. Additional information on perspective
functions can be found in [ 12, Section 2.2.3, p. 39]. ⊓⊔
Proof of Theorem 4.4 By Theorem 4.2, which applies under Assumption 4.1,t h e
worst-case expectation ( 10) coincides with the optimal value of the convex pro-
gram ( 11). From the proof of Theorem 4.2 we know that ( 11) is equivalent to ( 12f).
The Lagrangian dual of ( 12f) is given by
⎧
⎪⎪
⎪
⎨
⎪⎪
⎪
⎩
sup
βik ,αik
inf
λ,si ,zik
λε+
N∑
i=1
[
si
N +
K∑
k=1
[
βik
(
∥zik ∥∗ − λ
)
+αik
(
[−ℓk +χ/Xi1]∗(zik )−
⟨
zik ,ˆξi
⟩
−si
)]]
s.t. αik ≥ 0 ∀i ≤ N, ∀k ≤ K
βik ≥ 0 ∀i ≤ N, ∀k ≤ K,
where the products of dual variables and constraint functions in the objective are eval-
uated under the standard convention 0·∞ = 0. Strong duality holds since the function
[−ℓk + χ/Xi1]∗ is proper, convex, and lower semicontinuous under Assumption 4.1 and
because this function appears in a constraint of ( 12f) whose right-hand side is a free
decision variable. By explicitly carrying out the minimization over λ and si , one can
show that the above dual problem is equivalent to
123
134 P . Mohajerin Esfahani, D. Kuhn
⎧
⎪⎪
⎪
⎪⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪⎪⎪
⎪
⎩
sup
βik ,αik
infzik
N∑
i=1
K∑
k=1
βik ∥zik ∥∗+ αik [−ℓk + χ/Xi1]∗(zik ) − αik
⟨
zik ,ˆξi
⟩
s.t.
N∑
i=1
K∑
k=1
βik = ε
K∑
k=1
αik = 1
N ∀i ≤ N
αik ≥ 0 ∀i ≤ N, ∀k ≤ K
βik ≥ 0 ∀i ≤ N, ∀k ≤ K.
(14a)
By using the deﬁnition of the dual norm, ( 14a) can be re-expressed as
⎧
⎪⎪
⎪
⎪
⎪
⎪⎪⎪
⎪
⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪⎪⎪
⎪
⎩
sup
βik ,αik
infzik
N∑
i=1
K∑
k=1
max
∥qik ∥≤βik
⟨
zik , qik
⟩
+ αik [−ℓk + χ/Xi1]∗(zik ) − αik
⟨
zik ,ˆξi
⟩]
s.t.
N∑
i=1
K∑
k=1
βik = ε
K∑
k=1
αik = 1
N ∀i ≤ N
αik ≥ 0 ∀i ≤ N, ∀k ≤ K
βik ≥ 0 ∀i ≤ N, ∀k ≤ K
(14b)
=
⎧
⎪⎪
⎪
⎪
⎪⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪⎪⎪
⎪
⎪
⎩
sup
βik ,αik
max
∥qik ∥≤βik
infzik
N∑
i=1
K∑
k=1
⟨
zik , qik
⟩
+ αik [−ℓk + χ/Xi1]∗(zik ) − αik
⟨
zik ,ˆξi
⟩
s.t.
N∑
i=1
K∑
k=1
βik = ε
K∑
k=1
αik = 1
N ∀i ≤ N
αik ≥ 0 ∀i ≤ N, ∀k ≤ K
βik ≥ 0 ∀i ≤ N, ∀k ≤ K,
(14c)
where ( 14c) follows from the classical minimax theorem and the fact that the qik
variables range over a non-empty and compact feasible set for any ﬁnite ε;s e e[ 4,
Proposition 5.5.4]. Eliminating the βik variables and using Lemma 4.5 allows us to
reformulate (14c)a s
123
Data-driven distributionally robust optimization using the… 135
⎧
⎪⎪
⎪
⎪
⎪⎪⎪
⎪
⎪
⎪
⎨
⎪⎪⎪
⎪
⎪
⎪
⎪⎪⎪
⎪
⎩
sup
αik ,qik
infzik
N∑
i=1
K∑
k=1
⟨
zik , qik − αikˆξi
⟩
+ αik [−ℓk + χ/Xi1]∗(zik )
s.t.
N∑
i=1
K∑
k=1
∥qik ∥≤ ε
K∑
k=1
αik = 1
N ∀i ≤ N
αik ≥ 0 ∀i ≤ N, ∀k ≤ K
(14d)
=
⎧
⎪⎪⎪
⎪
⎪
⎪
⎪
⎪⎪⎪
⎨
⎪⎪
⎪
⎪⎪⎪
⎪
⎪
⎪
⎪
⎩
sup
αik ,qik
N∑
i=1
K∑
k=1
−αik
(
− ℓk
(ˆξi − qik
αik
)
+ χ/Xi1
(ˆξi − qik
αik
))
1{αik >0} − χ{0}(qik )1{αik =0}
s.t.
N∑
i=1
K∑
k=1
∥qik ∥≤ ε
K∑
k=1
αik = 1
N ∀i ≤ N
αik ≥ 0 ∀i ≤ N, ∀k ≤ K.
(14e)
Our conventions of extended arithmetics imply that the ik -th term in the objective
function of problem ( 14e) simpliﬁes to
αik ℓk
(
ˆξi − qik
αik
)
− χ/Xi1
(
ˆξi − qik
αik
)
. (14f)
Indeed, for αik > 0, this identity trivially holds. For αik = 0, on the other hand, the
ik -th objective term in ( 14e) reduces to −χ{0}(qik ). Moreover, the ﬁrst term in ( 14f)
vanishes wheneverαik = 0 regardless of qik , and the second term in (14f) evaluates to
0i f qik = 0( a s0/0 = 0 andˆξi ∈ /Xi1) and to −∞ if qik ̸= 0( a sqik /0 has at least one
inﬁnite component, implying thatˆξi + qik /0 /∈ /Xi1). Therefore, ( 14f) also reduces to
−χ{0}(qik ) when αik = 0. This proves that the ik -th objective term in (14e) coincides
with (14f). Substituting (14f)i n t o(14e) and re-expressing −χ/Xi1
(ˆξi − qik
αik
)
in terms of
an explicit hard constraint yields
⎧
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪⎪⎪
⎨
⎪⎪
⎪⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎩
sup
αik ,qik
N∑
i=1
K∑
k=1
αik ℓk
(ˆξi − qik
αik
)
s.t.
N∑
i=1
K∑
k=1
∥qik ∥≤ ε
K∑
k=1
αik = 1
N ∀i ≤ N
αik ≥ 0 ∀i ≤ N, ∀k ≤ K
ˆξi − qik
αik ∈ /Xi1 ∀i ≤ N, ∀k ≤ K.
(14g)
Finally, replacing
{
αik , qik
}
with 1
N
{
αik , qik
}
shows that ( 14g) is equivalent to ( 13).
This completes the ﬁrst part of the proof.
123
136 P . Mohajerin Esfahani, D. Kuhn
As for the second claim, let {αik (r), qik (r)}r∈N be a sequence of feasible solutions
that attains the supremum in ( 13), and set ξik (r):=ˆξi − qik (r)
αik (r) ∈ /Xi1. Then, the discrete
distribution
/Pi1r := 1
N
N∑
i=1
K∑
k=1
αik (r)δ(
ξik (r),ˆξi
)
has the distribution Qr deﬁned in the theorem statement and the empirical distribution
ˆPN as marginals. By the deﬁnition of the Wasserstein metric, /Pi1r represents a feasible
mass transportation plan that provides an upper bound on the distance between ˆPN
and Qr ; see Deﬁnition 3.1. Thus, we have
dW
(
Qr ,ˆPN
)
≤
∫
/Xi12
∥ξ − ξ′∥/Pi1r (dξ, dξ′) = 1
N
N∑
i=1
K∑
k=1
αik (r)
ξik (r)
−ˆξi
= 1
N
N∑
i=1
K∑
k=1
qik (r)
≤ ε,
where the last inequality follows readily from the feasibility of qik (r) in ( 13). We
conclude that
sup
Q∈Bε(ˆPN )
EQ[
ℓ(ξ)
]
≥ lim sup
k→∞
EQr
[
ℓ(ξ)
]
= lim sup
k→∞
1
N
N∑
i=1
K∑
k=1
αik (r)ℓ
(
ξik (r)
)
≥ lim sup
k→∞
1
N
N∑
i=1
K∑
k=1
αik (r)ℓk
(
ξik (r)
)
= sup
Q∈Bε(ˆPN )
EQ[
ℓ(ξ)
]
,
where the ﬁrst inequality holds as Qr ∈ Bε(ˆPN ) for all k ∈ N, and the second
inequality uses the trivial estimate ℓ ≥ ℓk for all k ≤ K . The last equality follows
from the construction of αik (r) and ξik (r) and the fact that ( 13) coincides with the
worst-case expectation (10). ⊓⊔
In the rest of this section we discuss some notable properties of the convex
program (13).
In the ambiguity-free limit, that is, when the radius of the Wasserstein ball is set to
zero, then the optimal value of the convex program ( 13) reduces to the expected loss
under the empirical distribution. Indeed, for ε = 0a l lqik variables are forced to zero,
and αik enters the objective only through∑K
k=1 αik = 1
N . Thus, the objective function
of ( 13) simpliﬁes to EˆPN [ℓ(ξ)].
We further emphasize that it is not possible to guarantee the existence of a worst-case
distribution that attains the supremum in ( 10). In general, as shown in Theorem 4.4,
we can only construct a sequence of distributions that attains the supremum asymptot-
ically. The following example discusses an instance of ( 10) that admits no worst-case
distribution.
123
Data-driven distributionally robust optimization using the… 137
Fig. 1 Example of a worst-case expectation problem without a worst-case distribution
Example 2 (Non-existence of a worst-case distribution) Assume that /Xi1= R, N = 1,
ˆξ1 = 0, K = 2, ℓ1(ξ) = 0 and ℓ2(ξ) = ξ − 1. In this case we haveˆPN = δ{0}, and
problem (13) reduces to
sup
Q∈Bε(δ0)
EQ[
ℓ(ξ)
]
=
⎧
⎪⎪
⎪
⎪
⎨
⎪⎪⎪
⎪
⎩
sup
α1 j ,q1 j
−q12 − α12
s.t. |q11|+| q12|≤ ε
α11 + α12 = 1
α11 ≥ 0,α 12 ≥ 0.
The supremum on the right-hand side amounts to ε and is attained, for instance, by the
sequence α11(r) = 1 − 1
k , α12(r) = 1
k , q11(r) = 0, q12(r) =− ε for k ∈ N. Deﬁne
Qr = α11(r)δξ11(r) + α12(r)δξ12(r),
with ξ11(r) =ˆξ1 − q11(r)
α11(r) = 0, and ξ12(r) =ˆξ1 − q12(r)
α12(r) = εk. By Theorem 4.4,
the two-point distributions Qr reside within the Wasserstein ball of radius ε around
δ0 and asymptotically attain the supremum in the worst-case expectation problem.
However, this sequence has no weak limit as ξ12(r) = εk tends to inﬁnity, see Fig. 1.
In fact, no single distribution can attain the worst-case expectation. Assume for the
sake of contradiction that there exists Q
⋆ ∈ Bε(δ0) with EQ⋆
[ℓ(ξ)]= ε. Then, we ﬁnd
ε = EQ⋆
[ℓ(ξ)] < EQ⋆
[|ξ|] ≤ ε, where the strict inequality follows from the relation
ℓ(ξ) <|ξ| for all ξ ̸= 0 and the observation that Q⋆ ̸= δ0, while the second inequality
follows from Theorem 3.2. Thus, Q⋆ does not exist.
The existence of a worst-case distribution can, however, be guaranteed in some
special cases.
Corollary 4.6 (Existence of a worst-case distribution) Suppose that Assumption 4.1
holds. If the uncertainty set/Xi1is compact or the loss function is concave (i.e., K= 1),
then the sequence{αik (r), ξik (r)}r∈N constructed in Theorem4.4 has an accumulation
point {α⋆
ik ,ξ ⋆
ik }, and
123
138 P . Mohajerin Esfahani, D. Kuhn
(a) (b) (c)
Fig. 2 Representative distributions in balls centered at ˆPN induced by different metrics. ( a) Empirical
distribution on a training dataset with N = 2 samples. (b) A representative discrete distribution in the total
variation or the Kullback–Leiber ball. ( c) A representative discrete distribution in the Wasserstein ball
Q⋆:= 1
N
N∑
i=1
K∑
k=1
α⋆
ik δξ⋆
ik
is a worst-case distribution achieving the supremum in (10).
Proof If /Xi1is compact, then the sequence {αik (r), ξik (r)}r∈N has a converging subse-
quence with limit {α⋆
ik ,ξ ⋆
ik }. Similarly, if K = 1, then αi1 = 1 for all i ≤ N , in which
case ( 13) reduces to a convex optimization problem with an upper semicontinuous
objective function over a compact feasible set. Hence, its supremum is attained at a
point {α⋆
ik ,ξ ⋆
ik }. In both cases, Theorem 4.4 guarantees that the distribution Q⋆ implied
by {α⋆
ik ,ξ ⋆
ik } achieves the supremum in ( 10). ⊓⊔
The worst-case distribution of Corollary 4.6 is discrete, and its atoms ξ⋆
ik reside in
the neighborhood of the given data pointsˆξi . By the constraints of problem ( 13), the
probability-weighted cumulative distance between the atoms and the respective data
points amounts to
N∑
i=1
K∑
k=1
αik ∥ξ⋆
ik −ˆξi∥=
N∑
i=1
K∑
k=1
∥qik ∥≤ ε,
which is bounded above by the radius of the Wasserstein ball. The fact that the
worst-case distribution Q⋆ (if it exists) is supported outside ofˆ/Xi1N is a key feature dis-
tinguishing the Wasserstein ball from the ambiguity sets induced by other probability
metrics such as the total variation distance or the Kullback–Leibler divergence; see
Fig. 2. Thus, the worst-case expectation criterion based on Wasserstein balls advo-
cated in this paper should appeal to decision makers who wish to immunize their
optimization problems against perturbations of the data points.
Remark 4.7 (Weak coupling) We highlight that the convex program (13) is amenable
to decomposition and parallelization techniques as the decision variables associated
with different sample points are only coupled through the norm constraint. We expect
the resulting scenario decomposition to offer a substantial speedup of the solution
times for problems involving large datasets. Efﬁcient decomposition algorithms that
could be used for solving the convex program ( 13) are described, for example, in [ 35]
and [5, Chapter 4].
123
Data-driven distributionally robust optimization using the… 139
5 Special loss functions
We now demonstrate that the convex optimization problems ( 11) and ( 13) reduce
to computationally tractable conic programs for several loss functions of practical
interest.
5.1 Piecewise afﬁne loss functions
We ﬁrst investigate the worst-case expectations of convex and concave piecewise afﬁne
loss functions, which arise, for example, in option pricing [ 8], risk management [ 34]
and in generic two-stage stochastic programming [6]. Moreover, piecewise afﬁne func-
tions frequently serve as approximations of smooth convex or concave loss functions.
Corollary 5.1 (Piecewise afﬁne loss functions) Suppose that the uncertainty set is
a polytope, that is, /Xi1={ ξ ∈ Rm : Cξ ≤ d} where C is a matrix and d a vector of
appropriate dimensions. Moreover, consider the afﬁne functions ak(ξ):=
⟨
ak,ξ
⟩
+ bk
for all k ≤ K.
(i) If ℓ(ξ) = maxk≤K ak(ξ), then the worst-case expectation (10) evaluates to
⎧
⎪⎪
⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎪
⎩
inf
λ,si ,γik
λε + 1
N
N∑
i=1
si
s.t. bk +
⟨
ak,ˆξi
⟩
+
⟨
γik , d − Cˆξi
⟩
≤ si ∀i ≤ N, ∀k ≤ K
∥C⊺γik − ak∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K
γik ≥ 0 ∀i ≤ N, ∀k ≤ K.
(15a)
(ii) If ℓ(ξ) = mink≤K ak(ξ), then the worst-case expectation (10) evaluates to
⎧
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪⎪⎪
⎨
⎪⎪
⎪⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎩
inf
λ,si ,γi ,θi
λε + 1
N
N∑
i=1
si
s.t.
⟨
θi, b + Aˆξi
⟩
+
⟨
γi, d − Cˆξi
⟩
≤ si ∀i ≤ N
∥C⊺γi − A⊺θi∥∗ ≤ λ ∀i ≤ N⟨
θi, e
⟩
= 1 ∀i ≤ N
γi ≥ 0 ∀i ≤ N
θi ≥ 0 ∀i ≤ N,
(15b)
where A is the matrix with rows a ⊺
k ,k ≤ K , b is the column vector with entries
bk ,k ≤ K , and e is the vector of all ones.
Proof Assertion (i) is an immediate consequence of Theorem 4.2, which applies
because ℓ(x) is the pointwise maximum of the afﬁne functions ℓk(ξ) = ak(ξ) , k ≤ K ,
and thus Assumption 4.1 holds for J = K . By deﬁnition of the conjugacy operator,
123
140 P . Mohajerin Esfahani, D. Kuhn
we have
[−ℓk]∗(z) =[ −ak]∗(z) = sup
ξ
⟨
z,ξ
⟩
+
⟨
ak,ξ
⟩
+ bk =
{ bk if z =− ak,
∞ else,
and
σ/Xi1(ν) =
⎧
⎨
⎩
sup
ξ
⟨
ν,ξ
⟩
s.t. Cξ ≤ d
=
{ inf
γ≥0
⟨
γ, d
⟩
s.t. C⊺γ = ν,
where the last equality follows from strong duality, which holds as the uncertainty
set is non-empty. Assertion (i) then follows by substituting the above expressions into
(11).
Assertion (ii) also follows directly from Theorem 4.2 because ℓ(ξ) = ℓ1(ξ) =
mink≤K a j(ξ) is concave and thus satisﬁes Assumption 4.1 for J = 1. In this setting,
we ﬁnd
[−ℓ]∗(z) = sup
ξ
⟨
z,ξ
⟩
+ min
k≤K
{⟨
ak,ξ
⟩
+ bk
}
=
⎧
⎨
⎩
sup
ξ,τ
⟨
z,ξ
⟩
+ τ
s.t. Aξ + b ≥ τe
=
⎧
⎪⎪⎨
⎪⎪⎩
inf
θ≥0
⟨
θ, b
⟩
s.t. A⊺θ =− z⟨
θ, e
⟩
= 1
where the last equality follows again from strong linear programming duality, which
holds since the primal maximization problem is feasible. Assertion (ii) then follows
by substituting [−ℓ]
∗ as well as the formula for σ/Xi1from the proof of assertion (i) into
(11). ⊓⊔
As a consistency check, we ascertain that in the ambiguity-free limit, the optimal
value of ( 15a) reduces to the expectation of max k≤K ak(ξ) under the empirical distri-
bution. Indeed, for ε = 0, the variable λ can be set to any positive value at no penalty.
For this reason and because all training samples must belong to the uncertainty set
(i.e., d − Cˆξi ≥ 0 for all i ≤ N ), it is optimal to set γik = 0. This in turn implies
that si = maxk≤K ak(ˆξi) at optimality, in which case 1
N
∑N
i=1 si represents the sample
average of the convex loss function at hand.
An analogous argument shows that, for ε = 0, the optimal value of ( 15b) reduces
to the expectation of min k≤K ak(ξ) under the empirical distribution. As before, λ can
be increased at no penalty. Thus, we conclude that γi = 0 and
si = min
θi ≥0
{⟨
θi, b + Aˆξi
⟩
:
⟨
θi, e
⟩
= 1
}
= min
k≤K
ak(ˆξi)
at optimality, in which case 1
N
∑N
i=1 si is the sample average of the given concave loss
function.
123
Data-driven distributionally robust optimization using the… 141
5.2 Uncertainty quantiﬁcation
A problem of great practical interest is to ascertain whether a physical, economic or
engineering system with an uncertain state ξ satisﬁes a number of safety constraints
with high probability. In the following we denote by A the set of states in which the
system is safe. Our goal is to quantify the probability of the event ξ ∈ A (ξ/∈ A)
under an ambiguous state distribution that is only indirectly observable through a ﬁnite
training dataset. More precisely, we aim to calculate the worst-case probability of the
system being unsafe, i.e.,
sup
Q∈Bε(ˆPN )
Q [ξ/∈ A] , (16a)
as well as the best-case probability of the system being safe, that is,
sup
Q∈Bε(ˆPN )
Q [ξ ∈ A] . (16b)
Remark 5.2 (Data-dependent sets) The set A may even depend on the samples
ˆξ1,...,ˆξN , in which case A is renamed asˆA. If the Wasserstein radius ε is set to
εN (β), then we have P ∈ Bε(ˆPN ) with probability 1 − β, implying that ( 16a) and
(16b) still provide 1 − β conﬁdence bounds on P[ξ/∈ˆA] and P[ξ ∈ˆA], respectively.
Corollary 5.3 (Uncertainty quantiﬁcation) Suppose that the uncertainty set is a poly-
tope of the form /Xi1={ ξ ∈ Rm : Cξ ≤ d} as in Corollary 5.1.
(i) If A ={ ξ ∈ Rm : Aξ< b} is an open polytope and the halfspace
{
ξ :
⟨
ak,ξ
⟩
≥
bk
}
has a nonempty intersection with /Xi1for any k ≤ K , where ak is the k-th
row of the matrix A and b k is the k-th entry of the vector b, then the worst-case
probability (16a) is given by
⎧
⎪⎪⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪⎪⎪
⎪
⎩
inf
λ,si ,γik ,θik
λε + 1
N
N∑
i=1
si
s.t. 1 − θik
(
bk −
⟨
ak,ˆξi
⟩)
+
⟨
γik , d − Cˆξi
⟩
≤ si ∀i ≤ N, ∀k ≤ K
∥akθik − C⊺γik ∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K
γik ≥ 0 ∀i ≤ N, ∀k ≤ K
θik ≥ 0 ∀i ≤ N, ∀k ≤ K
si ≥ 0 ∀i ≤ N.
(17a)
(ii) If A ={ ξ ∈ Rm : Aξ ≤ b} is a closed polytope that has a nonempty intersection
with /Xi1, then the best-case probability (16b) is given by
123
142 P . Mohajerin Esfahani, D. Kuhn
⎧
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪⎨
⎪⎪
⎪
⎪
⎪⎪⎪
⎪
⎪
⎪
⎪
⎩
inf
λ,si ,γi ,θi
λε + 1
N
N∑
i=1
si
s.t. 1 +
⟨
θi, b − Aˆξi
⟩
+
⟨
γi, d − Cˆξi
⟩
≤ si ∀i ≤ N
∥A⊺θi + C⊺γi∥∗ ≤ λ ∀i ≤ N
γi ≥ 0 ∀i ≤ N
θi ≥ 0 ∀i ≤ N
si ≥ 0 ∀i ≤ N.
(17b)
Proof The uncertainty quantiﬁcation problems ( 16a) and ( 16b) can be interpreted as
instances of ( 10) with loss functions ℓ= 1 − 1A and ℓ= 1A, respectively. In order
to be able to apply Theorem 4.2, we should represent these loss functions as ﬁnite
maxima of concave functions as shown in Fig. 3.
Formally, assertion (i) follows from Theorem 4.2 for a loss function with K + 1
pieces if we use the following deﬁnitions. For every k ≤ K we deﬁne
ℓk(ξ) =
{
1i f
⟨
ak,ξ
⟩
≥ bk,
−∞ otherwise.
Moreover, we deﬁne ℓK+1(ξ) = 0. As illustrated in Fig. 3a, we thus have ℓ(ξ) =
maxk≤K+1 ℓk(ξ) = 1 − 1A(ξ) and
sup
Q∈Bε(ˆPN )
Q [ξ/∈ A] = sup
Q∈Bε(ˆPN )
EQ [ℓ(ξ)].
Assumption 4.1 holds due to the postulated properties of A and /Xi1. In order to apply
Theorem 4.2, we must determine the support function σ/Xi1, which is already known
from Corollary 5.1, as well as the conjugate functions of −ℓk , k ≤ K + 1. A standard
duality argument yields
[−ℓk]∗(z) =
⎧
⎨
⎩
sup
ξ
⟨
z,ξ
⟩
+ 1
s.t.
⟨
ak,ξ
⟩
≥ bk
=
{ inf
θ≥0
1 − bkθ
s.t. akθ =− z,
for all k ≤ K . Moreover, we have [−ℓK+1]∗ = 0i f ξ = 0; =∞ otherwise. Asser-
tion (ii) then follows by substituting the formulas for [−ℓk]∗, k ≤ K + 1, and σ/Xi1into
(11).
Assertion (ii) follows from Theorem 4.2 by setting K = 2, ℓ1(ξ) = 1−χA(ξ) and
ℓ2(ξ) = 0. As illustrated in Fig. 3b, this implies that ℓ(ξ) = max{ℓ1(ξ), ℓ2(ξ)}=
1A(ξ) and
sup
Q∈Bε(ˆPN )
Q [ξ ∈ A] = sup
Q∈Bε(ˆPN )
EQ [ℓ(ξ)].
Assumption 4.1 holds by our assumptions on A and /Xi1. In order to apply Theorem 4.2,
we thus have to determine the support function σ/Xi1, which was already calculated in
123
Data-driven distributionally robust optimization using the… 143
(a) (b)
Fig. 3 Representing the indicator function of a convex set and its complement as a pointwise maximum
of concave functions. ( a) Indicator function of the unsafe set. ( b) Indicator function of the safe set
Corollary 5.1, and the conjugate functions of −ℓ1 and −ℓ2. By the deﬁnition of the
conjugacy operator, we ﬁnd
[−ℓ1]∗(z) = sup
ξ∈A
⟨
z,ξ
⟩
+ 1 =
⎧
⎨
⎩
sup
ξ
⟨
z,ξ
⟩
+ 1
s.t. Aξ ≤ b
=
{ inf
θk≥0
⟨
θ, b
⟩
+ 1
s.t. A⊺θ = z
where the last equality follows from strong linear programming duality, which holds
as the safe set is non-empty. Similarly, we ﬁnd [−ℓ2]∗ = 0i f ξ = 0; =∞ otherwise.
Assertion (ii) then follows by substituting the above expressions into ( 11). ⊓⊔
In the ambiguity-free limit (i.e., for ε = 0) the optimal value of (17a) reduces to the
fraction of training samples residing outside of the open polytope A ={ ξ : Aξ< b}.
Indeed, in this case the variableλ can be set to any positive value at no penalty. For this
reason and because all training samples belong to the uncertainty set (i.e., d −Cˆξi ≥ 0
for all i ≤ N ), it is optimal to set γik = 0. If the i-th training sample belongs to A (i.e.,
bk −
⟨
ak,ˆξi
⟩
> 0 for all k ≤ K ), then θik ≥ 1/(bk −
⟨
ak,ˆξi
⟩
) for all k ≤ K and si = 0
at optimality. Conversely, if the i-th training sample belongs to the complement of A,
(i.e., bk −
⟨
ak,ˆξi
⟩
≤ 0f o rs o m ek ≤ K ), then θik = 0f o rs o m ek ≤ K and si = 1a t
optimality. Thus,∑N
i=1 si coincides with the number of training samples outside of
A at optimality. An analogous argument shows that, for ε = 0, the optimal value of
(17b) reduces to the fraction of training samples residing inside of the closed polytope
A ={ ξ : Aξ ≤ b}.
5.3 Two-stage stochastic programming
A major challenge in linear two-stage stochastic programming is to evaluate the
expected recourse costs, which are only implicitly deﬁned as the optimal value of a lin-
ear program whose coefﬁcients depend linearly on the uncertain problem parameters
[46, Section 2.1]. The following corollary shows how we can evaluate the worst-case
expectation of the recourse costs with respect to an ambiguous parameter distribution
that is only observable through a ﬁnite training dataset. For ease of notation and without
loss of generality, we suppress here any dependence on the ﬁrst-stage decisions.
Corollary 5.4 (Two-stage stochastic programming) Suppose that the uncertainty set
is a polytope of the form /Xi1={ ξ ∈ R
m : Cξ ≤ d} as in Corollaries 5.1 and 5.3.
123
144 P . Mohajerin Esfahani, D. Kuhn
(i) If ℓ(ξ) = inf y
{⟨
y, Qξ
⟩
: Wy ≥ h
}
is the optimal value of a parametric linear
program with objective uncertainty, and if the feasible set {y : Wy ≥ h} is
non-empty and compact, then the worst-case expectation (10) is given by
⎧
⎪⎪
⎪
⎪
⎪⎪⎪
⎪
⎨
⎪⎪⎪⎪
⎪
⎪
⎪
⎪
⎩
inf
λ,si ,γi ,yi
λε + 1
N
N∑
i=1
si
s.t.
⟨
yi, Qˆξi
⟩
+
⟨
γi, d − Cˆξi
⟩
≤ si ∀i ≤ N
Wy i ≥ h ∀i ≤ N
∥Q⊺ yi − C⊺γi∥∗ ≤ λ ∀i ≤ N
γi ≥ 0 ∀i ≤ N.
(18a)
(ii) If ℓ(ξ) = inf y
{⟨
q, y
⟩
: Wy ≥ Hξ + h
}
is the optimal value of a parametric
linear program with right-hand side uncertainty, and if the dual feasible set
{θ ≥ 0 : W⊺θ = q} is non-empty and compact with vertices vk ,k ≤ K , then the
worst-case expectation (10) is given by
⎧
⎪⎪
⎪
⎪
⎪
⎪⎨
⎪⎪
⎪
⎪
⎪
⎪⎩
inf
λ,si ,γik
λε + 1
N
N∑
i=1
si
s.t.
⟨
vk, h
⟩
+
⟨
H⊺vk,ˆξi
⟩
+
⟨
γik , d − Cˆξi
⟩
≤ si ∀i ≤ N, ∀k ≤ K
∥C⊺γik − H⊺vk∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K
γik ≥ 0 ∀i ≤ N, ∀k ≤ K.
(18b)
Proof Assertion (i) follows directly from Theorem 4.2 because ℓ(ξ) is concave as
an inﬁmum of linear functions in ξ . Indeed, the compactness of the feasible set {y :
Wy ≥ h} ensures that Assumption 4.1 holds for K = 1. In this setting, we ﬁnd
[−ℓ]∗(z) = sup
ξ
{⟨
z,ξ
⟩
+ infy
{⟨
y, Qξ
⟩
: Wy ≥ h
}}
= infy
{
sup
ξ
{⟨
z + Q⊺ y,ξ
⟩}
: Wy ≥ h
}
=
{ 0 if there exists y with Q⊺ y =− z and Wy ≥ h,
∞ otherwise,
where the second equality follows from the classical minimax theorem [4, Proposition
5.5.4], which applies because {y : Wy ≥ h} is compact. Assertion (i) then follows by
substituting [−ℓ]∗ as well as the formula for σ/Xi1from Corollary 5.1 into (11).
Assertion (ii) relies on the following reformulation of the loss function,
ℓ(ξ) =
{ infy
⟨
q, y
⟩
s.t. Wy ≥ Hξ + h
=
⎧
⎨
⎩
sup
θ≥0
⟨
θ, Hξ + h
⟩
s.t. W⊺θ = q
= max
k≤K
⟨
vk, Hξ + h
⟩
= max
k≤K
⟨
H⊺vk,ξ
⟩
+
⟨
vk, h
⟩
,
123
Data-driven distributionally robust optimization using the… 145
where the ﬁrst equality holds due to strong linear programming duality, which applies
as the dual feasible set is non-empty. The second equality exploits the elementary
observation that the optimal value of a linear program with non-empty, compact fea-
sible set is always adopted at a vertex. As we managed to express ℓ(ξ) as a pointwise
maximum of linear functions, assertion (ii) follows immediately from Corllary 5.1 (i).
⊓⊔
As expected, in the ambiguity-free limit, problem (18a) reduces to a standard SAA
problem. Indeed, for ε = 0, the variable λ can be made large at no penalty, and thus
γ
i = 0 and si =
⟨
yi, Qˆξi
⟩
at optimality. In this case, problem ( 18a) is equivalent to
infyi
{
1
N
N∑
i=1
⟨
yi, Qˆξi
⟩
: Wy i ≥ h ∀i ≤ N
}
.
Similarly, one can verify that for ε = 0, (18b) reduces to the SAA problem
infyi
{
1
N
N∑
i=1
⟨
yi, q
⟩
: Wy i ≥ Hˆξi ∀i ≤ N
}
.
We close this section with a remark on the computational complexity of all the
convex optimization problems derived in this section.
Remark 5.5 (Computational tractability) ⊓⊔
• If the Wasserstein metric is deﬁned in terms of the 1-norm (i.e., ∥ξ∥=∑m
k=1 |ξk|)
or the ∞-norm (i.e., ∥ξ∥= maxk≤m |ξk|), then the optimization problems ( 15a),
(15b), ( 17a), ( 17b), ( 18a) and ( 18b) all reduce to linear programs whose sizes
scale with the number N of data points and the number J of afﬁne pieces of the
underlying loss functions.
• Except for the two-stage stochastic program with right-hand side uncertainty in
(18b), the resulting linear programs scale polynomially in the problem description
and are therefore computationally tractable. As the number of vertices vk , k ≤ K ,
of the polytope {θ ≥ 0 : W⊺θ = q} may be exponential in the number of its
facets, however, the linear program ( 18b) has generically exponential size.
• Inspecting ( 15a), one easily veriﬁes that the distributionally robust optimization
problem ( 5) reduces to a ﬁnite convex program if X is convex and h(x,ξ) =
maxk≤K
⟨
ak(x), ξ
⟩
+ bk(x), while the gradients ak(x) and the intercepts bk(x)
depend linearly on x. Similarly, ( 5) can be reformulated as a ﬁnite convex pro-
gram if X is convex and h(x,ξ) = inf y
{⟨
y, Qξ
⟩
: Wy ≥ h(x)
}
or h(x,ξ) =
inf y
{⟨
q, y
⟩
: Wy ≥ H(x)ξ + h(x)
}
, while the right hand side coefﬁcients h(x)
and H(x) depend linearly on x;s e e( 18a) and ( 18b), respectively. In contrast,
problems (15b), (17a) and (17b) result in non-convex optimization problems when
their data depends on x.
• We emphasize that the computational complexity of all convex programs examined
in this section is independent of the radius ε of the Wasserstein ball.
123
146 P . Mohajerin Esfahani, D. Kuhn
6 Tractable extensions
We now demonstrate that through minor modiﬁcations of the proofs, Theorems 4.2
and 4.4 extend to worst-case expectation problems involving even richer classes of
loss functions. First, we investigate problems where the uncertainty can be viewed as a
stochastic process and where the loss function is additively separable. Next, we study
problems whose loss functions are convex in the uncertain variables and are therefore
not necessarily representable as ﬁnite maxima of concave functions as postulated by
Assumption 4.1.
6.1 Stochastic processes with a separable cost
Consider a variant of the worst-case expectation problem ( 10), where the uncertain
parameters can be interpreted as a stochastic process ξ =
(
ξ
1,...,ξ T
)
, and assume
that ξt ∈ /Xi1t , where /Xi1t ⊆ Rm is non-empty and closed for any t ≤ T . Moreover,
assume that the loss function is additively separable with respect to the temporal
structure of ξ , that is,
ℓ(ξ):=
T∑
t=1
max
k≤K
ℓtk
(
ξt
)
, (19)
where ℓtk : Rm → R is a measurable function for any k ≤ K and t ≤ T . Such loss
functions appear, for instance, in open-loop stochastic optimal control or in multi-item
newsvendor problems. Consider a process norm ∥ξ∥T =∑T
t=1 ∥ξt∥ associated with
the base norm ∥·∥ on Rm , and assume that its induced metric is the one used in the
deﬁnition of the Wasserstein distance. Note that if ∥·∥ is the 1-norm on Rm , then ∥·∥T
reduces to the 1-norm on RmT .
By interchanging summation and maximization, the loss function ( 19) can be re-
expressed as
ℓ(ξ) = max
kt ≤K
T∑
t=1
ℓtkt
(
ξt
)
,
where the maximum runs over all K T combinations of k1,..., kT ≤ K . Under this
representation, Theorem 4.2 remains applicable. However, the resulting convex opti-
mization problem would involveO(K T ) decision variables and constraints, indicating
that an efﬁcient solution may not be available. Fortunately, this deﬁciency can be over-
come by modifying Theorem 4.2.
Theorem 6.1 (Convex reduction for separable loss functions) Assume that the loss
function ℓis of the form (19), and the Wasserstein ball is deﬁned through the process
norm ∥·∥
T. Then, for any ε ≥ 0, the worst-case expectation (10) is smaller or equal
to the optimal value of the ﬁnite convex program
123
Data-driven distributionally robust optimization using the… 147
⎧
⎪⎪
⎪⎨
⎪⎪
⎪
⎩
inf
λ,sti ,ztik ,νtik
λε + 1
N
N∑
i=1
T∑
t=1
sti
s.t. [−ℓtk ]∗(
ztik − νtik
)
+ σ/Xi1t (νtik ) −
⟨
ztik ,ˆξti
⟩
≤ sti ∀i ≤ N, ∀k ≤ K, ∀t ≤ T,
∥ztik ∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K, ∀t ≤ T.
(20)
If /Xi1t and {ℓtk }k≤K satisfy the convexity Assumption 4.1 for every t ≤ T , then the
worst-case expectation (10) coincides exactly with the optimal value of problem(20).
Proof Up until equation (12d), the proof of Theorem6.1 parallels that of Theorem 4.2.
Starting from ( 12d), we then have
sup
Q∈Bε(ˆPN )
EQ[
ℓ(ξ)
]
= inf
λ≥0
λε + 1
N
N∑
i=1
sup
ξ
(
ℓ(ξ)− λ
ξ −ˆξi

T
)
= inf
λ≥0
λε + 1
N
N∑
i=1
T∑
t=1
sup
ξt ∈/Xi1t
(
max
k≤K
ℓtk
(
ξt
)
− λ
ξt −ˆξti

)
,
where the interchange of the summation and the maximization is facilitated by the
separability of the overall loss function. Introducing epigraphical auxiliary variables
yields
⎧
⎪⎪⎪⎪
⎨
⎪⎪
⎪⎪⎩
inf
λ,sti
λε + 1
N
N∑
i=1
T∑
t=1
sti
s.t. sup
ξt ∈/Xi1t
(
ℓtk
(
ξt
)
− λ
ξt −ˆξti

)
≤ sti ∀i ≤ N, ∀k ≤ K, ∀t ≤ T
λ ≥ 0
≤
⎧
⎪⎪
⎪
⎪⎪⎨
⎪⎪
⎪
⎪⎪⎩
inf
λ,sti ,ztik
λε + 1
N
N∑
i=1
T∑
t=1
sti
s.t. sup
ξt ∈/Xi1t
(
ℓtk
(
ξt
)
−
⟨
ztik ,ξ t
⟩)
+
⟨
ztik ,ˆξti
⟩
≤ sti ∀i ≤ N, ∀k ≤ K, ∀t ≤ T
∥ztik ∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K, ∀t ≤ T
=
⎧
⎪⎪
⎪
⎨
⎪⎪
⎪
⎩
inf
λ,sti ,ztik
λε + 1
N
N∑
i=1
T∑
t=1
sti
s.t. [−ℓtk + χ/Xi1t ]∗(
− ztik
)
+
⟨
ztik ,ˆξti
⟩
≤ sti ∀i ≤ N, ∀k ≤ K, ∀t ≤ T
∥ztik ∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K, ∀t ≤ T,
where the inequality is justiﬁed in a similar manner as the one in ( 12e), and it holds
as an equality provided that /Xi1t and {ℓtk }k≤K satisfy Assumption 4.1 for all t ≤ T .
Finally, by Rockafellar and Wets [ 42, Theorem 11.23(a),p. 493], the conjugate of
−ℓtk +χ/Xi1t can be replaced by the inf-convolution of the conjugates of −ℓtk and χ/Xi1t .
This completes the proof. ⊓⊔
123
148 P . Mohajerin Esfahani, D. Kuhn
Note that the convex program ( 20) involves only O(NKT ) decision variables and
constraints. Moreover, ifℓtk is afﬁne for every t ≤ T and k ≤ K , while ∥·∥represents
the 1-norm or the ∞-norm on Rm , then ( 20) reduces to a tractable linear program
(see also Remark 5.5). A natural generalization of Theorem 4.4 further allows us to
characterize the extremal distributions of the worst-case expectation problem (10) with
a separable loss function of the form ( 19).
Theorem 6.2 (Worst-case distributions for separable loss functions) Assume that the
loss function ℓ is of the form (19), and the Wasserstein ball is deﬁned through the
process norm ∥·∥T.I f /Xi1t and {ℓtk }k≤K satisfy Assumption 4.1 for all t ≤ T , then
the worst-case expectation (10) coincides with the optimal value of the ﬁnite convex
program
⎧
⎪⎪
⎪
⎪⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪⎪⎪
⎪
⎪
⎪
⎩
sup
αtik ,qtik
1
N
N∑
i=1
K∑
k=1
T∑
t=1
αtik ℓtk
(
ˆξti − qtik
αtik
)
s.t. 1
N
N∑
i=1
K∑
k=1
T∑
t=1
∥qtik ∥≤ ε
K∑
k=1
αtik = 1 ∀i ≤ N, ∀t ≤ T
αtik ≥ 0 ∀i ≤ N, ∀t ≤ T, ∀k ≤ K
ˆξti − qtik
αtik ∈ /Xi1t ∀i ≤ N, ∀t ≤ T, ∀k ≤ K
(21)
irrespective of ε ≥ 0. Let
{
αtik (r), qtik (r)
}
r∈N be a sequence of feasible decisions
whose objective values converge to the supremum of(21). Then, the discrete (product)
probability distributions
Qr := 1
N
N∑
i=1
T⨂
t=1
( K∑
k=1
αtik (r)δξtik (r)
)
with ξtik (r):=ˆξti − qtik (r)
αtik (r)
belong to the Wasserstein ballBε(ˆPN ) and attain the supremum of(10) asymptotically,
i.e.,
sup
Q∈Bε(ˆPN )
EQ[
ℓ(ξ)
]
= limr→∞ EQr
[
ℓ(ξ)
]
= limr→∞
1
N
N∑
i=1
K∑
k=1
T∑
t=1
αtik (r)ℓtk
(
ξtik (r)
)
.
Proof As in the proof of Theorem 4.4, the claim follows by dualizing the convex
program (20). Details are omitted for brevity of exposition. ⊓⊔
We emphasize that the distributions Qr from Theorem 6.2 can be constructed efﬁ-
ciently by solving a convex program of polynomial size even though they have NK T
discretization points.
123
Data-driven distributionally robust optimization using the… 149
6.2 Convex loss functions
Consider now another variant of the worst-case expectation problem ( 10), where the
loss function ℓ is proper, convex and lower semicontinuous. Unless ℓ is piecewise
afﬁne, we cannot represent such a loss function as a pointwise maximum of ﬁnitely
many concave functions, and thus Theorem 4.2 may only provide a loose upper bound
on the worst-case expectation ( 10). The following theorem provides an alternative
upper bound that admits new insights into distributionally robust optimization with
Wasserstein balls and becomes exact for /Xi1= Rm .
Theorem 6.3 (Convex reduction for convex loss functions) Assume that the loss
function ℓis proper, convex, and lower semicontinuous, and deﬁne κ:= sup
{
∥θ∥∗ :
ℓ∗(θ) < ∞
}
. Then, for anyε ≥ 0, the worst-case expectation(10) is smaller or equal
to
κε + 1
N
N∑
i=1
ℓ(ˆξi). (22)
If /Xi1= Rm , then the worst-case expectation (10) coincides exactly with (22).
Remark 6.4 (Radius of effective domain) The parameterκ can be viewed as the radius
of the smallest ball containing the effective domain of the conjugate function ℓ∗ in
terms of the dual norm. By the standard conventions of extended arithmetic, the term
κε in (22) is interpreted as 0 if κ =∞ and ε = 0.
Proof Equation (12b) in the proof of Theorem 4.2 implies that
sup
Q∈Bε(ˆPN )
EQ[
ℓ(ξ)
]
= inf
λ≥0
λε + 1
N
N∑
i=1
sup
ξ∈/Xi1
(
ℓ(ξ)− λ∥ξ −ˆξi∥
)
(23)
for every ε> 0. As ℓis proper, convex, and lower semicontinuous, it coincides with
its bi-conjugate function ℓ∗∗, see e.g. [ 4, Proposition 1.6.1(c)]. Thus, we may write
ℓ(ξ) = sup
θ∈/Theta1
⟨
θ,ξ
⟩
− ℓ∗(θ),
where /Theta1:={θ ∈ Rm : ℓ∗(θ) < ∞} denotes the effective domain of the conjugate
function ℓ∗. Using this dual representation of ℓin conjunction with the deﬁnition of
the dual norm, we ﬁnd
sup
ξ∈/Xi1
(
ℓ(ξ)− λ∥ξ −ˆξi∥
)
= sup
ξ∈/Xi1
sup
θ∈/Theta1
(⟨
θ,ξ
⟩
− ℓ∗(θ) − λ∥ξ −ˆξi∥
)
= sup
ξ∈/Xi1
sup
θ∈/Theta1
inf
∥z∥∗≤λ
(⟨
θ,ξ
⟩
− ℓ∗(θ) +
⟨
z,ξ
⟩
−
⟨
z,ˆξi
⟩)
.
The classical minimax theorem [ 4, Proposition 5.5.4] then allows us to interchange
the maximization over ξ with the maximization over θ and the minimization over z to
obtain
123
150 P . Mohajerin Esfahani, D. Kuhn
sup
ξ∈/Xi1
(
ℓ(ξ)− λ∥ξ −ˆξi∥
)
= sup
θ∈/Theta1
inf
∥z∥∗≤λ
sup
ξ∈/Xi1
(⟨
θ + z,ξ
⟩
− ℓ∗(θ) −
⟨
z,ˆξi
⟩)
= sup
θ∈/Theta1
inf
∥z∥∗≤λ
σ/Xi1(θ + z) − ℓ∗(θ) −
⟨
z,ˆξi
⟩
. (24)
Recall that σ/Xi1denotes the support function of /Xi1. It seems that there is no simple
exact reformulation of ( 24) for arbitrary convex uncertainty sets /Xi1. Interchanging
the maximization over θ with the minimization over z in ( 24) would lead to the
conservative upper bound of Corollary 4.3. Here, however, we employ an alternative
approximation. By deﬁnition of the support function, we have σ/Xi1≤ σRm = χ{0}.
Replacing σ/Xi1with χ{0} in (24) thus results in the conservative approximation
sup
ξ∈Rm
(
ℓ(ξ)− λ∥ξ −ˆξi∥
)
≤
{
ℓ(ˆξi) if sup
{
∥θ∥∗ : θ ∈ /Theta1
}
≤ λ,
∞ otherwise. (25)
The inequality ( 22) then follows readily by substituting ( 25)i n t o(23) and using the
deﬁnition of κ in the theorem statement. For /Xi1= Rm we have σ/Xi1= χ{0}, and thus
the upper bound ( 22) becomes exact. Finally, if ε = 0, then ( 10) trivially coincides
with (22) under our conventions of extended arithmetic. Thus, the claim follows. ⊓⊔
Theorem 6.3 asserts that for /Xi1= Rm , the worst-case expectation ( 10) of a convex
loss function reduces the sample average of the loss adjusted by the simple correction
term κε . The following proposition highlights that κ can be interpreted as a measure
of maximum steepness of the loss function. This interpretation has intuitive appeal in
view of Deﬁnition 3.1.
Proposition 6.5 (Steepness of the loss function) Let κ be deﬁned as in Theorem6.3.
(i) If ℓis
L-Lipschitz continuous, i.e., if there existsξ′∈ Rm such thatℓ(ξ)−ℓ(ξ′) ≤
L∥ξ − ξ′∥for all ξ ∈ Rm , then κ ≤ L.
(ii) If ℓmajorizes an afﬁne function, i.e., if there exists θ ∈ Rm with ∥θ∥∗ =: L and
ξ′∈ Rm such that ℓ(ξ)− ℓ(ξ′) ≥
⟨
θ,ξ − ξ′⟩
for all ξ ∈ Rm , then κ ≥ L.
Proof The proof follows directly from the deﬁnition of conjugacy. As for (i), we have
ℓ∗(θ) = sup
ξ∈Rm
⟨
θ,ξ
⟩
− ℓ(ξ) ≥ sup
ξ∈Rm
⟨
θ,ξ
⟩
− L∥ξ − ξ′∥− ℓ(ξ′)
= sup
ξ∈Rm
inf
∥z∥∗≤L
⟨
θ,ξ
⟩
−
⟨
z,ξ − ξ′⟩
− ℓ(ξ′),
where the last equality follows from the deﬁnition of the dual norm. Applying the
minimax theorem [4, Proposition 5.5.4] and explicitly carrying out the maximization
over ξ yields
123
Data-driven distributionally robust optimization using the… 151
ℓ∗(θ) ≥
{⟨
θ,ξ ′⟩
− ℓ(ξ′) if ∥θ∥∗ ≤ L,
∞ otherwise.
Consequently,ℓ∗(θ) is inﬁnite for all θ with ∥θ∥∗ > L, which readily implies that the
∥·∥∗-ball of radius L contains the effective domain of ℓ∗. Thus, κ ≤ L.
As for (ii), we have
ℓ∗(θ) = sup
ξ∈Rm
⟨
θ,ξ
⟩
− ℓ(ξ) ≤ sup
ξ∈Rm
⟨
θ,ξ
⟩
−
⟨
z,ξ − ξ′⟩
− ℓ(ξ′)
= σRm (θ − z) +
⟨
z,ξ ′⟩
− ℓ(ξ′),
which implies that ℓ∗(θ) ≤
⟨
θ,ξ ′⟩
− ℓ(ξ′)< ∞. Thus, θ belongs to the effective
domain of ℓ∗. We then conclude that κ ≥∥θ∥∗ = L. ⊓⊔
Remark 6.6 (Consistent formulations) If /Xi1= Rm and the loss function is given
by ℓ(ξ) = maxk≤K {
⟨
ak,ξ
⟩
+ bk}, then both Corollary 5.1 and Theorem 6.3 offer an
exact reformulation of the worst-case expectation (10) in terms of a ﬁnite-dimensional
convex program. On the one hand, Corollary 5.1 implies that ( 10) is equivalent to
⎧
⎪⎨
⎪⎩
min
λ
λε + 1
N
N∑
i=1
ℓ(ˆξi)
s.t. ∥ak∥∗ ≤ λ ∀k ≤ K,
which is obtained by setting C = 0 and d = 0i n( 15a). At optimality we have
λ⋆ = maxk≤K ∥ak∥∗, which corresponds to the (best) Lipschitz constant of ℓ(ξ) with
respect to the norm∥·∥. On the other hand, Theorem6.3 implies that (10) is equivalent
to (22) with κ = λ⋆. Thus, Corollary 5.1 and Theorem 6.3 are consistent.
Remark 6.7 (ε-insensitive optimizers3) Consider a loss function h(x,ξ) that is con-
vex in ξ , and assume that /Xi1= Rm . In this case Theorem 6.3 remains valid, but the
steepness parameter κ(x) may depend on x. For loss functions whose Lipschitz mod-
ulus with respect to ξ is independent of x (e.g., the newsvendor loss), however, κ(x)
is constant. In this case the distributionally robust optimization problem ( 5) and the
SAA problem ( 4) share the same minimizers irrespective of the Wasserstein radius ε.
This phenomenon could explain why the SAA solutions tend to display a surprisingly
strong out-of-sample performance in these problems.
7 Numerical results
We validate the theoretical results of this paper in the context of a stylized portfolio
selection problem. The subsequent simulation experiments are designed to provide
additional insights into the performance guarantees of the proposed distributionally
robust optimization scheme.
3 We are indepted to Vishal Gupta who has brought this interesting observation to our attention.
123
152 P . Mohajerin Esfahani, D. Kuhn
7.1 Mean-risk portfolio optimization
Consider a capital market consisting of m assets whose yearly returns are captured
by the random vector ξ =[ ξ1,...,ξ m]⊺. If short-selling is forbidden, a portfolio
is encoded by a vector of percentage weights x =[ x1,..., xm]⊺ ranging over the
probability simplex X ={ x ∈ Rm
+ :∑m
i=1 xi = 1}. As portfolio x invests a percentage
xi of the available capital in asset i for each i = 1,..., m, its return amounts to
⟨
x,ξ
⟩
.
In the remainder we aim to solve the single-stage stochastic program
J⋆ = inf
x∈X
{
EP[
−
⟨
x,ξ
⟩]
+ ρ P-CV aRα
(
−
⟨
x,ξ
⟩)}
, (26)
which minimizes a weighted sum of the mean and the conditional value-at-risk (CV aR)
of the portfolio loss −
⟨
x,ξ
⟩
, where α ∈ (0, 1] is referred to as the conﬁdence level of
the CV aR, and ρ ∈ R+ quantiﬁes the investor’s risk-aversion. Intuitively, the CV aR
at level α represents the average of the α × 100% worst (highest) portfolio losses
under the distribution P. Replacing the CV aR in the above expression with its formal
deﬁnition [ 41], we obtain
J⋆ = inf
x∈X
{
EP[
−
⟨
x,ξ
⟩]
+ ρ inf
τ∈R
EP
[
τ + 1
α max
{
−
⟨
x,ξ
⟩
− τ, 0
}]}
= inf
x∈X,τ∈R
EP
[
max
k≤K
ak
⟨
x,ξ
⟩
+ bkτ
]
,
where K = 2, a1 =− 1, a2 =− 1 − ρ
α , b1 = ρ and b2 = ρ(1 − 1
α ). An investor who
is unaware of the distribution P but has observed a datasetˆ/Xi1N of N historical samples
from P and knows that the support ofP is contained in/Xi1={ ξ ∈ Rm : Cξ ≤ d} might
solve the distributionally robust counterpart of ( 26) with respect to the Wasserstein
ambiguity set Bε(ˆPN ), that is,
ˆJN (ε):= inf
x∈X,τ∈R
sup
Q∈Bε(ˆPN )
EQ
[
max
k≤K
ak
⟨
x,ξ
⟩
+ bkτ
]
,
where we make the dependence on the Wasserstein radius ε explicit. By Corollary 5.1
we know that
ˆJN (ε) =
⎧
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪
⎨
⎪⎪
⎪
⎪
⎪
⎪
⎪
⎪⎩
inf
x,τ,λ,si ,γik
λε + 1
N
N∑
i=1
si
s.t. x ∈ X
bkτ + ak
⟨
x,ˆξi
⟩
+
⟨
γik , d − Cˆξi
⟩
≤ si ∀i ≤ N, ∀k ≤ K
∥C⊺γik − ak x∥∗ ≤ λ ∀i ≤ N, ∀k ≤ K
γik ≥ 0 ∀i ≤ N, ∀k ≤ K.
(27)
123
Data-driven distributionally robust optimization using the… 153
Before proceeding with the numerical analysis of this problem, we provide some
analytical insights into its optimal solutions when there is signiﬁcant ambiguity. In
what follows we keep the training data set ﬁxed and let ˆxN (ε) be an optimal distri-
butionally robust portfolio corresponding to the Wasserstein ambiguity set of radius
ε. We will now show that, for natural choices of the ambiguity set, ˆxN (ε) converges
to the equally weighted portfolio 1
m e as ε tends to inﬁnity, where e:=(1,..., 1)⊺.
The optimality of the equally weighted portfolio under high ambiguity has ﬁrst been
demonstrated in [ 37] using analytical methods. We identify this result here as an
immediate consequence of Theorem 4.2, which is primarily a computational result.
For any non-empty set S ⊆ Rm we denote by recc (S):={y ∈ Rm : x + λy ∈
S ∀x ∈ S, ∀λ ≥ 0} the recession cone and by S◦:={y ∈ Rm :
⟨
y, x
⟩
≤ 0 ∀x ∈ S} the
polar cone of S.
Lemma 7.1 If {εk}k∈N ⊂ R+ tends to inﬁnity, then any accumulation point x ⋆ of{
ˆxN (εk)
}
k∈N is a portfolio that has minimum distance to (recc(/Xi1))◦ with respect to
∥·∥∗.
Proof Note ﬁrst thatˆxN (εk), k ∈ N, and x⋆ exist because X is compact. For large
Wasserstein radii ε,t h et e r mλε dominates the objective function of problem ( 27).
Using standard epi-convergence results [ 42, Section 7.E], one can thus show that
x⋆ ∈ arg min
x∈X
min
γik ≥0
max
i≤N, k≤K
∥C⊺γik − ak x∥∗
= arg min
x∈X
max
i≤N, k≤K
min
γ≥0
∥C⊺γ +| ak| x∥∗
= arg min
x∈X
min
γ≥0
∥C⊺γ + x∥∗ max
k≤K
|ak|
= arg min
x∈X
min
γ≥0
∥C⊺γ + x∥∗,
where the ﬁrst equality follows from the fact that ak < 0 for all k ≤ K , the second
equality uses the substitution γ → γ|ak|, and the last equality holds because the set
of minimizers of an optimization problem is not affected by a positive scaling of the
objective function. Thus, x⋆ is the portfolio nearest to the cone C ={ C⊺γ : γ ≥ 0}.
The claim now follows as the polar cone
C◦:= {y ∈ Rm : y⊺x ≤ 0 ∀x ∈ C}={ y ∈ Rm : y⊺C⊺γ ≤ 0 ∀γ ≥ 0}
={ y ∈ Rm : Cy ≥ 0}
is readily recognized as the recession cone of /Xi1and as C = (C◦)◦. ⊓⊔
Proposition 7.2 (Equally weighted portfolio) Assume that the Wasserstein metric
is deﬁned in terms of the p-norm in the uncertainty space for some p ∈[ 1,∞).I f
{εk}k∈N ⊂ R+ tends to inﬁnity, then
{
ˆxN (εk)
}
k∈N converges to the equally weighted
portfolio x⋆ = 1
m e provided that the uncertainty set is given by
(i) the entire space, i.e., /Xi1= Rm ,o r
123
154 P . Mohajerin Esfahani, D. Kuhn
ε
10-3 10-2 10-1 100
Average portfolio weights0
0.2
0.4
0.6
0.8
1
(a)
ε
10-3 10-2 10-1 100
Average portfolio weights0
0.2
0.4
0.6
0.8
1
(b)
ε
10-3 10-2 10-1 100
Average portfolio weights0
0.2
0.4
0.6
0.8
1
(c)
Fig. 4 Optimal portfolio composition as a function of the Wasserstein radius ε averaged over 200 simula-
tions; the portfolio weights are depicted in ascending order, i.e., the weight of asset 1 at the bottom (dark
blue area) and that of asset 10 at the top (dark red area). (a) N = 30 training samples. (b) N = 300 training
samples. (c) N = 3000 training samples (color ﬁgure online)
(ii) the nonnegative orthant shifted by −e, i.e., /Xi1={ ξ ∈ Rm : ξ ≥− e},w h i c h
captures the idea that no asset can lose more than 100% of its value.
Proof (i) One easily veriﬁes from the deﬁnitions that (recc(/Xi1))◦ ={ 0}. Moreover, we
have ∥·∥∗ =∥·∥ q where 1
p + 1
q = 1. As p ∈[ 1,∞), we conclude that q ∈ (1,∞],
and thus the unique nearest portfolio to (recc(/Xi1))◦ with respect to ∥·∥∗ is x⋆ = 1
m e.
The claim then follows from Lemma 7.1. Assertion (ii) follows in a similar manner
from the observation that (recc(/Xi1))◦ is now the non-positive orthant. ⊓⊔
With some extra effort one can show that for every p ∈[ 1,∞) there is a threshold
¯ε> 0 withˆxN (ε) = x⋆ for all ε ≥¯ε,s e e[37, Proposition 3]. Moreover, for p ∈{ 1, 2}
the threshold ¯ε is known analytically.
7.2 Simulation results: portfolio optimization
Our experiments are based on a market with m = 10 assets considered in [ 7, Sec-
tion 7.5]. In view of the capital asset pricing model we may assume that the return ξi
is decomposable into a systematic risk factor ψ ∼ N(0, 2%) common to all assets
and an unsystematic or idiosyncratic risk factor ζi ∼ N(i × 3%, i × 2.5%) speciﬁc
to asset i. Thus, we set ξi = ψ + ζi , where ψ and the idiosyncratic risk factors
ζi , i = 1,..., m, constitute independent normal random variables. By construction,
assets with higher indices promise higher mean returns at a higher risk. Note that the
given moments of the risk factors completely determine the distribution P of ξ .T h i s
distribution has support /Xi1= Rm and satisﬁes Assumption 3.3 for the tail exponent
a = 1, say. We also setα = 20% and ρ = 10 in all numerical experiments, and we use
the 1-norm to measure distances in the uncertainty space. Thus, ∥·∥∗ is the ∞-norm,
whereby (27) reduces to a linear program.
7.2.1 Impact of the Wasserstein radius
In the ﬁrst experiment we investigate the impact of the Wasserstein radius ε on the
optimal distributionally robust portfolios and their out-of-sample performance. We
123
Data-driven distributionally robust optimization using the… 155
10-4 10-3 10-2 10-1
-1.4
-1.3
-1.2
-1.1
-1
-0.9
0
.2
.4
.6
.8
1
(a)
10-4 10-3 10-2 10-1
-1.4
-1.3
-1.2
-1.1
-1
-0.9
0
.2
.4
.6
.8
1
(b)
10-4 10-3 10-2 10-1
-1.4
-1.3
-1.2
-1.1
-1
-0.9
0
.2
.4
.6
.8
1
(c)
Fig. 5 Out-of-sample performance J(ˆxN (ε)) (left axis , solid line and shaded area ) and reliability
PN [J(ˆxN (ε)) ≤ˆJN (ε)] (right axis , dashed line ) as a function of the Wasserstein radius ε and esti-
mated on the basis of 200 simulations. ( a) N = 30 training samples. ( b) N = 300 training samples. ( c)
N = 3000 training samples
solve problem ( 27) using training datasets of cardinality N ∈{ 30, 300, 3000}.F i g -
ure 4 visualizes the corresponding optimal portfolio weights ˆxN (ε) as a function of
ε, averaged over 200 independent simulation runs. Our numerical results conﬁrm the
theoretical insight of Proposition 7.2 that the optimal distributionally robust portfolios
converge to the equally weighted portfolio as the Wasserstein radius ε increases; see
also [37].
The out-of-sample performance
J
(
ˆxN (ε)
)
:= EP[
−
⟨
ˆxN (ε), ξ
⟩]
+ ρ P-CV aRα
(
−
⟨
ˆxN (ε), ξ
⟩)
of any ﬁxed distributionally robust portfolioˆxN (ε) can be computed analytically as P
constitutes a normal distribution by design, see, e.g., [ 41, p. 29]. Figure 5 shows the
tubes between the 20 and 80% quantiles (shaded areas) and the means (solid lines)
of the out-of-sample performance J
(
ˆxN (ε)
)
as a function of ε—estimated using 200
independent simulation runs. We observe that the out-of-sample performance improves
(decreases) up to a critical Wasserstein radius εcrit and then deteriorates (increases).
This stylized fact was observed consistently across all of simulations and provides an
empirical justiﬁcation for adopting a distributionally robust approach.
Figure 5 also visualizes the reliability of the performance guarantees offered by
our distributionally robust portfolio model. Speciﬁcally, the dashed lines represent the
empirical probability of the event J
(
ˆx
N (ε)
)
≤ˆJN (ε) with respect to 200 independent
training datasets. We ﬁnd that the reliability is nondecreasing in ε. This observation
has intuitive appeal becauseˆJN (ε) ≥ J(ˆxN (ε)) whenever P ∈ Bε(ˆPN ), and the latter
event becomes increasingly likely asε grows. Figure 5 also indicates that the certiﬁcate
guarantee sharply rises towards 1 near the critical Wasserstein radius εcrit. Hence,
the out-of-sample performance of the distributionally robust portfolios improves as
long as the reliability of the performance guarantee is noticeably smaller than 1 and
deteriorates when it saturates at 1. Even though this observation was made consistently
across all simulations, we were unable to validate it theoretically.
7.2.2 Portfolios driven by out-of-sample performance
Different Wasserstein radiiε may result in robust portfoliosˆx
N (ε) with vastly different
out-of-sample performance J(ˆxN (ε)). Ideally, one should select the radiusˆε opt
N that
123
156 P . Mohajerin Esfahani, D. Kuhn
minimizes J(ˆxN (ε)) over all ε ≥ 0; note thatˆε opt
N inherits the dependence on the
training data from J(ˆxN (ε)). As the true distribution P is unknown, however, it is
impossible to evaluate and minimize J(ˆxN (ε)). In practice, the best we can hope for
is to approximateˆε opt
N using the training data. Statistics offers several methods to
accomplish this goal:
• Holdout method: Partitionˆξ1,...,ˆξN into a training dataset of size NT and a
validation dataset of sizeNV = N −NT . Using only the training dataset, solve (27)
for a large but ﬁnite number of candidate radiiε to obtainˆxNT (ε). Use the validation
dataset to estimate the out-of-sample performance ofˆxNT (ε) via the sample average
approximation. Setˆε hm
N to any ε that minimizes this quantity. Report ˆx hm
N =
ˆxNT (ˆε hm
N ) as the data-driven solution andˆJ hm
N =ˆJNT (ˆε hm
N ) as the corresponding
certiﬁcate.
• k-fold cross validation: Partitionˆξ1,...,ˆξN into k subsets, and run the holdout
method k times. In each run, use exactly one subset as the validation dataset and
merge the remaining k − 1 subsets to a training dataset. Setˆε cv
N to the average of
the Wasserstein radii obtained from the k holdout runs. Resolve (27) with ε =ˆε cv
N
using all N samples, and reportˆx cv
N =ˆxN (ˆε cv
N ) as the data-driven solution and
ˆJ cv
N =ˆJN (ˆε cv
N ) as the corresponding certiﬁcate.
The holdout method is computationally cheaper, but cross validation has superior
statistical properties. There are several other methods to estimate the best Wassertein
radiusˆε opt
N . By construction, however, no method can provide a radius ˆεN such that
ˆxN (ˆεN ) has a better out-of-sample performance thanˆxN (ˆε opt
N ).
In all experiments we compare the distributionally robust approach based on the
Wasserstein ambiguity set with the classical sample average approximation (SAA)
and with a state-of-the-art data-driven distributionally robust approach, where the
ambiguity set is deﬁned via a linear-convex ordering (LCX)-based goodness-of-ﬁt
test [7, Section 3.3.2]. The size of the LCX ambiguity set is determined by a single
parameter, which should be tuned to optimize the out-of-sample performance. While
the best parameter value is unavailable, it can again be estimated using the holdout
method or via cross validation. To our best knowledge, the LCX approach represents
the only existing data-driven distributionally robust approach for continuous uncer-
tainty spaces that enjoys strong ﬁnite-sample guarantees, asymptotic consistency as
well as computational tractability.
4
To keep the computational burden manageable, in all experiments we select the
Wasserstein radius as well as the LCX size parameter from within the discrete set
E ={ ε = b · 10
c : b ∈{ 0,..., 9}, c ∈{ − 3,−2,−1}} instead of R+.W eh a v e
veriﬁed that reﬁning or extending E has only a marginal impact on our results, which
indicates that E provides a sufﬁciently rich approximation of R+.
In Fig. 6a–c the sizes of the (LCX and Wasserstein) ambiguity sets are determined
via the holdout method, where 80% of the data are used for training and 20% for
4 Much like worst-case expectations over Wasserstein balls, worst-case expectations over LCX ambiguity
sets can be reformulated as ﬁnite convex programs whenever the underlying loss function represents a
pointwise maximum of K concave component functions. Unlike problem ( 11) in Theorem 4.2,h o w e v e r ,
the resulting convex program scales exponentially with K .
123
Data-driven distributionally robust optimization using the… 157
101 102 103
-1.5
-1
-0.5
0
0.5
101 102 103
-2
0
2
4
6
8
10
101 102 103
0
0.2
0.4
0.6
0.8
1
101 102 103
-1.5
-1
-0.5
0
0.5
(d)
101 102 103
-2
0
2
4
6
8
10
(e)
101 102 103
0
0.2
0.4
0.6
0.8
1
(f)
(a) (b) (c)
(g) (h) (i)
101 102 103
-1.5
-1
-0.5
0
0.5
101 102 103
-2
0
2
4
6
8
10
101 102 103
0
0.2
0.4
0.6
0.8
1
Fig. 6 Out-of-sample performance J(ˆxN ), certiﬁcateˆJN , and certiﬁcate reliability PN[
J(ˆxN ) ≤ˆJN
]
for the performance-driven SAA, LCX and Wasserstein solutions as a function of N .( a) Holdout method,
(b) Holdout method, ( c) Holdout method, ( d) k-fold cross validation, (e) k-fold cross validation, (f) k-fold
cross validation, (g) optimal size, ( h) optimal size, ( i) optimal size (color ﬁgure online)
validation. Figure 6a visualizes the tube between the 20 and 80% quantiles (shaded
areas) as well as the mean value (solid lines) of the out-of-sample performance J(ˆxN )
as a function of the sample size N and based on 200 independent simulation runs,
whereˆxN is set to the minimizer of the SAA (blue), LCX (purple) and Wasserstein
(green) problems, respectively. The constant dashed line represents the optimal value
J⋆ of the original stochastic program (1), which is computed through an SAA problem
with N = 106 samples. We observe that the Wasserstein solutions tend to be superior
to the SAA and LCX solutions in terms of out-of-sample performance.
Figure 6b shows the optimal valuesˆJN of the SAA, LCX and Wasserstein problems,
where the sizes of the ambiguity sets are chosen via the holdout method. Unlike Fig.6a,
Fig. 6b thus reports in-sample estimates of the achievable portfolio performance. As
expected, the SAA approach is over-optimistic due to the optimizer’s curse, while the
LCX and Wasserstein approaches err on the side of caution. All three methods are
known to enjoy asymptotic consistency, which is in agreement with all in-sample and
out-of-sample results.
123
158 P . Mohajerin Esfahani, D. Kuhn
Figure 6c visualizes the reliability of the different performance certiﬁcates, that is,
the empirical probability of the event J(ˆxN ) ≤ˆJN evaluated over 200 independent
simulation runs. Here,ˆxN represents either an optimal portfolio of the SAA, LCX
or Wasserstein problems, while ˆJN denotes the corresponding optimal value. The
optimal SAA portfolios display a disappointing out-of-sample performance relative
to the optimistically biased mimimum of the SAA problem—particularly when the
training data is scarce. In contrast, the out-of-sample performance of the optimal LCX
and Wasserstein portfolios often undershootsˆJ
N .
Figure 6d–f show the same graphs as Fig. 6a–c, but now the sizes of the ambiguity
sets are determined via k-fold cross validation with k = 5. In this case, the out-of-
sample performance of both distributionally robust methods improves slightly, while
the corresponding certiﬁcates and their reliabilities increase signiﬁcantly with respect
to the naïve holdout method. However, these improvements come at the expense of a
k-fold increase in the computational cost.
One could think of numerous other statistical methods to select the size of the
Wasserstein ambiguity set. As discussed above, however, if the ultimate goal is to
minimize the out-of-sample performance of ˆxN (ε), then the best possible choice is
ε =ˆε opt
N . Similarly, one can construct a size parameter for the LCX ambiguity set that
leads to the best possible out-of-sample performance of any LCX solution. We empha-
size that these optimal Wasserstein radii and LCX size parameters are not available
in practice because computing J(ˆx
N (ε)) requires knowledge of the data-generating
distribution. In our experiments we evaluate J(ˆxN (ε)) to high accuracy for every
ﬁxed ε ∈ E using 2 · 105 validation samples, which are independent from the (much
fewer) training samples used to computeˆxN (ε). Figure 6g–i show the same graphs as
Fig. 6a–c for optimally sized ambiguity sets. By construction, no method for sizing the
Wasserstein or LCX ambiguity sets can result in a better out-of-sample performance,
respectively. In this sense, the graphs in Fig. 6g capture the fundamental limitations
of the different distributionally robust schemes.
7.2.3 Portfolios driven by reliability
In Sect. 7.2.2 the Wasserstein radii and LCX size parameters were calibrated with the
goal to achieve the best out-of-sample performance. Figure 6c, f, i reveal, however,
that by optimizing the out-of-sample performance one may sacriﬁce reliability. An
alternative objective more in line with the general philosophy of Sect. 2 would be
to choose Wasserstein radii that guarantee a prescribed reliability level. Thus, for a
given β ∈[ 0, 1] we should ﬁnd the smallest Wasserstein radius ε ≥ 0f o rw h i c h
the optimal valueˆJ
N (ε) of ( 27) provides an upper 1 − β conﬁdence bound on the
out-of-sample performance J(ˆxN (ε)) of its optimal solution. As the true distribution
P is unknown, however, the optimal Wasserstein radius corresponding to a given β
cannot be computed exactly. Instead, we must derive an estimatorˆε β
N that depends on
the training data. We constructˆε β
N and the corresponding reliability-driven portfolio
via bootstrapping as follows:
(1) Construct k resamples of size N (with replacement) from the original training
dataset. It is well known that, as N grows, the probability that any ﬁxed training
123
Data-driven distributionally robust optimization using the… 159
data point appears in a particular resample converges to e−1
e ≈ 2
3 . Thus, about N
3
training samples are absent from any resample. We collect all unused samples in
a validation dataset.
(2) For each resample κ = 1,..., k and ε ≥ 0, solve problem (27) using the Wasser-
stein ball of radius ε around the empirical distributionˆPκ
N on the κ-th resample.
The resulting optimal decision and optimal value are denoted asˆxκ
N (ε) andˆJκ
N (ε),
respectively. Next, estimate the out-of-sample performance J(ˆxκ
N (ε)) ofˆxκ
N (ε)
using the sample average over the κ-th validation dataset.
(3) Setˆε β
N to the smallest ε ≥ 0 so that the certiﬁcateˆJκ
N (ε) exceeds the estimate of
J(ˆxκ
N (ε)) in at least (1 − β) × k different resamples.
(4) Compute the data-driven portfolioˆxN =ˆxN (ˆε β
N ) and the corresponding certiﬁcate
ˆJN =ˆJN (ˆε β
N ) using the original training dataset.
As in Sect. 7.2.2, we compare the Wasserstein approach with the LCX and SAA
approaches. Speciﬁcally, by using bootstrapping, we calibrate the size of the LCX
ambiguity set so as to guarantee a desired reliability level 1 − β. The SAA problem,
on the other hand, has no free parameter that can be tuned to meet a prescribed
reliability target. Nevertheless, we can construct a meaningful certiﬁcate of the form
ˆJ
N (/Delta1):=ˆJSAA + /Delta1for the SAA portfolio by adding a non-negative constant to the
optimal value of the SAA problem. Our aim is to ﬁnd the smallest offset /Delta1≥ 0 with
the property thatˆJN (/Delta1)provides an upper 1 − β conﬁdence bound on the out-of-
sample performance J(ˆxSAA) of the optimal SAA portfolioˆxSAA. The optimal offset
corresponding to a given β cannot be computed exactly. Instead, we must derive an
estimatorˆ/Delta1β
N that depends on the training data. Such an estimator can be found through
a simple variant of the above bootstrapping procedure.
In all experiments we set the number of resamples to k = 50. Figure 7a–c visual-
ize the out-of-sample performance, the certiﬁcate and the empirical reliability of the
reliability-driven portfolios obtained with the SAA, LCX and Wasserstein approaches,
respectively, for the reliability target 1−β = 90% and based on 200 independent sim-
ulation runs. Figure 7d–f show the same graphs as Fig. 7a–c but for the reliability
target 1 − β = 75%. We observe that the new SAA certiﬁcate now overestimates the
true optimal value of the portfolio problem. Moreover, while the empirical reliability
of the SAA solution now closely matches the desired reliability target, the empirical
reliabilities of the LCX and Wasserstein solutions are similar but noticeably exceed
the prescribed reliability threshold. A possible explanation for this phenomenon is that
the k resamples generated by the bootstrapping algorithm are not independent, which
may give rise to a systematic bias in estimating the Wasserstein radii required for the
desired reliability levels.
7.2.4 Impact of the sample size on the Wasserstein radius
It is instructive to analyze the dependence of the Wasserstein radii on the sample size
N for different data-driven schemes. As for the performance-driven portfolios from
Sect. 7.2.2,F i g . 8 depicts the best possible Wasserstein radius ˆε
opt
N as well as the
Wasserstein radiiˆε hm
N andˆε cv
N obtained by the holdout method and via k-fold cross
123
160 P . Mohajerin Esfahani, D. Kuhn
101 102 103
-1.5
-1
-0.5
0
0.5
1
1.5
(a)
101 102 103
-2
0
2
4
6
8
10
(b)
101 102 103
0
0.2
0.4
0.6
0.8
1
(c)
101 102 103
-1.5
-1
-0.5
0
0.5
1
1.5
(d)
101 102 103
-2
-1
0
1
2
3
4
(e)
101 102 103
0
0.2
0.4
0.6
0.8
1
(f)
Fig. 7 Out-of-sample performance J(ˆxN ), certiﬁcateˆJN , and certiﬁcate reliability PN[
J(ˆxN ) ≤ˆJN
]
for
the reliability-driven SAA, LCX and Wasserstein portfolios as a function of N .( a) β = 10%, (b) β = 10%,
(c) β = 10%, (d) β = 25% (e) β = 25% (f) β = 25%
N
101 102 103
Average Wasserstein radii
10-2
10-1
ε hm
N Holdout
ε cv
N k-fold
ε opt
N Optimal
ε β
N Bootstrap β =2 5 %
ε β
N Bootstrap β =1 0 %
Fig. 8 Optimal performance-driven Wasserstein radiusˆε opt
N and its estimatesˆε hm
N andˆε cv
N obtained via
the holdout method and k-fold cross validation, respectively, as well as the reliability-driven Wasserstein
radiusˆεβ
N for β ∈{ 10%, 25%} obtained via bootstrapping
validation, respectively. As for the reliability-driven portfolios from Sect.7.2.3,F i g .8
further depicts the Wasserstein radiiˆεβ
N ,f o rβ ∈{ 10%, 25%}, obtained by bootstrap-
ping. All results are averaged across 200 independent simulation runs. As expected
from Theorem 3.6, all Wasserstein radii tend to zero as N increases. Moreover, the
convergence rate is approximately equal to N− 1
2 . This rate is likely to be optimal.
123
Data-driven distributionally robust optimization using the… 161
Indeed, if X is a singleton, then every quantile of the sample average estimator ˆJSAA
converges to J⋆ at rate N− 1
2 due to the central limit theorem. Thus, ifˆεN = o(N− 1
2 ),
thenˆJN also converges to J⋆ at leading order N− 1
2 by Theorem 6.3, which applies
as the loss function is convex. This indicates that the a priori rate N− 1
m suggested by
Theorem 3.4 is too pessimistic in practice.
7.3 Simulation results: uncertainty quantiﬁcation
Investors often wish to determine the probability that a given portfolio will outperform
various benchmark indices or assets. Our results on uncertainty quantiﬁcation devel-
oped in Sect. 5.2 enable us to compute this probability in a meaningful way—solely
on the basis of the training dataset.
Assume for example that we wish to quantify the probability that any data-driven
portfolioˆxN outperforms the three most risky assets in the market jointly.T h u s ,w e
should compute the probability of the closed polytope
ˆA =
{
ξ ∈ Rm :
⟨
ˆxN ,ξ
⟩
≥ ξi ∀i = 8, 9, 10
}
.
As the true distribution P is unknown, the probability P[ξ ∈ˆA] cannot be evaluated
exactly. Note thatˆA as well as P[ξ ∈ˆA] constitute random objects that depend onˆxN
and thus on the training data. Using thesame training dataset that was used to compute
ˆxN , however, we may estimate P[ξ ∈ˆA] from above and below by
sup
Q∈Bε(ˆPN )
Q
[
ξ ∈ˆA
]
and inf
Q∈Bε(ˆPN )
Q
[
ξ ∈ˆA
]
= 1 − sup
Q∈Bε(ˆPN )
Q
[
ξ/∈ˆA
]
,
respectively. Indeed, recall that the true data-generating probability distribution resides
in the Wasserstein ball of radiusεN (β) deﬁned in (8) with probability 1−β. Therefore,
we have
1 − β ≤ PN
[
ˆ/Xi1N : P ∈ BεN (β)(ˆPN )
]
≤ PN
[
ˆ/Xi1N : sup
Q∈BεN (β)(ˆPN )
Q
[
A
]
≥ P
[
A
]
∀A ∈ B(/Xi1)
]
= PN
[
ˆ/Xi1N : inf
A∈B(/Xi1)
sup
Q∈BεN (β)(ˆPN )
Q
[
A
]
− P
[
A
]
≥ 0
]
,
where B(/Xi1)denotes the set of all Borel subsets of /Xi1. The data-dependent setˆAN
can now be viewed as a (measurable) mapping fromˆ/Xi1N to the subsets in B(/Xi1).T h e
above inequality then implies
PN
[
ˆ/Xi1N : sup
Q∈BεN (β)(ˆPN )
Q
[ˆAN
]
− P
[ˆAN
]
≥ 0
]
≥ 1 − β.
123
162 P . Mohajerin Esfahani, D. Kuhn
10-6 10-5 10-4 10-3 10-2
-0.2
-0.1
0
0.1
0.2
0
0.2
0.4
0.6
0.8
1
(a)
10-6 10-5 10-4 10-3 10-2
-0.2
-0.1
0
0.1
0.2
0
0.2
0.4
0.6
0.8
1
(b)
Fig. 9 ExcessˆJ+
N (ε) − PˆA] and shortfallˆJ−
N (ε) − P[ˆA] (solid lines , left axis ) as well as reliability
PN [ˆJ−
N (ε) ≤ P[ˆA]≤ˆJ+
N (ε)] (dashed lines, right axis) as a function of ε.( a) N = 30, (b) N = 300
Thus, sup{Q[ˆAN ]: Q ∈ BεN (β)(ˆPN )} provides indeed an upper bound on P[ˆAN ]
with conﬁdence 1 − β. Similarly, one can show that inf {Q[ˆAN ]: Q ∈ BεN (β)(ˆPN )}
provides a lower conﬁdence bound on P[ˆAN ].
The upper conﬁdence bound can be computed by solving the linear program ( 17a).
ReplacingˆA with its interior in the lower conﬁdence bound leads to another (potentially
weaker) lower bound that can be computed by solving the linear program ( 17b). We
denote these computable bounds byˆJ+
N (ε) andˆJ−
N (ε), respectively. In all subsequent
experimentsˆxN is set to a solution of the distributionally robust program (27) calibrated
via k-fold cross validation as described in Sect. 7.2.2.
7.3.1 Impact of the Wasserstein radius
AsˆJ+
N (ε) andˆJ−
N (ε) estimate a random target P[ˆA], it makes sense to ﬁlter out
the randomness of the target and to study only the differences ˆJ+
N (ε) − P[ˆA] and
ˆJ−
N (ε) − P[ˆA]. Figure 9a, b visualize the empirical mean (solid lines) as well as the
tube between the empirical 20 and 80% quantiles (shaded areas) of these differences
as a function of the Wasserstein radius ε, based on 200 training datasets of cardinality
N = 30 and N = 300, respectively. Figure9 also shows the empirical reliability of the
bounds (dashed lines), that is, the empirical probability of the eventˆJ−
N (ε) ≤ P[ˆA]≤
ˆJ+
N (ε). Note that the reliability drops to 0 for ε = 0, in which case both ˆJ+
N (0) and
ˆJ−
N (0) coincide with the SAA estimator for P[ˆA]. Moreover, at ε = 0t h es e tˆA is
constructed from the SAA portfolioˆxN , whose performance is overestimated on the
training dataset. Thus, the SAA estimator for P[ˆA], which is evaluated using the same
training dataset, is positively biased. For ε> 0, ﬁnally, the reliability increases as the
shaded conﬁdence intervals move away from 0.
7.3.2 Impact of the sample size
We propose a variant of the k-fold cross validation procedure for selecting ε in uncer-
tainty quantiﬁcation. Partition ˆξ1,...,ˆξN into k subsets and repeat the following
123
Data-driven distributionally robust optimization using the… 163
101 102 103
-0.2
-0.1
0
0.1
0.2
N
101 102 103
Average Wasserstein radii
10-4
10-3
10-2
10-1
Excess
Shortfall
(a) (b)
Fig. 10 Dependence of the conﬁdence bounds and the Wasserstein radius on N .( a) ExcessˆJ+
N − P[ˆA]
and shortfallˆJ−
N − P[ˆA] of the data-driven conﬁdence bounds for P[ˆA].( b) Data-driven Wasserstein radius
ˆε cv
N obtained via k-fold cross validation
holdout method k times. Select one of the subsets as the validation set of size NV
and merge the remaining k − 1 subsets to a training dataset of size NT = N − NV .
Use the validation set to compute the SAA estimator of P[ˆA], and use the training
dataset to computeˆJ+
NT (ε) for a large but ﬁnite number of candidate radii ε. Setˆε hm
N
to the smallest candidate radius for which the SAA estimator of P[ˆA] is not larger
thanˆJ+
NT (ε).N e x t ,s e tˆε cv
N to the average of the Wasserstein radii obtained from the
k holdout runs, and reportˆJ+
N =ˆJ+
N (ˆε cv
N ) as the data-driven upper bound on P[ˆA].
The data-driven lower boundˆJ−
N is constructed analogously in the obvious way.
Figure 10a visualizes the empirical means (solid lines) as well as the tubes between
the empirical 20 and 80% quantiles (shaded areas) ofˆJ+
N − P[ˆA] andˆJ−
N − P[ˆA] as a
function of the sample sizeN , based on 300 independent training datasets. As expected,
the conﬁdence intervals shrink and converge to 0 as N increases. We emphasize that
ˆJ+
N andˆJ−
N are computed solely on the basis of N training samples, whereas the
computation of P[ˆA] necessitates a much larger dataset, particularly ifˆA constitutes
a rare event.
Figure 10b shows the Wasserstein radiusˆε cv
N obtained via k-fold cross validation
(both forˆJ+
N andˆJ−
N ). As usual, all results are averaged across 300 independent
simulation runs. A comparison with Fig. 8 reveals that the data-driven Wasserstein
radii in uncertainty quantiﬁcation display a similar but faster polynomial decay than in
portfolio optimization. We conjecture that this is due to the absence of decisions, which
implies that uncertainty quantiﬁcation is less susceptible to the optimizer’s curse. Thus,
nature (i.e., the ﬁctitious adversary choosing the distribution in the ambiguity set) only
has to compensate for noise but not for bias. A smaller Wasserstein radius seems to
be sufﬁcient for this purpose.
Acknowledgements We thank Soroosh Shaﬁeezadeh Abadeh for helping us with the numerical exper-
iments. The authors are grateful to Vishal Gupta, Ruiwei Jiang and Nathan Kallus for their valuable
comments. This research was supported by the Swiss National Science Foundation under Grant
BSCGI0_157733.
123
164 P . Mohajerin Esfahani, D. Kuhn
Open Access This article is distributed under the terms of the Creative Commons Attribution 4.0 Interna-
tional License (http://creativecommons.org/licenses/by/4.0/ ), which permits unrestricted use, distribution,
and reproduction in any medium, provided you give appropriate credit to the original author(s) and the
source, provide a link to the Creative Commons license, and indicate if changes were made.
Appendix A
The following technical lemma on the pointwise approximation of an upper semi-
continuous function by a non-increasing sequence of Lipschitz continuous majorants
strengthens [31, Theorem 4.2], which focuses on bounded domains and continuous
(but not necessarily Lipschitz continuous) majorants.
Lemma A.1 If h : /Xi1→ R is upper semicontinuous and satisﬁes h(ξ) ≤ L(1 +∥ξ∥)
for some L ≥ 0, then there exists a non-increasing sequence of Lipschitz continuous
functions that converge pointwise to h on /Xi1.
Proof The proof is constructive. Deﬁne the functions
hk(ξ) = sup
ξ′∈/Xi1
h(ξ′) − kL ∥ξ − ξ′∥, k ∈ N,
where L is the linear growth rate ofh. Note that by constructionhk(ξ) ≤ L(1+∥ξ∥).A s
ξ′= ξ is feasible in the maximization problem deﬁning hk(ξ) ,w eh a v ehk(ξ) ≥ h(ξ)
for all ξ ∈ /Xi1and k ∈ N. Moreover, hk(ξ) is Lipschitz continuous with Lipschitz
constant kL (as hk(ξ) constitutes a supremum of norm functions with this property).
Given any ξ ∈ /Xi1, it remains to be shown that lim k→∞ hk(ξ) = h(ξ) . Thus, choose
ξ′
k ∈ /Xi1with
hk(ξ) = sup
ξ′∈/Xi1
h(ξ′) − kL ∥ξ − ξ′∥≤ h(ξ′
k) − kL ∥ξ − ξ′
k∥+ 1
k .
We ﬁrst show that ξk converges to ξ as k tends to ∞. Indeed, we have
h(ξ) ≤ hk(ξ) ≤ h(ξ′
k) − kL ∥ξ − ξ′
k∥+ 1
k ≤ L(1 +∥ξ′
k∥) − kL ∥ξ − ξ′
k∥+ 1
k
≤ L(1 +∥ξ − ξ′
k∥+∥ξ∥) − kL ∥ξ − ξ′
k∥+ 1
k = L(1 +∥ξ∥) + 1
k
− (k − 1)L∥ξ − ξ′
k∥,
which implies
∥ξ − ξ′
k∥≤ 1
L(k − 1)
(
h(ξ) − L(1 +∥ξ∥) − 1
k
)
,
123
Data-driven distributionally robust optimization using the… 165
that is, ∥ξ − ξ′
k∥→ 0a s k →∞ . Therefore, we ﬁnd
h(ξ) ≤ lim
k→∞
hk(ξ) ≤ lim sup
k→∞
h(ξ′
k) − kL ∥ξ − ξ′
k∥+ 1
k ≤ lim sup
k→∞
h(ξ′
k) ≤ h(ξ),
where the last inequality is due to the upper semicontinuity of h. This concludes the
proof. ⊓⊔
References
1. Ben-Tal, A., den Hertog, D., Vial, J.-P .: Deriving robust counterparts of nonlinear uncertain inequalities.
Math. Program. 149, 265–299 (2015)
2. Ben-Tal, A., den Hertog, D., Waegenaere, A.D., Melenberg, B., Rennen, G.: Robust solutions of
optimization problems affected by uncertain probabilities. Manag. Sci. 59, 341–357 (2013)
3. Ben-Tal, A., El Ghaoui, L., Nemirovski, A.: Robust Optimization. Princeton University Press, Princeton
(2009)
4. Bertsekas, D.P .: Convex Optimization Theory. Athena Scientiﬁc, Belmont (2009)
5. Bertsekas, D.P .: Convex Optimization Algorithms. Athena Scientiﬁc, Belmont (2015)
6. Bertsimas, D., Doan, X.V ., Natarajan, K., Teo, C.-P .: Models for minimax stochastic linear optimization
problems with risk aversion. Math. Oper. Res. 35, 580–602 (2010)
7. Bertsimas, D., Gupta, V ., Kallus, N.: Robust SAA. Available at arXiv:1408.4445 (2014)
8. Bertsimas, D., Popescu, I.: On the relation between option and stock prices: a convex optimization
approach. Oper. Res. 50, 358–374 (2002)
9. Bertsimas, D., Sim, M.: The price of robustness. Oper. Res. 52, 35–53 (2004)
10. Boissard, E.: Simple bounds for convergence of empirical and occupation measures in 1-Wasserstein
distance. Electron. J. Probab. 16, 2296–2333 (2011)
11. Bolley, F., Guillin, A., Villani, C.: Quantitative concentration inequalities for empirical measures on
non-compact spaces. Probab. Theory Relat. Fields 137, 541–593 (2007)
12. Boyd, S., V andenberghe, L.: Convex Optimization. Cambridge University Press, Cambridge (2009)
13. Brownlees, C., Joly, E., Lugosi, G.: Empirical risk minimization for heavy-tailed losses. Ann. Stat. 43,
2507–2536 (2015)
14. Calaﬁore, G.C.: Ambiguous risk measures and optimal robust portfolios. SIAM J. Optim. 18, 853–877
(2007)
15. Catoni, O.: Challenging the empirical mean and empirical variance: a deviation study. Annales de
l’Institut Henri Poincaré, Probabilités et Statistiques 48, 1148–1185 (2012)
16. Chehrazi, N., Weber, T.A.: Monotone approximation of decision problems. Oper. Res. 58, 1158–1177
(2010)
17. del Barrio, E., Cuesta-Albertos, J.A., Matrán, C., et al.: Tests of goodness of ﬁt based on the l
2-
Wasserstein distance. Ann. Stat. 27, 1230–1239 (1999)
18. Delage, E., Y e, Y .: Distributionally robust optimization under moment uncertainty with application to
data-driven problems. Oper. Res. 58, 595–612 (2010)
19. El Ghaoui, L., Oks, M., Oustry, F.: Worst-case value-at-risk and robust portfolio optimization: a conic
programming approach. Oper. Res. 51, 543–556 (2003)
20. Erdo˘gan, E., Iyengar, G.: Ambiguous chance constrained problems and robust optimization. Math.
Program. 107, 37–61 (2006)
21. Fournier, N., Guillin, A.: On the rate of convergence in Wasserstein distance of the empirical measure.
Probab. Theory Relat. Fields 162, 1–32 (2014)
22. Goh, J., Sim, M.: Distributionally robust optimization and its tractable approximations. Oper. Res. 58,
902–917 (2010)
23. Hanasusanto, G.A., Kuhn, D.: Robust data-driven dynamic programming. In: Burges, C.J.C., Bottou,
L., Welling M., Ghahramani, Z., Weinberger, K.Q. (eds.) Advances in Neural Information Processing
Systems, 26: 27th Annual Conference on Neural Information Processing Systems 2013, pp. 827–835.
Curran Associates, Inc., (2013)
24. Hanasusanto, G.A., Kuhn, D., Wiesemann, W.: A comment on computational complexity of stochastic
programming problems. Math. Program. 159, 557–569 (2016)
123
166 P . Mohajerin Esfahani, D. Kuhn
25. Hu, Z., Hong, L.J.: Kullback–Leibler divergence constrained distributionally robust optimization.
Available at Optimization Online (2013)
26. Hu, Z., Hong, L.J., So, A.M.-C.: Ambiguous probabilistic programs. Available at Optimization Online
(2013)
27. Jiang, R., Guan, Y .: Data-driven chance constrained stochastic program. Math. Program. 158, 291–327
(2016)
28. Kallenberg, O.: Foundations of Modern Probability, Probability and its Applications. Springer, New
Y ork (1997)
29. Kantorovich, L.V ., Rubinshtein, G.S.: On a space of totally additive functions. V estn. Leningr. Univ.
13, 52–59 (1958)
30. Lang, S.: Real and Functional Analysis, 3rd edn. Springer, Berlin (1993)
31. Mashreghi, J.: Representation Theorems in Hardy Spaces. Cambridge University Press, Cambridge
(2009)
32. Mehrotra, S., Zhang, H.: Models and algorithms for distributionally robust least squares problems.
Math. Program. 146, 123–141 (2014)
33. Müller, A.: Integral probability metrics and their generating classes of functions. Adv. Appl. Probab.
29, 429–443 (1997)
34. Natarajan, K., Sim, M., Uichanco, J.: Tractable robust expected utility and risk models for portfolio
optimization. Math. Financ. 20, 695–731 (2010)
35. Parikh, N., Boyd, S.: Block splitting for distributed optimization. Math. Program. Comput. 6, 77–102
(2014)
36. Pﬂug, G.C., Pichler, A.: Multistage Sochastic Optimization. Springer, Berlin (2014)
37. Pﬂug, G.C., Pichler, A., Wozabal, D.: The 1/N investment strategy is optimal under high model ambi-
guity. J. Bank. Financ. 36, 410–417 (2012)
38. Pﬂug, G.C., Wozabal, D.: Ambiguity in portfolio selection. Quant. Financ. 7, 435–442 (2007)
39. Postek, K., den Hertog, D., Melenberg, B.: Computationally tractable counterparts of distributionally
robust constraints on risk measures. SIAM 58(4), 603–650 (2016). doi: 10.1137/151005221
40. Ramdas, A., Garcia, N., Cuturi, M.: On Wasserstein two sample testing and related families of non-
parametric tests. Available at arXiv:1509.02237 (2015)
41. Rockafellar, R.T., Uryasev, S.: Optimization of conditional value-at-risk. J. Risk 2, 21–42 (2000)
42. Rockafellar, R.T., Wets, R.J.-B.: V ariational Analysis. Springer, Berlin (2010)
43. Scarf, H.E.: Studies in the mathematical theory of inventory and production. In: Arrow, K.J., Karlin,
S., Scarf, H.E. (eds.) A Min–Max Solution of an Inventory Problem, pp. 201–209. Stanford University
Press, Stanford (1958)
44. Shapiro, A.: On duality theory of conic linear problems. In: Goberna, M.A., López, M.A. (eds.) Semi-
Inﬁnite Programming, pp. 135–165. Kluwer, Boston (2001)
45. Shapiro, A.: Distributionally robust stochastic programming. Available at Optimization Online (2015)
46. Shapiro, A., Dentcheva, D., Ruszczy´ nski, A.: Lectures on Stochastic Programming, 2nd edn, SIAM
(2014)
47. Shapiro, A., Nemirovski, A.: On complexity of stochastic programming problems. In: Jeyakumar, V .,
Rubinov, A. (eds.) Continuous Optimization, pp. 111–146. Springer, New Y ork (2005)
48. Smith, J.E., Winkler, R.L.: The optimizers curse: Skepticism and postdecision surprise in decision
analysis. Manag. Sci. 52, 311–322 (2006)
49. V apnik, V .N.: Statistical Learning Theory. Wiley, New Y ork (1998)
50. Villani, C.: Topics in Optimal Transportation. American Mathematical Society, Providence (2003)
51. Wiesemann, W., Kuhn, D., Sim, M.: Distributionally robust convex optimization. Oper. Res. 62, 1358–
1376 (2014)
52. Wozabal, D.: A framework for optimization under ambiguity. Ann. Oper. Res. 193, 21–47 (2012)
53. Wozabal, D.: Robustifying convex risk measures for linear portfolios: a nonparametric approach. Oper.
Res. 62, 1302–1315 (2014)
54. Zhao, C.: Data-Driven Risk-Averse Stochastic Program and Renewable Energy Integration. PhD thesis,
University of Florida (2014)
123
