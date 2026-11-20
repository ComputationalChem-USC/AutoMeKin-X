---
title: Fragmentation
layout: home
nav_order: 3
permalink: /docs/fragmentation.html
---
# Fragmentation

The fragmentation patterns and breakdown curves can be modelled using the script `amk_frag.sh`. This script provides a workflow to iteratively discover fragmentation pathways not only the parent molecule but also for the fragments resulting from the primary fragmentation. Usage:
```bash
nohup amk_frag.sh > amk_frag.log 2>&1 &
```
The inputfile must have an additional section called “Fragmentation”, as in this example:
```
--Fragmentation--
minsize 4
systems 1
CH3O+   3
```
The new keywords are explained below.

{: .important #kw-minsize }
`minsize value`   
[`value` is an integer; default value: `4` ]  
`value` is the minimum number of atoms for a fragment to be considered in secondary fragmentations. 

{: .important #kw-systems }
`systems value`   
[`value` is an integer; default value: `0`]  
`value` (or `ns`) is the number of additional fragments, or systems, to be considered in secondary fragmentations, besides those obtained in the fragmentation of the parent molecule. These could be fragments with other spin state, or fragments that are obtained through a barrierless process. 

This line must be followed by `ns` lines with two columns each one: the formula of each system, sys, and its multiplicity, mult. Note that for the formula the chemical symbols of the atoms must sorted following AutoMeKin’s convention: alphabetic order:
```
systems ns
sys(1) mult(1)
sys(2) mult(2)
...
sys(ns) mult(ns)
```
In the example above, only fragments with number of atoms greater than or equal to 4 are further
fragmented and an additional system has been added: CH<sub>3</sub>O<sup>+</sup> in its triplet state.

This workflow creates a new folder: `M3Cinp` containing files that can be read by program M3C to simulate
the breakdown curves of the studied system.
