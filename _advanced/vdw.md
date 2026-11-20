---
title: van der Waals complexes
layout: home
nav_order: 1
permalink: /docs/vdw.html
---
# van der Waals complexes

AutoMeKin includes an option to find van der Waals, vdW, complexes. In principle two related sampling
options are available: association and vdW. While association runs a number of structure
optimizations for randomly rotated fragments, vdW is a more powerful option representing a natural
[extension of our bbfs method to study vdW complexes](https://onlinelibrary.wiley.com/doi/abs/10.1002/qua.26008). The input files for these two options slightly differ
from those explained previously, as detailed below.

## association 
Here, a number of full optimizations are performed starting from random orientations of A and B. An example of such input file can be found in `path_to_program/examples/assoc.dat`. Two additional input files are also needed for this example, `Bz.xyz` and `N2.xyz`, which are also available in the same folder. The assoc.dat file contains the following data:
```
--General--
molecule  Bz-N2
fragmentA Bz
fragmentB N2

--Method--
sampling association
rotate   com com 4 .0 1. 5
Nassoc   50

--Screening--
MAPEmax 0.0001
BAPEmax 0.5
eigLmax 0.05
```
This type of sampling only needs three sections: General, Method and Screening. Some further `keyword
value(s)` pairs are needed for this sampling:

{: .important #kw-fragmenta }
`fragmentA value`  
[`value` is one string with no blank spaces; _mandatory keyword_ ]  
`value` is the name of fragment A (`Bz` in our case). A file with the Cartesian coordinates `Bz.xyz` must be present in `wrkdir`.

{: .important #kw-fragmentb }
`fragmentB value`   
[`value  is one string with no blank spaces; _mandatory keyword`_ ]   
`value` is the name of fragment B (`N2` in our case). A file with the Cartesian coordinates `N2.xyz` must be present as well.

{: .important #kw-rotate }
`rotate values`   
[four `values`: first two can be strings or integers and last two are floats; default values: `com com 4.0
1.5`]  
The first two values are the pivot positions of the random rotations: the center of mass (`com`) of fragment A and the center of mass of fragment B in our example; these pivots could be labels of atoms and therefore integers. The last two values are the distance, in Å, between both pivots and the minimum intermolecular distance between any two atoms of both fragments, respectively.

{: .important #kw-nassoc }
`Nassoc value`  
[`value` is an integer; default value: `100` ]  
`value` is the total number of intermolecular structures considered in the sampling. With this sampling, you cannot perform kinetics. However, you still need to provide the parameters for the screening. 

_To run the calculations, just type_:
```bash
amk.sh assoc.dat
```
This job will submit `value[Nassoc]` independent optimizations to find the structures. After the jobs finished, the script will automatically remove duplicates and select the best association “complex”.

{: .note }   
You cannot use `amk_parallel.sh` with this option, as this script is only employed to run MD
simulations.

You can check the optimized structures in folder `assoc_Bz_N2`. The program will also select the “best”
structure according to the minimum number of structural changes between the complex and the individual
fragments and its energy. The structure selected will be called `Bz-N2.xyz`. For fragments containing metals, the selection is also based on the valence of the metal center. The file assoclist_sorted (in
`assoc_Bz_N2` folder) collects a summary of the structures and their energies, as well as the MOPAC2016
output files of each of them, which are called _assocN.out_ , where N is a number from 1 to `value[Nassoc]`.

## vdW

For this option, the first part is common to association, and the program runs `value[Nassoc]` independent
optimizations to get an initial structure of the complex. From that point onwards, the program performs
BXDE simulations to find TSs and intermediates for the system. Here is the inputfile vdW.dat that you can
find in the examples folder:
```
--General--
molecule  Bz-N2
fragmentA Bz
fragmentB N2

--Method--
sampling vdW
rotate   com com 4.0 1.5
Nassoc   10
ntraj    1
fs       500

--Screening--
MAPEmax 0.0001
BAPEmax 0.5
eigLmax 0.01

--Kinetics--
Energy 150
```
As with other MD-based sampling methods, `amk_parallel.sh` can be employed here as well.
