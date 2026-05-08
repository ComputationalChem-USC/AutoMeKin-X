#!/bin/bash
file=$1
# Última energía SCF convergida (DFT)
awk '/FINAL SINGLE POINT ENERGY/{e=$NF} END{printf "%14.9f\n",e}' $file
