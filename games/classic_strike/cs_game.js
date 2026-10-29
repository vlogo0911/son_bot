/* CLASSIC STRIKE — GameEngine (renderer, loop, tozalash), PlayerController (touch/klaviatura/sichqoncha),
   RoundManager (TDM, Deathmatch, Bomb Mission, Survival) va CS3D.launch(). */
(function () {
  'use strict';
  const CS3D = window.CS3D, U = CS3D.U, W = CS3D.WeaponSystem.WEAPONS, UI = CS3D.UI, A = CS3D.Audio;
  const EYE = 1.62, GRAV = 15, JUMP = 5.2;

  function hasWebGL() {
    try { const c = document.createElement('canvas'); return !!(window.WebGLRenderingContext && (c.getContext('webgl') || c.getContext('experimental-webgl'))); } catch (e) { return false; }
  }

  // ══ GameEngine ══
  function Engine(view) {
    this.view = view;
    const q = CS3D.Save.data.settings.quality;
    const weak = (navigator.deviceMemory && navigator.deviceMemory <= 3) || (navigator.hardwareConcurrency && navigator.hardwareConcurrency <= 4);
    this.quality = q === 'auto' ? (weak ? 'low' : 'medium') : q; this.auto = q === 'auto';
    this.renderer = new THREE.WebGLRenderer({ antialias: this.quality !== 'low', powerPreference: 'high-performance', alpha: false });
    this.renderer.autoClear = false;
    view.appendChild(this.renderer.domElement);
    this.camera = new THREE.PerspectiveCamera(75, 1, 0.05, 160);
    this.camera.rotation.order = 'YXZ';
    this.vmScene = new THREE.Scene(); this.vmCam = new THREE.PerspectiveCamera(60, 1, 0.01, 10);
    this.vmScene.add(new THREE.HemisphereLight(0xffffff, 0x404040, 0.9)); const dl = new THREE.DirectionalLight(0xffffff, 0.6); dl.position.set(1, 2, 1); this.vmScene.add(dl);
    this.prScale = 1; this.applyQuality();
    this.onResize = () => this.resize(); window.addEventListener('resize', this.onResize); window.addEventListener('orientationchange', this.onResize);
    this.resize();
  }
  Engine.prototype.applyQuality = function () {
    const dpr = window.devicePixelRatio || 1, base = { low: 0.7, medium: 1.1, high: 1.6 }[this.quality] || 1;
    this.renderer.setPixelRatio(Math.min(dpr, base) * this.prScale);
    this.renderer.shadowMap.enabled = this.quality === 'high';
  };
  Engine.prototype.resize = function () {
    const w = this.view.clientWidth || window.innerWidth, h = this.view.clientHeight || window.innerHeight;
    this.renderer.setSize(w, h, false); this.renderer.domElement.style.width = '100%'; this.renderer.domElement.style.height = '100%';
    this.camera.aspect = this.vmCam.aspect = w / Math.max(1, h); this.camera.updateProjectionMatrix(); this.vmCam.updateProjectionMatrix();
    UI.rotateHint();
  };
  Engine.prototype.render = function (scene, vm) {
    const r = this.renderer; r.clear(); r.render(scene, this.camera);
    if (vm) { r.clearDepth(); r.render(this.vmScene, this.vmCam); }
  };
  Engine.prototype.dispose = function () {
    window.removeEventListener('resize', this.onResize); window.removeEventListener('orientationchange', this.onResize);
    this.vmScene.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); });
    this.renderer.dispose(); try { this.renderer.forceContextLoss(); } catch (e) { /* */ }
    this.renderer.domElement.remove();
  };

  // ══ PlayerController (kirish) ══
  function Input(root, ctl, canvas) {
    const inp = (this.s = { mx: 0, my: 0, lx: 0, ly: 0, fire: false, aim: false, run: false, jump: false, reload: false, sw: false, swTo: 0, use: false, pause: false, keys: {} });
    const ptr = new Map(), joy = ctl.querySelector('.cs-joy'), knob = joy.querySelector('i');
    const R = () => 58 * (parseFloat(getComputedStyle(root).getPropertyValue('--csb')) || 1);
    const btnAct = { fire: 1, aim: 1, reload: 1, switch: 1, jump: 1, run: 1, use: 1, pause: 1 };
    this.down = (e) => {
      if (e.pointerType === 'mouse') return;   // sichqoncha alohida
      e.preventDefault();
      const b = e.target.closest('.cs-b'), a = b && b.dataset.a;
      const p = { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, a: a || (e.clientX < window.innerWidth * 0.42 ? 'joy' : 'look'), b };
      ptr.set(e.pointerId, p);
      try { ctl.setPointerCapture(e.pointerId); } catch (_) { /* */ }
      if (p.a === 'joy') { joy.style.left = p.x + 'px'; joy.style.top = p.y + 'px'; joy.classList.add('on'); }
      else if (btnAct[p.a]) {
        b.classList.add('down');
        if (p.a === 'fire') inp.fire = true; else if (p.a === 'aim') inp.aim = !inp.aim; else if (p.a === 'reload') inp.reload = true;
        else if (p.a === 'switch') inp.sw = true; else if (p.a === 'jump') inp.jump = true; else if (p.a === 'run') inp.run = !inp.run;
        else if (p.a === 'use') inp.use = true; else if (p.a === 'pause') inp.pause = true;
      }
      CS3D.Audio.resume();
    };
    this.move = (e) => {
      const p = ptr.get(e.pointerId); if (!p) return; e.preventDefault();
      const dx = e.clientX - p.x, dy = e.clientY - p.y; p.x = e.clientX; p.y = e.clientY;
      if (p.a === 'joy') {
        let vx = p.x - p.sx, vy = p.y - p.sy; const r = R(), l = Math.hypot(vx, vy);
        if (l > r) { p.sx += vx - (vx / l) * r; p.sy += vy - (vy / l) * r; vx = (vx / l) * r; vy = (vy / l) * r; joy.style.left = p.sx + 'px'; joy.style.top = p.sy + 'px'; }
        knob.style.transform = 'translate(' + vx + 'px,' + vy + 'px)';
        inp.mx = vx / r; inp.my = vy / r;
        inp.joyRun = l > r * 0.98 && vy < -r * 0.7;   // joystickni oxirigacha oldinga — yugurish
      } else if (p.a === 'look' || p.a === 'fire') { inp.lx += dx; inp.ly += dy; }
    };
    this.up = (e) => {
      const p = ptr.get(e.pointerId); if (!p) return; ptr.delete(e.pointerId);
      if (p.a === 'joy') { inp.mx = inp.my = 0; inp.joyRun = false; knob.style.transform = ''; joy.classList.remove('on'); }
      if (p.b) p.b.classList.remove('down');
      if (p.a === 'fire' && ![...ptr.values()].some((q) => q.a === 'fire')) inp.fire = false;
      if (p.a === 'use') inp.use = false;
    };
    ctl.addEventListener('pointerdown', this.down, { passive: false });
    ctl.addEventListener('pointermove', this.move, { passive: false });
    ctl.addEventListener('pointerup', this.up); ctl.addEventListener('pointercancel', this.up); ctl.addEventListener('lostpointercapture', this.up);
    // Brauzer gesture/scroll/zoom aralashmasin
    this.block = (e) => { if (root.classList.contains('playing')) e.preventDefault(); };
    root.addEventListener('touchmove', this.block, { passive: false }); root.addEventListener('gesturestart', this.block); root.addEventListener('contextmenu', (e) => e.preventDefault());
    // Klaviatura
    const KEYS = { KeyW: 1, KeyA: 1, KeyS: 1, KeyD: 1, ArrowUp: 1, ArrowDown: 1, ArrowLeft: 1, ArrowRight: 1, ShiftLeft: 1, ShiftRight: 1 };
    this.kd = (e) => {
      if (!root.classList.contains('playing')) return;
      if (KEYS[e.code]) inp.keys[e.code] = true;
      if (e.repeat) return;
      if (e.code === 'Space') { inp.jump = true; e.preventDefault(); }
      if (e.code === 'KeyR') inp.reload = true; if (e.code === 'KeyQ') inp.sw = true; if (e.code === 'KeyE') inp.use = true;
      if (e.code === 'Digit1') inp.swTo = 1; if (e.code === 'Digit2') inp.swTo = 2; if (e.code === 'Digit3') inp.swTo = 3;
      if (e.code === 'Escape' || e.code === 'KeyP') inp.pause = true;
    };
    this.ku = (e) => { if (KEYS[e.code]) inp.keys[e.code] = false; if (e.code === 'KeyE') inp.use = false; };
    window.addEventListener('keydown', this.kd); window.addEventListener('keyup', this.ku);
    // Sichqoncha (Pointer Lock)
    this.canvas = canvas;
    this.mdown = (e) => {
      if (e.pointerType && e.pointerType !== 'mouse') return;
      if (!root.classList.contains('playing')) return;
      if (document.pointerLockElement !== canvas) { try { canvas.requestPointerLock(); } catch (_) { /* */ } }
      if (e.button === 0) inp.fire = true; if (e.button === 2) inp.aim = !inp.aim;
    };
    this.mup = (e) => { if (e.button === 0) inp.fire = false; };
    this.mmove = (e) => { if (document.pointerLockElement === canvas) { inp.lx += e.movementX * 0.42; inp.ly += e.movementY * 0.42; } };
    this.wheel = (e) => { if (root.classList.contains('playing')) inp.sw = true; };
    ctl.addEventListener('mousedown', this.mdown); window.addEventListener('mouseup', this.mup); window.addEventListener('mousemove', this.mmove); ctl.addEventListener('wheel', this.wheel, { passive: true });
    this.ctl = ctl; this.root = root; this.ptr = ptr;
  }
  Input.prototype.axes = function () {
    const s = this.s, k = s.keys;
    let x = s.mx, y = s.my;
    if (k.KeyA || k.ArrowLeft) x -= 1; if (k.KeyD || k.ArrowRight) x += 1; if (k.KeyW || k.ArrowUp) y -= 1; if (k.KeyS || k.ArrowDown) y += 1;
    const l = Math.hypot(x, y); if (l > 1) { x /= l; y /= l; }
    return [x, y, !!(k.ShiftLeft || k.ShiftRight || s.run || s.joyRun)];
  };
  Input.prototype.release = function () { const s = this.s; s.mx = s.my = 0; s.fire = false; s.use = false; s.keys = {}; this.ptr.clear(); if (document.pointerLockElement) document.exitPointerLock(); };
  Input.prototype.dispose = function () {
    const c = this.ctl;
    c.removeEventListener('pointerdown', this.down); c.removeEventListener('pointermove', this.move); c.removeEventListener('pointerup', this.up);
    c.removeEventListener('pointercancel', this.up); c.removeEventListener('lostpointercapture', this.up); this.root.removeEventListener('touchmove', this.block);
    window.removeEventListener('keydown', this.kd); window.removeEventListener('keyup', this.ku);
    c.removeEventListener('mousedown', this.mdown); window.removeEventListener('mouseup', this.mup); window.removeEventListener('mousemove', this.mmove); c.removeEventListener('wheel', this.wheel);
    if (document.pointerLockElement) document.exitPointerLock();
  };

  // ══ Player ══
  function Player(match, team) {
    this.match = match; this.id = 'player'; this.name = 'Siz'; this.bot = false; this.team = team;
    this.r = 0.34; this.h = 1.8; this.kills = 0; this.deaths = 0; this.st = { shots: 0, hits: 0, heads: 0 };
    const L = CS3D.Save.data.last, pri = CS3D.Save.weaponOpen(L.primary) ? L.primary : 'rifle';
    this.slots = { 1: pri === 'deagle' ? null : pri, 2: pri === 'deagle' || CS3D.Save.weaponOpen('deagle') ? 'deagle' : 'pistol', 3: 'knife' };
    this.respawn(0, 0);
  }
  const PP = Player.prototype;
  PP.respawn = function (x, z, yaw) {
    this.x = x; this.z = z; this.y = 0; this.vy = 0; this.yaw = yaw || 0; this.pitch = 0; this.hp = 100; this.alive = true; this.speed = 0;
    this.ammo = {}; for (const s of [1, 2]) { const w = this.slots[s]; if (w) this.ammo[w] = { mag: W[w].mag, res: W[w].res }; }
    this.cur = this.slots[1] ? 1 : 2; this.fireCd = 0; this.reloadT = 0; this.switchT = 0.4; this.bloom = 0; this.kick = 0; this.kickYaw = 0;
    this.aim = false; this.onGround = true; this.stepD = 0; this.pressFired = false; this.deadT = 0; this.carry = this.carry || false;
    this.match.setViewmodel(this.wid());
  };
  PP.wid = function () { return this.slots[this.cur]; };
  PP.refill = function () { for (const k of Object.keys(this.ammo)) this.ammo[k].res = W[k].res; };
  PP.hurt = function (dmg, from) {
    if (!this.alive || this.match.god) return;
    this.hp -= dmg; A.hurt();
    let rel = null;
    if (from) { const a = Math.atan2(-(from.x - this.x), -(from.z - this.z)); rel = -U.angDiff(this.yaw, a); }
    UI.damage(rel);
    try { window.Telegram.WebApp.HapticFeedback.impactOccurred('medium'); } catch (e) { /* */ }
    if (this.hp <= 0) { this.hp = 0; this.alive = false; this.deadT = 0; this.aim = false; }
  };
  PP.switchTo = function (slot) {
    if (!this.slots[slot] || slot === this.cur) return;
    this.cur = slot; this.switchT = 0.45; this.reloadT = 0; this.aim = false; this.match.setViewmodel(this.wid()); A.reload(0);
  };
  PP.nextSlot = function () { for (let i = 1; i <= 3; i++) { const s = ((this.cur - 1 + i) % 3) + 1; if (this.slots[s]) { this.switchTo(s); return; } } };
  PP.update = function (dt, inp) {
    const M = this.match, map = M.map, s = inp.s, sens = CS3D.Save.data.settings.sens;
    const w = W[this.wid()];
    // qarash
    const zoom = this.aim && w.zoom ? w.zoom : 1;
    this.yaw -= s.lx * 0.0052 * sens / zoom; this.pitch -= s.ly * 0.0052 * sens / zoom; s.lx = s.ly = 0;
    this.pitch = U.clamp(this.pitch, -1.45, 1.45);
    if (!this.alive) return;
    if (M.freeze) { inp.s.jump = false; }
    // harakat
    const [ax, ay, run] = inp.axes();
    const canMove = !M.freeze && !M.planting;
    const sp = (run && ay < -0.3 && !this.aim ? 5.6 : 3.5) * (w.move || 1) * (this.aim ? 0.62 : 1);
    const fx = -Math.sin(this.yaw), fz = -Math.cos(this.yaw), rx = Math.cos(this.yaw), rz = -Math.sin(this.yaw);
    let vx = (rx * ax - fx * ay) * sp, vz = (rz * ax - fz * ay) * sp;
    if (!canMove) vx = vz = 0;
    const ox = this.x, oz = this.z;
    map.move(this, vx * dt, vz * dt, this.r, this.y);
    for (const b of M.bots) { if (!b.alive) continue; const dx = this.x - b.x, dz = this.z - b.z, d = Math.hypot(dx, dz); if (d < 0.66 && d > 1e-3) map.move(this, dx / d * (0.66 - d), dz / d * (0.66 - d), this.r, this.y); }
    const moved = Math.hypot(this.x - ox, this.z - oz);
    this.speed = moved / Math.max(dt, 1e-4);
    // sakrash va gravitatsiya
    const ground = map.heightAt(this.x, this.z, this.r);
    if (s.jump && this.onGround && canMove) { this.vy = JUMP; this.onGround = false; A.jump(); }
    s.jump = false;
    this.vy -= GRAV * dt; this.y += this.vy * dt;
    if (this.y <= ground) { if (!this.onGround && this.vy < -6) A.step(true); this.y = ground; this.vy = 0; this.onGround = true; } else this.onGround = this.y - ground < 0.02;
    // qadam ovozi + botlar eshitadigan shovqin
    if (this.onGround && moved > 0) {
      this.stepD += moved;
      const stride = this.speed > 4.5 ? 2.1 : 2.6;
      if (this.stepD > stride) { this.stepD = 0; A.step(this.speed > 4.5); if (this.speed > 4.5) M.noise(this.x, this.z, 9, this.team); }
    }
    // qurol
    if (s.swTo) { this.switchTo(s.swTo); s.swTo = 0; }
    if (s.sw) { this.nextSlot(); s.sw = false; }
    this.aim = s.aim && !w.melee && this.reloadT <= 0 && this.switchT <= 0;
    if (!w.melee && !w.zoom && s.aim && this.reloadT <= 0) this.aim = true;
    if (this.fireCd > 0) this.fireCd -= dt;
    if (this.switchT > 0) this.switchT -= dt;
    this.bloom = Math.max(0, this.bloom - dt * 0.12);
    this.kick = Math.max(0, this.kick - dt * (this.kick * 9 + 0.02)); this.kickYaw *= Math.max(0, 1 - dt * 10);
    const am = this.ammo[this.wid()];
    if (this.reloadT > 0) {
      const prev = this.reloadT; this.reloadT -= dt;
      if (prev > w.reload * 0.45 && this.reloadT <= w.reload * 0.45) A.reload(1);
      if (this.reloadT <= 0) { const need = w.mag - am.mag, take = Math.min(need, am.res); am.mag += take; am.res -= take; }
    }
    if (s.reload) { s.reload = false; if (am && this.reloadT <= 0 && am.mag < w.mag && am.res > 0) { this.reloadT = w.reload; this.aim = false; A.reload(0); } }
    if (s.fire && !M.freeze && this.switchT <= 0) {
      if (w.melee) {
        if (this.fireCd <= 0) { this.fireCd = w.rate; A.knife(); M.vmSwing = 0.3; M.shoot(this, 0); }
      } else if (this.reloadT <= 0 && this.fireCd <= 0 && (w.auto || !this.pressFired)) {
        this.pressFired = true;
        if (am.mag <= 0) { A.dry(); this.fireCd = 0.25; if (am.res > 0) { this.reloadT = w.reload; A.reload(0); } }
        else {
          am.mag--; this.fireCd = w.rate;
          const spread = (this.aim && w.adsSpread !== undefined ? w.adsSpread : w.spread * (this.aim ? 0.55 : 1)) + w.moveSpread * Math.min(1, this.speed / 5) + (this.onGround ? 0 : 0.09) + this.bloom;
          M.shoot(this, spread);
          this.bloom = Math.min(0.09, this.bloom + w.recoil * 0.45);
          this.kick += w.recoil * U.rand(0.8, 1.2); this.kickYaw += U.rand(-1, 1) * w.recoil * 0.4;
          this.pitch = U.clamp(this.pitch + w.recoil * 0.35, -1.45, 1.45);
          if (am.mag === 0 && am.res > 0) this.autoReload = 0.25;
        }
      }
    }
    if (!s.fire) this.pressFired = false;
    if (this.autoReload > 0 && (this.autoReload -= dt) <= 0 && this.reloadT <= 0 && am && am.mag === 0 && am.res > 0) { this.reloadT = w.reload; A.reload(0); }
    this.curSpread = (this.aim && w.adsSpread !== undefined ? w.adsSpread : (w.spread || 0.02) * (this.aim ? 0.55 : 1)) + (w.moveSpread || 0) * Math.min(1, this.speed / 5) + (this.onGround ? 0 : 0.09) + this.bloom;
  };

  // ══ Match (o'yin) + RoundManager ══
  function Match(game, cfg) {
    this.game = game; this.cfg = cfg; this.E = game.engine; this.time = 0; this.paused = false; this.over = false; this.ff = false;
    this.scene = new THREE.Scene();
    this.map = new CS3D.MapSystem.GameMap(cfg.map); this.map.build(this.scene, this.E.quality);
    this.fx = new CS3D.WeaponSystem.Effects(this.scene, this.E.quality);
    this.bots = []; this.entities = []; this.respawns = []; this.spotT = 0;
    this.vm = null; this.vmSwing = 0; this.vmBob = 0;
    this.world = this; // botlar uchun interfeys
    this.net = cfg.net || null;
    const pteam = cfg.mode === 'bomb' && cfg.side === 'attack' ? 'T' : 'CT';
    this.player = new Player(this, pteam);
    this.entities.push(this.player);
    this.R = RoundManager[cfg.mode] || RoundManager.tdm;
    this.R.init(this);
    UI.playing(true); A.roundStart(); A.music(true);
  }
  const MP = Match.prototype;
  MP.botCap = function () { return { low: 6, medium: 8, high: 8 }[this.E.quality] || 8; };
  MP.addBot = function (team, opt) {
    const b = new CS3D.EnemyAI.Bot(this, team, this.cfg.diff, opt); this.bots.push(b); this.entities.push(b); return b;
  };
  MP.setViewmodel = function (wid) {
    if (this.vm) { this.E.vmScene.remove(this.vm); CS3D.WeaponSystem.vmDispose(this.vm); }
    this.vm = CS3D.WeaponSystem.vmBuild(wid); this.E.vmScene.add(this.vm); this.vmWid = wid;
  };
  MP.noise = function (x, z, r, team) { const n = { x, z, r, team }; for (const b of this.bots) if (b.alive && b.team !== team) b.hear(n); };
  MP.sound = function (kind, x, z, wid) {
    const d = Math.hypot(x - this.player.x, z - this.player.z);
    if (kind === 'shot') A.shot(W[wid].snd || 'rifle', d); else if (kind === 'impact' && d < 25) A.impact(d);
  };
  MP.onSpotted = function (bot) { if (bot.team !== this.player.team && this.time - this.spotT > 4) { this.spotT = this.time; A.spotted(); } };
  MP.shoot = function (pl, spread) {
    const e = [pl.x, pl.y + EYE, pl.z], wid = pl.wid();
    if (this.net && !W[wid].melee) this.net.emit({ k: 'sh', w: wid, y: +(pl.yaw + pl.kickYaw).toFixed(3), p: +(pl.pitch + pl.kick).toFixed(3) });
    const res = CS3D.WeaponSystem.fire(this, pl, wid, e[0], e[1], e[2], pl.yaw + pl.kickYaw, pl.pitch + pl.kick, spread, 1);
    if (!W[wid].melee) {
      pl.st.shots++; A.shot(W[wid].snd, 0); this.noise(pl.x, pl.z, 38, pl.team);
      this.vmKick = 1; if (this.vm) this.vm.userData.flash.forEach((f) => { f.visible = true; f.rotation.z = Math.random() * 3; }); this.flashT = 0.045;
    }
    let any = false;
    for (const r of res) if (r.hit) { any = true; if (r.head) pl.st.heads++; }
    if (any) { pl.st.hits++; A.hit(); UI.hitmark(res.some((r) => r.head), res.some((r) => r.hit && !r.e.alive)); }
  };
  MP.botFire = function (bot, yaw, pitch, spread) {
    const e = bot.eye();
    CS3D.WeaponSystem.fire(this, bot, bot.wid, e[0], e[1] - 0.08, e[2], yaw, pitch, spread, bot.D.dmg * (bot.dmgMul || 1));
    this.fx.flash(e[0] - Math.sin(yaw) * 0.6, e[1] - 0.25, e[2] - Math.cos(yaw) * 0.6);
    this.sound('shot', bot.x, bot.z, bot.wid); this.noise(bot.x, bot.z, 30, bot.team);
  };
  MP.damage = function (e, dmg, from, wid, head, dir) {
    if (!e.alive) return;
    if (this.net) {   // online: zararni qurbon o'zi qabul qiladi (hodisa orqali)
      if (e.net && from === this.player) this.net.emit({ k: 'hit', to: e.uid, dmg: Math.round(dmg), head: head ? 1 : 0, wid });
      return;
    }
    if (e.bot) e.hurt(dmg, from, dir); else e.hurt(dmg, from);
    if (e.bot) A.flesh();
    if (!e.alive) {
      e.deaths++; if (from) from.kills++;
      UI.feed(from ? from.name : '?', W[wid].name, e.name, from === this.player || e === this.player, head);
      this.R.onKill(this, from, e, wid, head);
    }
  };
  MP.update = function (dt) {
    this.time += dt;
    const pl = this.player, inp = this.game.input;
    pl.update(dt, inp);
    for (const b of this.bots) if (b.net) netBot(b, dt); else b.update(dt);
    if (this.net) this.net.send({ x: +pl.x.toFixed(2), z: +pl.z.toFixed(2), y: +pl.y.toFixed(2), yw: +pl.yaw.toFixed(2), al: pl.alive ? 1 : 0, w: pl.wid(), k: pl.kills });
    for (let i = this.respawns.length - 1; i >= 0; i--) { const r = this.respawns[i]; r.t -= dt; if (r.t <= 0) { this.respawns.splice(i, 1); this.R.respawn(this, r.e); } }
    this.R.update(this, dt);
    this.fx.update(dt, this.E.camera);
    this.updateCamera(dt);
  };
  MP.updateCamera = function (dt) {
    const pl = this.player, cam = this.E.camera, w = W[pl.wid()];
    const bobOn = pl.alive && pl.onGround && pl.speed > 0.5;
    this.vmBob += dt * (bobOn ? pl.speed * 2.3 : 0);
    const bob = bobOn ? Math.sin(this.vmBob) * 0.035 : 0;
    if (pl.alive) {
      cam.position.set(pl.x, pl.y + EYE + Math.abs(bob) * 0.6, pl.z);
      cam.rotation.set(pl.pitch + pl.kick, pl.yaw + pl.kickYaw, 0);
    } else {
      pl.deadT += dt; const k = Math.min(1, pl.deadT / 0.8);
      cam.position.set(pl.x, pl.y + EYE - k * 1.2, pl.z); cam.rotation.set(pl.pitch - k * 0.5, pl.yaw, k * 0.6);
    }
    const fov = pl.aim ? 75 / (w.zoom || 1.18) : 75;
    if (Math.abs(cam.fov - fov) > 0.05) { cam.fov = U.lerp(cam.fov, fov, Math.min(1, dt * 14)); cam.updateProjectionMatrix(); }
    // Viewmodel animatsiyasi
    const vm = this.vm; if (!vm) return;
    this.vmKick = Math.max(0, (this.vmKick || 0) - dt * 9);
    if (this.flashT > 0 && (this.flashT -= dt) <= 0) vm.userData.flash.forEach((f) => (f.visible = false));
    if (this.vmSwing > 0) this.vmSwing -= dt;
    const ads = pl.aim && !w.scope;
    let px = ads ? 0 : 0.2, py = ads ? -0.13 : -0.2, pz = ads ? -0.3 : -0.42;
    let rx = 0, ry = 0, rz = 0;
    px += Math.cos(this.vmBob * 0.5) * (bobOn ? 0.012 : 0); py += bob * 0.5;
    pz += this.vmKick * 0.07; rx += this.vmKick * 0.12;
    if (pl.reloadT > 0) { const k = Math.sin(Math.PI * (1 - pl.reloadT / w.reload)); py -= k * 0.16; rx -= k * 0.7; rz += k * 0.3; }
    if (pl.switchT > 0) py -= pl.switchT * 0.6;
    if (this.vmSwing > 0) { const k = Math.sin((0.3 - this.vmSwing) / 0.3 * Math.PI); px -= k * 0.15; ry += k * 0.9; rx -= k * 0.4; }
    vm.position.set(px, py, pz); vm.rotation.set(rx, ry, rz);
    vm.visible = pl.alive && !(pl.aim && w.scope);
  };
  MP.hud = function () {
    const pl = this.player, w = W[pl.wid()], am = pl.ammo[pl.wid()], R = this.R;
    UI.hudUpdate({
      hp: pl.hp, wn: w.name, am: w.melee ? '—' : (pl.reloadT > 0 ? '…' : am.mag), res: w.melee ? '' : '/ ' + am.res, lowAmmo: am && am.mag <= w.mag * 0.25,
      timer: R.timerText(this), score: R.scoreText(this), obj: R.objText(this), use: R.useText ? R.useText(this) : '', run: this.game.input.s.run,
      aim: pl.aim, scope: pl.aim && w.scope, spread: pl.curSpread || 0, bar: R.bar ? R.bar(this) : null,
    });
  };
  MP.end = function (win, reason, extra) {
    if (this.over) return; this.over = true;
    const pl = this.player, st = pl.st;
    const res = Object.assign({ mode: this.cfg.mode, map: this.cfg.map, diff: this.cfg.diff, win, reason, kills: pl.kills, deaths: pl.deaths,
      heads: st.heads, shots: st.shots, hits: st.hits, time: this.time }, extra || {});
    const mult = { easy: 0.7, normal: 1, hard: 1.4 }[this.cfg.diff] || 1;
    res.score = Math.round((res.kills * 100 + res.heads * 50 + (win ? 1000 : 0) + (res.wave || 0) * 300 + (res.roundsW || 0) * 400) * mult);
    const before = { w: Object.keys(CS3D.Save.WEAPON_UNLOCK).filter((k) => CS3D.Save.weaponOpen(k)), m: Object.keys(CS3D.Save.MAP_UNLOCK).filter((k) => CS3D.Save.mapOpen(k)) };
    res.best = res.score > CS3D.Save.data.stats.best;
    CS3D.Save.record(res);
    res.unlocks = Object.keys(CS3D.Save.WEAPON_UNLOCK).filter((k) => CS3D.Save.weaponOpen(k) && before.w.indexOf(k) < 0).map((k) => W[k].name)
      .concat(Object.keys(CS3D.Save.MAP_UNLOCK).filter((k) => CS3D.Save.mapOpen(k) && before.m.indexOf(k) < 0).map((k) => CS3D.MapSystem.MAPS[k].name));
    win ? A.victory() : A.defeat(); A.music(false);
    this.game.input.release();
    UI.results(res, this.game.H);
    this.game.result(res);
  };
  MP.dispose = function () {
    for (const b of this.bots) b.dispose();
    this.fx.dispose(); this.map.dispose();
    this.scene.traverse((o) => { if (o.geometry && !o.isInstancedMesh) { /* bot/map umumiy geometriyasi alohida tozalanadi */ } });
    if (this.vm) { this.E.vmScene.remove(this.vm); CS3D.WeaponSystem.vmDispose(this.vm); this.vm = null; }
    if (this.bomb) { this.scene.remove(this.bomb.mesh); this.bomb.mesh.traverse((o) => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
  };

  // ── 🌐 Online: boshqa o'yinchilar bot modeli bilan ko'rsatiladi, holat tarmoqdan keladi ──
  function netBot(b, dt) {
    const s = b.netS, ud = b.mesh.userData; if (!s) return;
    if (!s.al && b.alive) { b.alive = false; b.deathT = 0; b.fallDir = Math.random() < 0.5 ? -1 : 1; }
    if (s.al && !b.alive) { b.spawn(s.x, s.z); }
    if (!b.alive) { b.update(dt); return; }
    const f = Math.min(1, dt * 12), ox = b.x, oz = b.z;
    b.x += (s.x - b.x) * f; b.z += (s.z - b.z) * f; b.y += (s.y - b.y) * f; b.yaw += U.angDiff(b.yaw, s.yw) * f;
    if (s.w && W[s.w]) b.wid = s.w;
    const mv = Math.hypot(b.x - ox, b.z - oz); b.walkPh = (b.walkPh || 0) + mv * 4; const sw = mv > 0.002 ? Math.sin(b.walkPh) * 0.6 : 0;
    b.mesh.position.set(b.x, b.y, b.z); b.mesh.rotation.y = b.yaw; ud.legL.rotation.x = sw; ud.legR.rotation.x = -sw;
  }
  function netKill(M, e, by, wid, head) {
    if (!e) return; const from = by === M.net.me ? M.player : M.bots.find((b) => b.uid === by);
    if (e === M.player) { if (M.player.alive) M.player.hp = 0; M.player.alive = false; }
    else if (e.alive) { e.alive = false; e.deathT = 0; e.fallDir = 1; }
    e.deaths++; if (from && from !== e) from.kills++;
    UI.feed(from ? from.name : '?', (W[wid] || W.rifle).name, e.name, from === M.player || e === M.player, !!head);
    M.R.onKill(M, from, e, wid, head);
  }
  CS3D.netHandlers = {
    sync(M, r) {
      const seen = {};
      for (const p of r.players) {
        if (p.uid === M.net.me) continue; seen[p.uid] = 1;
        let b = M.bots.find((x) => x.uid === p.uid);
        if (!b) { b = M.addBot('T', { name: p.name.slice(0, 14), weapon: 'rifle' }); b.net = true; b.uid = p.uid; if (p.state) { b.spawn(p.state.x, p.state.z); } else b.mesh.visible = false; }
        if (p.state) b.netS = p.state;
      }
      for (let i = M.bots.length - 1; i >= 0; i--) { const b = M.bots[i]; if (b.net && !seen[b.uid]) { b.dispose(); M.bots.splice(i, 1); M.entities.splice(M.entities.indexOf(b), 1); } }
    },
    event(M, e) {
      const d = e.d, me = M.net.me, pl = M.player;
      if (d.k === 'hit' && d.to === me && pl.alive && !M.over) {
        const from = M.bots.find((b) => b.uid === e.u); pl.hurt(Math.min(200, d.dmg | 0), from);
        if (!pl.alive) M.net.emit({ k: 'die', by: e.u, wid: d.wid, head: d.head });
      } else if (d.k === 'die') {
        netKill(M, e.u === me ? pl : M.bots.find((b) => b.uid === e.u), d.by, d.wid, d.head);
      } else if (d.k === 'sh' && e.u !== me) {
        const b = M.bots.find((x) => x.uid === e.u); if (!b || !b.alive) return;
        const o = b.eye(), cp = Math.cos(d.p), dx = -Math.sin(d.y) * cp, dy = Math.sin(d.p), dz = -Math.cos(d.y) * cp, wh = M.map.ray(o[0], o[1], o[2], dx, dy, dz, 120);
        M.fx.tracer([o[0] + dx * 0.6, o[1] - 0.1, o[2] + dz * 0.6], [o[0] + dx * wh.d, o[1] + dy * wh.d, o[2] + dz * wh.d]);
        M.fx.flash(o[0] - Math.sin(d.y) * 0.6, o[1] - 0.25, o[2] - Math.cos(d.y) * 0.6); M.sound('shot', b.x, b.z, W[d.w] ? d.w : 'rifle');
      }
    },
  };

  // ── Spawn yordamchilari ──
  function spawnTeam(M, e, team) {
    const p = M.map.spawnPoint(team);
    if (e.bot) e.spawn(p[0], p[1]); else { const enemy = team === 'T' ? 'CT' : 'T', es = M.map.spawns[enemy][0]; e.respawn(p[0], p[1], es ? Math.atan2(-(M.map.center(es[0]) - p[0]), -(M.map.center(es[1]) - p[1])) : 0); }
  }
  function spawnFar(M, e) {
    const foes = M.entities.filter((o) => o.alive && o !== e && o.team !== e.team);
    const p = M.map.spawnPoint(null, foes.length ? foes : [M.player]);
    if (e.bot) e.spawn(p[0], p[1]); else e.respawn(p[0], p[1], Math.random() * 6.28);
  }
  const alive = (M, team) => M.entities.filter((e) => e.alive && e.team === team).length;

  const RoundManager = {
    // ── Team Deathmatch ──
    tdm: {
      init(M) {
        M.target = 30; M.limit = 360; M.sc = { CT: 0, T: 0 };
        const cap = M.botCap(), per = Math.max(3, Math.floor(cap / 2));
        for (let i = 0; i < per - 1; i++) M.addBot(M.player.team, { ally: true });
        for (let i = 0; i < per; i++) M.addBot(M.player.team === 'CT' ? 'T' : 'CT');
        for (const e of M.entities) spawnTeam(M, e, e.team);
        UI.msg('TEAM DEATHMATCH<br><small>30 fragga birinchi yeting</small>', 2.5);
      },
      onKill(M, from, victim) {
        if (from && from.team !== victim.team) M.sc[from.team]++;
        M.respawns.push({ e: victim, t: 3 });
        if (victim === M.player) UI.msg('Siz halok bo‘ldingiz<br><small>3 soniyada qayta tug‘ilasiz</small>', 2.8, 'bad');
        if (M.sc.CT >= M.target || M.sc.T >= M.target) this.finish(M);
      },
      respawn(M, e) { spawnTeam(M, e, e.team); },
      update(M) { if (M.time >= M.limit) this.finish(M); },
      finish(M) {
        const me = M.sc[M.player.team], op = M.sc[M.player.team === 'CT' ? 'T' : 'CT'];
        M.end(me > op, me > op ? 'Jamoangiz g‘olib bo‘ldi' : me === op ? 'Durang' : 'Raqib jamoa g‘olib', { teamScore: me + ' : ' + op });
      },
      timerText: (M) => U.fmtTime(M.limit - M.time),
      scoreText: (M) => '<span class="ct">CT ' + M.sc.CT + '</span><i>' + M.target + '</i><span class="t">' + M.sc.T + ' T</span>',
      objText: (M) => 'Fraglar: ' + M.player.kills + ' · O‘limlar: ' + M.player.deaths,
    },
    // ── Deathmatch ──
    dm: {
      init(M) {
        M.target = 20; M.limit = 300;
        const n = Math.min(M.botCap(), 7);
        for (let i = 0; i < n; i++) M.addBot('T');
        for (const e of M.entities) spawnFar(M, e);
        UI.msg('DEATHMATCH<br><small>20 fragga yeting</small>', 2.5);
      },
      onKill(M, from, victim) {
        M.respawns.push({ e: victim, t: victim === M.player ? 3 : 2.5 });
        if (victim === M.player) UI.msg('Siz halok bo‘ldingiz', 2.5, 'bad');
        if (M.player.kills >= M.target) M.end(true, M.target + ' fragga birinchi yetdingiz!');
        else if (from && from.bot && from.kills >= M.target) M.end(false, from.name + ' ' + M.target + ' fragga yetdi');
      },
      respawn(M, e) { spawnFar(M, e); },
      update(M) {
        if (M.time >= M.limit) { const top = Math.max(0, ...M.bots.map((b) => b.kills)); M.end(M.player.kills > top, M.player.kills > top ? 'Vaqt tugadi — eng ko‘p frag sizda' : 'Vaqt tugadi'); }
      },
      timerText: (M) => U.fmtTime(M.limit - M.time),
      scoreText: (M) => { const top = M.bots.reduce((a, b) => (b.kills > (a ? a.kills : -1) ? b : a), null); return '<span class="ct">Siz ' + M.player.kills + '</span><i>' + M.target + '</i><span class="t">' + (top ? top.name + ' ' + top.kills : '') + '</span>'; },
      objText: (M) => 'O‘limlar: ' + M.player.deaths,
    },
    // ── 🌐 Online Deathmatch (har kim har kimga qarshi, botlarsiz) ──
    online: {
      init(M) {
        M.target = 25; M.limit = 360;
        spawnFar(M, M.player);
        UI.msg('🌐 ONLINE DEATHMATCH<br><small>' + M.target + ' fragga birinchi yeting</small>', 2.5);
      },
      onKill(M, from, victim) {
        if (victim === M.player) { M.respawns.push({ e: victim, t: 3 }); UI.msg('Siz halok bo‘ldingiz', 2.5, 'bad'); }
        if (M.player.kills >= M.target) M.end(true, M.target + ' fragga birinchi yetdingiz!');
        else if (from && from.net && from.kills >= M.target) M.end(false, from.name + ' ' + M.target + ' fragga yetdi');
      },
      respawn(M, e) { if (e === M.player) spawnFar(M, e); },
      update(M) {
        if (M.time >= M.limit) { const top = Math.max(0, ...M.bots.map((b) => b.kills)); M.end(M.player.kills > top, 'Vaqt tugadi'); }
      },
      timerText: (M) => U.fmtTime(M.limit - M.time),
      scoreText: (M) => { const top = M.bots.reduce((a, b) => (b.kills > (a ? a.kills : -1) ? b : a), null); return '<span class="ct">Siz ' + M.player.kills + '</span><i>' + M.target + '</i><span class="t">' + (top ? top.name + ' ' + top.kills : '—') + '</span>'; },
      objText: (M) => 'O‘yinchilar: ' + (M.bots.length + 1) + ' · O‘limlar: ' + M.player.deaths,
    },
    // ── Bomb Mission ──
    bomb: {
      init(M) {
        M.sc = { T: 0, CT: 0 }; M.toWin = 4; M.round = 0;
        const cap = M.botCap(), per = Math.max(3, Math.floor(cap / 2));
        const me = M.player.team, op = me === 'T' ? 'CT' : 'T';
        for (let i = 0; i < per - 1; i++) M.addBot(me, { ally: true });
        for (let i = 0; i < per; i++) M.addBot(op);
        this.newRound(M);
      },
      newRound(M) {
        M.round++; M.phase = 'freeze'; M.phaseT = 3.5; M.freeze = true; M.roundT = 100; M.planted = false; M.bombT = 0; M.plantP = 0; M.defuseP = 0; M.planting = false; M.respawns = [];
        if (M.bomb) { M.scene.remove(M.bomb.mesh); M.bomb = null; }
        for (const e of M.entities) { spawnTeam(M, e, e.team); e.carry = false; if (e.bot) { e.plantT = 0; e.defT = 0; } }
        // bomba tashuvchi
        const Ts = M.entities.filter((e) => e.team === 'T');
        const carrier = M.player.team === 'T' ? M.player : U.pick(Ts); carrier.carry = true; M.drop = null;
        M.site = Math.random() < 0.5 ? 'A' : 'B';
        for (const b of M.bots) this.goal(M, b);
        UI.msg('RAUND ' + M.round + '<br><small>' + (M.player.team === 'T' ? 'Bombani A yoki B hududiga qo‘ying' : 'A va B hududlarini himoya qiling') + '</small>', 3);
        A.roundStart();
      },
      goal(M, b) {
        if (M.planted && M.bomb) { b.goal = { x: M.bomb.x, z: M.bomb.z }; return; }
        if (b.team === 'T') { const c = M.map.siteC[M.site]; b.goal = { x: c[0], z: c[1] }; }
        else { const k = M.bots.indexOf(b) % 2 ? 'A' : 'B', c = M.map.siteC[k]; b.goal = { x: c[0], z: c[1] }; }
      },
      onKill(M, from, victim) {
        if (victim.carry) { victim.carry = false; M.drop = { x: victim.x, z: victim.z }; }
        if (victim === M.player) UI.msg('Siz halok bo‘ldingiz<br><small>Raund oxirini kuting</small>', 3, 'bad');
      },
      respawn() {},
      plant(M, e) {
        M.planted = true; M.bombT = 35; M.plantP = 0; e.carry = false;
        const g = new THREE.Group(), box = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.18, 0.3), new THREE.MeshLambertMaterial({ color: 0x3a3f2a }));
        box.position.y = 0.09; g.add(box);
        const led = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.04, 0.08), new THREE.MeshBasicMaterial({ color: 0xff2020 })); led.position.set(0.12, 0.2, 0); g.add(led);
        g.position.set(e.x, M.map.heightAt(e.x, e.z, 0.1), e.z); M.scene.add(g);
        M.bomb = { x: e.x, z: e.z, mesh: g, led, beep: 0 };
        for (const b of M.bots) b.goal = { x: e.x, z: e.z };
        UI.msg('💣 BOMBA QO‘YILDI', 2.2, 'warn'); A.beep(true);
      },
      update(M, dt) {
        const pl = M.player;
        if (M.phase === 'freeze') { M.phaseT -= dt; if (M.phaseT <= 0) { M.phase = 'live'; M.freeze = false; } return; }
        if (M.phase === 'end') { M.phaseT -= dt; if (M.phaseT <= 0) { if (M.sc.T >= M.toWin || M.sc.CT >= M.toWin) this.finish(M); else this.newRound(M); } return; }
        if (!M.planted) M.roundT -= dt;
        // tushib qolgan bombani T olib ketadi
        if (M.drop) for (const e of M.entities) if (e.alive && e.team === 'T' && Math.hypot(e.x - M.drop.x, e.z - M.drop.z) < 1.2) { e.carry = true; M.drop = null; if (e === pl) UI.msg('💣 Bombani oldingiz', 1.5); break; }
        // o'yinchi: bomba qo'yish / zararsizlantirish (USE bosib turish)
        M.planting = false;
        if (pl.alive && pl.carry && !M.planted && M.map.siteAt(pl.x, pl.z) && pl.onGround) {
          if (M.game.input.s.use) { M.planting = true; M.plantP += dt / 3; if (Math.random() < dt * 6) A.beep(false); if (M.plantP >= 1) this.plant(M, pl); } else M.plantP = 0;
        } else if (!M.planted) M.plantP = 0;
        if (M.planted && pl.alive && pl.team === 'CT' && Math.hypot(pl.x - M.bomb.x, pl.z - M.bomb.z) < 1.6) {
          if (M.game.input.s.use) { M.planting = true; M.defuseP += dt / 5; if (M.defuseP >= 1) return this.roundEnd(M, 'CT', 'Bomba zararsizlantirildi'); } else M.defuseP = Math.max(0, M.defuseP - dt);
        }
        // botlar: bomba qo'yish va zararsizlantirish
        for (const b of M.bots) {
          if (!b.alive) continue;
          if (!b.goal || (M.planted && b.goal.x !== M.bomb.x)) this.goal(M, b);
          if (M.drop && b.team === 'T' && !M.entities.some((e) => e.carry && e.alive)) b.goal = { x: M.drop.x, z: M.drop.z };
          if (b.carry && !M.planted && M.map.siteAt(b.x, b.z) && b.state !== 'attack') { b.plantT += dt; if (b.plantT > 3) this.plant(M, b); } else if (b.carry) b.plantT = 0;
          if (M.planted && b.team === 'CT' && Math.hypot(b.x - M.bomb.x, b.z - M.bomb.z) < 1.4 && b.state !== 'attack') { b.defT += dt; if (b.defT > 6) return this.roundEnd(M, 'CT', b.name + ' bombani zararsizlantirdi'); } else if (b.team === 'CT') b.defT = 0;
        }
        if (M.planted) {
          M.bombT -= dt; const bm = M.bomb; bm.beep -= dt;
          if (bm.beep <= 0) { bm.beep = M.bombT < 5 ? 0.18 : M.bombT < 12 ? 0.45 : 0.95; A.beep(M.bombT < 5); bm.led.visible = true; } else if (bm.beep < 0.08) bm.led.visible = false;
          if (M.bombT <= 0) {
            A.explode(); M.fx.burst(bm.x, 0.5, bm.z, 120, [1, 0.55, 0.15], 14);
            for (const e of M.entities) if (e.alive && Math.hypot(e.x - bm.x, e.z - bm.z) < 9) M.damage(e, 500, null, 'rifle', false);
            return this.roundEnd(M, 'T', 'Bomba portladi');
          }
        }
        const t = alive(M, 'T'), ct = alive(M, 'CT');
        if (!ct) return this.roundEnd(M, 'T', 'CT jamoa yo‘q qilindi');
        if (!t && !M.planted) return this.roundEnd(M, 'CT', 'T jamoa yo‘q qilindi');
        if (M.roundT <= 0 && !M.planted) return this.roundEnd(M, 'CT', 'Vaqt tugadi — bomba qo‘yilmadi');
      },
      roundEnd(M, winner, why) {
        M.phase = 'end'; M.phaseT = 4; M.sc[winner]++; M.planting = false;
        const won = winner === M.player.team;
        UI.msg((won ? '✅ RAUND SIZNIKI' : '❌ RAUND YUTQAZILDI') + '<br><small>' + why + '</small>', 3.6, won ? 'good' : 'bad'); A.roundEnd(won);
      },
      finish(M) {
        const me = M.sc[M.player.team], op = M.sc[M.player.team === 'T' ? 'CT' : 'T'];
        M.end(me > op, me > op ? 'Jamoangiz ' + me + ' raundda g‘olib' : 'Raqib ' + op + ' raundda g‘olib', { roundsW: me, roundsL: op });
      },
      timerText: (M) => (M.phase === 'freeze' ? '⏸ ' + Math.ceil(M.phaseT) : M.planted ? '💣 ' + Math.ceil(M.bombT) : U.fmtTime(M.roundT)),
      scoreText: (M) => '<span class="t">T ' + M.sc.T + '</span><i>R' + M.round + '</i><span class="ct">' + M.sc.CT + ' CT</span>',
      objText(M) {
        const pl = M.player;
        if (pl.team === 'T') return M.planted ? 'Bombani himoya qiling!' : pl.carry ? '💣 Bomba sizda — A yoki B hududiga boring' : M.drop ? 'Tushgan bombani oling' : 'Tashuvchini qo‘llab-quvvatlang';
        return M.planted ? 'Bomba qo‘yildi — zararsizlantiring (USE)!' : 'A va B hududlarini himoya qiling';
      },
      useText(M) {
        const pl = M.player; if (!pl.alive || M.phase !== 'live') return '';
        if (pl.carry && !M.planted && M.map.siteAt(pl.x, pl.z)) return '💣 PLANT';
        if (M.planted && pl.team === 'CT' && Math.hypot(pl.x - M.bomb.x, pl.z - M.bomb.z) < 1.6) return '🔧 DEFUSE';
        return '';
      },
      bar(M) { if (M.plantP > 0) return [M.plantP, 'Bomba qo‘yilmoqda…']; if (M.defuseP > 0) return [M.defuseP, 'Zararsizlantirilmoqda…']; return null; },
    },
    // ── Survival ──
    survival: {
      init(M) { M.wave = 0; M.queue = 0; M.phase = 'inter'; M.phaseT = 2.5; spawnTeam(M, M.player, 'CT'); UI.msg('SURVIVAL<br><small>To‘lqinlarga dosh bering</small>', 2.5); },
      startWave(M) {
        M.wave++; M.phase = 'wave'; M.queue = 2 + M.wave * 2;
        UI.msg('TO‘LQIN ' + M.wave, 2, 'warn'); A.roundStart();
      },
      spawnOne(M) {
        let b = M.bots.find((x) => !x.alive && x.deathT > 4.5);
        const D = CS3D.EnemyAI.DIFF[M.cfg.diff];
        if (!b) b = M.addBot('T');
        b.hpMax = Math.round(D.hp * (1 + 0.08 * (M.wave - 1))); b.dmgMul = 1 + 0.05 * (M.wave - 1);
        b.D = Object.assign({}, D, { err: D.err * Math.max(0.55, 1 - 0.05 * (M.wave - 1)), react: D.react * Math.max(0.6, 1 - 0.04 * (M.wave - 1)), view: D.view + M.wave });
        spawnFar(M, b); b.state = 'investigate'; b.setPath(M.player.x, M.player.z);
        M.queue--;
      },
      onKill(M, from, victim) { if (victim === M.player) M.end(M.wave >= 5, M.wave + '-to‘lqinda halok bo‘ldingiz', { wave: M.wave }); },
      respawn() {},
      update(M, dt) {
        if (M.phase === 'inter') { M.phaseT -= dt; if (M.phaseT <= 0) this.startWave(M); return; }
        const live = M.bots.filter((b) => b.alive).length;
        if (M.queue > 0 && live < Math.min(M.botCap(), 4 + M.wave)) this.spawnOne(M);
        if (M.queue <= 0 && live === 0) {
          M.phase = 'inter'; M.phaseT = 6; const pl = M.player; pl.hp = Math.min(100, pl.hp + 35); pl.refill();
          UI.msg('✅ To‘lqin ' + M.wave + ' tugadi<br><small>+35 HP · o‘q to‘ldirildi</small>', 3, 'good'); A.roundEnd(true);
        }
      },
      timerText: (M) => U.fmtTime(M.time).replace(/^/, '⏱ '),
      scoreText: (M) => '<span class="ct">To‘lqin ' + M.wave + '</span><i>☠</i><span class="t">' + M.player.kills + '</span>',
      objText: (M) => (M.phase === 'inter' ? 'Keyingi to‘lqin: ' + Math.ceil(M.phaseT) + ' s' : 'Qolgan: ' + (M.queue + M.bots.filter((b) => b.alive).length)),
    },
  };

  // ══ Game (launch) ══
  function Game(opts) {
    this.opts = opts || {};
    CS3D.Save.load();
    const root = (this.root = document.createElement('div')); root.className = 'cs3d';
    document.body.appendChild(root);
    this.prevOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
    const H = (this.H = {
      play: () => this.start(), exit: () => this.exit(), menu: () => this.toMenu(), restart: () => this.start(),
      resume: () => this.resume(), online: () => this.online(), settings: (q) => { if (q && this.engine) { const s = CS3D.Save.data.settings.quality; this.engine.auto = s === 'auto'; this.engine.quality = s === 'auto' ? 'medium' : s; this.engine.prScale = 1; this.engine.applyQuality(); } },
    });
    UI.mount(root, H);
    if (!window.THREE || !hasWebGL()) { UI.error('Bu qurilma yoki brauzer WebGL’ni qo‘llab-quvvatlamaydi. Chrome’ning yangi versiyasida oching.'); root.querySelector('button').onclick = () => this.exit(); return; }
    try { this.engine = new Engine(UI.view); } catch (e) { UI.error('3D grafika ishga tushmadi: ' + e.message); root.querySelector('button').onclick = () => this.exit(); return; }
    this.input = new Input(root, UI.ctl, this.engine.renderer.domElement);
    const tg = window.Telegram && window.Telegram.WebApp;
    try { tg && tg.disableVerticalSwipes && tg.disableVerticalSwipes(); } catch (e) { /* */ }
    this.onVis = () => { if (document.hidden && this.match && !this.match.over && !this.match.paused) this.pause(); };
    document.addEventListener('visibilitychange', this.onVis);
    this.last = performance.now(); this.fpsT = 0; this.fpsN = 0; this.lowT = 0; this.alive = true;
    this.loop = (t) => this.frame(t); this.raf = requestAnimationFrame(this.loop);
    UI.showMenu('main');
  }
  const GP = Game.prototype;
  GP.start = function () {
    A.init(); A.resume();
    if (this.match) { this.match.dispose(); this.match = null; }
    const L = CS3D.Save.data.last;
    if (!CS3D.Save.mapOpen(L.map)) L.map = 'desert';
    try { this.match = new Match(this, { mode: L.mode, map: L.map, diff: L.diff, side: L.side }); }
    catch (e) { console.error(e); UI.toast('⚠️ O‘yin ishga tushmadi: ' + e.message); UI.showMenu('main'); return; }
    UI.pause(false); this.input.release();
  };
  GP.online = function () {
    if (!window.MPNET) { UI.toast('⚠️ Online yuklanmadi'); return; }
    const MAPN = CS3D.MapSystem.MAPS;
    window.MPNET.lobby({ game: 'cstrike', title: 'CLASSIC STRIKE', icon: '🎯', min: 2, modes: Object.keys(MAPN).map((k) => [k, '🗺 ' + MAPN[k].name]),
      maxNote: 'Deathmatch, 8 kishigacha. Ketayotgan o‘yinga ham qo‘shilish mumkin.', onStart: (s) => this.startNet(s), onClose: () => UI.showMenu('main') });
  };
  GP.startNet = function (s) {
    if (this.sess !== s) {
      this.sess = s;
      s.on('sync', (r) => { if (this.sess === s && this.match && this.match.net) CS3D.netHandlers.sync(this.match, r); });
      s.on('event', (e) => {
        if (this.sess !== s) return;
        if (e.d.k === 'start') return this.startNet(s);
        if (e.d.k === 'kicked') return this.leaveNet();
        if (this.match && this.match.net) CS3D.netHandlers.event(this.match, e);
      });
      this.H.restart = () => { if (!this.sess) return this.start(); if (this.sess.isHost()) this.sess.start(); else UI.toast('⏳ Xona egasi qayta boshlaydi'); };
      this.H.menu = () => { this.leaveNet(); this.toMenu(); };
    }
    A.init(); A.resume();
    if (this.match) { this.match.dispose(); this.match = null; }
    const MAPN = CS3D.MapSystem.MAPS, map = MAPN[s.room.mode] ? s.room.mode : 'desert';
    try { this.match = new Match(this, { mode: 'online', map, diff: 'normal', net: { me: s.me, emit: (e) => s.emit(e), send: (st) => s.send(st) } }); }
    catch (e) { console.error(e); UI.toast('⚠️ O‘yin ishga tushmadi: ' + e.message); UI.showMenu('main'); return; }
    UI.pause(false); this.input.release();
  };
  GP.leaveNet = function () {
    if (!this.sess) return; this.sess.leave(); this.sess = null;
    this.H.restart = () => this.start(); this.H.menu = () => this.toMenu();
  };
  GP.pause = function () { if (!this.match || this.match.over) return; if (this.match.net) { UI.toast('🌐 Online o‘yinda pauza yo‘q'); return; } this.match.paused = true; this.input.release(); UI.pause(true, this.H); A.music(false); };
  GP.resume = function () { if (!this.match) return; this.match.paused = false; UI.pause(false); this.last = performance.now(); A.music(true); };
  GP.toMenu = function () { if (this.match) { this.match.dispose(); this.match = null; } A.music(false); UI.pause(false); UI.showMenu('main'); };
  GP.result = function (res) { try { this.opts.onResult && this.opts.onResult(res); } catch (e) { /* */ } };
  GP.frame = function (t) {
    if (!this.alive) return;
    this.raf = requestAnimationFrame(this.loop);
    const dt = Math.min(0.05, Math.max(0, (t - this.last) / 1000)); this.last = t;
    const M = this.match;
    if (!M || document.hidden) return;
    if (this.input.s.pause) { this.input.s.pause = false; if (!M.over) { M.paused ? this.resume() : this.pause(); } }
    if (M.paused) return;
    if (!M.over) { M.update(dt); M.hud(); }
    else M.updateCamera(dt);
    this.engine.render(M.scene, !M.over && M.player.alive);
    // FPS va avtomatik sifat
    this.fpsT += dt; this.fpsN++;
    if (this.fpsT >= 1) {
      const fps = Math.round(this.fpsN / this.fpsT); this.fpsT = 0; this.fpsN = 0; UI.fps(fps);
      const E = this.engine;
      if (E.auto) {
        if (fps < 27) this.lowT++; else this.lowT = 0;
        if (this.lowT >= 2 && E.prScale > 0.55) { E.prScale = Math.max(0.55, E.prScale - 0.15); E.applyQuality(); E.resize(); this.lowT = 0; }
        else if (fps > 57 && E.prScale < 1) { E.prScale = Math.min(1, E.prScale + 0.05); E.applyQuality(); E.resize(); }
      }
    }
  };
  GP.exit = function () {
    if (!this.alive && this.engine === undefined) { /* */ }
    this.leaveNet(); this.alive = false; cancelAnimationFrame(this.raf);
    if (this.match) { this.match.dispose(); this.match = null; }
    if (this.input) this.input.dispose();
    if (this.engine) this.engine.dispose();
    CS3D.EnemyAI.disposeShared(); A.dispose();
    document.removeEventListener('visibilitychange', this.onVis);
    const tg = window.Telegram && window.Telegram.WebApp;
    try { tg && tg.enableVerticalSwipes && tg.enableVerticalSwipes(); } catch (e) { /* */ }
    document.body.style.overflow = this.prevOverflow || '';
    this.root.remove(); CS3D.current = null;
    try { this.opts.onExit && this.opts.onExit(); } catch (e) { /* */ }
  };

  CS3D.launch = function (opts) {
    if (CS3D.current) CS3D.current.exit();
    CS3D.current = new Game(opts);
    return CS3D.current;
  };
  CS3D._internal = { Match, RoundManager, Player, Engine, Input };
})();
