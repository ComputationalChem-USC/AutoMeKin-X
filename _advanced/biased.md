---
title: Biased dynamics
layout: home
nav_order: 5
permalink: /docs/biased.html
---
# Biased dynamics

AutoMeKin includes several methods to bias the dynamics towards specific reaction pathways. So far, these
are the available options, _only for MD and MD-micro_:

- The first option uses the [AXD algorithm](https://pubs.acs.org/doi/10.1021/ct060042z), with which selected bond lengths are not allowed to stretch more than 5 0% with respect to their initial values. This can be useful to prevent the breakage of certain bonds. This option can be invoked using the following “ `keyword value` pair:

{: .important #kw-nbondsfrozen }
`nbondsfrozen value`    
[`value` is an integer; default value: `0` ]  
where `value`, or `nfr`, is the number of constrained bonds. 

The line containing the `bondsfrozen nfr` pair must be followed by `nfr` lines, each one with two values:  
`fr_i(k) fr_j(k)`   
which are integers indicating the indexes of the atoms that form each constrained bond, as in the following example:
```
nbondsfrozen 2
1 13
2 8
```
This would “freeze” two bond distances connecting atoms 1 and 13 and 2 and 8 , respectively. This keyword
has not been tested thoroughly and the more robust Hookean keyword, see above, is suggested.


- The second algorithm biases the dynamics towards a particular reaction channel. An example of this
option is provided in file `path_to_program/examples/FA_biasH2.dat`; you also need `FA.xyz`, which
illustrates a way to search for H<sub>2</sub> elimination transition states from formic acid. For this we use two sets of keywords to apply constant external forces to break or form bonds. For bond breakage we use the following:

{: .important #kw-nbondsbreak }
`nbondsbreak value`   
[`value` is an integer; default value: `0` ]   
where `value`, or `nbr`, is the number of bonds we want to break. 

The line containing this `keyword value` pair must be followed by `nbr` lines, each one with three values `(br_i(1,...,nbr) br_j(1,...,nbr) force(1,...,nbr)`   
of which the first two are integers and the last a float. These three numbers indicate the indexes of the atoms that form each bond we want to break, and the magnitude of the applied external force in kcal/mol/Å, respectively.

For bond formation we use the analogous keyword `nbondsform` as in this example (taken from
`FA_biasH2.dat`):
```
nbondsform 1
4 5 30
nbondsbreak 2
3 5 80
1 4 80
```
A similar test can be performed on the same molecule to get the TS for H<sub>2</sub>O elimination. The corresponding input file, `FA_biasH2O.dat`, is also available in directory path_to_program/examples. Additionally, a retro Diels-Alder reaction has also been tested: cyclohexene$\scriptstyle{\rightarrow}$ethylene+1,3-butadiene, using the input files `rdiels_bias.dat` and `rdiels.xyz` provided in the amk distribution.

The above examples can be tested using the `amk.sh` script:
```bash
amk.sh inputfile
```
