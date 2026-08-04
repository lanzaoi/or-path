# Branch and Price for Submodular Bin Packing


- kind: paper-note
- title: Branch and Price for Submodular Bin Packing
- source: curated

- kind: paper-note
- content_class: abstract_plus_modeling_sketch
- domain: cutting_packing
- domains_all: cutting_packing
- source: api-metadata (top500_snip)
- top200_rank: 141
- source_top500_rank: 365
- year: 2022
- venue: arXiv
- citations_index: 0
- has_public_abstract: yes
- fulltext: no
- copyright_policy: abstract+metadata only; no PDF body dump
- numbers_policy: literature never authoritative optima; solve+validate only

- authors: Liding Xu, Claudia D'Ambrosio, Sonia Haddad Vanier, Emiliano Traversi
- arxiv: https://arxiv.org/abs/2204.00320v2

## Abstract (from public metadata APIs)

The Submodular Bin Packing (SMBP) problem asks for packing unsplittable items into a minimal number of bins for which the capacity utilization function is submodular. SMBP is equivalent to chance-constrained and robust bin packing problems under various conditions. SMBP is a hard binary nonlinear programming optimization problem. In this paper, we propose a branch-and-price algorithm to solve this problem. The resulting price subproblems are submodular knapsack problems, and we propose a tailore

## Core modeling sketch (from title+abstract only)

- Problem class: packing / cutting / knapsack.
- Uncertainty: robust/DRO/stochastic/chance constraints.
- Model family: linear / continuous LP.
- Method: decomposition (CG/Benders/Lagrangian/B&P).
- RAG: method pointer only — never treat lit numbers as user-case optima.

## Not included

- Full paper body / proofs / tables
- Case optima numbers
