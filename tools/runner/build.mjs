// METRO DASH resurslari: Kenney "Train Kit", "City Kit (Commercial)", "Mini Characters" — barchasi CC0 (kenney.nl).
// Foydalanish: node build.mjs <kenney_papkalar_ildizi> <chiqish_papka>
//   → md_world.glb (poyezd/rels/bino — har model alohida nomlangan tugun), md_char_<nom>.glb (faqat kerakli animatsiyalar)
const M = '/opt/node22/lib/node_modules/@gltf-transform/cli/node_modules/';
const { NodeIO } = await import(M + '@gltf-transform/core/dist/index.js');
const { ALL_EXTENSIONS } = await import(M + '@gltf-transform/extensions/dist/index.js');
const F = await import(M + '@gltf-transform/functions/dist/index.js');
const { MeshoptEncoder } = await import(M + 'meshoptimizer/index.js');
const sharp = (await import(M + 'sharp/dist/index.mjs')).default;
const path = await import('node:path');
const [, , SRC, OUT] = process.argv;
await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
const TRAIN = path.join(SRC, 'kenney_train-kit/Models/GLB format'), CITY = path.join(SRC, 'kenney_city-kit-commercial_2.1/Models/GLB format');
const CHAR = path.join(SRC, 'kenney_mini-characters/Models/GLB format');
const WORLD = [
  ...['train-electric-subway-a', 'train-electric-subway-b', 'train-electric-subway-c', 'train-electric-city-a', 'train-electric-city-b', 'train-electric-city-c',
    'train-carriage-container-red', 'train-carriage-container-blue', 'train-carriage-container-green', 'track-single', 'train-tram-modern'].map((n) => [TRAIN, n]),
  ...['building-a', 'building-b', 'building-c', 'building-d', 'building-e', 'building-f', 'building-g', 'building-h', 'building-skyscraper-a', 'building-skyscraper-b',
    'building-skyscraper-c', 'low-detail-building-a', 'low-detail-building-c', 'low-detail-building-e', 'low-detail-building-wide-a', 'detail-awning', 'detail-parasol-a'].map((n) => [CITY, n]),
];
const out = new (await import(M + '@gltf-transform/core/dist/index.js')).Document();
const scene = out.createScene('world');
for (const [dir, name] of WORLD) {
  const d = await io.read(path.join(dir, name + '.glb'));
  const root = d.getRoot(); const sc = root.listScenes()[0];
  const g = d.createNode(name); for (const n of sc.listChildren()) { sc.removeChild(n); g.addChild(n); } sc.addChild(g);
  F.mergeDocuments(out, d);
}
const R = out.getRoot();
for (const s of R.listScenes()) if (s !== scene) { for (const n of s.listChildren()) { s.removeChild(n); scene.addChild(n); } s.dispose(); }
for (const b of R.listBuffers().slice(1)) { for (const a of R.listAccessors()) if (a.getBuffer() === b) a.setBuffer(R.listBuffers()[0]); b.dispose(); }
await out.transform(F.dedup(), F.prune(), F.weld(), F.textureCompress({ encoder: sharp, targetFormat: 'webp', quality: 90 }), F.quantize(), F.meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
await io.write(path.join(OUT, 'md_world.glb'), out);
console.log('md_world.glb nodes', scene.listChildren().map((n) => n.getName()).join(','));
// Personajlar
const KEEP = new Set(['idle', 'sprint', 'jump', 'fall', 'crouch', 'die', 'emote-yes']);
for (const g of ['male', 'female']) for (const v of 'abcdef') {
  const name = `character-${g}-${v}`, d = await io.read(path.join(CHAR, name + '.glb'));
  for (const a of d.getRoot().listAnimations()) if (!KEEP.has(a.getName())) a.dispose();
  await d.transform(F.prune(), F.dedup(), F.resample(), F.textureCompress({ encoder: sharp, targetFormat: 'webp', quality: 90 }), F.quantize(), F.meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
  await io.write(path.join(OUT, `md_char_${g[0]}${v}.glb`), d);
}
console.log('characters ok');
