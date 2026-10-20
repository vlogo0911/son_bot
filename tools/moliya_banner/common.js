// Moliya bannerlari uchun umumiy: renderer, muhit, oltin material, EMP tanga
const W = 960, H = 480;
function setup(bgDraw, envStops) {
  const R = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
  R.setPixelRatio(2); R.setSize(W, H); R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFSoftShadowMap;
  R.toneMapping = THREE.ACESFilmicToneMapping; R.toneMappingExposure = 1.2; R.outputEncoding = THREE.sRGBEncoding;
  document.getElementById('stage').appendChild(R.domElement);
  const S = new THREE.Scene();
  const c = document.createElement('canvas'); c.width = W * 2; c.height = H * 2;
  bgDraw(c.getContext('2d'), c.width, c.height);
  const tx = new THREE.CanvasTexture(c); tx.encoding = THREE.sRGBEncoding; S.background = tx;
  // muhit (metall aksi)
  const envS = new THREE.Scene();
  const ec = document.createElement('canvas'); ec.width = 4; ec.height = 512; const eg = ec.getContext('2d');
  const l = eg.createLinearGradient(0, 0, 0, 512); envStops.forEach(([o, col]) => l.addColorStop(o, col)); eg.fillStyle = l; eg.fillRect(0, 0, 4, 512);
  const et = new THREE.CanvasTexture(ec); et.encoding = THREE.sRGBEncoding;
  envS.add(new THREE.Mesh(new THREE.SphereGeometry(10, 32, 16), new THREE.MeshBasicMaterial({side: THREE.BackSide, map: et})));
  for (const [x, y, z, w, h] of [[-4, 6, 3, 6, 3], [5, 2, 4, 2, 5], [0, -3, 6, 8, 1]]) {
    const p = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({color: 0xfff1cf}));
    p.position.set(x, y, z); p.lookAt(0, 0, 0); envS.add(p);
  }
  const pm = new THREE.PMREMGenerator(R); S.environment = pm.fromScene(envS, 0.03).texture;
  return {R, S};
}
const GOLD = () => new THREE.MeshPhysicalMaterial({color: 0xf2b640, metalness: 1, roughness: 0.22, clearcoat: 0.4, clearcoatRoughness: 0.15});
const GOLD_D = () => new THREE.MeshPhysicalMaterial({color: 0xb07a1c, metalness: 1, roughness: 0.32});
const STEEL = () => new THREE.MeshPhysicalMaterial({color: 0x2a2620, metalness: 0.9, roughness: 0.35});

function loadTex(url) {
  return new Promise(res => new THREE.TextureLoader().load(url, t => { t.encoding = THREE.sRGBEncoding; t.anisotropy = 8; res(t); }));
}
// EMP tanga: oltin qirrali silindr + ikki yuzida emp_face
function coin(face, r = 0.9, h = 0.14) {
  const g = new THREE.Group();
  const edge = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 96, 1, false), GOLD_D());
  // qirra tishchalari
  g.add(edge);
  for (let k = 0; k < 72; k++) {
    const a = k / 72 * Math.PI * 2;
    const n = new THREE.Mesh(new THREE.BoxGeometry(0.025, h * 0.86, 0.03), GOLD());
    n.position.set(Math.cos(a) * r, 0, Math.sin(a) * r); n.rotation.y = -a; g.add(n);
  }
  for (const s of [1, -1]) {
    const back = new THREE.Mesh(new THREE.CircleGeometry(r * 0.995, 96), GOLD());
    back.rotation.x = -Math.PI / 2 * s; back.position.y = s * (h / 2 + 0.001); g.add(back);
    const f = new THREE.Mesh(new THREE.CircleGeometry(r * 0.99, 96), new THREE.MeshPhysicalMaterial({
      map: face, transparent: true, metalness: 0.55, roughness: 0.3, clearcoat: 0.6, emissive: 0x2a1800, emissiveMap: face, emissiveIntensity: 0.35}));
    f.rotation.x = -Math.PI / 2 * s; f.position.y = s * (h / 2 + 0.004); if (s < 0) f.rotation.z = Math.PI; g.add(f);
  }
  g.traverse(o => { o.castShadow = true; o.receiveShadow = true; });
  return g;
}
function coinStack(face, n, r = 0.62, h = 0.12) {
  const g = new THREE.Group();
  for (let i = 0; i < n; i++) {
    const c = coin(face, r, h); c.position.set((Math.random() - 0.5) * 0.06, i * h * 1.02 + h / 2, (Math.random() - 0.5) * 0.06);
    c.rotation.y = Math.random() * 6; g.add(c);
  }
  return g;
}
// oltin quyma (trapetsiya)
function goldBar() {
  const geo = new THREE.CylinderGeometry(0.42 / Math.SQRT2, 0.6 / Math.SQRT2, 0.24, 4, 1); geo.rotateY(Math.PI / 4);
  const m = new THREE.Mesh(geo, GOLD()); m.scale.set(1.9, 1, 0.9); m.castShadow = true; m.receiveShadow = true; return m;
}
function done(R, S, cam) { R.render(S, cam); window.DONE = true; }
