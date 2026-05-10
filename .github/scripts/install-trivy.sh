#!/usr/bin/env bash
set -euo pipefail

TRIVY_VERSION="${TRIVY_VERSION:-0.70.0}"

OS="Linux"
ARCH="64bit"

BASE_URL="https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}"
TARBALL="trivy_${TRIVY_VERSION}_${OS}-${ARCH}.tar.gz"
CHECKSUMS="trivy_${TRIVY_VERSION}_checksums.txt"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Installing Trivy v${TRIVY_VERSION}"

curl -fsSLo "${TMP_DIR}/${TARBALL}" "${BASE_URL}/${TARBALL}"
curl -fsSLo "${TMP_DIR}/${CHECKSUMS}" "${BASE_URL}/${CHECKSUMS}"

cd "$TMP_DIR"

grep "[[:space:]]${TARBALL}$" "${CHECKSUMS}" | sha256sum -c -

sudo tar -xzf "${TARBALL}" -C /usr/local/bin trivy

trivy --version
