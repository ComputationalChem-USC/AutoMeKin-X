#!/bin/bash
cd "$2"
name="$(sqlite3 inputs.db "select name from gaussian where id=$1")"
inp="$(sqlite3 inputs.db "select input from gaussian where id=$1")"
echo -e "$inp\n\n" > ${name}.dat
if [ "$inp" != "salir" ]; then
   if [ "$3" = "g09" ]; then
      g09 <${name}.dat &>${name}.log
      t=$(awk 'BEGIN{t=0};/Error termination via/{t=1};END{print t}' ${name}.log)
      if [ $t -eq 1 ]; then
         echo -e "$inp\n\n" | sed 's/calcfc/cartesian,maxcycle=100,calcfc/;s/calcall/cartesian,maxcycle=100,calcall/' > ${name}.dat
         g09 <${name}.dat &> ${name}.log
      fi
      t=$(awk 'BEGIN{t=0};/Error termination via/{t=1};END{print t}' ${name}.log)
      if [ $t -eq 1 ]; then
         echo -e "$inp\n\n" | sed 's/calcfc,noraman)/cartesian,maxcycle=100,calcfc,noraman) nosymm/;s/calcall,noraman)/cartesian,maxcycle=100,calcall,noraman) nosymm/' > ${name}.dat
         g09 <${name}.dat &> ${name}.log
      fi
   elif [ "$3" = "g16" ]; then
      g16 <${name}.dat &>${name}.log
      t=$(awk 'BEGIN{t=0};/Error termination via/{t=1};END{print t}' ${name}.log)
      if [ $t -eq 1 ]; then
         echo -e "$inp\n\n" | sed 's/calcfc/cartesian,maxcycle=100,calcfc/;s/calcall/cartesian,maxcycle=100,calcall/' > ${name}.dat
         g16 <${name}.dat &> ${name}.log
      fi
      t=$(awk 'BEGIN{t=0};/Error termination via/{t=1};END{print t}' ${name}.log)
      if [ $t -eq 1 ]; then
         echo -e "$inp\n\n" | sed 's/calcfc,noraman)/cartesian,maxcycle=100,calcfc,noraman) nosymm/;s/calcall,noraman)/cartesian,maxcycle=100,calcall,noraman) nosymm/' > ${name}.dat
         g16 <${name}.dat &> ${name}.log
      fi
   elif [ "$3" = "orca" ]; then
      cp ${name}.dat ${name}.inp
      unset SLURM_JOBID PMI_FD PMI_PORT PMIX_ID PMIX_SERVER_URI
      $(which orca) ${name}.inp > ${name}.out 2>&1
      t=$(awk 'BEGIN{t=0};/ORCA TERMINATED NORMALLY/{t=1};/ERROR !!!/{t=0};END{print t}' ${name}.out)
      if [ $t -eq 0 ]; then
         sed 's/^!/! SlowConv /' ${name}.inp > ${name}_retry.inp
         unset SLURM_JOBID PMI_FD PMI_PORT PMIX_ID PMIX_SERVER_URI
         $(which orca) ${name}_retry.inp > ${name}.out 2>&1
      fi
      # Copiar salida con extensión .log para compatibilidad con el resto del pipeline
      cp ${name}.out ${name}.log
   elif [ "$3" = "qcore" ]; then
      entos.py ${name}.dat > ${name}.log 2>&1
   elif [ "$3" = "mlip" ]; then
      source $2/mlip_config
      printf "%s" "$inp" > ${name}.xyz
      mlip_calc.py tsopt ${name}.xyz $mlip_model $models_dir $charge $mult >> ${name}.log 2>&1
   fi
fi