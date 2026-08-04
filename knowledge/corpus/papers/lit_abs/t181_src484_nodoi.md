# Solving the Steiner Tree Problem with few Terminals


- kind: paper-note
- title: Solving the Steiner Tree Problem with few Terminals
- source: curated

- kind: paper-note
- content_class: abstract_plus_modeling_sketch
- domain: graph_or
- domains_all: graph_or
- source: api-metadata (top500_snip)
- top200_rank: 181
- source_top500_rank: 484
- year: 2020
- venue: arXiv
- citations_index: 0
- has_public_abstract: yes
- fulltext: no
- copyright_policy: abstract+metadata only; no PDF body dump
- numbers_policy: literature never authoritative optima; solve+validate only

- authors: Johannes K. Fichte, Markus Hecher, Andre Schidler
- arxiv: https://arxiv.org/abs/2011.04593v1

## Abstract (from public metadata APIs)

The Steiner tree problem is a well-known problem in network design, routing, and VLSI design. Given a graph, edge costs, and a set of dedicated vertices (terminals), the Steiner tree problem asks to output a sub-graph that connects all terminals at minimum cost. A state-of-the-art algorithm to solve the Steiner tree problem by means of dynamic programming is the Dijkstra-Steiner algorithm. The algorithm builds a Steiner tree of the entire instance by systematically searching for smaller instance

## Core modeling sketch (from title+abstract only)

- Problem class: shortest path on a network.
- Method: DP / MDP sequential decisions.
- RAG: method pointer only — never treat lit numbers as user-case optima.

## Not included

- Full paper body / proofs / tables
- Case optima numbers
