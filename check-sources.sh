#!/usr/bin/env bash
# check-sources.sh — repository gate.
#
# Enforces the invariants this repo promises:
#   1. No leaked working files (docs_manifest.json, progress.json, *.notion.*).
#   2. Zero third-party runtime dependencies: every import in the package
#      resolves to the standard library or to the package itself.
#   3. The HTML demo is self-contained: no external http(s) script/style/font.
#   4. The test suite passes.
set -euo pipefail
cd "$(dirname "$0")"
PKG="gantry_clearance"
fail(){ echo "FAIL: $1" >&2; exit 1; }
ok(){ echo "  ok  $1"; }

echo "[1/4] leaked working files"
LEAKS=$(find . -type f \( -name 'docs_manifest.json' -o -name 'progress.json' \
  -o -name '*.notion.*' -o -name '*.bid.*' \) 2>/dev/null || true)
[ -z "$LEAKS" ] || fail "leaked files present:\n$LEAKS"
ok "no docs_manifest.json / progress.json / notion / bid files"

echo "[2/4] zero third-party dependencies"
python3 - "$PKG" <<'PY' || fail "non-stdlib import found (see above)"
import ast,sys,pathlib
pkg=sys.argv[1]
std=set(sys.stdlib_module_names)
local={pkg}
bad=[]
for p in pathlib.Path(pkg).rglob("*.py"):
    tree=ast.parse(p.read_text(),filename=str(p))
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            mods=[a.name.split(".")[0] for a in n.names]
        elif isinstance(n,ast.ImportFrom):
            if n.level: continue
            mods=[(n.module or "").split(".")[0]]
        else: continue
        for m in mods:
            if m and m not in std and m not in local:
                bad.append(f"{p}: imports third-party '{m}'")
if bad:
    print("\n".join(bad),file=sys.stderr); sys.exit(1)
print("  ok  all imports resolve to stdlib or "+pkg)
PY

echo "[3/4] self-contained HTML demo"
if grep -RniE '(src|href)=["'"'"']https?://' demo/ >/dev/null 2>&1; then
  grep -RniE '(src|href)=["'"'"']https?://' demo/ >&2
  fail "demo references an external http(s) resource"
fi
ok "demo/ has no external http(s) resources"

echo "[4/4] test suite"
python3 -m pytest -q >/tmp/pytest_$PKG.log 2>&1 || { cat /tmp/pytest_$PKG.log; fail "pytest failed"; }
tail -1 /tmp/pytest_$PKG.log | sed 's/^/  /'

echo "PASS: all source invariants hold."
