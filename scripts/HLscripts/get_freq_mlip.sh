#!/bin/bash
# Vibrational frequencies in cm-1 from MLIP log
# Skips near-zero (<50 cm-1), prints including imaginary (negative values)
awk '/VIBRATIONAL FREQUENCIES/{flag=1; next}
flag && /cm\*\*-1/{
   freq=$2+0
   val=freq; if(val<0) val=-val
   if(val<50) next
   printf "%5.0f\n", freq
}
/^$/{flag=0}' $1
