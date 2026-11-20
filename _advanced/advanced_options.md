---
title: Advanced options
layout: home
nav_order: 4
permalink: /docs/advanced_options.html
---
# Advanced options

The following are keywords that can be useful for experienced users.

## General

Here is a list of additional keywords that can be employed in the General section:

{: .important #kw-iop }
`iop value`  
[`value` is one string with no blank spaces; no default value]   
`value` is a gaussian IOp string or any other additional keyword you want to add. 

Example:
```
HighLevel g16 mpwb95/6-31+G(d,p)
iop       iop(3/76=0560004400)
```

{: .warning }   
Care must be taken when `LowLevel_TSopt`, see below, is employed with `iop`, as this keyword
will also be activated in `LowLevel_TSopt` calculations. If the iop is only desired for high-level gaussian
calculations, then, the keyword should be removed while running the low-level computations.

{: .important #kw-lowlevel-tsopt }
`LowLevel_TSopt values`  
[two `values`: two strings; no blank spaces in each string; default values: `mopac value[LowLevel]`]   
First `value` is the program (`mopac`, `qcore`, `g09`, `g16`, `orca` or `mlip`) and second value is the electronic structure level employed to optimize the TSs at the low-level stage, or the model name (`uma` or `mace`) for `mlip`. _This keyword is employed if you want to use an ab initio/DFT method or an ML potential for the low-level TS
optimizations, as shown in the examples below, but take into account that ab initio/DFT optimizations are very CPU-time consuming_.
Besides the TSs, the starting minimum in `name.xyz` is also optimized at this level of theory. With `mlip`, the TS optimizations are carried out with [Sella](https://github.com/zadorlab/sella).

Examples:
```
LowLevel_TSopt g09 hf/3-21g
LowLevel_TSopt mlip uma
```

{: .important #kw-lowlevel-irc }
`LowLevel_IRC values`
[two `values`: two strings; default value: the program of `LowLevel_TSopt`]
Program and model employed for the low-level IRC calculations and minima optimizations, once the TSs have been located. At present, the only alternative to the default is `mlip`, followed by the model name:
```
LowLevel_IRC mlip uma
```
Only one ML model is used for the whole low-level workflow: if several low-level keywords use `mlip`, the model given in the most specific one (`LowLevel_IRC`, then `LowLevel_TSopt`) is employed.

{: .important #kw-recalc }
`recalc value`   
[one `value`: one integer; by default this keyword is not employed; _only with mopac_ ]  
If the last point of the IRC is an intermediate, MOPAC will try to optimize it. 

For difficult cases, the user can employ this keyword like in this example:

```
recalc 10
```
which tells MOPAC to recalculate the Hessian every 10 steps in the EF optimization. For small values, the
calculation is costly but is also very effective in terms of convergence.

## Method

Here is a list of additional keywords that can be employed in the Method section:

{: .important #kw-atoms }
`atoms value(s)`    
[one or two `values`: first is a string with no blank spaces or an integer and second, if present, is a string with no blank spaces; _only with MD_ ; default value: `all`]   
The first `value` can be `all`, in which case no other values are needed, or the number of atoms initially
excited followed by a second value, a string, which is the list of atoms separated by commas, without blank
spaces. It is analogous to modes, explained below. 

This is an example where atoms 1, 2 and 3 are initially excited:
```
atoms 3 1,2,3
```

{: .important #kw-etraj }
`etraj value`   
[`value` is an integer or string with no blank spaces; _only with MD-micro_ ; no default]  
If an integer, `value` is the energy, in kcal/mol, of the MD-micro simulations. 

If value is a range as in the example below, the energy is randomly selected in the given energy range:
```
etraj 200-300
```
If `etraj` is not specified, the program automatically employs the following range of energies: $\scriptstyle{16.25(s−1)−46.25(s−1)}$ kcal/mol, where $\scriptstyle{s}$ is the number of vibrational degrees of freedom of the system. The values $\scriptstyle{16.25}$ and $\scriptstyle{46.25}$ have been determined from the formic acid results and making use of RRK theory.
The program automatically adjusts the range to obtain at least 60% reactivity at the boundaries.

{: .important #kw-factorflipv }
`factorflipv value`  
[`value` is a float; _only with MD and MD-micro_ ; no default]   
Using the default options, trajectories are halted when the simulation time reaches the `value[fs]`, see below, or when there an interatomic distance, $\scriptstyle{r_{ij}}$, reaches 5 times its initial value $\scriptstyle{r_{ij}^0}$, which is regarded as a fragmentation. 

Using `factorflipv`, fragmentation can be prevented because the atomic velocities change their sign: whenever the following relationship is fulfilled: $\scriptstyle{r_{ij}>=\mathrm{FP}\times r_{ij}^0}$, where $\scriptstyle{\mathrm{FP}}$ is `value[factorflipv]`. We recommend this value to be in the range 3.0-5.0.

{: .important #kw-fs }
`fs value`  
[`value` is an integer; default value: `500` for MD and MD-micro and `5000` for BXDE]  
`value` is the simulation time in fs in MD, MD-micro and BXDE samplings. Notice that this is the maximum
simulation time, because when any interatomic distance reaches 5 times its initial value, the simulation
stops. 

To run 2 ps trajectories the following should be employed:
```
fs 2000
```

{: .important #kw-modes }
`modes value(s)`    
[one or two `values`: first is a string with no blank spaces or an integer and second, if present, is a string with no blank spaces; _only with MD-micro_ ; default value: `all`]   
The first `value` can be `all`, in which case no other values are needed, or the number of modes initially
excited followed by a second value, string, which is the list of modes separated by commas and without blank spaces. It is analogous to `atoms`, explained above.

{: .important #kw-multiple-minima }
`multiple_minima value`   
[`value` is one string: `yes` or `no`; default value: `yes`]   
`value` can be `yes`, in which case the exploratory simulations start from multiple minima, or `no`, where the all the MD simulations start from the input initial structure.

{: .important #kw-post-proc }
`post_proc value(s)`   
[from one to three `values`: first `value` is a string: `bbfs`, `bots` or `no`; the second and third are integers or floats; default values: `bbfs 20 1` for all samplings except association where the default value is `no`]   
The first `value` is the post-processing algorithm employed to detect reaction events and it can be bbfs, the default, `bots` or `no`, if no algorithm is applied; this makes only sense for the purpose of testing the MD module. For `bbfs` two more values can follow: the time window in fs employed by `bbfs` and the number of guess structures selected per candidate. Possible choices for this last number can be 1 or 3. 

Example:
```
post_proc bbfs 20 1
```
If `bots`, for bond order time series, is employed, _only with BXDE, vdW and external_, the algorithm
developed by [Hutchings et al.](https://pubs.acs.org/doi/abs/10.1021/acs.jctc.9b01039) is employed. In this case the two additional values are the cutoff frequency (in cm<sup>−1</sup>) for the low-pass filter
used to smooth bond order time series, and the number of standard deviations considered to identify peaks
associated with reactive events. The default values for this algorithm are:
```
post_proc bots 200 2.5
```

{: .important #kw-temp }
`temp value`  
[`value` is an integer or string with no blank spaces; _only with MD and BXDE_ ; no default]  
If an integer, `value` is the temperature, in K, of the MD or BXDE simulations. If a range, _only valid for MD_, the temperature is randomly selected in the given range. In the absence of the temp keyword, the program automatically defines the following range of temperatures: $\scriptstyle{5452(s−1)/n−15517(s−1)/n}$ K, which has been optimized for formic acid and $\scriptstyle{n}$ being the number of atoms. However, as for `etraj`, the boundaries are adjusted _on the fly_ to obtain a minimum reactivity of 60%. _For BXDE, temp has only one value and 1000 K is the default)._

{: .important #kw-thmass }
`thmass value`   
[`value` is an integer; _only with MD_ ; default value: `0`]   
`value` is the required minimum mass in a.u. of an atom to be initially excited.

{: .important #kw-use-let }
`Use_LET value`  
[`value` is one string: `yes` or `no`; _only with mopac_ ; default value: `no` for all samplings except `ChemKnow`]   
If `value` is `yes`, then mopac TS optimizations that fail throwing the error: “NUMERICAL PROBLEMS
BRACKETING LAMDA” are rerun using LET keyword, which allows [more of the potential energy surface to be
sampled:](http://openmopac.net/manual/error_messages.html). To help the user judge whether to use this
keyword, the results of the optimizations using LET are collected in the file `stats_let` located in
`tsdirLL_molecule`. This file contains several lines, one per iteration, with two numbers: the first is the
number of optimized TSs, and the second is the number of total attempts using LET.

## Screening

Here is a list of additional keywords that can be employed in the Screening section:

{: .important #kw-tight-ts }
`tight_ts value`   
[`value` is one string: `yes` or `no`; default value: `yes`]   
`value` can be `yes`, in which case only first order saddles are considered, or `no` if we want to keep also higher order saddles.

## Kinetics

Here is a list of additional keywords that can be employed in the Kinetics section:

{: .important #kw-imin }
`imin value`  
[`value` is an integer or the string `min0`; default value: `min0`]   
`value` is the starting minimum for the KMC simulations. value can be an integer, which identifies the
desired structure or `min0`, which refers to the input structure. All the minima are listed in `MINinfo` file and the user must examine `RXNet.cg` file to check that the minimum is indeed connected with the other ones.

{: .important #kw-nmol }
`nmol value`   
[`value` is an integer; default value: `1000` ]    
`value` is the number of molecules for the KMC simulations. 

{: .important #kw-stepsize }
`Stepsize value`   
[`value` is an integer; default value: `10` ]   
`value` is the number of reactions that have to take place before printing the population in the KMC runs.

{: .important #kw-maxen }
`MaxEn value`   
[`value` is an integer; default value: `100` for thermal kinetics or 3/2 the value of Energy for
microcanonical kinetics]  
`value` is the maximum allowed energy, in kcal/mol and relative to the input structure, for a TS to be included in the reaction network.

{: .important #kw-imppaths }
`ImpPaths value`   
[`value` is a float; default value: `0` ]   
`value` is the minimum percentage of processes occurring through a particular pathway that has to be achieved in order to be considered relevant and finally included in `RXNet.rel`. The default value means that pathways which are overcome at least once by the KMC simulations are included in these files. To reduce to number of channels printed in `RXNet.rel` you can increase the default value. Notice that these pathways may refer to the “coarse-grained” mechanism or to the complete mechanism that includes conformational isomers, obtained by using the `allstates` option as described above. For practical reasons, _a maximum of 100 TSs_ will be printed in `RXNet.rel`. If this maximum value is reached (which can be checked in `RXNet.rel`), it means that part of the channels are missing in these files.
