#!/bin/bash
cd "$2"/IRC
name="$(sqlite3 inputs.db "select name from gaussian where id=$1")"
if [ "$3" = "g09" ];then
   echo -e "$(sqlite3 inputs.db "select input from gaussian where id=$1")\n\n" > ${name}.dat
   g09 <${name}.dat &>${name}.log
   rm ${name}.dat
elif [ "$3" = "g16" ];then
   echo -e "$(sqlite3 inputs.db "select input from gaussian where id=$1")\n\n" > ${name}.dat
   g16 <${name}.dat &>${name}.log
   rm ${name}.dat
elif [ "$3" = "qcore" ];then
   DVV_hl.py ${name} &> irc_${name}.log
elif [ "$3" = "orca" ];then
   echo "$(sqlite3 inputs.db "select input from gaussian where id=$1")" > ${name}.inp
   unset SLURM_JOBID PMI_FD PMI_PORT PMIX_ID PMIX_SERVER_URI
   $(which orca) ${name}.inp > ${name}.log 2>&1
   # Check if terminated normally, retry with looser convergence if failed
   t=$(awk 'BEGIN{t=0};/ORCA TERMINATED NORMALLY/{t=1};/ERROR !!!/{t=0};END{print t}' ${name}.log)
   if [ $t -eq 0 ]; then
      sed 's/^!/! SlowConv /' ${name}.inp > ${name}_retry.inp
      unset SLURM_JOBID PMI_FD PMI_PORT PMIX_ID PMIX_SERVER_URI
      $(which orca) ${name}_retry.inp > ${name}.log 2>&1
   fi
fi