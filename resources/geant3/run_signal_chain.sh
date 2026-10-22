#!/bin/sh
# Pinned offline container; output directory mounted as /work.
set -eu
/build/laggen/transport_probe > /work/transport_probe.log 2>&1
grep -q '^ TRANSPORT PROBE PASS' /work/transport_probe.log
GRAAL=/home/gmandaglio/graal
export CERN_ROOT=$GRAAL/2004 LAGGEN=$GRAAL/software/prog/laggen/
for program in laggen lagdig prean; do
  grep -q '^#define GRAAL_21$' /build/$program/GRAAL_period.h
  grep -q '^#define GRAAL_OLD_CYL$' /build/$program/pilot.h
done
mkdir -p /tmp/signal_input
cp /work/laggen_signal.dat /tmp/signal_input/
ln -s "$GRAAL/data/inp_laggen/channel.mat" /tmp/signal_input/channel.mat
export INP_LAGGEN=/tmp/signal_input/ OUT_LAGGEN=/work/out_laggen/
export OUT_LAGDIG=/work/out_lagdig/ OUT_PREAN_SIM=/work/out_prean/
export BEAM=$GRAAL/data/simul_beam/ TAG_DAT=$GRAAL/data/simul_beam/
mkdir -p /work/base
sed 's/^6\. *!THLENGTH/12.             !THLENGTH/' "$GRAAL/data/base/data21.base" > /work/base/data21.base
export KILL_LAGGEN=/tmp/stop_requested DATA_BASE=/work/base/
export CALIB_TAG=$GRAAL/data/calib_tag/ CALIB_STRIP=$GRAAL/data/calib_strip/
export CALIB_BGO=$GRAAL/data/calib_bgo/ CALIB_BARREL=$GRAAL/data/calib_barrel/
export CALIB_WALL=$GRAAL/data/calib_wall/ CALIB_MWPC=$GRAAL/data/calib_mwpc/
export CALIB_RW=$GRAAL/data/calib_rw/ BGO_SOFT_THRES=0.002 CLUS_SOFT_THRES=0.015
mkdir -p /work/out_laggen /work/out_lagdig /work/out_prean
cd /work
sha256sum /build/laggen/laggen /build/laggen/transport_probe /build/lagdig/lagdig /build/prean/prean > binary-sha256.txt
sha256sum /build/laggen/src/gsking.F "$CERN_ROOT/lib/libgeant321.a" "$CERN_ROOT/lib/libphtools.a" "$CERN_ROOT/lib/libkernlib.a" /build/laggen/GRAAL_period.h /build/lagdig/GRAAL_period.h /build/prean/GRAAL_period.h /build/laggen/pilot.h /build/lagdig/pilot.h /build/prean/pilot.h "$BEAM/tag.hist" "$CALIB_WALL/calib_3700.cal" "$CALIB_RW/rw_calibr_144_391.dat" > dependency-sha256.txt
/build/laggen/laggen signal signal > laggen.log 2>&1
grep -q 'Time of CPU Used =' laggen.log
/build/lagdig/lagdig signal 21 > lagdig.log 2>&1
grep -q 'Normal termination' lagdig.log
/build/prean/prean signal S T C 2 1 > prean.log 2>&1
grep -q 'Normal Termination' prean.log
sha256sum out_laggen/signal.hit out_lagdig/signal.dig out_prean/signal.pol
