# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.
#
# The container `build.sh` runs in. `base-builder-python` is the image
# ClusterFuzzLite's docs/build-integration/python_lang.md names for a
# Python project: atheris and what `compile_python_fuzzer` runs are
# pre-installed there, and so is the `cmake` scripts/cffi_build.py
# drives over the vendored library, which is why nothing is installed
# here.
#
# ClusterFuzzLite copies the checked-out tree in rather than cloning it:
# `COPY .` is what puts the source `docker build` sees on disk, and the
# vendored `secp256k1/` arrives only where that tree holds it, which is
# what .github/workflows/fuzz.yml's header is about.
FROM gcr.io/oss-fuzz-base/base-builder-python

COPY . $SRC/btclib-secp256k1
WORKDIR $SRC/btclib-secp256k1
COPY ./.clusterfuzzlite/build.sh $SRC/
