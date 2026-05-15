#!/bin/bash
# ZPE in kcal/mol from MLIP log - takes LAST instance
awk '/Zero point energy/{zpe=$(NF-1)} END{print zpe}' $1
