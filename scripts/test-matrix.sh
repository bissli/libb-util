#!/usr/bin/env bash
# Run the test suite against every supported interpreter.
#
# Notes:
# - uv provisions the interpreters itself, which is why this replaced tox:
#   tox can only use interpreters already on the host, and neither a 3.15
#   prerelease nor a free-threaded build is normally installed.
# - Extras are read from pyproject.toml rather than restated, so this cannot
#   drift from the package metadata the way tox.ini's copied dep list did.
# - Each version gets its own venv under .venvs/ because the compiled
#   extension is version-specific; a shared venv would load a stale .so.

set -uo pipefail

STABLE_VERSIONS=${STABLE_VERSIONS:-"3.10 3.11 3.12 3.13 3.14"}
# Versions that are allowed to fail: a prerelease interpreter, and any build
# whose compiled dependencies have no wheels yet.
PRERELEASE_VERSIONS=${PRERELEASE_VERSIONS:-"3.15"}
FREETHREADED_VERSIONS=${FREETHREADED_VERSIONS:-"3.14t"}

# pyarrow needs the Arrow C++ toolchain to build from source, so it cannot be
# installed on any interpreter that has no prebuilt wheel yet.
FULL_EXTRAS="test,pandas,text,math,web,ldapauth,tokenauth"
REDUCED_EXTRAS="test,text,math,ldapauth,tokenauth"

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

command -v uv >/dev/null || { echo "ERROR: uv is required (https://docs.astral.sh/uv/)"; exit 1; }

declare -a PASSED=() FAILED=() SOFT_FAILED=()

run_one() {
    local version=$1 extras=$2 soft=$3
    local venv=".venvs/$version"

    echo
    echo "=================================================================="
    echo " Python $version  (extras: $extras)"
    echo "=================================================================="

    rm -rf "$venv"
    if ! uv venv --python "$version" "$venv"; then
        echo "SKIP: uv could not provision Python $version"
        [ "$soft" = "soft" ] && SOFT_FAILED+=("$version (no interpreter)") \
                             || FAILED+=("$version (no interpreter)")
        return
    fi

    # A stale uv download index silently resolves a bare "3.15" to an old
    # alpha, and a PyO3 extension built for one alpha fails to import on
    # another (the module slots were renumbered during the 3.15 cycle). An
    # alpha therefore tests nothing useful; say so instead of reporting a
    # failure that is really an out-of-date toolchain.
    local resolved
    resolved=$("$venv/bin/python" -c 'import sys; print(sys.version.split()[0])')
    if [[ "$resolved" == *a* ]]; then
        echo "SKIP: $version resolved to $resolved (alpha); update uv for a current build"
        SOFT_FAILED+=("$version (stale index -> $resolved)")
        return
    fi
    echo "Resolved to $resolved"

    # A stale .so from another interpreter shadows the module it was built
    # from, so clear it before rebuilding.
    rm -f src/libb/*.so src/libb/*.pyd

    if ! VIRTUAL_ENV="$venv" uv pip install --quiet -e ".[$extras]"; then
        echo "FAIL: dependency install"
        [ "$soft" = "soft" ] && SOFT_FAILED+=("$version (install)") \
                             || FAILED+=("$version (install)")
        return
    fi

    # doctest.rst is named explicitly: it sits outside pytest.ini's testpaths,
    # so `pytest tests/` never collects it. That gap hid a VirtualModule
    # recursion bug that had been failing since 3.13. It walks every module
    # including the pandas-backed ones, so it only means anything where the
    # full extras installed.
    local targets=(tests/)
    [ "$extras" = "$FULL_EXTRAS" ] && targets+=(doctest.rst)

    if "$venv/bin/python" -m pytest "${targets[@]}" -q --no-header -p no:cacheprovider; then
        PASSED+=("$version")
    else
        [ "$soft" = "soft" ] && SOFT_FAILED+=("$version (tests)") \
                             || FAILED+=("$version (tests)")
    fi
}

for v in $STABLE_VERSIONS; do run_one "$v" "$FULL_EXTRAS" hard; done
for v in $PRERELEASE_VERSIONS; do run_one "$v" "$REDUCED_EXTRAS" soft; done
for v in $FREETHREADED_VERSIONS; do run_one "$v" "$REDUCED_EXTRAS" soft; done

echo
echo "=================================================================="
echo " Summary"
echo "=================================================================="
[ ${#PASSED[@]} -gt 0 ] && printf 'PASS      %s\n' "${PASSED[@]}"
[ ${#SOFT_FAILED[@]} -gt 0 ] && printf 'ALLOWED   %s\n' "${SOFT_FAILED[@]}"
[ ${#FAILED[@]} -gt 0 ] && printf 'FAIL      %s\n' "${FAILED[@]}"

[ ${#FAILED[@]} -eq 0 ] || exit 1
echo
echo "All required interpreters passed."
