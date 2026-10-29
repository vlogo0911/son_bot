/* AKIT — 3D arena o'yinlari uchun umumiy qism: renderer, joystik, menyu, ovoz, effektlar (three r128). */
(function () {
  'use strict';
  if (window.AKIT) return;
  var T = window.THREE;
  function three() { T = window.THREE; return T; }
  function rng(seed) { var a = (seed >>> 0) || 1; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function el(h) { var d = document.createElement('div'); d.innerHTML = h.trim(); return d.firstChild; }
  function esc(s) { return window.MPNET ? window.MPNET.esc(s) : String(s); }

  function root(cls) {
    var r = el('<div class="akit ' + cls + '"><div class="ak-gl"></div><div class="ak-hud"></div><div class="ak-ctl"></div><div class="ak-menu"></div></div>');
    document.body.appendChild(r);
    return { el: r, gl: r.querySelector('.ak-gl'), hud: r.querySelector('.ak-hud'), ctl: r.querySelector('.ak-ctl'), menu: r.querySelector('.ak-menu') };
  }

  function world(host, opt) {
    three(); opt = opt || {};
    var low = (navigator.deviceMemory && navigator.deviceMemory <= 3) || (navigator.hardwareConcurrency || 8) <= 4;
    var rd = new T.WebGLRenderer({ antialias: !low, powerPreference: 'high-performance' });
    rd.setPixelRatio(Math.min(window.devicePixelRatio || 1, low ? 1.25 : 2));
    rd.outputEncoding = T.sRGBEncoding;
    host.appendChild(rd.domElement);
    var sc = new T.Scene(); sc.background = new T.Color(opt.sky || 0x0a0e1f); sc.fog = new T.Fog(opt.sky || 0x0a0e1f, 40, 140);
    var cam = new T.PerspectiveCamera(55, 1, 0.5, 400);
    sc.add(new T.HemisphereLight(0xbfd4ff, 0x1a1030, 0.85));
    var sun = new T.DirectionalLight(0xffffff, 0.9); sun.position.set(30, 60, 20); sc.add(sun);
    function resize() { var w = host.clientWidth || innerWidth, h = host.clientHeight || innerHeight; rd.setSize(w, h, false); cam.aspect = w / h; cam.updateProjectionMatrix(); }
    resize(); addEventListener('resize', resize);
    var fx = [];
    return {
      rd: rd, scene: sc, cam: cam, low: low,
      render: function (dt) {
        for (var i = fx.length - 1; i >= 0; i--) { var f = fx[i]; f.t += dt; var k = f.t / f.life; f.m.scale.setScalar(f.s0 + f.s1 * k); f.m.material.opacity = 1 - k; if (k >= 1) { sc.remove(f.m); f.m.geometry.dispose(); f.m.material.dispose(); fx.splice(i, 1); } }
        rd.render(sc, cam);
      },
      boom: function (x, y, z, color, size) {
        var m = new T.Mesh(new T.SphereGeometry(1, 12, 8), new T.MeshBasicMaterial({ color: color || 0xffa040, transparent: true, depthWrite: false }));
        m.position.set(x, y, z); sc.add(m); fx.push({ m: m, t: 0, life: 0.45, s0: 0.3 * (size || 1), s1: 2.6 * (size || 1) });
      },
      dispose: function () { removeEventListener('resize', resize); rd.dispose(); sc.traverse(function (o) { if (o.geometry) o.geometry.dispose(); if (o.material) [].concat(o.material).forEach(function (m) { m.dispose(); }); }); rd.domElement.remove(); }
    };
  }

  function grid(sc, size, color) {
    three();
    var g = new T.Mesh(new T.PlaneGeometry(size, size), new T.MeshStandardMaterial({ color: 0x141a33, roughness: 0.9 }));
    g.rotation.x = -Math.PI / 2; sc.add(g);
    var h = new T.GridHelper(size, size / 2, color || 0x3b5bff, color || 0x23306a); h.position.y = 0.02; sc.add(h);
    return g;
  }

  // Virtual joystik: el ichida bosilgan joydan tortiladi. {x,y (-1..1), on}
  function stick(host, side, label) {
    var z = el('<div class="ak-zone ' + side + '"><div class="ak-base"><div class="ak-knob"></div></div>' + (label ? '<span>' + label + '</span>' : '') + '</div>');
    host.appendChild(z);
    var base = z.querySelector('.ak-base'), knob = z.querySelector('.ak-knob'), st = { x: 0, y: 0, on: false, id: null, cx: 0, cy: 0 };
    z.addEventListener('pointerdown', function (e) { st.id = e.pointerId; st.on = true; st.cx = e.clientX; st.cy = e.clientY; base.style.left = (e.clientX - z.getBoundingClientRect().left) + 'px'; base.style.top = (e.clientY - z.getBoundingClientRect().top) + 'px'; base.classList.add('on'); try { z.setPointerCapture(e.pointerId); } catch (x) {} });
    z.addEventListener('pointermove', function (e) { if (e.pointerId !== st.id) return; var dx = e.clientX - st.cx, dy = e.clientY - st.cy, d = Math.hypot(dx, dy), m = 48; if (d > m) { dx *= m / d; dy *= m / d; } st.x = dx / m; st.y = dy / m; knob.style.transform = 'translate(' + dx + 'px,' + dy + 'px)'; });
    function up(e) { if (e.pointerId !== st.id) return; st.on = false; st.x = st.y = 0; st.id = null; knob.style.transform = ''; base.classList.remove('on'); }
    z.addEventListener('pointerup', up); z.addEventListener('pointercancel', up);
    return st;
  }
  function button(host, cls, label) { var b = el('<div class="ak-btn ' + cls + '">' + label + '</div>'), st = { on: false, tap: 0 }; host.appendChild(b);
    b.addEventListener('pointerdown', function (e) { e.stopPropagation(); st.on = true; st.tap++; b.classList.add('on'); });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (k) { b.addEventListener(k, function () { st.on = false; b.classList.remove('on'); }); });
    return st; }
  function keys() { var k = {}; function d(e) { k[e.code] = true; } function u(e) { k[e.code] = false; } addEventListener('keydown', d); addEventListener('keyup', u); k.off = function () { removeEventListener('keydown', d); removeEventListener('keyup', u); }; return k; }

  var ac = null;
  function sfx(type) {
    try {
      ac = ac || new (window.AudioContext || window.webkitAudioContext)();
      var t = ac.currentTime, o = ac.createOscillator(), g = ac.createGain(); o.connect(g); g.connect(ac.destination);
      var P = { shot: ['square', 520, 140, 0.08, 0.12], boom: ['sawtooth', 120, 30, 0.35, 0.25], pick: ['triangle', 660, 1320, 0.15, 0.15],
        hit: ['square', 220, 90, 0.1, 0.12], bump: ['triangle', 160, 80, 0.12, 0.2], win: ['triangle', 520, 1040, 0.5, 0.18], tick: ['sine', 880, 880, 0.05, 0.1] }[type] || ['sine', 440, 440, 0.1, 0.1];
      o.type = P[0]; o.frequency.setValueAtTime(P[1], t); o.frequency.exponentialRampToValueAtTime(Math.max(20, P[2]), t + P[3]);
      g.gain.setValueAtTime(P[4], t); g.gain.exponentialRampToValueAtTime(0.001, t + P[3]); o.start(t); o.stop(t + P[3] + 0.02);
    } catch (e) {}
  }
  function haptic(k) { try { window.Telegram.WebApp.HapticFeedback.impactOccurred(k || 'light'); } catch (e) {} }

  // Menyu: items [[label, fn, cls]]
  function menu(host, title, sub, items) {
    host.innerHTML = '<div class="ak-card"><h1>' + title + '</h1>' + (sub ? '<div class="ak-sub">' + sub + '</div>' : '') +
      items.map(function (it, i) { return '<button class="ak-mb ' + (it[2] || '') + '" data-i="' + i + '">' + it[0] + '</button>'; }).join('') + '</div>';
    host.style.display = 'flex';
    host.querySelectorAll('.ak-mb').forEach(function (b) { b.onclick = function () { sfx('tick'); items[+b.dataset.i][1](); }; });
  }
  function hideMenu(host) { host.style.display = 'none'; host.innerHTML = ''; }

  function loop(fn) { var run = true, last = performance.now(); (function f(now) { if (!run) return; var dt = Math.min(0.05, (now - last) / 1000); last = now; fn(dt, now / 1000); requestAnimationFrame(f); })(last); return function () { run = false; }; }
  function lerpAng(a, b, k) { var d = ((b - a + Math.PI * 3) % (Math.PI * 2)) - Math.PI; return a + d * k; }
  function label(text, color) {
    three();
    var c = document.createElement('canvas'); c.width = 256; c.height = 64; var x = c.getContext('2d');
    x.font = 'bold 30px system-ui'; x.textAlign = 'center'; x.lineWidth = 6; x.strokeStyle = '#000a'; x.strokeText(text, 128, 42); x.fillStyle = color || '#fff'; x.fillText(text, 128, 42);
    var s = new T.Sprite(new T.SpriteMaterial({ map: new T.CanvasTexture(c), depthTest: false, transparent: true })); s.scale.set(5, 1.25, 1); return s;
  }

  window.AKIT = { rng: rng, el: el, esc: esc, root: root, world: world, grid: grid, stick: stick, button: button, keys: keys, sfx: sfx, haptic: haptic,
    menu: menu, hideMenu: hideMenu, loop: loop, lerpAng: lerpAng, label: label,
    COLORS: [0x3ea8ff, 0xff4d6d, 0x5dff7a, 0xffc93e, 0xc77dff, 0x2ef2e0, 0xff8a3d, 0xf5f5f5] };
})();
