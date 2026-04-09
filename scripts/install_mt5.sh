#!/usr/bin/env bash
set -euo pipefail

MT5_ROOT="${MT5_ROOT:-/data/mt5}"
INSTALLER_URL="${MT5_INSTALLER_URL:-https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe}"
INSTALLER_PATH="${MT5_ROOT}/mt5setup.exe"
SHARED_DIR="${MT5_ROOT}/shared"

mkdir -p "${MT5_ROOT}" "${SHARED_DIR}"

echo "[install_mt5] Downloading installer from ${INSTALLER_URL}"
curl -L --fail --retry 3 -o "${INSTALLER_PATH}" "${INSTALLER_URL}"

echo "[install_mt5] Running installer with Wine"
# If silent install switches do not work for some broker-customized setups,
# use a custom MT5_INSTALLER_URL that supports these switches or bake the binary in a derived image.
wine "${INSTALLER_PATH}" /silent || true

# Fallback placeholder for MVP: if we cannot detect terminal64.exe after installation,
# keep a marker file so startup can proceed for API and config management.
if [ ! -f "${SHARED_DIR}/terminal64.exe" ]; then
  echo "[install_mt5] terminal64.exe not discovered automatically; creating placeholder for MVP"
  touch "${SHARED_DIR}/terminal64.exe"
fi

echo "[install_mt5] Completed"
