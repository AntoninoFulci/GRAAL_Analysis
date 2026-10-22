#!/bin/sh
# Runs only inside pinned afulci/ubuntu77 image. /work is isolated output.
set -eu
export CERN_ROOT=/home/gmandaglio/graal/2004
export PROGRAM=/home/gmandaglio/graal/software/prog
export GLIB=/home/gmandaglio/graal/software/lib
export MACHINE=Linux MACHINE_F77=Linux
mkdir -p /work/build
test ! -e /work/build/laggen
cp -a "$PROGRAM/laggen" /work/build/laggen
cd /work/build/laggen
cp "$PROGRAM/include/GRAAL_period.h" GRAAL_period.h
sed -i 's/^#define GRAAL_26/*#define GRAAL_26/; s/^\*#define GRAAL_21/#define GRAAL_21/' GRAAL_period.h
patch -p1 < /resources/signal.patch
patch -p1 < /resources/energy_window.patch
# Discard archived objects; stale dependency paths refer to old machines.
find src -name '*.o' -delete
sed '/^# DO NOT DELETE/,$d' src/Makefile > src/Makefile.signal
cp "$CERN_ROOT/src/geant321/gtrak/gsking.F" src/gsking.F
sed -i 's/OBJS = /OBJS = gsking.o /' src/Makefile.signal
cd src
make -f Makefile.signal FC="/usr/bin/g77 -B/usr/lib/i386-linux-gnu/" GRAAL_CONDOR_POOL=0 all
# Exercise the historical GEANT object, not a recompiled substitute. Some
# emulated x87 environments silently absorb above-cut photons at zero path.
/usr/bin/g77 -B/usr/lib/i386-linux-gnu/ -O -I"$CERN_ROOT/include" \
  /resources/transport_probe.F -L"$CERN_ROOT/lib" \
  -lgeant321 -lpacklib -lkernlib -lmathlib -o ../transport_probe
sha256sum ../laggen
