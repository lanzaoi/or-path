# Learning to Optimize at Scale: A Benders Decomposition-TransfORmers Framework for Stochastic Combinatorial Optimization


- kind: paper-note
- title: Learning to Optimize at Scale: A Benders Decomposition-TransfORmers Framework for Stochastic Combinatorial Optimization
- source: curated

- kind: paper-note
- content_class: abstract_plus_modeling_sketch
- domain: ml_or_hybrid
- domains_all: ml_or_hybrid, column_generation_decomp
- source: api-metadata (top500_snip)
- top200_rank: 159
- source_top500_rank: 429
- year: 2026
- venue: arXiv
- citations_index: 0
- has_public_abstract: yes
- fulltext: no
- copyright_policy: abstract+metadata only; no PDF body dump
- numbers_policy: literature never authoritative optima; solve+validate only

- authors: Seung Jin Choi, Kimiya Jozani, Josh Cooper, Esra Buyuktahtakin Toy
- arxiv: https://arxiv.org/abs/2607.22550v1

## Abstract (from public metadata APIs)

We propose a learning-augmented Benders decomposition framework to solve large-scale two-stage stochastic mixed-integer programs. We focus on the two-stage stochastic capacitated lot-sizing problem (TSSCLSP) under demand uncertainty. Our method accelerates the convergence of the decomposition by using a pre-trained TransfORmer model to rapidly generate high-quality approximate solutions for the scenario subproblems. This hybrid strategy uses the TransfORmer predictions to generate strong optimal

## Core modeling sketch (from title+abstract only)

- Model family: mixed-integer programming.
- Method: decomposition (CG/Benders/Lagrangian/B&P).
- RAG: method pointer only — never treat lit numbers as user-case optima.

## Not included

- Full paper body / proofs / tables
- Case optima numbers
