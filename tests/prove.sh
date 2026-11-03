#!/bin/sh
# Red/green/mutant proof for every tests/test_issueNN.py, on the real firmware in the image.
#   stock firmware (93cb12f)          -> the issue's test must FAIL
#   with every patches/*.patch        -> it must PASS
#   with each tests/mutants/NN-*.patch -> it must FAIL
# Usage, from the repo root: tests/prove.sh [image] [evidence-root]   (exit 0 = all as expected)
image=${1:-u1-fixpack:local}
evidence=$2
status=0
check() {  # issue label patches expected
  out=$(docker run --rm -e FIXPACK_PATCHES="$3" -v "$PWD:/fixpack" -w /fixpack/tests \
        --entrypoint python3 "$image" -m unittest -v "test_issue$1" 2>&1)
  rc=$?
  if [ "$4" = pass ]; then [ $rc -eq 0 ]; else [ $rc -ne 0 ]; fi && verdict=ok || { verdict=UNEXPECTED; status=1; }
  echo "#$1 $2: expected $4, unittest exit $rc -> $verdict"
  if [ -n "$evidence" ]; then
    mkdir -p "$evidence/issue-$1"
    { echo "firmware: u1-klipper 93cb12f, FIXPACK_PATCHES=$3"; echo "expected: $4; unittest exit code: $rc ($verdict)"; echo; echo "$out"; } \
      > "$evidence/issue-$1/harness-$2.txt"
  fi
}
for t in tests/test_issue*.py; do
  n=$(basename "$t" .py | sed 's/test_issue//')
  check "$n" stock none fail
  check "$n" patched all pass
  for m in tests/mutants/"$n"-*.patch; do
    [ -e "$m" ] || continue
    check "$n" "mutant-$(basename "$m" .patch | sed "s/^$n-//")" "$m" fail
  done
done
exit $status
