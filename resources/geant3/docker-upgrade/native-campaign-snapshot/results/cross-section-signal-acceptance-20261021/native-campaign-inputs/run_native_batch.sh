#!/bin/sh
set -eu
campaign=/data/graal/GRAAL_Analysis/results/cross-section-native-campaign-20261021
case "${1:-}" in
  uniform-smoke-100) batch=$1; dig_seed=310031;;
  uniform-production-99900) batch=$1; dig_seed=310035;;
  *) exit 2;;
esac
out=$campaign/$batch
test ! -e "$out/chain.log"
docker run --rm --name "graal-xs-$batch-20261021" --platform linux/386   --network none --read-only --cpus 2 --memory 2g --pids-limit 256   --tmpfs /tmp:rw,size=256m --env "GRAAL_DIG_SEED=$dig_seed"   -v "$campaign/build-output/build:/build:ro"   -v "$campaign/resource_snapshot:/resources:ro" -v "$out:/work"   --entrypoint /bin/sh   afulci/ubuntu77@sha256:cb810e84914ae1a440663c391b26058c3bb13fff1b41760da6bbc4d1c31a3ca6   /resources/run_signal_chain.sh > "$out/chain.log" 2>&1
cd "$out"
/data/soft/root-6.36.02/bin/h2root out_prean/signal.pol converted.root > conversion.log 2>&1
sha256sum generated_signal.dat generated_decays.dat converted.root > completed-sha256.txt
