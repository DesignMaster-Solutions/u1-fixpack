#!/bin/sh
# Inside the firmware image: turn patches/0018 and 0022 into git format-patch files that sit on top
# of the Extended firmware's 01..08, named as its overlay names them (09_*, 10_*).
# Usage: docker run --rm -v "$PWD:/fixpack" --entrypoint sh u1-fixpack:2.1.0 /fixpack/tests/extended/format.sh
set -e
out=/fixpack/out/extended/pr
rm -rf /tmp/f "$out"; mkdir -p "$out"
cp -a /opt/klipper /tmp/f; cd /tmp/f
git -c user.name=x -c user.email=x@x checkout -q -b extended
for p in /fixpack/out/extended/ext/*.patch; do git apply "$p"; done
git -c user.name=ext -c user.email=ext@ext commit -qam "Extended 01..08"
n=9
for src in 0018-fan-gcode-motion-sync 0022-exclude-object-manual-move; do
  f=/fixpack/patches/$src.patch
  # message = folded Subject (minus "[PATCH] ") + body up to the first "diff --git"
  # Trailers written above the body in our patch (Suggested-by:) move to the end, as git expects.
  awk '/^Subject: /{sub(/^Subject: \[PATCH\] /,""); s=$0; insub=1; next}
       insub && /^ /{sub(/^ /,""); s=s" "$0; next}
       insub{insub=0; print s; print ""; body=1}
       body && (/^diff --git / || /^---$/ || /^--- a\//){exit}
       body && /^[A-Z][a-z-]+-by: /{t=t $0 "\n"; next}
       body{b=b $0 "\n"}
       END{sub(/\n+$/,"\n",b); printf "%s", b; if (t!="") printf "\n%s", t}' "$f" > /tmp/msg
  git apply "$f"
  git -c user.name="Alan de Bortolo" -c user.email=info@designmastersolutions.com \
      commit -qa --author="Alan de Bortolo <info@designmastersolutions.com>" -F /tmp/msg
  name=$(printf '%02d_%s.patch' $n "$(echo "${src#*-}" | tr - _)")
  git format-patch -1 --stdout --no-signature > "$out/$name"
  echo "$out/$name: $(head -4 "$out/$name" | sed -n 's/^Subject: //p')"
  n=$((n+1))
done
