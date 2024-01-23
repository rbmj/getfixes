#!/bin/bash
for i in `ls *.fix`; do python3 getfixes.py < $i > $i.csv ; done
