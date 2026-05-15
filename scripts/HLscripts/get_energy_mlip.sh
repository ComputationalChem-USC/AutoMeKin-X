#!/bin/bash
# Energy in Hartree from MLIP log - takes LAST instance
awk '/FINAL SINGLE POINT ENERGY/{e=$NF} END{printf "%14.9f\n",e}' $1
