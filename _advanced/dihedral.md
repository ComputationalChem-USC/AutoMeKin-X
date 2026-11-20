---
title: Dihedral scans
layout: home
nav_order: 2
permalink: /docs/dihedral.html
---
# Scanning dihedral angles

Dihedral angles can be scanned using script tors.sh. You will need the inputfile and the XYZ file in your
`wrkdir` and just type:
```bash
tors.sh inputfile file
```
The first argument is the name of the inputfile and the second one can be: `all`, the default, or `file`. Using `all`, all the rotatable angles are scanned, while if you use `file`, the four indices that specify the dihedrals you want to scan must be present in file `dihedrals`.

The dihedrals will be scanned and the highest point, or points, along the scan, or scans, will be subjected to TS optimizations.

In general, dihedral scans are automatically performed in all parallel calculations, except with vdW and assoc samplings. For big and/or highly flexible molecules these automated scans can be very CPU intensive, and they can be avoided adding the keyword `torsion` with the value no to your Method section like in the next example:
```
--Method--
sampling MD
ntraj    10
torsion  no
```
The default value for `torsion` is `yes`.

When there are many rotatable bonds, or the number of minima grows quickly, the torsional scan of each iteration can become a bottleneck, since by default it is done by a single task. The keyword `ntorstasks` splits it among several parallel tasks:

{: .important #kw-ntorstasks }
`ntorstasks value`
[`value` is an integer; default value: `1`]
`value` is the number of parallel tasks that share the torsional scan in each iteration of `llcalcs.sh`/`amk_parallel.sh`. The new minima are distributed round-robin among these tasks. With the default value, a single task scans all the dihedrals, as in previous versions.

```
--Method--
sampling   MD
ntraj      10
ntorstasks 4
```
