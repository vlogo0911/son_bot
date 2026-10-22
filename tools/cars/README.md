# NEON RUSH mashina modellari

Natija: `games/neon_rush/car_hi.glb` (yaqin, ~34k uchburchak, 512px teksturalar) va `car_lo.glb` (uzoq LOD, ~9k, teksturasiz).

Manba: **"Car Concept"** — Khronos Group glTF-Sample-Assets (`Models/CarConcept/glTF-WEBP`), muallif Eric Chadwick
(Darmstadt Graphics Group), litsenziya **CC BY 4.0**. Asl model — Unity Fan, Sketchfab'da public domain (CC0).
Khronos logotiplari va savdo belgilari litsenziyaga kirmaydi — `build.mjs` ularni (Khronos_C teksturasi) olib tashlaydi.
O'yin ichida (HOW TO PLAY) muallif va litsenziya ko'rsatilgan.

O'zgartirishlar: salon, dvigatel, dvorniklar, tormoz kolodkalari, raqam belgisi olib tashlangan; material variantlari,
iridescence/transmission o'chirilgan; material bo'yicha birlashtirilgan, meshopt simplify, WebP teksturalar, quantize + meshopt.

```
git clone --depth 1 --filter=blob:none --sparse https://github.com/KhronosGroup/gltf-sample-assets && git -C gltf-sample-assets sparse-checkout set Models/CarConcept
node build.mjs gltf-sample-assets/Models/CarConcept/glTF-WEBP/CarConcept.gltf car_hi.glb 0.25 512 0.003
node build.mjs gltf-sample-assets/Models/CarConcept/glTF-WEBP/CarConcept.gltf car_lo.glb 0.06 256 0.004 lod
```
`build.mjs` global `gltf-transform` CLI ichidagi modullardan foydalanadi (`/opt/node22/lib/node_modules/@gltf-transform/cli`).
