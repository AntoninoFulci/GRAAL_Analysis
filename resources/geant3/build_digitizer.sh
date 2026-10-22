#!/bin/sh
set -eu
export CERN_ROOT=/home/gmandaglio/graal/2004 PROGRAM=/home/gmandaglio/graal/software/prog GLIB=/home/gmandaglio/graal/software/lib MACHINE=Linux MACHINE_F77=Linux
test ! -e /work/build/lagdig
cp -a "$PROGRAM/lagdig" /work/build/lagdig
cd /work/build/lagdig
cp "$PROGRAM/include/GRAAL_period.h" GRAAL_period.h
sed -i 's/^#define GRAAL_26/*#define GRAAL_26/; s/^\*#define GRAAL_21/#define GRAAL_21/' GRAAL_period.h
cp pilot.h pilot.h.original
sed -i 's/^\*#define GRAAL_T_BGO/#define GRAAL_T_BGO/' pilot.h
sed -i '/^#define OFFSET/d; /^#define GRAAL_OMEGA/d; /^#define GRAAL_NEW_CYL/d; s/^\*#define GRAAL_OLD_CYL/#define GRAAL_OLD_CYL/' pilot.h
sed -i 's/IDRUN:U:8,IDEVT:U:23/IDRUN:U:16,IDEVT:U:24/' src/opennt_out.F
# Explicit seed replaces wall-clock seeding of g77 RAND sequence.
sed -i '/INTEGER\*4 ISL/a\      CHARACTER*32 CSEED' src/init_random.F
sed -i 's/CALL SRAND(II)/CALL GETENVF(\x27GRAAL_DIG_SEED\x27,CSEED)\n      READ(CSEED,*) II\n      CALL RDMIN(II)\n      CALL SRAND(II)/' src/init_random.F
find src -name '*.o' -delete
sed '/^# DO NOT DELETE/,$d' src/Makefile > src/Makefile.signal
cd src
make -f Makefile.signal FC="/usr/bin/g77 -B/usr/lib/i386-linux-gnu/" all
sha256sum ../lagdig
