#!/bin/bash
# Extracts the LAST "CARTESIAN COORDINATES (ANGSTROEM)" block from an ORCA output
# Symbol is in column 1, coordinates in columns 2,3,4
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
}' $1
