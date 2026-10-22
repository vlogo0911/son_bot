// NEON RUSH mashina modeli: Khronos glTF-Sample-Assets "CarConcept" (CC-BY 4.0, Eric Chadwick; asli Unity Fan CC0)
// → logotiplar olib tashlanadi, salon/mayda detallar o'chiriladi, material bo'yicha birlashtiriladi, simplify, siqiladi.
// Foydalanish: node build.mjs <CarConcept.gltf (glTF-WEBP)> <chiqish.glb> <simplify_ratio> <tex_max>
const M = '/opt/node22/lib/node_modules/@gltf-transform/cli/node_modules/';
const { NodeIO } = await import(M + '@gltf-transform/core/dist/index.js');
const { ALL_EXTENSIONS, EXTMeshoptCompression, KHRMeshQuantization } = await import(M + '@gltf-transform/extensions/dist/index.js');
const F = await import(M + '@gltf-transform/functions/dist/index.js');
const { MeshoptSimplifier, MeshoptEncoder } = await import(M + 'meshoptimizer/index.js');
const sharp = (await import(M + 'sharp/dist/index.mjs')).default;
const [, , IN, OUT, RATIO = '0.25', TEX = '512', ERR = '0.003'] = process.argv;
await MeshoptSimplifier.ready; await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
const doc = await io.read(IN), root = doc.getRoot();
// 1) Ko'rinmaydigan / og'ir / logotipli qismlar
const DROP = /^(Interior|Engine|License|BodyWindshieldWipers|BodyHoodInterior|BodyHoodUnder|.*BrakePad)/;
for (const n of root.listNodes()) if (DROP.test(n.getName())) n.dispose();
// 2) Variantlar (boshqa ranglar), iridescence, transmission — mobil uchun keraksiz
for (const e of root.listExtensionsUsed()) if (/variants|iridescence|transmission|volume/i.test(e.extensionName)) e.dispose();
for (const t of root.listTextures()) if (/Khronos/i.test(t.getURI() + t.getName())) t.dispose();     // logotiplar litsenziyaga kirmaydi
for (const m of root.listMaterials()) {
  if (/glass/i.test(m.getName())) { m.setAlphaMode('BLEND').setBaseColorFactor([0.02, 0.03, 0.05, 0.82]).setRoughnessFactor(0.05).setMetallicFactor(0.2); }
  if (!m.getName()) m.setName('Trim');
}
// 2b) Uzoq LOD (5-argument "lod"): teksturalar/UV/normallar olib tashlanadi → choklarsiz kuchli soddalashtirish, keyin silliq normal
const LOD = process.argv[7] === 'lod';
if (LOD) {
  for (const m of root.listMaterials()) { m.setNormalTexture(null).setOcclusionTexture(null).setMetallicRoughnessTexture(null); if (!/Tireside/.test(m.getName())) m.setBaseColorTexture(null); }
  for (const me of root.listMeshes()) for (const p of me.listPrimitives()) for (const sem of p.listSemantics()) if (sem !== 'POSITION') p.setAttribute(sem, null);
}
// 3) Tozalash, birlashtirish, soddalashtirish
await doc.transform(
  F.prune(), F.dedup(), F.flatten(), F.join({ keepNamed: false }), F.weld(),
  F.simplify({ simplifier: MeshoptSimplifier, ratio: parseFloat(RATIO), error: parseFloat(ERR), lockBorder: !LOD }),
  ...(LOD ? [F.normals({ overwrite: true })] : []),
  F.prune(),
  F.textureCompress({ encoder: sharp, targetFormat: 'webp', resize: [parseInt(TEX), parseInt(TEX)], quality: 80 }),
  F.quantize(), F.meshopt({ encoder: MeshoptEncoder, level: 'medium' }),
);
await io.write(OUT, doc);
let tris = 0; for (const me of root.listMeshes()) for (const p of me.listPrimitives()) tris += (p.getIndices() ? p.getIndices().getCount() : p.getAttribute('POSITION').getCount()) / 3;
console.log(OUT, 'tris', Math.round(tris), 'meshes', root.listMeshes().length, 'materials', root.listMaterials().map((m) => m.getName()).join('|'));
