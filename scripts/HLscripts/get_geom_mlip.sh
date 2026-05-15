#!/bin/bash
# Extracts the last geometry block from an MLIP log (FINAL GEOMETRY or IRC ENDPOINT GEOMETRY)
awk '
/FINAL GEOMETRY|IRC ENDPOINT GEOMETRY/{
   getline          # natom line
   getline          # Energy= line
   delete sym; delete x; delete y; delete z
   i=1
   while(1){
      getline
      if(NF==0) break
      sym[i]=$1; x[i]=$2; y[i]=$3; z[i]=$4
      natom=i; i++
   }
}
END{
   for(i=1;i<=natom;i++) print sym[i], x[i], y[i], z[i]
}' $1
