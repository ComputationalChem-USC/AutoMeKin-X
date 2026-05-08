#!/bin/bash
# ZPE in kcal/mol from ORCA output - takes LAST instance
awk '/Zero point energy/{zpe=$(NF-1)} END{print zpe}' $1
