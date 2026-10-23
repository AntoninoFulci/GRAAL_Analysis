#!/bin/sh
# Run only inside the pinned linux/386 image, with a fresh build at /work.
set -eu
cd /work/src
/usr/bin/g77 -B/usr/lib/i386-linux-gnu/ -O -fno-globals \
  -fno-automatic -fno-second-underscore -ffixed-line-length-none \
  -I/work/include -I/home/gmandaglio/graal/2004/include ./*.F \
  -L/home/gmandaglio/graal/2004/lib \
  -lgeant321 -lgraflib -lgrafX11 -lpacklib -lkernlib -lmathlib -lX11 \
  -o /work/geometry_reference
/work/geometry_reference
test -s /work/geometry.g3
test -s /work/navigation.g3
