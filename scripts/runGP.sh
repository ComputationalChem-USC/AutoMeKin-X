#!/bin/bash
## This script is invoked as:
##doparallel "runGP.sh {1} $molecule $cwd $nojf $nchan $e0 $ntorstasks" "$(seq $noj1 $nojf)"
##The first $ntorstasks jobs are tors scan shards (ntorstasks defaults to 1
##when not passed, matching the original single-torsion-task behavior).
ntors="${7:-1}"
if [ $1 -le $ntors ]; then
   if [ $ntors -eq 1 ]; then
      batch=torsion
   else
      batch=torsion$1
   fi
else
   batchn=$(($1-$ntors))
   batch=batch$batchn
fi
#Make batch directory
if [ -d ${batch} ]; then  rm -r ${batch} ; fi
mkdir ${batch}
#copy neccesary files.
cp amk.dat $2.xyz ${batch}
echo "tsdirll $3/tsdirLL_$2"  >> ${batch}/amk.dat
##copy frags only if sampling is vdw
copyfrags=$(awk 'BEGIN{cf=0};{if($1=="sampling" && $2=="vdW") cf=1};END{print cf}'  amk.dat)
if [ $copyfrags -eq 1 ]; then
   frA=$(awk '{if($1=="fragmentA") print $2}' amk.dat)
   frB=$(awk '{if($1=="fragmentB") print $2}' amk.dat)
   cp ${frA}.xyz ${frB}.xyz ${batch}
fi
##Launch the calcs
if [ $1 -le $ntors ]; then
   (cd ${batch} && TORS_SHARD=$1 TORS_NSHARDS=$ntors tors.sh > scan_tors.log)
elif [ $5 -eq 0 ]; then
   (cd ${batch} && amk.sh amk.dat >amk.log)
else
   (cd ${batch} && LocateTs.py amk.dat $((batchn-1)) 1 $6 > amk.log)
fi
