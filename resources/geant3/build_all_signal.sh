#!/bin/sh
# /resources read-only, /work empty writable, pinned image only.
set -eu
/bin/sh /resources/build_signal.sh
/bin/sh /resources/build_digitizer.sh
/bin/sh /resources/build_prean.sh
cd /work
sha256sum build/laggen/laggen build/laggen/transport_probe build/lagdig/lagdig build/prean/prean > build-binaries.sha256
