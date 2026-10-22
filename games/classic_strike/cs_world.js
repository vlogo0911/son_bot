/* CLASSIC STRIKE — MapSystem: 3 ta original xarita (grid), instanced 3D devorlar, collision, 3D raycast (DDA), A* nav. */
(function () {
  'use strict';
  const CS3D = window.CS3D;
  const S = 2;              // katak o'lchami (metr)
  const N = 28;             // xarita 28×28 katak (56×56 m)
  // Katak turlari: balandlik (m), o'qni/ko'rishni to'sadimi (balandlik bo'yicha), yurish mumkinmi
  const KIND = {
    '.': { h: 0 }, A: { h: 0, site: 'A' }, B: { h: 0, site: 'B' }, t: { h: 0, spawn: 'T' }, u: { h: 0, spawn: 'CT' },
    '#': { h: 4.2, m: 'wall' }, H: { h: 7.5, m: 'tall' }, p: { h: 4.2, m: 'pillar' },
    c: { h: 1.05, m: 'crate' }, C: { h: 2.2, m: 'crate2' }, K: { h: 2.8, m: 'cont' }, v: { h: 1.35, m: 'car' },
  };

  function grid() { const g = []; for (let z = 0; z < N; z++) { g.push([]); for (let x = 0; x < N; x++) g[z].push(x === 0 || z === 0 || x === N - 1 || z === N - 1 ? '#' : '.'); } return g; }
  function rect(g, x, z, w, h, ch) { for (let j = z; j < z + h; j++) for (let i = x; i < x + w; i++) if (i > 0 && j > 0 && i < N - 1 && j < N - 1) g[j][i] = ch; }
  function put(g, list, ch) { for (const [x, z] of list) if (x > 0 && z > 0 && x < N - 1 && z < N - 1) g[z][x] = ch; }

  // ── Xaritalar (original dizayn) ──
  const MAPS = {
    desert: {
      name: 'Desert Base', sub: 'Cho‘ldagi harbiy baza', sky: 0xe6cfa2, skyTop: 0x5d8cc4, wallTex: 'block', fog: [0xd8c39a, 30, 95], sun: 0xfff1d0, amb: [0xfff4dc, 0x8a6f48],
      floor: ['#c9a56a', '#b8945a'], wall: 0xd2b27a, tall: 0xc9a46c, crate: 0x8a5a2b, crate2: 0x7a4e24, pillar: 0xbfa070, cont: 0x7c6a4a, car: 0x6b5a40,
      build(g) {
        rect(g, 11, 1, 6, 3, 'u'); rect(g, 11, 24, 6, 3, 't');
        rect(g, 2, 2, 7, 6, 'A'); rect(g, 19, 2, 7, 6, 'B');
        put(g, [[3, 3], [4, 3], [7, 6]], 'c'); put(g, [[6, 4], [2, 6]], 'C');
        put(g, [[21, 4], [22, 4]], 'C'); put(g, [[24, 6], [19, 3]], 'c');
        rect(g, 1, 8, 9, 1, '#'); rect(g, 3, 8, 2, 1, '.'); rect(g, 18, 8, 9, 1, '#'); rect(g, 23, 8, 2, 1, '.');
        rect(g, 10, 7, 8, 1, '#'); rect(g, 13, 7, 2, 1, '.');
        rect(g, 6, 9, 4, 12, '#'); rect(g, 6, 14, 4, 2, '.');
        rect(g, 18, 9, 4, 12, '#'); rect(g, 18, 11, 4, 2, '.');
        rect(g, 22, 10, 1, 9, '#'); rect(g, 22, 16, 1, 1, '.');
        put(g, [[13, 13], [14, 13], [13, 14], [14, 14]], 'C'); put(g, [[11, 10], [16, 18], [11, 19], [16, 10]], 'c');
        put(g, [[2, 12], [3, 12], [4, 17]], 'c'); put(g, [[24, 13], [25, 19]], 'c'); put(g, [[12, 16], [15, 11]], 'p');
        rect(g, 1, 21, 9, 1, '#'); rect(g, 3, 21, 2, 1, '.'); rect(g, 18, 21, 9, 1, '#'); rect(g, 23, 21, 2, 1, '.');
        rect(g, 10, 22, 8, 1, '#'); rect(g, 13, 22, 2, 1, '.'); rect(g, 10, 22, 1, 1, '.'); rect(g, 17, 22, 1, 1, '.');
        put(g, [[3, 24], [24, 24], [6, 25], [21, 25]], 'c');
      },
    },
    urban: {
      name: 'Urban Strike', sub: 'Tor ko‘chalar va binolar', sky: 0xb7c6d6, skyTop: 0x4f6f99, fog: [0x9fb3c8, 25, 85], sun: 0xe8f0ff, amb: [0xdde8ff, 0x4a4f5a],
      floor: ['#5d6168', '#53575e'], wall: 0x8d8f94, tall: 0x9a8f86, crate: 0x6b5435, crate2: 0x5d4a30, pillar: 0x7a7c80, cont: 0x4a6a8a, car: 0x9c2f2f,
      build(g) {
        rect(g, 10, 1, 8, 2, 'u'); rect(g, 10, 25, 8, 2, 't');
        for (const [x, z, w, h] of [[2, 3, 6, 5], [11, 4, 6, 4], [20, 3, 6, 5], [2, 11, 5, 6], [21, 11, 5, 6], [2, 20, 6, 5], [11, 20, 6, 4], [20, 20, 6, 5]]) rect(g, x, z, w, h, 'H');
        rect(g, 4, 3, 2, 5, '.'); rect(g, 22, 13, 4, 2, '.'); rect(g, 13, 20, 2, 4, '.'); rect(g, 2, 13, 3, 2, '.');
        rect(g, 10, 10, 8, 8, 'A'); rect(g, 13, 13, 2, 2, 'C'); put(g, [[11, 11], [16, 16]], 'c');
        rect(g, 8, 12, 1, 4, '#'); rect(g, 19, 12, 1, 4, '#');
        rect(g, 22, 8, 4, 2, 'B'); rect(g, 22, 17, 4, 2, 'B');
        put(g, [[9, 5], [18, 6], [9, 22], [18, 21], [5, 9], [23, 9], [5, 18], [24, 19]], 'v');
        put(g, [[1, 9], [26, 9], [1, 18], [26, 18], [14, 8], [14, 19]], 'c');
        put(g, [[8, 9], [19, 9], [8, 18], [19, 18]], 'p');
      },
    },
    warehouse: {
      name: 'Warehouse', sub: 'Ombor, konteynerlar, yashirinish joylari', sky: 0x2a2f38, fog: [0x2a2f38, 18, 60], sun: 0xffe0b0, amb: [0xb9c4d8, 0x2a2a30],
      floor: ['#4a4e55', '#43474e'], wall: 0x5b6068, tall: 0x50555c, crate: 0x8b6a3c, crate2: 0x7a5c32, pillar: 0x6a6e75, cont: 0x2f6f5a, car: 0x6a6e75,
      build(g) {
        rect(g, 1, 1, 4, 4, 'u'); rect(g, 23, 23, 4, 4, 't');
        rect(g, 2, 18, 6, 6, 'A'); rect(g, 20, 3, 6, 6, 'B');
        for (const [x, z, w, h] of [[7, 3, 6, 2], [7, 7, 2, 6], [15, 6, 6, 2], [11, 11, 6, 2], [11, 15, 6, 2], [19, 14, 2, 6], [7, 21, 6, 2], [15, 23, 6, 2]]) rect(g, x, z, w, h, 'K');
        rect(g, 13, 1, 1, 4, '#'); rect(g, 14, 22, 1, 5, '#');
        put(g, [[3, 20], [4, 20], [6, 22]], 'C'); put(g, [[21, 5], [24, 7], [22, 4]], 'C');
        put(g, [[5, 10], [9, 16], [18, 10], [22, 17], [12, 9], [16, 19], [3, 14], [25, 13]], 'c');
        for (const [x, z] of [[5, 5], [22, 22], [9, 19], [18, 8], [5, 14], [22, 13]]) put(g, [[x, z]], 'p');
      },
    },
  };

  // ── Map obyekti ──
  function GameMap(id) {
    const def = MAPS[id] || MAPS.desert;
    const g = grid(); def.build(g);
    this.id = id; this.def = def; this.g = g; this.N = N; this.S = S;
    this.h = []; this.sites = { A: [], B: [] }; this.spawns = { T: [], CT: [] }; this.free = []; this.cover = [];
    for (let z = 0; z < N; z++) { this.h.push(new Float32Array(N)); for (let x = 0; x < N; x++) {
      const k = KIND[g[z][x]] || KIND['.']; this.h[z][x] = k.h;
      if (!k.h) { this.free.push([x, z]); if (k.site) this.sites[k.site].push([x, z]); if (k.spawn) this.spawns[k.spawn].push([x, z]); }
    } }
    // Faqat T spawnidan yetib boriladigan kataklar (ulanganlik)
    const reach = new Set(), start = this.spawns.T[0] || this.free[0], q = [start];
    reach.add(start[0] + ',' + start[1]);
    while (q.length) { const [x, z] = q.shift(); for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const nx = x + dx, nz = z + dz, k = nx + ',' + nz; if (!reach.has(k) && this.walk(nx, nz)) { reach.add(k); q.push([nx, nz]); } } }
    this.reach = reach;
    this.free = this.free.filter(([x, z]) => reach.has(x + ',' + z));
    for (const [x, z] of this.free) { let n = 0; for (const [dx, dz] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) if (this.hc(x + dx, z + dz) >= 1) n++; if (n) this.cover.push([x, z]); }
    for (const k of ['A', 'B']) this.sites[k] = this.sites[k].filter(([x, z]) => reach.has(x + ',' + z));
    const cen = (l) => l.length ? [l.reduce((s, c) => s + c[0], 0) / l.length, l.reduce((s, c) => s + c[1], 0) / l.length] : [N / 2, N / 2];
    this.siteC = { A: cen(this.sites.A).map((v) => v * S + S / 2), B: cen(this.sites.B).map((v) => v * S + S / 2) };
  }
  const P = GameMap.prototype;
  P.hc = function (x, z) { return x < 0 || z < 0 || x >= N || z >= N ? 99 : this.h[z][x]; };
  P.walk = function (x, z) { return this.hc(x, z) === 0; };
  P.cell = (v) => Math.floor(v / S);
  P.center = (c) => c * S + S / 2;
  P.siteAt = function (x, z) { const cx = this.cell(x), cz = this.cell(z); if (cx < 0 || cz < 0 || cx >= N || cz >= N) return null; const k = KIND[this.g[cz][cx]]; return k && k.site || null; };
  // Doira ostidagi eng baland katak (oyoq ostidagi yer)
  P.heightAt = function (x, z, r) {
    let m = 0;
    const x0 = this.cell(x - r), x1 = this.cell(x + r), z0 = this.cell(z - r), z1 = this.cell(z + r);
    for (let j = z0; j <= z1; j++) for (let i = x0; i <= x1; i++) {
      const h = this.hc(i, j); if (h <= m) continue;
      const nx = Math.max(i * S, Math.min(x, i * S + S)), nz = Math.max(j * S, Math.min(z, j * S + S));
      if ((nx - x) * (nx - x) + (nz - z) * (nz - z) < r * r) m = h;
    }
    return m;
  };
  // Harakat: o'qlar bo'yicha alohida, step-up 0.45 m (sakrab qutiga chiqish mumkin)
  P.move = function (e, dx, dz, r, feet) {
    const step = 0.45;
    if (dx && this.heightAt(e.x + dx, e.z, r) <= feet + step) e.x += dx;
    if (dz && this.heightAt(e.x, e.z + dz, r) <= feet + step) e.z += dz;
  };
  // 3D raycast: devor/quti yuzasi yoki yer. {d, x,y,z, nx,ny,nz}
  P.ray = function (ox, oy, oz, dx, dy, dz, max) {
    let best = max, nx = 0, ny = 0, nz = 0;
    if (dy < -1e-6) { const tg = -oy / dy; if (tg > 0 && tg < best) { best = tg; nx = 0; ny = 1; nz = 0; } }
    let cx = this.cell(ox), cz = this.cell(oz);
    const sx = dx > 0 ? 1 : -1, sz = dz > 0 ? 1 : -1;
    const tdx = Math.abs(dx) > 1e-9 ? S / Math.abs(dx) : Infinity, tdz = Math.abs(dz) > 1e-9 ? S / Math.abs(dz) : Infinity;
    let tmx = Math.abs(dx) > 1e-9 ? ((dx > 0 ? (cx + 1) * S - ox : ox - cx * S) / Math.abs(dx)) : Infinity;
    let tmz = Math.abs(dz) > 1e-9 ? ((dz > 0 ? (cz + 1) * S - oz : oz - cz * S) / Math.abs(dz)) : Infinity;
    let t0 = 0, side = -1;
    for (let it = 0; it < 80 && t0 < best; it++) {
      const h = this.hc(cx, cz), t1 = Math.min(tmx, tmz, best);
      if (h > 0) {
        const y0 = oy + dy * t0;
        if (y0 < h && t0 > 0) { // yon yuzaga tegdi
          if (t0 < best) { best = t0; ny = 0; if (side === 0) { nx = -sx; nz = 0; } else { nx = 0; nz = -sz; } }
          break;
        }
        const y1 = oy + dy * t1;
        if (y1 < h && dy < 0) { const tt = (h - oy) / dy; if (tt >= t0 && tt < best) { best = tt; nx = 0; ny = 1; nz = 0; } break; }
        if (t0 === 0 && oy < h) { best = 0; break; }
      }
      if (tmx < tmz) { t0 = tmx; tmx += tdx; cx += sx; side = 0; } else { t0 = tmz; tmz += tdz; cz += sz; side = 1; }
      if (cx < 0 || cz < 0 || cx >= N || cz >= N) { if (t0 < best) { best = t0; ny = 0; nx = side === 0 ? -sx : 0; nz = side === 1 ? -sz : 0; } break; }
    }
    return { d: best, x: ox + dx * best, y: oy + dy * best, z: oz + dz * best, nx, ny, nz };
  };
  P.los = function (ax, ay, az, bx, by, bz) {
    const dx = bx - ax, dy = by - ay, dz = bz - az, d = Math.hypot(dx, dy, dz);
    if (d < 0.01) return true;
    return this.ray(ax, ay, az, dx / d, dy / d, dz / d, d).d >= d - 0.05;
  };
  // A* (8 yo'nalish, burchak kesmaydi). Natija: katak markazlari ro'yxati
  P.path = function (sx, sz, tx, tz) {
    const a = [this.cell(sx), this.cell(sz)], b = [this.cell(tx), this.cell(tz)];
    if (!this.walk(b[0], b[1])) { const nb = this.nearestFree(b[0], b[1]); if (!nb) return null; b[0] = nb[0]; b[1] = nb[1]; }
    if (!this.walk(a[0], a[1])) { const na = this.nearestFree(a[0], a[1]); if (!na) return null; a[0] = na[0]; a[1] = na[1]; }
    const key = (x, z) => z * N + x, start = key(a[0], a[1]), goal = key(b[0], b[1]);
    const gS = new Float32Array(N * N).fill(1e9), from = new Int32Array(N * N).fill(-1), closed = new Uint8Array(N * N);
    const open = [start]; gS[start] = 0;
    const hf = (k) => { const x = k % N, z = (k / N) | 0; const ddx = Math.abs(x - b[0]), ddz = Math.abs(z - b[1]); return Math.max(ddx, ddz) + 0.414 * Math.min(ddx, ddz); };
    let guard = 0;
    while (open.length && guard++ < 2000) {
      let bi = 0, bf = 1e9;
      for (let i = 0; i < open.length; i++) { const f = gS[open[i]] + hf(open[i]); if (f < bf) { bf = f; bi = i; } }
      const cur = open.splice(bi, 1)[0];
      if (cur === goal) break;
      closed[cur] = 1;
      const x = cur % N, z = (cur / N) | 0;
      for (let dz = -1; dz <= 1; dz++) for (let dx = -1; dx <= 1; dx++) {
        if (!dx && !dz) continue;
        const nx = x + dx, nz = z + dz; if (!this.walk(nx, nz)) continue;
        if (dx && dz && (!this.walk(x + dx, z) || !this.walk(x, z + dz))) continue;
        const k = key(nx, nz); if (closed[k]) continue;
        const ng = gS[cur] + (dx && dz ? 1.414 : 1);
        if (ng < gS[k]) { gS[k] = ng; from[k] = cur; if (open.indexOf(k) < 0) open.push(k); }
      }
    }
    if (from[goal] < 0 && goal !== start) return null;
    const out = []; let k = goal;
    while (k !== start && k >= 0) { out.push([this.center(k % N), this.center((k / N) | 0)]); k = from[k]; }
    out.reverse();
    return out;
  };
  P.nearestFree = function (x, z) {
    for (let r = 0; r < 6; r++) for (let dz = -r; dz <= r; dz++) for (let dx = -r; dx <= r; dx++) if (this.walk(x + dx, z + dz) && this.reach.has((x + dx) + ',' + (z + dz))) return [x + dx, z + dz];
    return null;
  };
  P.randomFree = function (filter) {
    const list = filter ? this.free.filter(filter) : this.free;
    const c = list.length ? list[(Math.random() * list.length) | 0] : this.free[0];
    return [this.center(c[0]) + (Math.random() - 0.5) * 0.6, this.center(c[1]) + (Math.random() - 0.5) * 0.6];
  };
  P.spawnPoint = function (team, avoid) {
    let list = (this.spawns[team] || []).filter(([x, z]) => this.reach.has(x + ',' + z));
    if (!list.length || avoid) {
      // Deathmatch: dushmanlardan uzoqroq tasodifiy joy
      const cand = list.length && !avoid ? list : this.free;
      let best = null, bd = -1;
      for (let i = 0; i < 14; i++) {
        const c = cand[(Math.random() * cand.length) | 0];
        let dmin = 1e9; for (const e of avoid || []) dmin = Math.min(dmin, Math.hypot(this.center(c[0]) - e.x, this.center(c[1]) - e.z));
        if (dmin > bd) { bd = dmin; best = c; }
      }
      list = [best];
    }
    const c = list[(Math.random() * list.length) | 0];
    return [this.center(c[0]) + (Math.random() - 0.5) * 0.8, this.center(c[1]) + (Math.random() - 0.5) * 0.8];
  };

  // ── 3D qurilish (instancing) ──
  // ── Protsedura teksturalar (256px, 1 takrorlanish = 2 m; UV metr bo'yicha — cho'zilmaydi) ──
  const shade = (hex, k) => { const c = new THREE.Color(hex); c.multiplyScalar(k); return '#' + c.getHexString(); };
  function noise(g, w, h, n, a) { for (let i = 0; i < n; i++) { g.fillStyle = Math.random() < 0.5 ? 'rgba(0,0,0,' + a + ')' : 'rgba(255,255,255,' + a * 0.6 + ')'; g.fillRect(Math.random() * w, Math.random() * h, 1 + Math.random() * 2, 1 + Math.random() * 2); } }
  function canvasTex(base, kind) {
    const cv = document.createElement('canvas'), W = (cv.width = cv.height = 256), g = cv.getContext('2d');
    g.fillStyle = base; g.fillRect(0, 0, W, W);
    if (kind === 'brick') {            // g'isht: 10 qator, har g'isht rangi biroz farq qiladi
      const rh = W / 10, bw = W / 4;
      for (let r = 0; r < 10; r++) for (let c = -1; c < 5; c++) {
        const x = c * bw + (r % 2 ? bw / 2 : 0), y = r * rh;
        g.fillStyle = shade(base, 0.82 + Math.random() * 0.3); g.fillRect(x + 2, y + 2, bw - 4, rh - 4);
        g.fillStyle = 'rgba(255,255,255,.08)'; g.fillRect(x + 2, y + 2, bw - 4, 2); g.fillStyle = 'rgba(0,0,0,.12)'; g.fillRect(x + 2, y + rh - 4, bw - 4, 2);
      }
      noise(g, W, W, 1600, 0.06);
    } else if (kind === 'block') {     // katta tosh bloklar (cho'l devori)
      const rh = W / 4;
      for (let r = 0; r < 4; r++) for (let c = -1; c < 3; c++) {
        const x = c * W / 2 + (r % 2 ? W / 4 : 0), y = r * rh; g.fillStyle = shade(base, 0.88 + Math.random() * 0.2); g.fillRect(x + 3, y + 3, W / 2 - 6, rh - 6);
        g.fillStyle = 'rgba(255,255,255,.1)'; g.fillRect(x + 3, y + 3, W / 2 - 6, 3);
      }
      noise(g, W, W, 2600, 0.07); g.strokeStyle = 'rgba(0,0,0,.18)'; g.lineWidth = 1;
      for (let i = 0; i < 5; i++) { g.beginPath(); let x = Math.random() * W, y = Math.random() * W; g.moveTo(x, y); for (let k = 0; k < 5; k++) { x += (Math.random() - 0.5) * 30; y += Math.random() * 18; g.lineTo(x, y); } g.stroke(); }
    } else if (kind === 'tile') {      // pol plitkasi 1 m
      for (let y = 0; y < 2; y++) for (let x = 0; x < 2; x++) { g.fillStyle = shade(base, 0.92 + Math.random() * 0.14); g.fillRect(x * 128 + 2, y * 128 + 2, 124, 124); }
      g.fillStyle = 'rgba(0,0,0,.28)'; g.fillRect(0, 0, W, 3); g.fillRect(0, 127, W, 3); g.fillRect(0, 0, 3, W); g.fillRect(127, 0, 3, W);
      noise(g, W, W, 3000, 0.05);
      for (let i = 0; i < 14; i++) { const r = g.createRadialGradient(0, 0, 0, 0, 0, 30); const x = Math.random() * W, y = Math.random() * W; g.save(); g.translate(x, y); r.addColorStop(0, 'rgba(0,0,0,.09)'); r.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = r; g.fillRect(-30, -30, 60, 60); g.restore(); }
    } else if (kind === 'concrete') {
      noise(g, W, W, 5000, 0.06); g.fillStyle = 'rgba(0,0,0,.15)'; g.fillRect(0, 126, W, 3);
      for (let i = 0; i < 8; i++) { g.fillStyle = 'rgba(0,0,0,.25)'; g.beginPath(); g.arc(20 + (i % 4) * 70, i < 4 ? 40 : 210, 3, 0, 7); g.fill(); }
    } else if (kind === 'crate') {     // yog'och yashik: taxtalar + ramka + diagonal
      for (let i = 0; i < 6; i++) { g.fillStyle = shade(base, 0.85 + Math.random() * 0.25); g.fillRect(0, i * W / 6, W, W / 6 - 2); for (let k = 0; k < 6; k++) { g.fillStyle = 'rgba(0,0,0,.08)'; g.fillRect(Math.random() * W, i * W / 6 + Math.random() * 30, 60 + Math.random() * 80, 1); } }
      const fr = shade(base, 0.62); g.fillStyle = fr; g.fillRect(0, 0, W, 22); g.fillRect(0, W - 22, W, 22); g.fillRect(0, 0, 22, W); g.fillRect(W - 22, 0, 22, W);
      g.save(); g.translate(W / 2, W / 2); g.rotate(Math.PI / 4); g.fillRect(-W * 0.68, -11, W * 1.36, 22); g.restore();
      g.fillStyle = 'rgba(255,255,255,.1)'; g.fillRect(0, 0, W, 3); g.fillRect(0, 0, 3, W);
      g.fillStyle = 'rgba(40,30,20,.9)'; for (const [x, y] of [[11, 11], [W - 11, 11], [11, W - 11], [W - 11, W - 11]]) { g.beginPath(); g.arc(x, y, 4, 0, 7); g.fill(); }
      noise(g, W, W, 1200, 0.05);
    } else if (kind === 'cont') {      // konteyner: vertikal qovurg'alar + zang
      for (let x = 0; x < W; x += 32) { g.fillStyle = 'rgba(255,255,255,.1)'; g.fillRect(x, 0, 6, W); g.fillStyle = 'rgba(0,0,0,.22)'; g.fillRect(x + 18, 0, 8, W); }
      g.fillStyle = 'rgba(0,0,0,.3)'; g.fillRect(0, 0, W, 10); g.fillRect(0, W - 10, W, 10);
      for (let i = 0; i < 40; i++) { g.fillStyle = 'rgba(110,55,20,' + (0.1 + Math.random() * 0.25) + ')'; g.fillRect(Math.random() * W, Math.random() * W, 2 + Math.random() * 10, 2 + Math.random() * 18); }
      noise(g, W, W, 1500, 0.05);
    } else if (kind === 'metal') {
      noise(g, W, W, 2500, 0.05); g.fillStyle = 'rgba(0,0,0,.25)'; g.fillRect(0, 0, W, 4); g.fillRect(0, 0, 4, W);
    }
    const t = new THREE.CanvasTexture(cv); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.anisotropy = 4;
    return t;
  }
  // Quti geometriyasi: UV metr bo'yicha (1 takrorlanish = 2 m), pastki qirrasi y=0
  function boxM(w, h, d) {
    const g = new THREE.BoxGeometry(w, h, d); g.translate(0, h / 2, 0);
    const uv = g.attributes.uv, dims = [[d, h], [d, h], [w, d], [w, d], [w, h], [w, h]];
    for (let f = 0; f < 6; f++) for (let k = 0; k < 4; k++) { const i = f * 4 + k; uv.setXY(i, uv.getX(i) * dims[f][0] / 2, uv.getY(i) * dims[f][1] / 2); }
    return g;
  }
  function gradTex(stops, w, h, radial) {
    const cv = document.createElement('canvas'); cv.width = w; cv.height = h; const g = cv.getContext('2d');
    const gr = radial ? g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2) : g.createLinearGradient(0, 0, 0, h);
    for (const [o, c] of stops) gr.addColorStop(o, c); g.fillStyle = gr; g.fillRect(0, 0, w, h); return new THREE.CanvasTexture(cv);
  }
  CS3D.Tex = { gradTex };
  P.build = function (scene, quality) {
    const def = this.def, disp = (this.disposables = []), own = (o) => { disp.push(o); return o; }, lq = quality === 'low', hq = quality === 'high';
    const C = N * S / 2;
    scene.background = new THREE.Color(def.sky);
    scene.fog = new THREE.Fog(this.id === 'warehouse' ? def.fog[0] : def.sky, def.fog[1], def.fog[2]);   // tuman = ufq rangi (chok ko'rinmaydi)
    const hemi = new THREE.HemisphereLight(def.amb[0], def.amb[1], 0.62); scene.add(hemi);
    const sun = new THREE.DirectionalLight(def.sun, 0.95); sun.position.set(C + 30, 60, C + 18); scene.add(sun); scene.add(sun.target);
    sun.target.position.set(C, 0, C);
    if (hq) {
      sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024); sun.shadow.bias = -0.0005;
      Object.assign(sun.shadow.camera, { left: -40, right: 40, top: 40, bottom: -40, near: 10, far: 140 });
      sun.position.set(C + 25, 60, C + 12);
    }
    // Osmon: vertikal gradient gumbaz + quyosh (warehouse — yopiq bino)
    const top = new THREE.Color(def.skyTop || def.sky).multiplyScalar(def.skyTop ? 1 : 0.62), hor = new THREE.Color(def.sky);
    const sg = own(new THREE.SphereGeometry(300, 20, 10)), cols = [], tmp = new THREE.Color(), pos = sg.attributes.position;
    for (let i = 0; i < pos.count; i++) { const h = Math.max(0, pos.getY(i) / 300); tmp.copy(hor).lerp(top, Math.pow(h, 0.7)); cols.push(tmp.r, tmp.g, tmp.b); }
    sg.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
    const sky = new THREE.Mesh(sg, own(new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, fog: false, depthWrite: false })));
    sky.position.set(C, 0, C); sky.renderOrder = -10; scene.add(sky);
    const glow = own(gradTex([[0, 'rgba(255,255,255,1)'], [0.2, 'rgba(255,255,255,.6)'], [1, 'rgba(255,255,255,0)']], 64, 64, true));
    if (this.id !== 'warehouse') {
      const sm = own(new THREE.SpriteMaterial({ map: glow, color: def.sun, fog: false, depthWrite: false, blending: THREE.AdditiveBlending }));
      const sp = new THREE.Sprite(sm); sp.scale.set(46, 46, 1); sp.position.set(C + 170, 105, C + 140); scene.add(sp);
    }
    // Pol
    const ft = own(canvasTex(def.floor[0], 'tile')); ft.repeat.set(N, N);
    const fm = own(new THREE.MeshLambertMaterial({ map: ft })), fg = own(new THREE.PlaneGeometry(N * S, N * S));
    const floor = new THREE.Mesh(fg, fm); floor.rotation.x = -Math.PI / 2; floor.position.set(C, 0, C); floor.receiveShadow = true; scene.add(floor);
    // Atrofdagi yer (arena tashqarisi)
    const og = own(new THREE.PlaneGeometry(600, 600)), om = own(new THREE.MeshLambertMaterial({ color: new THREE.Color(def.floor[1]).multiplyScalar(0.9) }));
    const outer = new THREE.Mesh(og, om); outer.rotation.x = -Math.PI / 2; outer.position.set(C, -0.03, C); scene.add(outer);
    // Bomba hududlari belgisi
    for (const k of ['A', 'B']) {
      if (!this.sites[k].length) continue;
      const cv = document.createElement('canvas'); cv.width = cv.height = 128; const g = cv.getContext('2d');
      g.strokeStyle = 'rgba(200,30,30,.75)'; g.lineWidth = 8; g.strokeRect(8, 8, 112, 112);
      g.fillStyle = 'rgba(200,30,30,.75)'; g.font = 'bold 84px Arial'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(k, 64, 70);
      const tx = own(new THREE.CanvasTexture(cv)), mm = own(new THREE.MeshBasicMaterial({ map: tx, transparent: true, depthWrite: false })), gg = own(new THREE.PlaneGeometry(5, 5));
      const m = new THREE.Mesh(gg, mm); m.rotation.x = -Math.PI / 2; m.position.set(this.siteC[k][0], 0.02, this.siteC[k][1]); scene.add(m);
    }
    // Instanced bloklar (har tur — o'z geometriyasi, UV metrda)
    const types = {
      wall: [def.wall, def.wallTex || 'brick', 1, 1], tall: [def.tall, 'brick', 1, 1], pillar: [def.pillar, 'concrete', 0.55, 0.55], crate: [def.crate, 'crate', 0.92, 0.92],
      crate2: [def.crate2, 'crate', 1, 1], cont: [def.cont, 'cont', 1, 1], car: [def.car, 'metal', 0.6, 0.9],
    };
    const cells = {};
    for (let z = 0; z < N; z++) for (let x = 0; x < N; x++) { const k = KIND[this.g[z][x]]; if (k && k.m) (cells[k.m] = cells[k.m] || []).push([x, z, k.h]); }
    const m4 = new THREE.Matrix4(), col = new THREE.Color();
    const CONT = [0x2f6f5a, 0x8a3b2f, 0x2f4f8a, 0x8a7a2f, 0x5a5a5a];
    for (const m of Object.keys(cells)) {
      const list = cells[m], [c, tk, sw, sd] = types[m], h = m === 'car' ? 0.82 : list[0][2];
      const geo = own(boxM(S * sw, h, S * sd)); if (m === 'car') geo.translate(0, 0.22, 0);
      const tex = own(canvasTex(m === 'cont' ? '#9a9a9a' : '#' + new THREE.Color(c).getHexString(), tk));
      const mat = own(new THREE.MeshLambertMaterial({ map: tex, color: m === 'cont' ? 0xffffff : 0xffffff }));
      const im = new THREE.InstancedMesh(geo, mat, list.length);
      list.forEach(([x, z], i) => {
        m4.makeTranslation(x * S + S / 2, 0, z * S + S / 2); im.setMatrixAt(i, m4);
        col.set(m === 'cont' ? CONT[(x * 7 + z * 3) % CONT.length] : 0xffffff).multiplyScalar(0.9 + ((x * 13 + z * 7) % 5) * 0.03);
        im.setColorAt(i, col);
      });
      im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true;
      im.castShadow = hq; im.receiveShadow = hq;
      scene.add(im);
    }
    // Mashina rekvizitlari: kabina (oyna) + g'ildiraklar
    if (cells.car) {
      const cg2 = own(new THREE.BoxGeometry(S * 0.52, 0.5, S * 0.5)); cg2.translate(0, 1.27, 0.08);
      const wg = own(new THREE.CylinderGeometry(0.32, 0.32, S * 0.62, 10)); wg.rotateZ(Math.PI / 2);
      const glass = new THREE.InstancedMesh(cg2, own(new THREE.MeshLambertMaterial({ color: 0x1b2430 })), cells.car.length);
      const wheels = new THREE.InstancedMesh(wg, own(new THREE.MeshLambertMaterial({ color: 0x141416 })), cells.car.length * 2);
      cells.car.forEach(([x, z], i) => {
        const cx = x * S + S / 2, cz = z * S + S / 2; m4.makeTranslation(cx, 0, cz); glass.setMatrixAt(i, m4);
        m4.makeTranslation(cx, 0.32, cz - S * 0.3); wheels.setMatrixAt(i * 2, m4); m4.makeTranslation(cx, 0.32, cz + S * 0.3); wheels.setMatrixAt(i * 2 + 1, m4);
      });
      glass.instanceMatrix.needsUpdate = true; wheels.instanceMatrix.needsUpdate = true; scene.add(glass, wheels);
    }
    // Devor/bino tepasidagi qirra (ko'rinishni aniqroq qiladi)
    const capCells = [].concat(cells.wall || [], cells.tall || []);
    if (capCells.length) {
      const cg = own(new THREE.BoxGeometry(S + 0.12, 0.16, S + 0.12)), cm = own(new THREE.MeshLambertMaterial({ color: new THREE.Color(def.wall).multiplyScalar(0.7) }));
      const ci = new THREE.InstancedMesh(cg, cm, capCells.length);
      capCells.forEach(([x, z, h], i) => { m4.makeTranslation(x * S + S / 2, h + 0.08, z * S + S / 2); ci.setMatrixAt(i, m4); });
      ci.instanceMatrix.needsUpdate = true; scene.add(ci);
    }
    // Soya (ambient occlusion) — devor tagidagi qorong'i lentalar, bitta draw call
    if (!lq) {
      const ao = [], DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1]];
      for (let z = 0; z < N; z++) for (let x = 0; x < N; x++) {
        const k = KIND[this.g[z][x]]; if (!k || !k.h) continue;
        for (const [dx, dz] of DIRS) { const nx = x + dx, nz = z + dz; if (this.walk(nx, nz)) ao.push([x, z, dx, dz, Math.min(1, k.h / 2.2)]); }
      }
      const ag = own(new THREE.PlaneGeometry(S, 1.1)); ag.rotateX(-Math.PI / 2);
      const at = own(gradTex([[0, 'rgba(0,0,0,.55)'], [1, 'rgba(0,0,0,0)']], 4, 64));
      const am = own(new THREE.MeshBasicMaterial({ map: at, transparent: true, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2, fog: true }));
      const ai = new THREE.InstancedMesh(ag, am, ao.length), q = new THREE.Quaternion(), e = new THREE.Euler(), v = new THREE.Vector3(), sc = new THREE.Vector3();
      ao.forEach(([x, z, dx, dz, f], i) => {
        e.set(0, Math.atan2(dx, dz) + Math.PI, 0); q.setFromEuler(e);
        m4.compose(v.set(x * S + S / 2 + dx * (S / 2 + 0.55), 0.015, z * S + S / 2 + dz * (S / 2 + 0.55)), q, sc.set(1, 1, f)); ai.setMatrixAt(i, m4);
      });
      ai.instanceMatrix.needsUpdate = true; scene.add(ai);
    }
    // Arena tashqarisidagi manzara (uzoq siluetlar) — bitta instanced mesh
    const bk = [], R0 = C + 14;
    const nB = lq ? 26 : 48;
    for (let i = 0; i < nB; i++) {
      const a = i / nB * Math.PI * 2 + Math.random() * 0.05, r = R0 + 6 + Math.random() * 60;
      bk.push([C + Math.cos(a) * r, C + Math.sin(a) * r, a]);
    }
    if (this.id === 'desert') {
      const dg = own(new THREE.DodecahedronGeometry(1, 0)), dm = own(new THREE.MeshLambertMaterial({ color: new THREE.Color(def.wall).multiplyScalar(0.85), flatShading: true }));
      const di = new THREE.InstancedMesh(dg, dm, bk.length), q = new THREE.Quaternion(), e = new THREE.Euler(), v = new THREE.Vector3(), sc = new THREE.Vector3();
      bk.forEach(([x, z], i) => { const s = 8 + Math.random() * 22; e.set(0, Math.random() * 6, 0); q.setFromEuler(e); m4.compose(v.set(x, -s * 0.35, z), q, sc.set(s * 1.6, s * (0.4 + Math.random() * 0.6), s)); di.setMatrixAt(i, m4); });
      di.instanceMatrix.needsUpdate = true; scene.add(di);
    } else {
      const bg = own(new THREE.BoxGeometry(1, 1, 1)); bg.translate(0, 0.5, 0);
      const wt = own(canvasTex('#' + new THREE.Color(this.id === 'urban' ? 0x6d7480 : 0x3a3f48).getHexString(), 'concrete')); wt.repeat.set(3, 6);
      const bm = own(new THREE.MeshLambertMaterial({ map: wt, color: 0xffffff }));
      const bi = new THREE.InstancedMesh(bg, bm, bk.length), q = new THREE.Quaternion(), e = new THREE.Euler(), v = new THREE.Vector3(), sc = new THREE.Vector3();
      bk.forEach(([x, z, a], i) => { e.set(0, -a, 0); q.setFromEuler(e); m4.compose(v.set(x, 0, z), q, sc.set(8 + Math.random() * 12, (this.id === 'urban' ? 14 : 8) + Math.random() * (this.id === 'urban' ? 30 : 6), 8 + Math.random() * 10)); bi.setMatrixAt(i, m4); bi.setColorAt(i, col.setScalar(0.75 + Math.random() * 0.4)); });
      bi.instanceMatrix.needsUpdate = true; if (bi.instanceColor) bi.instanceColor.needsUpdate = true; scene.add(bi);
    }
    // Ombor: tom, temir to'sinlar va chiroqlar
    if (this.id === 'warehouse') {
      const rg = own(new THREE.PlaneGeometry(N * S + 8, N * S + 8)), rm = own(new THREE.MeshLambertMaterial({ color: 0x1c1f25, side: THREE.DoubleSide }));
      const roof = new THREE.Mesh(rg, rm); roof.rotation.x = Math.PI / 2; roof.position.set(C, 10.5, C); scene.add(roof);
      const tg = own(new THREE.BoxGeometry(N * S + 4, 0.35, 0.3)), tmM = own(new THREE.MeshLambertMaterial({ color: 0x3a3e46 }));
      const ti = new THREE.InstancedMesh(tg, tmM, 7);
      for (let i = 0; i < 7; i++) { m4.makeTranslation(C, 10.1, 4 + i * (N * S - 8) / 6); ti.setMatrixAt(i, m4); }
      ti.instanceMatrix.needsUpdate = true; scene.add(ti);
      const lg = own(new THREE.BoxGeometry(2.2, 0.12, 0.5)), lm = own(new THREE.MeshBasicMaterial({ color: 0xfff1c8 }));
      const lights = [], li = new THREE.InstancedMesh(lg, lm, 12);
      for (let i = 0; i < 12; i++) { const x = 8 + (i % 4) * 13.3, z = 8 + Math.floor(i / 4) * 20; m4.makeTranslation(x, 9.6, z); li.setMatrixAt(i, m4); lights.push(x, 9.4, z); }
      li.instanceMatrix.needsUpdate = true; scene.add(li);
      const pg = own(new THREE.BufferGeometry()); pg.setAttribute('position', new THREE.Float32BufferAttribute(lights, 3));
      scene.add(new THREE.Points(pg, own(new THREE.PointsMaterial({ map: glow, color: 0xffe2a0, size: 7, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }))));
    }
  };
  P.dispose = function () { for (const d of this.disposables || []) { try { d.dispose(); } catch (e) { /* */ } } this.disposables = []; };

  CS3D.MapSystem = { MAPS, GameMap, S, N, KIND, list: () => Object.keys(MAPS) };
})();
