---
title: Analysis
layout: home
nav_order: 7
permalink: /docs/analysis.html
---
# Analysis

## Visualization tools<a name="amktools"></a>

The Python library [![GitHub - amk_tools_X](https://img.shields.io/badge/GitHub-amk__tools__X-blue?logo=github)](https://github.com/ComputationalChem-USC/amk_tools_X), maintained by the ComputationalChem-USC group and based on the original [amk_tools](https://github.com/dgarayr/amk_tools) by Diego Garay-Ruiz (Institute of Chemical Research of Catalonia), is a useful package to parse, process and transform the reaction networks created by AutoMeKin. All the data contained in `FINALDIR` can be easily accessed using these tools. Install it in `amk_env` with `pip install git+https://github.com/ComputationalChem-USC/amk_tools_X.git` (see [Installation](installation.html#amktools)).

The commandline script `amk_gen_view.py` allows to generate visualizations directly taking arguments
from STDIN:
```bash
amk_gen_view.py FINALDIR RXNFILE
```` 
where `RXNFILE` is the name of the `RXNet` files explained above (`RXNet`, `RXNet.cg` or `RXNet.rel`). Additional arguments that may be passed are [detailed here](https://github.com/ComputationalChem-USC/amk_tools_X#usage-guidelines).

The following example shows how to create interactive plots from `RXNet.cg` file including all paths found at low level for Formic Acid:
```bash
amk_gen_view.py FINAL_LL_FA RXNet.cg -b --paths
```
While this one creates the corresponding plots for the paths that connect MIN1 with the H<sub>2</sub>+CO<sub>2</sub> products:
```bash
amk_gen_view.py FINAL_LL_FA RXNet.cg --paths MIN1 H2+CO2
```
More details can be found in the [user guide](https://github.com/ComputationalChem-USC/amk_tools_X/blob/master/UserGuide.md)

Example of an interactive dashboard for FA: the reaction network, the 3D structure of a selected node or edge (_i.e._, a minimum or a TS) with its normal modes, and the energy profiles.
<p align="center">
   <img src="{{ "/assets/images/amk_tools_X/dashboard.jpg" | relative_url }}" alt="amk_tools_X dashboard for formic acid" width="800">
</p>

## Properties of the reaction network<a name="amktools2"></a>

Another commandline script from the same Python library [![GitHub - amk_tools_X](https://img.shields.io/badge/GitHub-amk__tools__X-blue?logo=github)](https://github.com/ComputationalChem-USC/amk_tools_X) can be used to obtain the properties of the reaction network: 
```bash
amk_rxn_stats.py FINALDIR -r RXNFILE
```

With `FINALDIR` and `RXNFILE` having the same meaning as for `amk_gen_view.py`. 

Properties like the average shortest path length, the average clustering coefficient or the transitivity will be printed in a file called `rxn_stats.txt`.



## Kinetics simulations at different temperatures<a name="kint"></a>

The kinetics calculations can be rerun for a temperature/energy different from that specified in the input file after the keywords Temperature or Energy. You may also want to use the allstates option as seen below. This can be easily done using the `kinetics.sh` command line script:
```bash
kinetics.sh value calc (allstates)
```
where `value` is the new value of the temperature in K or energy in kcal/mol, depending on your initial
choice in the Kinetics section, and `calc` is either `ll`, for low-level, or `hl`, for high-level. Finally, with no other options, the conformational isomers will form a single state, which is the default for all sampling except vdW. However, using `allstates` as the last argument, the calculations will regard every conformational isomer as a different state, which is the default for vdW. Each calculation will create a new folder named `FINAL_XL_molecule_Fvalue`, with X = H,L and F=T,E.

## Removing unwanted TS structures<a name="rmts"></a>

As explained above, the use of very tight criteria in the screening process might lead to redundant TS
structures in the `FINAL` directories. In those cases, the user can remove those structures as shown in the
following example:
```bash
remove_ts.sh 2 4 7
```
where 2 , 4 and 7 are the labels of the TSs to be removed for the LL calculations. The corresponding script for the HL calculations is `REMOVE_TS.sh`. These two scripts will create a new `FINAL_XL_FA` $\scriptstyle{(}$X = H,L$\scriptstyle{)}$ directory where the selected TS structures have been removed.

## Modifying the reaction network<a name="trxn"></a>

Although unlikely, the algorithm for identifying conformational isomers may fail. The conformer families are stored in the `MINinfo` and `TSinfo` files within the `FINALDIR` folder. If one or more conformers are mistakenly assigned, the user can follow these steps to modify them:

1. Modify the families of conformational isomers in the files `tsdirXL_molecule/working/conf_isomer.out` and/or `tsdirXL_molecule/working/conf_isomer_ts.out` as needed $\scriptstyle{(}$X = H,L$\scriptstyle{)}$.
2. Then, run the script `tweak_rxnet.sh` for low-level or `TWEAK_RXNET.sh` for high-level adjustments, respectively.

This will create a new `FINALDIR` with the manually modified reaction network structure.


