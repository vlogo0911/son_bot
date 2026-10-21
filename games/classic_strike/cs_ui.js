/* CLASSIC STRIKE — UIManager: menyular, HUD, pauza, natijalar, mobil boshqaruv elementlari (DOM). */
(function () {
  'use strict';
  const CS3D = window.CS3D, U = CS3D.U;
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const MODES = {
    tdm: { name: 'Team Deathmatch', d: 'Siz + 3 ittifoqchi botga qarshi 4 bot. 30 fragga birinchi yetgan jamoa yutadi (6 daqiqa).' },
    dm: { name: 'Deathmatch', d: 'Siz botlarga qarshi. 20 fragga yeting — yoki vaqt tugaganda eng ko‘p frag sizda bo‘lsin (5 daqiqa).' },
    bomb: { name: 'Bomb Mission', d: 'Raundlar (4 g‘alabagacha). Hujum: bombani A yoki B ga qo‘ying. Himoya: bomba qo‘yilishiga yo‘l qo‘ymang yoki zararsizlantiring.' },
    survival: { name: 'Survival', d: 'Botlar to‘lqin bo‘lib hujum qiladi, har to‘lqin qiyinroq. Qancha yashadingiz va nechta raqibni yengdingiz — qayd qilinadi.' },
  };
  const DIFFS = { easy: ['Easy', 'Sekin reaksiya, past aniqlik'], normal: ['Normal', 'Muvozanatli botlar'], hard: ['Hard', 'Tez reaksiya, pana va strafe taktikasi'] };

  const UI = (CS3D.UI = {
    MODES, DIFFS, root: null, h: null,
    mount(root, H) {
      this.root = root; this.H = H;
      root.innerHTML = '';
      this.view = el('div', 'cs-view'); root.appendChild(this.view);
      // HUD
      const hud = (this.hud = el('div', 'cs-hud'));
      hud.innerHTML =
        '<div class="cs-top"><div class="cs-score" id="csScore"></div><div class="cs-timer" id="csTimer">0:00</div><div class="cs-obj" id="csObj"></div></div>' +
        '<div class="cs-feed" id="csFeed"></div><div class="cs-fps" id="csFps"></div>' +
        '<div class="cs-cross" id="csCross"><i></i><i></i><i></i><i></i></div><div class="cs-hitm" id="csHit"></div>' +
        '<div class="cs-scope" id="csScope"></div><div class="cs-dmg" id="csDmg"></div><div class="cs-dir" id="csDir"></div>' +
        '<div class="cs-hp"><b id="csHpN">100</b><span>HP</span><div class="cs-hpbar"><i id="csHpB"></i></div></div>' +
        '<div class="cs-ammo"><div class="cs-wn" id="csWn"></div><b id="csAm">30</b><span id="csRes">/ 90</span></div>' +
        '<div class="cs-msg" id="csMsg"></div><div class="cs-bar" id="csBar"><div class="cs-barl" id="csBarL"></div><div class="cs-bari"><i id="csBarI"></i></div></div>';
      root.appendChild(hud);
      // Boshqaruv
      const ctl = (this.ctl = el('div', 'cs-ctl'));
      ctl.innerHTML =
        '<div class="cs-look" data-z="look"></div><div class="cs-joyz" data-z="joy"><div class="cs-joy"><i></i></div></div>' +
        '<button class="cs-b cs-fire" data-a="fire">🎯</button><button class="cs-b cs-fire2" data-a="fire">🎯</button>' +
        '<button class="cs-b cs-aim" data-a="aim">⊕</button><button class="cs-b cs-rl" data-a="reload">R</button>' +
        '<button class="cs-b cs-sw" data-a="switch">⇄</button><button class="cs-b cs-jmp" data-a="jump">⤒</button>' +
        '<button class="cs-b cs-run" data-a="run">»</button><button class="cs-b cs-use" data-a="use">USE</button>' +
        '<button class="cs-b cs-pz" data-a="pause">❚❚</button>';
      root.appendChild(ctl);
      this.menu = el('div', 'cs-menu'); root.appendChild(this.menu);
      this.over = el('div', 'cs-over'); root.appendChild(this.over);
      this.rot = el('div', 'cs-rot', '<div>📱↻</div><b>Telefonni yotqizing</b><span>Landscape rejimi tavsiya etiladi — lekin vertikal ham o‘ynash mumkin</span><button class="cs-btn">Davom etish</button>');
      root.appendChild(this.rot);
      this.rot.querySelector('button').onclick = () => { this.rot.classList.remove('on'); this.rotDismissed = true; };
      const $ = (id) => root.querySelector('#' + id);
      this.e = { score: $('csScore'), timer: $('csTimer'), obj: $('csObj'), feed: $('csFeed'), fps: $('csFps'), cross: $('csCross'), hit: $('csHit'),
        scope: $('csScope'), dmg: $('csDmg'), dir: $('csDir'), hpN: $('csHpN'), hpB: $('csHpB'), wn: $('csWn'), am: $('csAm'), res: $('csRes'),
        msg: $('csMsg'), bar: $('csBar'), barL: $('csBarL'), barI: $('csBarI'), use: ctl.querySelector('.cs-use'), run: ctl.querySelector('.cs-run'), aim: ctl.querySelector('.cs-aim') };
      this.cache = {};
      this.applySettings();
    },
    applySettings() {
      const s = CS3D.Save.data.settings;
      this.root.style.setProperty('--csb', String(U.clamp(s.btn, 0.7, 1.5)));
      this.e.fps.style.display = s.fps ? '' : 'none';
    },
    playing(on) { this.root.classList.toggle('playing', on); this.menu.classList.toggle('on', !on); },
    set(key, v, fn) { if (this.cache[key] === v) return; this.cache[key] = v; fn(v); },
    hudUpdate(o) {
      const e = this.e;
      this.set('hp', o.hp, (v) => { e.hpN.textContent = Math.max(0, Math.ceil(v)); e.hpB.style.width = U.clamp(v, 0, 100) + '%'; e.hpN.parentNode.classList.toggle('low', v < 30); });
      this.set('wn', o.wn, (v) => (e.wn.textContent = v));
      this.set('am', o.am, (v) => { e.am.textContent = v; e.am.classList.toggle('low', o.lowAmmo); });
      this.set('res', o.res, (v) => (e.res.textContent = v));
      this.set('timer', o.timer, (v) => (e.timer.textContent = v));
      this.set('score', o.score, (v) => (e.score.innerHTML = v));
      this.set('obj', o.obj, (v) => (e.obj.textContent = v));
      this.set('use', o.use, (v) => { e.use.classList.toggle('on', !!v); if (v) e.use.textContent = v; });
      this.set('run', o.run, (v) => e.run.classList.toggle('act', !!v));
      this.set('aimb', o.aim, (v) => e.aim.classList.toggle('act', !!v));
      this.set('scope', o.scope, (v) => { e.scope.classList.toggle('on', !!v); e.cross.style.display = v ? 'none' : ''; });
      const gap = Math.round(4 + o.spread * 420);
      this.set('gap', gap, (v) => e.cross.style.setProperty('--g', Math.min(v, 46) + 'px'));
      this.set('bar', o.bar ? Math.round(o.bar[0] * 100) + o.bar[1] : '', () => {
        e.bar.classList.toggle('on', !!o.bar); if (o.bar) { e.barI.style.width = Math.round(o.bar[0] * 100) + '%'; e.barL.textContent = o.bar[1]; }
      });
    },
    fps(v) { this.e.fps.textContent = v + ' FPS'; },
    msg(text, dur, cls) {
      const m = this.e.msg; m.innerHTML = text; m.className = 'cs-msg on ' + (cls || '');
      clearTimeout(this.msgT); if (dur) this.msgT = setTimeout(() => { m.className = 'cs-msg'; }, dur * 1000);
    },
    feed(a, w, b, mine, head) {
      const r = el('div', 'cs-kf' + (mine ? ' me' : ''), esc(a) + ' <i>' + esc(w) + (head ? ' ◉' : '') + '</i> ' + esc(b));
      this.e.feed.prepend(r); while (this.e.feed.children.length > 5) this.e.feed.lastChild.remove();
      setTimeout(() => r.remove(), 5000);
    },
    hitmark(head, kill) { const h = this.e.hit; h.className = 'cs-hitm on' + (head ? ' head' : '') + (kill ? ' kill' : ''); clearTimeout(this.hitT); this.hitT = setTimeout(() => (h.className = 'cs-hitm'), 140); },
    damage(rel) {
      const d = this.e.dmg; d.classList.remove('on'); void d.offsetWidth; d.classList.add('on');
      if (rel !== null && rel !== undefined) { const r = this.e.dir; r.style.transform = 'translate(-50%,-50%) rotate(' + rel + 'rad)'; r.classList.remove('on'); void r.offsetWidth; r.classList.add('on'); }
    },
    rotateHint() {
      const portrait = window.innerHeight > window.innerWidth * 1.1 && ('ontouchstart' in window);
      this.rot.classList.toggle('on', portrait && !this.rotDismissed);
    },
    // ── Menyular ──
    btn(label, cls) { return '<button class="cs-btn ' + (cls || '') + '">' + label + '</button>'; },
    showMenu(screen) {
      const H = this.H, S = CS3D.Save.data, L = S.last, m = this.menu, WS = CS3D.WeaponSystem.WEAPONS, MS = CS3D.MapSystem.MAPS;
      this.playing(false); m.classList.add('on'); this.over.className = 'cs-over';
      const back = '<button class="cs-back" data-go="main">‹ Orqaga</button>';
      let h = '';
      if (screen === 'main' || !screen) {
        const st = S.stats;
        h = '<div class="cs-logo"><b>CLASSIC</b><span>STRIKE</span><i>tactical mobile shooter</i></div>' +
          '<div class="cs-sel">' + esc(MODES[L.mode].name) + ' · ' + esc(MS[L.map].name) + ' · ' + esc(DIFFS[L.diff][0]) + ' · ' + esc(WS[L.primary].name) + '</div>' +
          '<div class="cs-mm">' + this.btn('▶ PLAY', 'play" data-go="play') + this.btn('GAME MODE', '" data-go="mode') + this.btn('MAP SELECT', '" data-go="map') +
          this.btn('DIFFICULTY', '" data-go="diff') + this.btn('WEAPONS', '" data-go="weap') + this.btn('SETTINGS', '" data-go="set') +
          this.btn('HOW TO PLAY', '" data-go="how') + this.btn('✕ CHIQISH', 'ghost" data-go="exit') + '</div>' +
          '<div class="cs-stats"><span>O‘yinlar <b>' + st.games + '</b></span><span>G‘alaba <b>' + st.wins + '</b></span><span>Mag‘lubiyat <b>' + st.losses + '</b></span>' +
          '<span>Fraglar <b>' + st.kills + '</b></span><span>Rekord <b>' + st.best + '</b></span>' + (st.survWave ? '<span>Survival <b>' + st.survWave + '-to‘lqin</b></span>' : '') + '</div>';
      } else if (screen === 'mode') {
        h = back + '<h2>GAME MODE</h2><div class="cs-cards">' + Object.keys(MODES).map((k) => '<div class="cs-card' + (L.mode === k ? ' on' : '') + '" data-mode="' + k + '"><b>' + MODES[k].name + '</b><span>' + MODES[k].d + '</span></div>').join('') + '</div>' +
          '<div class="cs-side' + (L.mode === 'bomb' ? '' : ' off') + '"><span>Bomb Mission tomoni:</span><button class="cs-chip' + (L.side === 'attack' ? ' on' : '') + '" data-side="attack">💣 Hujum (T)</button><button class="cs-chip' + (L.side === 'defend' ? ' on' : '') + '" data-side="defend">🛡 Himoya (CT)</button></div>';
      } else if (screen === 'map') {
        h = back + '<h2>MAP SELECT</h2><div class="cs-cards">' + Object.keys(MS).map((k) => {
          const open = CS3D.Save.mapOpen(k), need = CS3D.Save.MAP_UNLOCK[k];
          return '<div class="cs-card map m-' + k + (L.map === k ? ' on' : '') + (open ? '' : ' lock') + '" data-map="' + k + '"><b>' + MS[k].name + '</b><span>' + MS[k].sub + '</span>' + (open ? '' : '<em>🔒 ' + need + ' ta o‘yindan keyin ochiladi</em>') + '</div>';
        }).join('') + '</div>';
      } else if (screen === 'diff') {
        h = back + '<h2>DIFFICULTY</h2><div class="cs-cards">' + Object.keys(DIFFS).map((k) => '<div class="cs-card' + (L.diff === k ? ' on' : '') + '" data-diff="' + k + '"><b>' + DIFFS[k][0] + '</b><span>' + DIFFS[k][1] + '</span></div>').join('') + '</div>';
      } else if (screen === 'weap') {
        const bar = (v, max) => '<i style="width:' + Math.round(U.clamp(v / max, 0.05, 1) * 100) + '%"></i>';
        h = back + '<h2>WEAPONS</h2><p class="cs-note">Asosiy qurolni tanlang. Har o‘yinda P-9 Pistol va Knife ham bo‘ladi (Hawk .50 ochilsa — pistol o‘rniga).</p><div class="cs-cards">' +
          ['rifle', 'smg', 'shotgun', 'sniper', 'deagle'].map((k) => {
            const w = WS[k], open = CS3D.Save.weaponOpen(k), dps = w.dmg * (w.pellets || 1) / w.rate;
            return '<div class="cs-card wp' + (L.primary === k ? ' on' : '') + (open ? '' : ' lock') + '" data-wp="' + k + '"><b>' + w.name + '</b>' +
              '<div class="cs-st"><span>Zarar</span><div>' + bar(w.dmg * (w.pellets || 1), 128) + '</div><span>Tezlik</span><div>' + bar(1 / w.rate, 14) + '</div>' +
              '<span>Aniqlik</span><div>' + bar(0.09 - (w.adsSpread || w.spread), 0.09) + '</div><span>DPS</span><div>' + bar(dps, 330) + '</div></div>' +
              '<span>Magazin ' + w.mag + ' · zaxira ' + w.res + '</span>' + (open ? '' : '<em>🔒 ' + CS3D.Save.WEAPON_UNLOCK[k] + ' frag kerak</em>') + '</div>';
          }).join('') + '</div>';
      } else if (screen === 'set') {
        const st = S.settings, sl = (k, min, max, stp, lbl) => '<label class="cs-sl"><span>' + lbl + ' <b data-v="' + k + '">' + st[k] + '</b></span><input type="range" min="' + min + '" max="' + max + '" step="' + stp + '" value="' + st[k] + '" data-set="' + k + '"></label>';
        h = back + '<h2>SETTINGS</h2><div class="cs-form">' + sl('music', 0, 1, 0.05, '🎵 Musiqa') + sl('sfx', 0, 1, 0.05, '🔊 Ovozlar') + sl('sens', 0.3, 2.5, 0.05, '🎯 Kamera sezgirligi') + sl('btn', 0.7, 1.5, 0.05, '🔘 Tugmalar o‘lchami') +
          '<div class="cs-row"><span>🖥 Grafika</span>' + ['auto', 'low', 'medium', 'high'].map((q) => '<button class="cs-chip' + (st.quality === q ? ' on' : '') + '" data-q="' + q + '">' + q.toUpperCase() + '</button>').join('') + '</div>' +
          '<div class="cs-row"><span>📈 FPS ko‘rsatkichi</span><button class="cs-chip' + (st.fps ? ' on' : '') + '" data-fps="1">' + (st.fps ? 'YOQIQ' : 'O‘CHIQ') + '</button></div>' +
          '<p class="cs-note">Telefon: chapda joystick — yurish; o‘ng tomonni surish — qarash; 🎯 — otish (surib nishonga ham olasiz). Kompyuter: WASD, sichqoncha, LMB/RMB, R, Q/1-3, Space, Shift, E, Esc.</p></div>';
      } else if (screen === 'how') {
        h = back + '<h2>HOW TO PLAY</h2><div class="cs-how">' +
          '<p><b>📱 Telefon</b> (landscape tavsiya): chap pastda joystick — yurish. O‘ng yarmini barmoq bilan surish — kamera/nishon. <b>🎯</b> — otish (bosib turib surish ham mumkin). <b>⊕</b> — nishonga olish (snayperda optik). <b>R</b> — qayta o‘qlash, <b>⇄</b> — qurol, <b>⤒</b> — sakrash, <b>»</b> — yugurish, <b>USE</b> — bomba qo‘yish/zararsizlantirish, <b>❚❚</b> — pauza.</p>' +
          '<p><b>⌨ Kompyuter</b>: o‘yin ekranini bosing — sichqoncha ushlanadi. WASD — yurish, sichqoncha — qarash, LMB — otish, RMB — nishon, R — o‘qlash, Q/1/2/3 — qurol, Space — sakrash, Shift — yugurish, E — USE, Esc/P — pauza.</p>' +
          '<p><b>🎯 Jang</b>: boshga tegish 2.4× zarar. Yugurish va sakrash aniqlikni pasaytiradi, nishonga olish oshiradi. Qutilar ortida pana qiling — botlar devor orqali ko‘rmaydi, lekin otishma va yugurish ovozini eshitadi.</p>' +
          '<p><b>🏆 Progress</b>: fraglar Hawk .50 (10) va Longshot (30) ni ochadi; o‘yinlar Urban Strike (1) va Warehouse (2) xaritalarini ochadi.</p></div>';
      }
      m.innerHTML = '<div class="cs-mwrap">' + h + '</div>';
      m.querySelectorAll('[data-go]').forEach((b) => (b.onclick = () => { CS3D.Audio.init(); CS3D.Audio.resume(); const g = b.dataset.go; if (g === 'play') H.play(); else if (g === 'exit') H.exit(); else this.showMenu(g); }));
      const pick = (attr, key, scr, lockFn) => m.querySelectorAll('[data-' + attr + ']').forEach((c) => (c.onclick = () => {
        const v = c.dataset[attr]; if (lockFn && !lockFn(v)) { this.toast('🔒 Hali ochilmagan'); return; }
        L[key] = v; CS3D.Save.save(); this.showMenu(scr);
      }));
      pick('mode', 'mode', 'mode'); pick('side', 'side', 'mode'); pick('map', 'map', 'map', (v) => CS3D.Save.mapOpen(v)); pick('diff', 'diff', 'diff'); pick('wp', 'primary', 'weap', (v) => CS3D.Save.weaponOpen(v));
      m.querySelectorAll('[data-set]').forEach((r) => (r.oninput = () => {
        const k = r.dataset.set; S.settings[k] = parseFloat(r.value); m.querySelector('[data-v="' + k + '"]').textContent = r.value;
        CS3D.Save.save(); this.applySettings(); CS3D.Audio.setVol(S.settings.music, S.settings.sfx); H.settings && H.settings();
      }));
      m.querySelectorAll('[data-q]').forEach((b) => (b.onclick = () => { S.settings.quality = b.dataset.q; CS3D.Save.save(); H.settings && H.settings(true); this.showMenu('set'); }));
      const fb = m.querySelector('[data-fps]'); if (fb) fb.onclick = () => { S.settings.fps = !S.settings.fps; CS3D.Save.save(); this.applySettings(); this.showMenu('set'); };
    },
    toast(t) { const d = el('div', 'cs-toast', esc(t)); this.root.appendChild(d); setTimeout(() => d.remove(), 1600); },
    pause(on, H) {
      if (!on) { this.over.className = 'cs-over'; return; }
      const s = CS3D.Save.data.settings;
      this.over.className = 'cs-over on';
      this.over.innerHTML = '<div class="cs-pbox"><h2>PAUZA</h2>' + this.btn('▶ DAVOM ETISH', 'play" data-p="resume') + this.btn('↻ QAYTA BOSHLASH', '" data-p="restart') +
        '<label class="cs-sl"><span>🎯 Sezgirlik <b>' + s.sens + '</b></span><input type="range" min="0.3" max="2.5" step="0.05" value="' + s.sens + '" data-ps="sens"></label>' +
        '<label class="cs-sl"><span>🔊 Ovoz <b>' + s.sfx + '</b></span><input type="range" min="0" max="1" step="0.05" value="' + s.sfx + '" data-ps="sfx"></label>' +
        '<label class="cs-sl"><span>🎵 Musiqa <b>' + s.music + '</b></span><input type="range" min="0" max="1" step="0.05" value="' + s.music + '" data-ps="music"></label>' +
        this.btn('☰ MENYUGA', '" data-p="menu') + this.btn('✕ WEB APP’GA QAYTISH', 'ghost" data-p="exit') + '</div>';
      this.over.querySelectorAll('[data-p]').forEach((b) => (b.onclick = () => H[b.dataset.p]()));
      this.over.querySelectorAll('[data-ps]').forEach((r) => (r.oninput = () => {
        s[r.dataset.ps] = parseFloat(r.value); r.previousElementSibling.querySelector('b').textContent = r.value; CS3D.Save.save(); CS3D.Audio.setVol(s.music, s.sfx);
      }));
    },
    results(res, H) {
      this.over.className = 'cs-over on res ' + (res.win ? 'win' : 'lose');
      const acc = res.shots ? Math.round(res.hits / res.shots * 100) : 0;
      const rows = [['Fraglar', res.kills], ['O‘limlar', res.deaths], ['Boshga tegish', res.heads], ['Aniqlik', acc + '%'], ['Vaqt', U.fmtTime(res.time)]];
      if (res.mode === 'survival') rows.push(['To‘lqin', res.wave]);
      if (res.mode === 'bomb') rows.push(['Raundlar', (res.roundsW || 0) + ' : ' + (res.roundsL || 0)]);
      if (res.teamScore) rows.push(['Jamoa hisobi', res.teamScore]);
      this.over.innerHTML = '<div class="cs-pbox"><div class="cs-banner">' + (res.win ? 'VICTORY' : 'DEFEAT') + '</div><div class="cs-rsub">' + esc(res.reason || '') + '</div>' +
        '<div class="cs-rgrid">' + rows.map((r) => '<span>' + r[0] + '</span><b>' + r[1] + '</b>').join('') + '</div><div class="cs-rscore">SCORE <b>' + res.score + '</b>' + (res.best ? ' · 🏆 yangi rekord!' : '') + '</div>' +
        (res.unlocks && res.unlocks.length ? '<div class="cs-unl">🔓 Ochildi: ' + res.unlocks.map(esc).join(', ') + '</div>' : '') +
        this.btn('↻ YANA O‘YNASH', 'play" data-p="restart') + this.btn('☰ MENYU', '" data-p="menu') + this.btn('✕ WEB APP’GA QAYTISH', 'ghost" data-p="exit') + '</div>';
      this.over.querySelectorAll('[data-p]').forEach((b) => (b.onclick = () => H[b.dataset.p]()));
    },
    error(text) { this.root.innerHTML = '<div class="cs-err"><b>CLASSIC STRIKE</b><p>' + esc(text) + '</p><button class="cs-btn">Orqaga</button></div>'; },
  });
  void UI;
})();
