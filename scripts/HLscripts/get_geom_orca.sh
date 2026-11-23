#!/bin/bash
# Geometry of an ORCA job, consistent with its energy (get_energy_orca_*.sh = last FINAL SINGLE
# POINT ENERGY).
# 1) If ORCA wrote <base>.xyz (base = output without extension) and the energy in its comment line
#    equals the last FINAL SINGLE POINT ENERGY of the output, print that geometry: it is the last
#    geometry of the run (ORCA stops printing "CARTESIAN COORDINATES" after the first cycles of a
#    long optimisation, so the last printed block can be many cycles old). 20261014.
# 2) Otherwise, the LAST "CARTESIAN COORDINATES (ANGSTROEM)" block (previous behaviour).
# Symbol is in column 1, coordinates in columns 2,3,4
out=$1
xyz="${out%.*}.xyz"
if [ -f "$xyz" ]; then
   efin=$(awk '/FINAL SINGLE POINT ENERGY/{e=$NF} END{if(e!="") printf "%.6f", e}' "$out")
   exyz=$(awk 'NR==2{for(i=1;i<NF;i++) if($i=="E"){printf "%.6f", $(i+1); exit}}' "$xyz")
   if [ -n "$efin" ] && [ "$efin" = "$exyz" ]; then
      awk 'NR>2 && NF==4{print $1, $2, $3, $4}' "$xyz"
      exit 0
   fi
fi
awk '
/CARTESIAN COORDINATES \(ANGSTROEM\)/{
   getline   # skip "---..." line
   delete sym; delete x; delete y; delete z
   i=1
   while(1){
      getline
      if(NF==0) break
      sym[i]=$1
      x[i]=$2
      y[i]=$3
      z[i]=$4
      natom=i
      i++
   }
}
END{
   for(i=1;i<=natom;i++) print sym[i], x[i], y[i], z[i]
}' "$out"
