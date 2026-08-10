#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" != "2" || ( "$1" != "--simulate" && "$1" != "--install" ) ]]; then
  printf '%s\n' "FAIL offline_debian_installer_arguments" >&2
  exit 2
fi

MODE="$1"
DEBIAN_ROOT="$2"
if [[ \
  "${DEBIAN_ROOT}" != /* \
  || ! -d "${DEBIAN_ROOT}" \
  || -L "${DEBIAN_ROOT}" \
  || ! -f "${DEBIAN_ROOT}/Packages" \
  || ! -f "${DEBIAN_ROOT}/Packages.gz" \
  || ! -f "${DEBIAN_ROOT}/package-specs.txt" \
  || ( "${MODE}" == "--install" && "$(id -u)" != "0" ) \
]]; then
  printf '%s\n' "FAIL offline_debian_installer_inputs" >&2
  exit 1
fi

PACKAGE_SPECS=()
while IFS= read -r package_spec || [[ -n "${package_spec}" ]]; do
  PACKAGE_SPECS+=("${package_spec}")
done < "${DEBIAN_ROOT}/package-specs.txt"
if [[ "${#PACKAGE_SPECS[@]}" == "0" ]]; then
  printf '%s\n' "FAIL offline_debian_installer_package_specs" >&2
  exit 1
fi
for package_spec in "${PACKAGE_SPECS[@]}"; do
  if [[ ! "${package_spec}" =~ ^[a-z0-9][a-z0-9+.-]*=[^[:space:]]+$ ]]; then
    printf '%s\n' "FAIL offline_debian_installer_package_specs" >&2
    exit 1
  fi
done

APT_ROOT="$(mktemp -d)"
cleanup() {
  rm -rf "${APT_ROOT}"
}
trap cleanup EXIT

SOURCE_LIST="${APT_ROOT}/local.list"
SOURCE_PARTS="${APT_ROOT}/source-parts"
APT_LISTS="${APT_ROOT}/lists"
APT_ARCHIVES="${APT_ROOT}/archives"
printf 'deb [trusted=yes] file:%s ./\n' "${DEBIAN_ROOT}" > "${SOURCE_LIST}"
mkdir -p "${SOURCE_PARTS}" "${APT_LISTS}/partial" "${APT_ARCHIVES}/partial"
APT_OPTIONS=(
  -o Dir::Etc::main=/dev/null
  -o Dir::Etc::parts=-
  -o "Dir::Etc::sourcelist=${SOURCE_LIST}"
  -o "Dir::Etc::sourceparts=${SOURCE_PARTS}"
  -o "Dir::State::lists=${APT_LISTS}"
  -o "Dir::Cache::archives=${APT_ARCHIVES}"
  -o Acquire::Languages=none
)

apt-get "${APT_OPTIONS[@]}" update -qq
if [[ "${MODE}" == "--simulate" ]]; then
  APT_STATUS="${APT_ROOT}/status"
  : > "${APT_STATUS}"
  apt-get "${APT_OPTIONS[@]}" -o "Dir::State::status=${APT_STATUS}" \
    install --simulate --no-install-recommends "${PACKAGE_SPECS[@]}"
else
  apt-get "${APT_OPTIONS[@]}" install -y -qq --allow-downgrades \
    --no-install-recommends "${PACKAGE_SPECS[@]}"
fi
