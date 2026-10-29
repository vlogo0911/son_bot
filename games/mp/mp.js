/* MPNET — VIP o'yinlar uchun umumiy multiplayer: lobbi UI + ~10 Hz sinxron sessiya (/app/api/mp/*). */
(function () {
  'use strict';
  if (window.MPNET) return;
  var api = function (p, b) { return window.api('/app/api/mp/' + p, b); };
  var ERR = { vip: '👑 Faqat VIP', not_found: '🔎 Xona topilmadi', room_full: '🚪 Xona to‘la', started: '▶ O‘yin boshlangan',
    full: '⚠️ Server band', host_only: '👑 Faqat xona egasi', not_in_room: '⚠️ Xonadan chiqib ketdingiz' };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function el(h) { var d = document.createElement('div'); d.innerHTML = h; return d.firstChild; }
  function toast(t) { if (window.toast) window.toast(t); }

  // ---- sessiya ----
  function Session(room, game) {
    var S = this, timer = 0, busy = false, alive = true, outbox = [], state = null, after = room.eseq || 0;
    S.game = game; S.code = room.code; S.me = room.me; S.room = room; S.players = room.players;
    S.handlers = { sync: [], event: [] };
    S.isHost = function () { return S.room.host === S.me; };
    S.send = function (st) { state = st; };
    S.emit = function (ev) { outbox.push(ev); };
    S.on = function (k, fn) { S.handlers[k].push(fn); return S; };
    S.name = function (uid) { for (var i = 0; i < S.players.length; i++) if (S.players[i].uid === uid) return S.players[i].name; return '?'; };
    S.others = function () { return S.players.filter(function (p) { return p.uid !== S.me; }); };
    S.rate = 110;
    function tick() {
      if (!alive) return;
      if (busy) { timer = setTimeout(tick, 40); return; }
      busy = true;
      var ev = outbox.splice(0, 12), body = { code: S.code, after: after, ev: ev };
      if (state) body.state = state;
      api('sync', body).then(function (r) {
        busy = false;
        if (!alive) return;
        if (r.error) { if (r.error === 'not_in_room') { alive = false; S.handlers.event.forEach(function (f) { f({ s: 0, u: 0, d: { k: 'kicked' } }); }); } return; }
        S.room = r.room; S.players = r.room.players;
        r.room.events.forEach(function (e) { after = Math.max(after, e.s); S.handlers.event.forEach(function (f) { f(e); }); });
        S.handlers.sync.forEach(function (f) { f(r.room); });
      }).catch(function () { busy = false; outbox = ev.concat(outbox); }).finally(function () { if (alive) timer = setTimeout(tick, S.rate); });
    }
    S.start = function () { return api('start', { code: S.code }); };
    S.end = function () { return api('end', { code: S.code }); };
    S.leave = function () { alive = false; clearTimeout(timer); return api('leave', { code: S.code }).catch(function () {}); };
    S.alive = function () { return alive; };
    tick();
  }

  // ---- lobbi ----
  // opts: {game, title, icon, maxNote, modes:[[key,label]], onStart(session) , onClose()}
  function lobby(opts) {
    var root = el('<div class="mpl"><div class="mpl-box"><div class="mpl-h"><b>' + (opts.icon || '🌐') + ' ' + esc(opts.title) +
      ' · ONLINE</b><span class="mpl-x">✕</span></div><div class="mpl-body"></div></div></div>');
    document.body.appendChild(root);
    var body = root.querySelector('.mpl-body'), sess = null, listT = 0, closed = false;
    function close(keep) {
      if (closed) return; closed = true; clearInterval(listT);
      if (sess && !keep) sess.leave();
      root.remove(); if (!keep && opts.onClose) opts.onClose();
    }
    root.querySelector('.mpl-x').onclick = function () { close(false); };
    function err(r) { toast(ERR[r.error] || '⚠️ Xatolik'); }
    function mode() { var s = body.querySelector('.mpl-mode'); return s ? s.value : ''; }
    function home() {
      clearInterval(listT);
      body.innerHTML = (opts.modes ? '<select class="mpl-mode">' + opts.modes.map(function (m) { return '<option value="' + m[0] + '">' + esc(m[1]) + '</option>'; }).join('') + '</select>' : '') +
        '<button class="mpl-b go" data-a="quick">⚡ Tez o‘yin</button>' +
        '<div class="mpl-row"><button class="mpl-b" data-a="create">➕ Xona yaratish</button><button class="mpl-b" data-a="priv">🔒 Yopiq xona</button></div>' +
        '<div class="mpl-row"><input class="mpl-in" maxlength="5" placeholder="KOD"><button class="mpl-b" data-a="join">🔑 Kirish</button></div>' +
        '<div class="mpl-lbl">Ochiq xonalar</div><div class="mpl-list">⏳</div>' + (opts.maxNote ? '<div class="mpl-note">' + esc(opts.maxNote) + '</div>' : '');
      body.querySelectorAll('[data-a]').forEach(function (b) {
        b.onclick = function () {
          var a = b.dataset.a, p;
          if (a === 'join') { var c = body.querySelector('.mpl-in').value.trim().toUpperCase(); if (c.length < 4) return toast('🔑 Kodni kiriting'); p = api('join', { code: c }); }
          else p = api(a === 'priv' ? 'create' : a, { game: opts.game, mode: mode(), private: a === 'priv' });
          b.disabled = true;
          p.then(function (r) { b.disabled = false; if (r.error) return err(r); enter(r.room); }).catch(function () { b.disabled = false; toast('⚠️ Tarmoq xatosi'); });
        };
      });
      var load = function () {
        api('list', { game: opts.game }).then(function (r) {
          var L = body.querySelector('.mpl-list'); if (!L) return;
          L.innerHTML = (r.rooms || []).length ? r.rooms.map(function (x) {
            return '<div class="mpl-room" data-c="' + x.code + '"><span>👑 ' + esc(x.host) + (x.mode ? ' · ' + esc(x.mode) : '') + '</span><b>' + x.n + '/' + x.max + (x.started ? ' ▶' : '') + '</b></div>';
          }).join('') : '<div class="mpl-note">Hozircha ochiq xona yo‘q — yarating!</div>';
          L.querySelectorAll('.mpl-room').forEach(function (d) { d.onclick = function () { api('join', { code: d.dataset.c }).then(function (r) { if (r.error) return err(r); enter(r.room); }); }; });
        }).catch(function () {});
      };
      load(); listT = setInterval(load, 3000);
    }
    function enter(room) {
      clearInterval(listT);
      sess = new Session(room, opts.game); sess.rate = 600;
      var started = false;
      var draw = function () {
        if (started) return;
        var r = sess.room, host = sess.isHost();
        body.innerHTML = '<div class="mpl-code">Xona kodi: <b>' + r.code + '</b> <span class="mpl-copy">📋</span></div>' +
          (r.mode ? '<div class="mpl-note">Rejim: ' + esc(r.mode) + '</div>' : '') +
          '<div class="mpl-lbl">O‘yinchilar ' + r.players.length + '/' + r.max + '</div>' +
          '<div class="mpl-list">' + r.players.map(function (p) { return '<div class="mpl-room"><span>' + (p.uid === r.host ? '👑 ' : '🎮 ') + esc(p.name) + (p.uid === r.me ? ' (siz)' : '') + '</span></div>'; }).join('') + '</div>' +
          (host ? '<button class="mpl-b go" data-a="start"' + (r.players.length < (opts.min || 2) ? ' disabled' : '') + '>▶ Boshlash</button>' : '<div class="mpl-note">⏳ Xona egasi boshlashini kuting…</div>') +
          '<button class="mpl-b" data-a="out">🚪 Chiqish</button>';
        var cp = body.querySelector('.mpl-copy'); if (cp) cp.onclick = function () { try { navigator.clipboard.writeText(r.code); toast('📋 Nusxa olindi'); } catch (e) {} };
        var st = body.querySelector('[data-a=start]'); if (st) st.onclick = function () { st.disabled = true; sess.start().then(function (x) { if (x.error) { st.disabled = false; err(x); } }); };
        body.querySelector('[data-a=out]').onclick = function () { sess.leave(); sess = null; home(); };
      };
      var go = function (seed) { if (started) return; started = true; sess.seed = seed; sess.rate = 110; close(true); opts.onStart(sess); };
      sess.on('sync', function (r) { if (r.started && !started) go(r.seed); else draw(); });
      sess.on('event', function (e) { if (e.d.k === 'start') go(e.d.seed); });
      if (room.started) go(room.seed); else draw();
    }
    home();
    return { close: close };
  }

  window.MPNET = { lobby: lobby, Session: Session, esc: esc };
})();
