# Copyright (c) The btclib developers
# Distributed under the MIT software license, see the accompanying
# LICENSE file or https://opensource.org/license/mit for the full text.
#
# uv, pinned by digest below the same way as the image build.sh runs in:
# build.sh reads uv.lock through it, and the image below carries no uv
# of its own (install_python.sh, upstream, installs only atheris,
# pyinstaller, setuptools and coverage). A `pip3 install uv` inside
# build.sh would fetch it unpinned -- Scorecard's PinnedDependenciesID
# reads any argument to `pip install` that is not a wheel, an editable
# local source or `-r <hashed file>` as unpinned, a bare version
# constraint included -- where a digest-pinned distroless image copied
# in below is a dependency `docker`'s own Dependabot entry already
# tracks (btclib-org/btclib-wallet's identical Dockerfile is the same
# pattern, one repository over).
FROM ghcr.io/astral-sh/uv@sha256:a7aed3216253ee804de3e2d8afa5073baa1a177335345d43845cd4165e43b711 AS uv

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
#
# Pinned to a digest, the tag it resolves named in this comment rather
# than trailing the line the way `uses:`'s `# vN` does elsewhere in this
# tree: a Dockerfile's `FROM` takes one argument, or three with
# `AS <name>`, and a fourth token is a parse error rather than a
# comment, `#` opening one only where a line starts with it.
#
# `latest` and `v1` are this image's only tags, and both name the same
# digest as of this pin, so whether it is current is read from the
# registry rather than from this comment:
#
#   S=repository:oss-fuzz-base/base-builder-python:pull
#   T=$(curl -s "https://gcr.io/v2/token?service=gcr.io&scope=$S" \
#     | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')
#   curl -sI -H "Authorization: Bearer $T" \
#     https://gcr.io/v2/oss-fuzz-base/base-builder-python/manifests/latest \
#     | grep -i docker-content-digest
#
# a digest other than the one this line pins is `latest` having moved
FROM gcr.io/oss-fuzz-base/base-builder-python@sha256:58f80c90a90944b68b8e70b98e38997ee9396225311cfb0f3aea78671446ab4e

COPY --from=uv /uv /usr/local/bin/uv

COPY . $SRC/btclib-secp256k1
WORKDIR $SRC/btclib-secp256k1
COPY ./.clusterfuzzlite/build.sh $SRC/
