#!/bin/bash
# opt.sh in.glb out.glb [texsize]
set -e
T=$(mktemp -d); S=${3:-1024}
gltf-transform prune "$1" $T/a.glb >/dev/null
gltf-transform weld $T/a.glb $T/b.glb >/dev/null
gltf-transform resize $T/b.glb $T/c.glb --width $S --height $S >/dev/null
gltf-transform webp $T/c.glb $T/d.glb --quality 82 >/dev/null
gltf-transform quantize $T/d.glb $T/e.glb --pattern "{POSITION,NORMAL,TEXCOORD_0}" >/dev/null
gltf-transform meshopt $T/e.glb "$2" >/dev/null
rm -rf $T
