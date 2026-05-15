#!/bin/bash
sharedir=${AMK}/share
source utils.sh
tmp_files=(tmp*)
trap 'err_report $LINENO' ERR
trap cleanup2 EXIT INT

exe=$(basename $0)
cwd=$PWD
inputfile=amk.dat
read_input

i=$1
get_geom_irc   # sets geof, geor, chkfilef, chkfiler

inp_hlminf="$(printf "$natom\n\n$geof")"
inp_hlminr="$(printf "$natom\n\n$geor")"

if [ -z "$diss" ]; then
   echo -e "insert or ignore into gaussian values (NULL,'minf_$i','$inp_hlminf');\n.quit" | sqlite3 ${tsdirhl}/IRC/inputs.db
   echo -e "insert or ignore into gaussian values (NULL,'minr_$i','$inp_hlminr');\n.quit" | sqlite3 ${tsdirhl}/IRC/inputs.db
else
   echo -e "insert or ignore into gaussian values (NULL,'min_diss_$i','$inp_hlminf');\n.quit" | sqlite3 ${tsdirhl}/IRC/DISS/inputs.db
fi
