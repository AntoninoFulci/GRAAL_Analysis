#!/bin/sh
set -eu
export CERN_ROOT=/home/gmandaglio/graal/2004 PROGRAM=/home/gmandaglio/graal/software/prog GLIB=/home/gmandaglio/graal/software/lib MACHINE=Linux MACHINE_F77=Linux
test ! -e /work/build/prean
cp -a "$PROGRAM/prean" /work/build/prean
cd /work/build/prean
sed -i '/^#define GRAAL_NEW_CYL/d; s/^\*#define GRAAL_OLD_CYL/#define GRAAL_OLD_CYL/' pilot.h
cp "$PROGRAM/include/GRAAL_period.h" GRAAL_period.h
sed -i 's/^#define GRAAL_26/*#define GRAAL_26/; s/^\*#define GRAAL_21/#define GRAAL_21/' GRAAL_period.h
# Barrel cabling/run trigger overrides belong only to real decoded data.
sed -i 's/IF((IDRUN.GE.3778).AND.(IDRUN.LE.4407))THEN/IF(LDATA.AND.(IDRUN.GE.3778).AND.(IDRUN.LE.4407))THEN/; s/IF (IDRUN.LE.666) ITRIG=1/IF (LDATA.AND.IDRUN.LE.666) ITRIG=1/' src/readevents.F
find src -name '*.o' -delete
sed '/^# DO NOT DELETE/,$d; s/ ; make version ; make clean//' src/Makefile > src/Makefile.signal
cd src
make -f Makefile.signal FC='/usr/bin/g77 -B/usr/lib/i386-linux-gnu/' all
sha256sum ../prean
