#!/bin/bash
#default sbatch resources
#SBATCH --time=04:00:00
#SBATCH -n 4
#SBATCH --output=TS-%j.log
#SBATCH --ntasks-per-node=2
#SBATCH -c 12
#

sharedir=${AMK}/share

exe="TS.sh"
cwd=$PWD
source utils.sh
tmp_files=(tmp*)
trap cleanup EXIT INT

print_ref

if [ $# -eq 0 ]; then 
   echo "One argument is required" 
   exit 1
else
   inputfile=$1
fi

define_inputfile
screening.sh $inputfile
read_input

if [ $noHLcalc -eq 0 ]; then echo Please, provide HighLevel keyword ; exit ; fi

# Check that the required HL program is installed
if [ "$program_hl" = "g09" ] || [ "$program_hl" = "g16" ]; then
   check_g09
elif [ "$program_hl" = "orca" ]; then
   check_orca
elif [ "$program_hl" = "mlip" ]; then
   : # model file already validated in hl_print
fi

min0=${molecule}

###Make $tsdirhl folder
if [ ! -d "$tsdirhl" ]; then
   echo "$tsdirhl does not exist. It will be created"
   mkdir $tsdirhl 2>tmp_err
   if [ -s tmp_err ]; then
      echo "check the path of tsdirhl folder"
      exit
   fi
else
   echo "$tsdirhl already exists."
fi

###Make $tsdirhl/MINs folder
if [ ! -d "$tsdirhl/MINs" ]; then
   echo "$tsdirhl/MINs does not exist. It will be created"
   mkdir $tsdirhl/MINs
else
   echo "$tsdirhl/MINs already exists."
fi

if [ "$program_opt" = "g09" ] || [ "$program_opt" = "g16" ]; then reduce=0 ; fi
if [ -z "$reduce" ]; then
   echo Keyword HL_rxn_network has not been specified
   exit 1
else
   if [ $reduce -lt 0 ]; then
      echo "Running the HL calculations for a subset of the TSs (bimolecular channels excluded)"
      reduce_RXNet.py $molecule
   elif [ $reduce -gt 0 ]; then
      echo "Running the HL calculations for a subset of the TSs (bimolecular channels excluded)"
      reduce_RXNet.py $molecule $reduce
   else
      echo "Running the HL calculations for the whole reaction network"
   fi
fi

echo "Molecule name" $min0
echo "tsdirll is " $tsdirll

m=0
file=${tsdirll}/tslist
sqlite3 ${tsdirhl}/inputs.db "drop table if exists gaussian; create table gaussian (id INTEGER PRIMARY KEY,name TEXT, input TEXT, unique(name));"

for name in $(awk '{print $3}' $file)
do
  check_ts
  if [ $calc -eq 0 ]; then
    echo $tsdirhl/$name "already optimized"
  else
    ((m=m+1))
    echo $name "not optimized"

    chkfile=$name
    calc=ts
    level=hl

    # Extract geometry depending on low-level program
    if [ "$program_opt" = "g09" ] || [ "$program_opt" = "g16" ]; then
       geo="$(get_geom_g09.sh $tsdirll/$name.out | awk '{if(NF==4) print $0};END{print ""}')"
    elif [ "$program_opt" = "mopac" ]; then
       geo="$(get_geom_mopac.sh $tsdirll/$name.out | awk '{if(NF==4) print $0};END{print ""}')"
    elif [ "$program_opt" = "qcore" ]; then
       geo="$(awk '/Final structure/{flag=1; next} EOF{flag=0} flag;END{print ""}' $tsdirll/$name.out)"
    elif [ "$program_opt" = "orca" ]; then
       geo="$(get_geom_orca.sh $tsdirll/$name.out | awk '{if(NF==4) print $0};END{print ""}')"
    fi

    # Build input file for the HL program
    if [ "$program_hl" = "g16" ] || [ "$program_hl" = "g09" ]; then
       g09_input
    elif [ "$program_hl" = "orca" ]; then
       orca_input
    elif [ "$program_hl" = "mlip" ]; then
       inp_hl="$(printf "$natom\n\n$geo")"
    else
       ${program_hl}_input
    fi

    echo -e "insert or ignore into gaussian values (NULL,'$name','$inp_hl');\n.quit" | sqlite3 ${tsdirhl}/inputs.db
  fi
done
echo "$m TS opt calculations"

# Check / build input for the initial minimum (min0)
if [ -f $tsdirhl/min0.log ]; then
   if [ "$program_hl" = "g09" ] || [ "$program_hl" = "g16" ]; then
      calc=$(awk 'BEGIN{calc=1;nt=0};/Normal termi/{++nt};/Error termi/{calc=0};END{if(nt=='$noHLcalc') calc=0;print calc}' $tsdirhl/min0.log)
   elif [ "$program_hl" = "orca" ]; then
      calc=$(awk 'BEGIN{calc=1;nt=0};/ORCA TERMINATED NORMALLY/{++nt};/ERROR !!!/{calc=0};END{if(nt==1) calc=0;print calc}' $tsdirhl/min0.log)
   elif [ "$program_hl" = "qcore" ]; then
      calc=$(awk 'BEGIN{calc=1;ncheck=0};/Energy=/{if(NF==2) ncheck+=1};/Lowest/{ncheck+=1};/Error/{calc=0};END{if(ncheck==2) calc=0;print calc}' $tsdirhl/min0.log)
   elif [ "$program_hl" = "mlip" ]; then
      calc=$(awk 'BEGIN{calc=1};/AMK_TERMINATED_NORMALLY/{calc=0};END{print calc}' $tsdirhl/min0.log)
   fi
else
   calc=1
fi

if [ $calc -eq 0 ]; then
   echo "min0 already optimized"
else
   ((m=m+1))
   echo "min0 not optimized"

   chkfile=min0
   calc=min
   level=hl
   geo="$(awk '{if(NF==4) print $0};END{print ""}' ${min0}_ref.xyz)"

   if [ "$program_hl" = "g16" ] || [ "$program_hl" = "g09" ]; then
      g09_input
   elif [ "$program_hl" = "orca" ]; then
      orca_input
   elif [ "$program_hl" = "mlip" ]; then
      inp_hl="$(printf "$natom\n\n$geo")"
   else
      ${program_hl}_input
   fi

   echo -e "insert or ignore into gaussian values (NULL,'min0','$inp_hl');\n.quit" | sqlite3 ${tsdirhl}/inputs.db
fi

echo Performing a total of $m ts opt calculations
if [ $m -gt 0 ]; then
   if [ "$program_hl" = "mlip" ]; then
      # Load model once and process all TSs sequentially to avoid GPU OOM
      mlip_calc.py batch tsopt $tsdirhl $mlip_model $models_dir $charge $mult
   else
      doparallel "runTS.sh {1} $tsdirhl $program_hl" "$(seq $m)"
   fi
fi