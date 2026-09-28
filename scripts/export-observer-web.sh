#!/usr/bin/env bash
# Export the committed Web preset. Container and CI only; not a user launcher.
# Caller sets PALIMPSEST_REVISION. Destination is the first argument.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PINS="${ROOT}/clients/godot-observer/export/pins.env"
PROJECT="${ROOT}/clients/godot-observer/project.godot"
PRESET="${ROOT}/clients/godot-observer/export_presets.cfg"
CLIENT="${ROOT}/clients/godot-observer"
MIN_WASM_BYTES=4096

log_info() {
  printf 'INFO %s\n' "$*"
}

fail() {
  printf 'ERROR observer_export_failed reason_code=%s\n' "$1" >&2
  exit 1
}

ensure_writable_home() {
  if [[ -n "${HOME:-}" && -d "${HOME}" && -w "${HOME}" ]]; then
    export HOME
    return 0
  fi
  HOME="$(mktemp -d)"
  export HOME
}

load_pins() {
  if [[ ! -f "${PINS}" ]]; then
    fail "pins_missing"
  fi
  # shellcheck disable=SC1090
  set -a
  source "${PINS}"
  set +a
  : "${GODOT_VERSION:?}"
  : "${GODOT_LINUX_URL:?}"
  : "${GODOT_LINUX_SHA512:?}"
  : "${GODOT_TEMPLATES_URL:?}"
  : "${GODOT_TEMPLATES_SHA512:?}"
}

assert_project_contract() {
  if [[ "${GODOT_VERSION}" != "4.7.2-stable" ]]; then
    fail "version_pin"
  fi
  case "${GODOT_LINUX_URL}${GODOT_TEMPLATES_URL}" in
    *latest*) fail "latest_url_forbidden" ;;
  esac
  if ! grep -q 'platform="Web"' "${PRESET}"; then
    fail "preset_platform"
  fi
  if ! grep -q 'variant/thread_support=false' "${PRESET}"; then
    fail "thread_support"
  fi
  if ! grep -q 'renderer/rendering_method="gl_compatibility"' "${PROJECT}"; then
    fail "renderer"
  fi
  if ! grep -Fq 'config/features=PackedStringArray("4.7", "GL Compatibility")' "${PROJECT}"; then
    fail "features"
  fi
  if find "${CLIENT}" -name '*.csproj' -print -quit | grep -q .; then
    fail "csharp_project"
  fi
  if grep -Eq '^\[(dotnet|csharp|mono)\]' "${PROJECT}" "${PRESET}"; then
    fail "csharp_section"
  fi
}

download_checked() {
  local url="$1"
  local expected="$2"
  local name dest actual bytes
  name="$(basename "${url}")"
  dest="${WORKDIR}/${name}"
  if ! curl -fsSL --retry 3 --retry-delay 2 -o "${dest}" "${url}"; then
    fail "download_failed"
  fi
  actual="$(sha512sum "${dest}" | awk '{print $1}')"
  if [[ "${actual}" != "${expected}" ]]; then
    fail "checksum_mismatch"
  fi
  bytes="$(wc -c <"${dest}" | tr -d '[:space:]')"
  log_info "observer_export_download_ok file=${name} bytes=${bytes}"
}

application_version() {
  local version
  version="$(awk -F'"' '/^version = "/ { print $2; exit }' "${ROOT}/pyproject.toml")"
  if [[ -z "${version}" ]]; then
    fail "application_version_missing"
  fi
  printf '%s' "${version}"
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/}"
  value="${value//$'\r'/}"
  printf '%s' "${value}"
}

write_build_info() {
  local app_version revision escaped_revision
  app_version="$(application_version)"
  revision="${PALIMPSEST_REVISION:-unknown}"
  if [[ -z "${revision}" ]]; then
    revision="unknown"
  fi
  escaped_revision="$(json_escape "${revision}")"
  cat >"${DEST}/build-info.json" <<EOF
{
  "application_version": "${app_version}",
  "protocol_version": "observer-protocol-v1",
  "export_engine": "4.7.2-stable",
  "export_renderer": "gl_compatibility",
  "revision": "${escaped_revision}"
}
EOF
}

if [[ $# -lt 1 || -z "${1}" ]]; then
  fail "dest_missing"
fi

load_pins
assert_project_contract
ensure_writable_home

DEST="$(mkdir -p "$1" && cd "$1" && pwd)"
WORKDIR="$(mktemp -d)"
cleanup() {
  rm -rf "${WORKDIR}"
}
trap cleanup EXIT

download_checked "${GODOT_LINUX_URL}" "${GODOT_LINUX_SHA512}"
download_checked "${GODOT_TEMPLATES_URL}" "${GODOT_TEMPLATES_SHA512}"

mkdir -p "${WORKDIR}/editor" "${WORKDIR}/templates_pkg"
if ! unzip -q "${WORKDIR}/$(basename "${GODOT_LINUX_URL}")" -d "${WORKDIR}/editor"; then
  fail "unzip_failed"
fi
if ! unzip -q "${WORKDIR}/$(basename "${GODOT_TEMPLATES_URL}")" -d "${WORKDIR}/templates_pkg"; then
  fail "unzip_failed"
fi

BINARY="$(find "${WORKDIR}/editor" -type f -name 'Godot_v4.7.2-stable_linux.x86_64' -print -quit)"
if [[ -z "${BINARY}" ]]; then
  fail "binary_missing"
fi
chmod +x "${BINARY}"

TEMPLATES_DIR="$(find "${WORKDIR}/templates_pkg" -type d -name templates -print -quit)"
if [[ -z "${TEMPLATES_DIR}" ]]; then
  fail "templates_missing"
fi
TEMPLATE_HOME="${HOME}/.local/share/godot/export_templates/4.7.2.stable"
mkdir -p "${TEMPLATE_HOME}"
cp -a "${TEMPLATES_DIR}/." "${TEMPLATE_HOME}/"

VERSION_LINE="$("${BINARY}" --version 2>&1 | tr -d '\r' | head -n 1 || true)"
case "${VERSION_LINE}" in
  4.7.2.stable*)
    log_info "observer_export_version_ok version=${VERSION_LINE}"
    ;;
  *)
    fail "version_mismatch"
    ;;
esac

if ! "${BINARY}" --headless --path "${CLIENT}" --import; then
  fail "import_failed"
fi

log_info "observer_export_started preset=Web"
if ! "${BINARY}" --headless --path "${CLIENT}" --export-release "Web" "${DEST}/index.html"; then
  fail "export_failed"
fi

for required in index.html index.js index.wasm index.pck; do
  if [[ ! -f "${DEST}/${required}" ]]; then
    fail "missing_file"
  fi
done

WASM_BYTES="$(wc -c <"${DEST}/index.wasm" | tr -d '[:space:]')"
if [[ "${WASM_BYTES}" -lt "${MIN_WASM_BYTES}" ]]; then
  fail "wasm_trivial"
fi

write_build_info
FILE_COUNT="$(find "${DEST}" -type f | wc -l | tr -d '[:space:]')"
log_info "observer_export_finished file_count=${FILE_COUNT} wasm_bytes=${WASM_BYTES}"
