/* Diadiction 오프라인 꾸러미 — 화면 하나(`index.html`)가 해시로 갈린다.
 *
 * **자료는 `<script src>` 로 온다.** `file://` 에서는 `fetch` 가 막혀
 * (브라우저가 로컬 파일을 다른 출처로 본다) JSON 을 못 읽는다 — 그래서
 * `data/*.js` 가 전역에 값을 놓는 모양이다. 웹서버 없이 열리는 것이 이
 * 꾸러미의 존재 이유라 여기서 물러설 수 없다.
 *
 * 규칙은 뷰어에서 그대로 가져왔다 — 검색 셋(표제어·이명법·속) · 이명의 현재
 * 학명으로도 찾기(P24) · 권역(한국·남극·전역, 196) · 속 고르는 목록 · 자동완성 ·
 * 한 판 50줄 · 격자 60칸 · 펼침의 좌우 판정 · 바둑판·비교와 "크롭이 먼저"(238 · v1.4.0).
 * **굽는 쪽(`tools/build_offline_atlas.py`)이
 * 이미지 경로를 미리 만들어 준다**: 이름 규칙은 `web/viewer/atlas.py` 하나뿐이고
 * 화면이 다시 만들지 않는다.
 */
(function () {
  'use strict';

  var META = window.DIA_META || {};
  var BOOKS = window.DIA_BOOKS || {};
  var ENTRIES = window.DIA_ENTRIES || [];
  var NAMES = window.DIA_NAMES || { cols: [], rows: [] };
  // 이명 판정(P24) · 출현 기록(P20) — 뷰어가 항목에 붙여 내는 둘 (v1.2.0)
  var TAXA = window.DIA_TAXA || {};
  var OCC = window.DIA_OCC || {};
  // 생층서 기준면(P28) — 카드 줄 · 속마다의 수 (v1.3.0)
  var BD = (window.DIA_BD || {}).card || {};
  var BD_GENUS = (window.DIA_BD || {}).genus || {};
  var SUGGEST_MAX = 20;  // 자동완성 (뷰어 `atlas_suggest` 와 같은 수)
  var PER = 50;        // 검색 한 판 (뷰어 `ATLAS_PER_PAGE`)
  var GRID = 60;       // 격자 한 판 (뷰어 `atlas.PER_PAGE`)
  var app, preview, previewImg, previewCap;

  /* ── 자잘한 것 ─────────────────────────────────────────────── */

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // 색인의 주석에 굵게·홑따옴표 표기가 섞여 있다 (`**…**` · `` `…` `` ).
  // **글자 그대로 내보내면 별표가 화면에 뜬다** — 원문은 md 로 적힌 것이다.
  function mdlite(s) {
    return esc(s).replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  }

  // 발음부호를 눕힌다 — 색인에 `Bréhissonii` 같은 표기가 섞여 있다.
  function fold(s) {
    return String(s || '').normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  function qs(obj) {
    var out = [];
    for (var k in obj) {
      if (obj[k] !== '' && obj[k] !== null && obj[k] !== undefined) {
        out.push(encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]));
      }
    }
    return out.length ? '?' + out.join('&') : '';
  }

  function parseHash() {
    var h = location.hash.replace(/^#/, '') || '/';
    var i = h.indexOf('?');
    var path = i < 0 ? h : h.slice(0, i);
    var p = {}, multi = {};
    if (i >= 0) {
      h.slice(i + 1).split('&').forEach(function (pair) {
        if (!pair) return;
        var j = pair.indexOf('=');
        var k = decodeURIComponent(j < 0 ? pair : pair.slice(0, j));
        p[k] = decodeURIComponent(j < 0 ? '' : pair.slice(j + 1).replace(/\+/g, ' '));
        (multi[k] = multi[k] || []).push(p[k]);
      });
    }
    // `multi` — 같은 이름이 거듭 오는 값(비교의 `e`). `q` 는 늘 마지막 값이다
    return { parts: path.split('/').filter(Boolean), q: p, multi: multi };
  }

  function go(path, params) { location.hash = '#' + path + qs(params || {}); }

  function num(v, d) { var n = parseInt(v, 10); return isNaN(n) ? d : n; }

  /* ── 자료 손질 (한 번만) ───────────────────────────────────── */

  ENTRIES.forEach(function (e) {
    e._f = fold((e.name || '') + ' ' + (e.binomial || '') + ' ' + (e.genus || ''));
    e._s = fold(e.binomial || e.name || '');
  });
  ENTRIES.sort(function (a, b) {
    return a._s < b._s ? -1 : a._s > b._s ? 1 : (a.name < b.name ? -1 : 1);
  });

  // **현재 통용 학명 → 옛 이름(이명)들** (뷰어 `_synonym_binomials`). 도감·논문은
  // 옛 표기를 그대로 쓰므로 지금 학명으로 찾으면 못 걸린다 — 검색어를 옛
  // 이름으로도 넓혀야 한다. 정확 일치(대소문자만 눕힌다)다.
  var SYN = {};
  Object.keys(TAXA).forEach(function (b) {
    var t = TAXA[b];
    if (t.status !== 'synonym' || !t.valid_name) return;
    var k = fold(t.valid_name);
    (SYN[k] = SYN[k] || []).push(b);
  });

  function atlasMeta(key) {
    var list = META.atlases || [];
    for (var i = 0; i < list.length; i++) if (list[i].key === key) return list[i];
    return { key: key, short: key, title: key, area: '' };
  }

  var AREAS = META.areas || [];
  function areaLabel(code) {
    for (var i = 0; i < AREAS.length; i++) if (AREAS[i].code === code) return AREAS[i].label;
    return '';
  }
  // 권역 안의 도감인가. **도감이 권역보다 좁다** — 도감을 골랐으면 권역은 안 본다.
  function inScope(e, akey, area) {
    if (akey) return e.atlas === akey;
    if (area) return atlasMeta(e.atlas).area === area;
    return true;
  }

  /* ── 바둑판·비교 (뷰어 238) ────────────────────────────────── */

  // 항목의 열쇠는 `<도감>:<표제어>` — 뷰어 `atlas_compare` 와 같다. 한국 도감에
  // 표제어가 한 번 겹치는데(항목번호가 둘) 그때는 앞엣것이다(뷰어도 `seq` 앞).
  function entryKey(e) { return e.atlas + ':' + e.name; }
  var BYKEY = {};
  ENTRIES.forEach(function (e) { var k = entryKey(e); if (!BYKEY[k]) BYKEY[k] = e; });
  var CMP_MAX = 5;  // 뷰어 `ATLAS_COMPARE_MAX`
  var VKEY = 'diaruga.atlas.view', TKEY = 'diaruga.atlas.compare';

  // 칸에 띄울 그림 하나 (뷰어 `data._row_figure`). **크롭이 먼저**, 없으면 도판
  // 쪽 하나. **주석이 달린 자리는 안 띄운다** — 실측 21건 전부가 `Tafel 아님 ·
  // 권 뒤 Verzeichnis` 이고 그 "도판 쪽" 은 글자뿐인 색인 쪽이다.
  function rowFigure(e) {
    var pl, i, places = e.places || [];
    for (i = 0; i < places.length; i++) {
      pl = places[i];
      if (pl.crop_rel) return { src: pl.crop_rel, href: plateHref(pl), crop: true,
        label: pl.figures ? 'fig. ' + pl.figures : '' };
    }
    for (i = 0; i < places.length; i++) {
      pl = places[i];
      if (pl.plate_rel && !pl.note) return { src: pl.plate_thumb || pl.plate_rel,
        full: pl.plate_rel, href: plateHref(pl), crop: false,
        label: '도판 p.' + pl.pdf_plate_page };
    }
    return null;
  }

  function plateHref(pl) {
    return (pl.plate_rel && META.images)
      ? '#/page/' + pl.vol_path + '/' + pl.pdf_plate_page : '';
  }

  function loadPicked() {
    var v = [];
    try { v = JSON.parse(localStorage.getItem(TKEY) || '[]'); } catch (err) { v = []; }
    return Array.isArray(v) ? v.filter(function (x) { return x && x.k; }).slice(0, CMP_MAX) : [];
  }
  function storePicked(v) {
    try { localStorage.setItem(TKEY, JSON.stringify(v)); } catch (err) { /* 사생활 모드 */ }
  }
  function compareHash(picked) {
    return '#/compare?' + picked.map(function (x) {
      return 'e=' + encodeURIComponent(x.k);
    }).join('&');
  }

  // 그림이 안 열리면 칸이 그렇게 말한다 — 빈 흰 칸은 "그림이 원래 없다" 로 읽힌다
  function bindFigFail(root, sel, capSel) {
    function failed(img) {
      var box = img.closest(sel);
      if (!box || box.classList.contains('failed')) return;
      box.classList.add('failed');
      var cap = capSel ? box.querySelector(capSel) : null;
      if (cap) cap.textContent += ' — 이 꾸러미에 없습니다';
      else box.setAttribute('data-msg', '이 꾸러미에 없습니다');
    }
    root.addEventListener('error', function (e) {
      if (e.target.tagName === 'IMG') failed(e.target);
    }, true);
    root.querySelectorAll(sel + ' img').forEach(function (img) {
      if (img.complete && img.naturalWidth === 0) failed(img);
    });
  }

  function bookOf(code) { return BOOKS[code] || null; }

  function volOf(code, vcode) {
    var b = bookOf(code);
    if (!b) return null;
    for (var i = 0; i < b.volumes.length; i++) {
      if (b.volumes[i].code === vcode) return b.volumes[i];
    }
    return null;
  }

  /* ── 미리보기 (뷰어 141 과 같은 자리) ──────────────────────── */

  function bindPreview(root) {
    if (!META.images) return;
    root.querySelectorAll('[data-prev]').forEach(function (a) {
      a.addEventListener('mouseenter', function () { showPreview(a); });
      a.addEventListener('focus', function () { showPreview(a); });
      a.addEventListener('mouseleave', hidePreview);
      a.addEventListener('blur', hidePreview);
    });
  }

  function showPreview(a) {
    var rel = a.getAttribute('data-prev');
    if (!rel) return;
    preview.classList.remove('failed');
    previewCap.textContent = a.getAttribute('data-prevlabel') || '';
    previewImg.onerror = function () {
      preview.classList.add('failed');
      previewCap.textContent = '이 쪽은 꾸러미에 없습니다';
    };
    previewImg.src = rel;
    var r = a.getBoundingClientRect();
    var top = Math.min(r.bottom + 8, window.innerHeight - 260);
    var left = Math.min(r.left, window.innerWidth - 336);
    preview.style.top = Math.max(8, top) + 'px';
    preview.style.left = Math.max(8, left) + 'px';
    preview.hidden = false;
  }

  function hidePreview() { preview.hidden = true; previewImg.removeAttribute('src'); }

  /* ── 검색 화면 ─────────────────────────────────────────────── */

  function viewSearch(p) {
    var q = (p.q || '').trim(), akey = p.atlas || '', genus = p.genus || '';
    var area = p.area || '';
    var off = Math.max(0, num(p.off, 0));
    // **권역은 검색이 아니라 보는 자리다** — 권역만 고른 채로는 카드가 좁혀질 뿐이다
    var searched = !!(q || akey || genus);
    var fq = fold(q), fg = fold(genus);
    var syn = SYN[fq] || [];
    var areaKnown = !area || !!areaLabel(area);

    function matchQ(e) {
      if (!fq) return true;
      return e._f.indexOf(fq) >= 0 || syn.indexOf(e.binomial) >= 0;
    }

    var hits = ENTRIES.filter(function (e) {
      if (!inScope(e, akey, area)) return false;
      if (fg && fold(e.genus) !== fg) return false;
      return matchQ(e);
    });

    // 도감 칩의 수 — 도감 거르개를 뺀 나머지 조건으로 센다
    var counts = {};
    ENTRIES.forEach(function (e) {
      if (!matchQ(e)) return;
      if (fg && fold(e.genus) !== fg) return;
      counts[e.atlas] = (counts[e.atlas] || 0) + 1;
    });
    // 속 목록 — 거르개(도감·권역) 안의 것 전부, 이름순 (뷰어 `atlas_genera`)
    var gc = {};
    ENTRIES.forEach(function (e) {
      if (e.genus && inScope(e, akey, area)) gc[e.genus] = (gc[e.genus] || 0) + 1;
    });
    var genera = Object.keys(gc).sort();

    var h = [];
    // **자동완성은 datalist 다** (뷰어 196 과 같은 모양). 두 글자부터, 거르개
    // 안의 이름만 — 밖의 이름을 권하면 골라도 결과가 빈다.
    h.push('<form class="q" id="qform">'
      + '<input name="q" id="qinput" value="' + esc(q) + '" autofocus autocomplete="off"'
      + ' list="qsuggest"'
      + ' placeholder="학명·속으로 찾는다 (예: Melosira ambigua · Navicula)"'
      + ' aria-label="학명 검색">'
      + '<datalist id="qsuggest"></datalist>'
      + '<select id="qgenus" aria-label="속으로 거른다" title="속으로 거른다 — 고르면 바로 찾는다">'
      + '<option value="">속 전체</option>');
    genera.forEach(function (g) {
      h.push('<option value="' + esc(g) + '"' + (fold(g) === fg && fg ? ' selected' : '')
        + '>' + esc(g) + ' (' + gc[g] + (BD_GENUS[g] ? ' · 기준면 ' + BD_GENUS[g] : '')
        + ')</option>');
    });
    h.push('</select>'
      + '<button type="submit">찾는다</button>'
      + (searched ? '<a class="chip" href="#/' + qs({ area: area }) + '">지운다</a>' : '')
      + '</form>');

    // **권역이 먼저, 도감이 그 안이다.** 권역 칩은 도감을 떼고 도감 칩은 권역을
    // 들고 간다. "전체" 와 "전역" 이 닮아 권역 쪽은 "모든 권역" 이라 적는다.
    h.push('<div class="chips"><span class="dim">권역</span>');
    h.push('<a class="chip' + (area ? '' : ' on') + '" href="#/'
      + qs({ q: q, genus: genus }) + '">모든 권역</a>');
    AREAS.forEach(function (a) {
      h.push('<a class="chip' + (area === a.code ? ' on' : '') + '" href="#/'
        + qs({ q: q, genus: genus, area: a.code }) + '">' + esc(a.label) + '</a>');
    });
    h.push('</div>');
    if (!areaKnown) {
      h.push('<p class="warn">모르는 권역입니다: <code>' + esc(area)
        + '</code> — 아무것도 안 걸립니다. 위에서 고르세요.</p>');
    }

    h.push('<div class="chips"><span class="dim">도감</span>');
    h.push('<a class="chip' + (akey ? '' : ' on') + '" href="#/'
      + qs({ q: q, genus: genus, area: area }) + '">전체</a>');
    (META.atlases || []).forEach(function (a) {
      // 권역을 골랐으면 그 권역의 도감만 — 밖의 도감을 고르면 권역이 조용히 풀린다
      if (area && !akey && a.area !== area) return;
      h.push('<a class="chip' + (akey === a.key ? ' on' : '') + '" title="' + esc(a.title)
        + '" href="#/' + qs({ q: q, atlas: a.key, genus: genus, area: area }) + '">'
        + esc(a.short) + ' <span class="dim">' + (counts[a.key] || 0) + '</span></a>');
    });
    h.push('</div>');

    if (!searched) {
      h.push(bookCards(area));
      app.innerHTML = h.join('');
      wireSearchForm(akey, genus, area);
      return;
    }

    off = Math.min(off, Math.max(0, hits.length - 1));
    var rows = hits.slice(off, off + PER);
    var pager = pagerHtml(hits.length, off, rows.length, q, akey, genus, area);
    // 보기 단추는 **앞 판 줄에만** 둔다 — 뒤 줄에도 두면 같은 id 가 둘이 된다
    h.push(pager.replace(/<\/div>$/, rows.length
      ? '<span class="aviewbtns">'
        + '<button type="button" class="chip" data-aview="list"'
        + ' title="목록으로 본다 — 자리·생태·분포까지">목록</button>'
        + '<button type="button" class="chip" data-aview="grid"'
        + ' title="도판 그림을 칸마다 띄운다 · 비교할 종을 고른다">바둑판</button>'
        + '</span></div>'
      : '</div>'));
    if (!rows.length) {
      h.push('<p class="warn">찾은 것이 없습니다. <b>도감에 없는 것</b>일 수도, '
        + '<b>표기가 달라 안 걸린 것</b>일 수도 있습니다 — 도감은 옛 표기를 쓰고'
        + ' (<i>Actinocyclus Ehrenbergii</i>) Schmidt 는 전량 OCR 입니다.'
        + ' 속만으로 다시 찾아 보세요.</p>');
    }
    // 비교에 담은 것 — 페이지·검색을 바꿔도 남는다(`localStorage`). 다른 속끼리
    // 비교하려면 검색을 두 번 해야 하기 때문이다 (뷰어 238)
    h.push('<div class="atray" id="atray"><span class="dim">비교할 종</span>'
      + ' <b id="atray-n">0</b><span class="dim">/' + CMP_MAX + '</span>'
      + '<span id="atray-list"></span>'
      + '<a class="chip off" id="atray-go" aria-disabled="true"'
      + ' title="고른 종을 나란히 놓는다 (2~' + CMP_MAX + '종)">비교</a>'
      + '<button type="button" class="chip" id="atray-clear">비운다</button></div>');
    // **보기는 감싸는 칸의 클래스 하나가 정한다** — `[hidden]` 을 안 쓴다:
    // `.agrid` 의 `display: grid` 가 특이도에서 이겨 그대로 보인다(CLAUDE.md)
    var view = 'list';
    try { view = localStorage.getItem(VKEY) === 'grid' ? 'grid' : 'list'; } catch (err) { /* 사생활 모드 */ }
    h.push('<div id="aresults" class="av-' + view + '"><div class="alist">');
    rows.forEach(function (e) { h.push(entryHtml(e)); });
    h.push('</div><div class="agrid">');
    rows.forEach(function (e) { h.push(cardHtml(e)); });
    h.push('</div></div>');
    h.push(pager);
    app.innerHTML = h.join('');
    wireSearchForm(akey, genus, area);
    bindPreview(app);
    if (rows.length) wireGrid();
  }

  function cardHtml(e) {
    var a = atlasMeta(e.atlas), f = META.images ? rowFigure(e) : null, k = entryKey(e);
    var h = ['<div class="acard" data-key="' + esc(k) + '">'];
    if (f) {
      h.push((f.href ? '<a class="afig" href="' + esc(f.href) + '">' : '<div class="afig">')
        + '<img loading="lazy" alt="' + esc(e.name) + '" src="' + esc(f.src) + '">'
        + (f.href ? '</a>' : '</div>'));
    } else {
      // 한국 도감 201건은 PDF 쪽이 없다 — 빈 칸 대신 말한다
      h.push('<div class="afig nofig">그림 없음</div>');
    }
    h.push('<div class="aname"><i>' + esc(e.name) + '</i></div>'
      + '<div class="dim">' + esc(a.short) + (f && f.label ? ' · ' + esc(f.label) : '')
      + (e.genus_guess ? ' · 속명 추정' : '') + '</div>'
      + '<label class="apick"><input type="checkbox" class="apick-cb" value="' + esc(k)
      + '" data-name="' + esc(e.name) + '"><span>비교에 담기</span></label></div>');
    return h.join('');
  }

  function wireGrid() {
    var box = document.getElementById('aresults');
    var tray = document.getElementById('atray');
    var goBtn = document.getElementById('atray-go');
    var picked = loadPicked();
    function view() { return box.className === 'av-grid' ? 'grid' : 'list'; }
    function has(k) { return picked.some(function (x) { return x.k === k; }); }

    function draw() {
      var full = picked.length >= CMP_MAX;
      box.querySelectorAll('.apick-cb').forEach(function (cb) {
        cb.checked = has(cb.value);
        // 다 찼으면 담지 않은 칸만 잠근다 — 담은 것은 뺄 수 있어야 한다
        cb.disabled = full && !cb.checked;
        cb.closest('.acard').classList.toggle('picked', cb.checked);
      });
      document.getElementById('atray-n').textContent = picked.length;
      var list = document.getElementById('atray-list');
      list.innerHTML = picked.map(function (x) {
        return '<span class="chip"><i>' + esc(x.n || x.k) + '</i>'
          + '<button type="button" class="adrop" data-k="' + esc(x.k)
          + '" title="뺀다" aria-label="뺀다">×</button></span>';
      }).join('');
      if (picked.length >= 2) {
        goBtn.href = compareHash(picked);
        goBtn.classList.remove('off');
        goBtn.removeAttribute('aria-disabled');
      } else {
        goBtn.removeAttribute('href');
        goBtn.classList.add('off');
        goBtn.setAttribute('aria-disabled', 'true');
      }
      tray.classList.toggle('on', view() === 'grid' || picked.length > 0);
      document.querySelectorAll('[data-aview]').forEach(function (b) {
        b.classList.toggle('on', b.getAttribute('data-aview') === view());
      });
    }

    document.querySelectorAll('[data-aview]').forEach(function (b) {
      b.addEventListener('click', function () {
        var v = b.getAttribute('data-aview');
        box.className = 'av-' + v;
        try { localStorage.setItem(VKEY, v); } catch (err) { /* 사생활 모드 */ }
        draw();
      });
    });
    box.addEventListener('change', function (e) {
      var cb = e.target;
      if (!cb.classList || !cb.classList.contains('apick-cb')) return;
      // **담기 직전에 다시 읽는다** — 다른 탭에서 담은 것을 덮지 않게
      picked = loadPicked().filter(function (x) { return x.k !== cb.value; });
      if (cb.checked && picked.length < CMP_MAX) {
        picked.push({ k: cb.value, n: cb.getAttribute('data-name') });
      }
      storePicked(picked);
      draw();
    });
    tray.addEventListener('click', function (e) {
      var b = e.target.closest('.adrop');
      if (b) {
        picked = loadPicked().filter(function (x) { return x.k !== b.getAttribute('data-k'); });
        storePicked(picked);
        draw();
      } else if (e.target.id === 'atray-clear') {
        picked = [];
        storePicked(picked);
        draw();
      }
    });
    bindFigFail(box, '.afig');
    draw();
  }

  function wireSearchForm(akey, genus, area) {
    var f = document.getElementById('qform');
    if (!f) return;
    var inp = document.getElementById('qinput');
    var sel = document.getElementById('qgenus');
    var dl = document.getElementById('qsuggest');
    function submit(g) {
      go('/', { q: inp.value.trim(), atlas: akey, genus: g, area: area });
    }
    f.addEventListener('submit', function (e) { e.preventDefault(); submit(sel.value); });
    // 속을 고르면 바로 간다 — 목록은 거르개라 "찾는다" 를 한 번 더 누르게 하지 않는다
    sel.addEventListener('change', function () { submit(sel.value); });

    // 자동완성 — 거르개 안의 이명법(`binomial`)만. 빈 것은 도감이 속까지만
    // 내려갔거나 못 읽는 표기라(뷰어 119) 값으로 권하지 않는다.
    var last = '';
    inp.addEventListener('input', function () {
      var v = inp.value.trim(), fv = fold(v);
      if (v.length < 2 || v === last) return;
      last = v;
      var seen = {}, out = [];
      for (var i = 0; i < ENTRIES.length && out.length < SUGGEST_MAX; i++) {
        var e = ENTRIES[i];
        if (!e.binomial || !inScope(e, akey, area)) continue;
        if (e._f.indexOf(fv) < 0) continue;
        var k = fold(e.binomial);
        if (seen[k]) { seen[k].atlases[e.atlas] = 1; continue; }
        seen[k] = { value: e.binomial, atlases: {}, guess: !!e.genus_guess };
        seen[k].atlases[e.atlas] = 1;
        out.push(seen[k]);
      }
      dl.textContent = '';
      out.forEach(function (row) {
        var o = document.createElement('option');
        o.value = row.value;
        // **"확정" 이라고 말하지 않는다** (뷰어 119). 표시가 있는 쪽만 말한다.
        o.label = Object.keys(row.atlases).map(function (k) { return atlasMeta(k).short; })
          .join(' · ') + (row.guess ? ' · 속명 추정' : '');
        dl.appendChild(o);
      });
    });
  }

  function pagerHtml(total, off, shown, q, akey, genus, area) {
    var h = ['<div class="pager"><span class="dim">' + total + '건'];
    if (total) h.push(' 중 ' + (off + 1) + '~' + (off + shown));
    if (genus) h.push(' · 속 <b>' + esc(genus) + '</b>');
    h.push('</span>');
    if (off > 0) {
      h.push('<a class="chip" href="#/' + qs({ q: q, atlas: akey, genus: genus, area: area,
        off: Math.max(0, off - PER) }) + '">← 앞</a>');
    }
    if (off + PER < total) {
      h.push('<a class="chip" href="#/' + qs({ q: q, atlas: akey, genus: genus, area: area,
        off: off + PER }) + '">뒤 →</a>');
    }
    return h.join('') + '</div>';
  }

  function entryHtml(e) {
    var a = atlasMeta(e.atlas);
    var h = ['<div class="entry"><div class="ename"><i>' + esc(e.name) + '</i>'];
    // **"확정" 이라는 말을 안 쓴다** — 표시가 있는 쪽만 말한다 (뷰어 119).
    if (e.genus_guess) {
      h.push('<span class="chip warnchip" title="색인이 속명을 문맥에서 복원했다고 표시한 항목">속명 추정</span>');
    }
    if (e.rank === 'genus_only') {
      h.push('<span class="chip" title="도감이 속까지만 내려간 항목 (sp. · group)">속까지</span>');
    } else if (e.rank === 'unreadable') {
      h.push('<span class="chip warnchip" title="색인의 표기를 우리가 못 읽는다">못 읽음</span>');
    }
    h.push('<span class="dim">' + esc(a.short) + (e.item_no ? ' #' + esc(e.item_no) : '')
      + '</span></div><div class="places">');
    if (!(e.places || []).length) h.push('<span class="dim">자리가 안 적혀 있다</span>');
    (e.places || []).forEach(function (pl) {
      h.push('<span class="place">');
      if (pl.volume) h.push('<span class="dim">' + esc(pl.volume) + '</span> ');
      if (pl.where) h.push(esc(pl.where));
      if (pl.figures) h.push(' <span class="dim">fig. ' + esc(pl.figures) + '</span>');
      if (pl.book_page) h.push(' <span class="dim">책 p.' + esc(pl.book_page) + '</span>');
      h.push(pageLink(e.atlas, pl, 'text'));
      h.push(pageLink(e.atlas, pl, 'plate'));
      // **그림 하나의 크롭** (뷰어 P23·239~241). 도판 쪽 전체가 아니라 이 그림만
      // 미리 보여 준다. 누르면 도판 쪽으로 간다 — 크롭 자체는 쪽이 아니다
      if (pl.crop_rel && META.images) {
        var ph = plateHref(pl);
        h.push((ph ? '<a class="chip" href="' + esc(ph) + '"' : '<span class="chip"')
          + ' data-prev="' + esc(pl.crop_rel) + '" data-prevlabel="'
          + esc(pl.figures ? 'fig. ' + pl.figures : '그림') + '">그림 보기'
          + (ph ? '</a>' : '</span>'));
      }
      if (pl.note) h.push('<span class="pnote">' + esc(pl.note) + '</span>');
      h.push('</span>');
    });
    h.push('</div>');
    var ex = e.extra || {};
    if (ex.ecology || ex.distribution || ex.original_note || (ex.samples || []).length) {
      h.push('<div class="entryextra">');
      if (ex.ecology) h.push('<div><span class="dim">생태</span> ' + esc(ex.ecology) + '</div>');
      if (ex.distribution) h.push('<div><span class="dim">분포</span> ' + esc(ex.distribution) + '</div>');
      if (ex.original_note) h.push('<div><span class="dim">원문 표기</span> ' + esc(ex.original_note) + '</div>');
      (ex.samples || []).forEach(function (s) {
        h.push('<div><span class="dim">시료</span> fig. ' + esc(s.figure) + ' · '
          + esc(s.raw || '') + '</div>');
      });
      h.push('</div>');
    }
    // 학명 유효성 (P24) — 사람이 AlgaeBase 를 열어 확인한 이명 판정. **이명일
    // 때만 낸다** — 유효·미확인은 낼 것이 없다(뷰어 `atlas_search` 와 같은 규칙).
    var t = e.binomial ? TAXA[e.binomial] : null;
    if (t && t.status === 'synonym') {
      h.push('<div class="entryextra taxon">'
        + '<span class="chip warnchip" title="AlgaeBase 확인 — 이 표기는 이명이다">이명</span> '
        + '현재 통용 학명 <a href="#/' + qs({ q: t.valid_name }) + '"><i>' + esc(t.valid_name)
        + '</i></a>'
        + (t.note ? ' <span class="pnote">' + esc(t.note) + '</span>' : '') + '</div>');
    }
    // 출현 기록 (P20) — 도감의 "분포" 문장이 낳은 종 × 지역 × 문헌. 위의
    // `분포`(원문 그대로)와 다른 자리라 나란히 낸다.
    var occ = e.binomial ? (OCC[e.binomial] || []) : [];
    if (occ.length) {
      h.push('<div class="entryextra occurrences"><span class="dim">출현</span> ');
      h.push(occ.map(function (o) {
        return '<span class="occ">' + esc(o.region) + ' <span class="dim">(' + esc(o.authors)
          + ', ' + esc(o.year) + ')</span>'
          + (o.note ? ' <span class="pnote">' + esc(o.note) + '</span>' : '') + '</span>';
      }).join(' · '));
      h.push('</div>');
    }
    // 생층서 기준면 (P28) — 이 종의 FO·LO 를 어느 문헌이 몇 Ma 로 봤나. 없으면
    // 줄을 안 낸다. 뷰어 카드와 같은 모양이고 범위 그림 링크만 없다(서버 화면이다).
    var bd = e.binomial ? (BD[e.binomial] || []) : [];
    if (bd.length) {
      h.push('<div class="entryextra biodatums"><span class="dim">기준면</span> ');
      h.push(bd.map(function (b) {
        return '<span class="bdm">' + esc(b.datum) + ' ' + esc(b.age)
          + (b.uncertainty ? '±' + esc(b.uncertainty) : '') + ' Ma <span class="dim">('
          + esc(b.ref_label) + (b.via_label ? ' — ' + esc(b.via_label) + ' 경유' : '')
          + (b.infra ? ' · ' + esc(b.infra) : '')
          + (b.variant_label ? ' · ' + esc(b.variant_label) : '') + ')</span></span>';
      }).join(' · '));
      h.push('</div>');
    }
    return h.join('') + '</div>';
  }

  // **PDF 쪽이 없으면 링크를 안 낸다** (한국 도감 201건). 눌러서 빈 화면이 나오는
  // 링크는 "안 구웠다" 로 읽혀 원인을 엉뚱한 데서 찾게 한다 (뷰어 `_placement_dict`).
  function pageLink(akey, pl, which) {
    var n = which === 'text' ? pl.pdf_page : pl.pdf_plate_page;
    var rel = which === 'text' ? pl.text_rel : pl.plate_rel;
    var thumb = which === 'text' ? pl.text_thumb : pl.plate_thumb;
    var label = (which === 'text' ? '해설 p.' : '도판 p.') + n;
    if (!n) return '';
    // **자리는 남기고 링크만 뺀다.** 라벨까지 지우면 색인이 짚어 준 쪽 번호가
    // 화면에서 사라져 "안 적혀 있다" 로 읽힌다 — 안 실린 것과 안 적힌 것은 다르다.
    if (!rel || !META.images) {
      return '<span class="chip" title="이 꾸러미에 그 쪽이 없다">' + esc(label) + '</span>';
    }
    return '<a class="chip" href="#/page/' + esc(pl.vol_path) + '/' + n + '"'
      + ' data-prev="' + esc(thumb) + '" data-prevlabel="' + esc(label) + '">'
      + esc(label) + '</a>';
  }

  /* ── 도감 카드·격자 ────────────────────────────────────────── */

  // 도감 카드 — **권역별로 묶는다** (뷰어 196). 권역을 모르는 도감은 "권역
  // 미정" 으로 따로 선다 — "전역" 에 뭉개면 새 도감이 조용히 거기 앉는다.
  function bookCards(area) {
    if (!META.images) {
      return '<p class="note">이 꾸러미는 <b>글자만</b> 담았습니다 — 도판 이미지는 없습니다.</p>';
    }
    var h = ['<h1>도감</h1>'];
    var groups = AREAS.filter(function (a) { return !area || a.code === area; })
      .map(function (a) { return { code: a.code, label: a.label }; });
    if (!area) groups.push({ code: '', label: '권역 미정' });
    var any = false;
    groups.forEach(function (g) {
      var mine = (META.atlases || []).filter(function (a) {
        return (a.area || '') === g.code && bookOf(a.key);
      });
      if (!mine.length) return;
      any = true;
      h.push('<h2 class="areahead">' + esc(g.label) + ' <span class="dim">' + mine.length
        + '권</span></h2>');
      mine.forEach(function (a) {
        var b = bookOf(a.key);
        h.push('<div class="bookrow"><div class="cover">'
          + (b.cover ? '<img src="' + esc(b.cover) + '" alt="">' : '')
          + '</div><div class="body"><h2>' + esc(a.title) + '</h2>'
          + '<div class="dim">' + esc(a.short) + ' · 항목 ' + a.count + '개 · 쪽 '
          + b.rendered + '</div>'
          + (a.note ? '<div class="note">' + mdlite(a.note) + '</div>' : '')
          + '<div class="vols">');
        b.volumes.forEach(function (v) {
          h.push('<a class="chip" href="#/book/' + esc(b.code) + '/' + esc(v.code) + '">'
            + esc(v.label) + ' <span class="dim">' + v.pages.length + '쪽</span></a>');
        });
        h.push('</div></div></div>');
      });
    });
    if (!any) h.push('<p class="warn">이 권역에 도감이 없습니다.</p>');
    return h.join('');
  }

  function viewBook(parts, p) {
    var code = parts[1], vcode = parts[2];
    var b = bookOf(code), v = volOf(code, vcode);
    if (!b || !v) { app.innerHTML = '<p class="warn">그런 권이 없습니다.</p>'; return; }
    var off = Math.max(0, num(p.off, 0));
    if (off >= v.pages.length) off = Math.max(0, (Math.ceil(v.pages.length / GRID) - 1) * GRID);
    var slice = v.pages.slice(off, off + GRID);
    var h = ['<h1>' + esc(b.label) + ' <span class="dim">' + esc(v.label) + '</span></h1>'];
    h.push('<div class="pager"><span class="dim">' + v.pages.length + '쪽 중 '
      + (off + 1) + '~' + (off + slice.length) + '</span>');
    if (off > 0) h.push('<a class="chip" href="#/book/' + code + '/' + vcode
      + qs({ off: Math.max(0, off - GRID) }) + '">← 앞</a>');
    if (off + GRID < v.pages.length) h.push('<a class="chip" href="#/book/' + code + '/'
      + vcode + qs({ off: off + GRID }) + '">뒤 →</a>');
    h.push('<span class="ajump"><label class="dim" for="jump">쪽으로</label>'
      + '<input id="jump" inputmode="numeric" placeholder="' + v.pages[0] + '">'
      + '<button type="button" id="jumpgo">간다</button></span></div>');
    h.push('<div class="grid">');
    slice.forEach(function (n) {
      h.push('<a class="gcell" href="#/page/' + code + '/' + vcode + '/' + n + '">'
        + '<img loading="lazy" src="' + esc(v.thumb_dir + 'p' + pad(n) + '.jpg') + '" alt="">'
        + 'p.' + n + '</a>');
    });
    h.push('</div>');
    app.innerHTML = h.join('');
    var jump = document.getElementById('jump');
    function doJump() {
      var n = num(jump.value, 0);
      if (v.pages.indexOf(n) >= 0) go('/page/' + code + '/' + vcode + '/' + n, {});
      else jump.value = '';
    }
    document.getElementById('jumpgo').addEventListener('click', doJump);
    jump.addEventListener('keydown', function (e) { if (e.key === 'Enter') doJump(); });
  }

  function pad(n) { return ('0000' + n).slice(-4); }

  /* ── 쪽 보기 ───────────────────────────────────────────────── */

  var zoom = { k: 1, tx: 0, ty: 0, fit: 1 };

  function viewPage(parts, p) {
    var code = parts[1], vcode = parts[2], n = num(parts[3], 0);
    var b = bookOf(code), v = volOf(code, vcode);
    if (!b || !v || v.pages.indexOf(n) < 0) {
      app.innerHTML = '<p class="warn">그 쪽은 이 꾸러미에 없습니다. '
        + '<b>안 구운 것</b>과 <b>원본에 없는 것</b>은 다른 말입니다.</p>';
      return;
    }
    var two = p.spread === '1';
    var idx = v.pages.indexOf(n);
    var shots, left = null, right = null;
    if (two) {
      // **번호가 바깥 모서리로 간다** (뷰어 `atlas.spread`). 좌우 판정은 도감마다
      // 다르다 — `left_parity` 가 그것을 말한다.
      var wantEven = b.left_parity === 'even';
      var l = ((n % 2 === 0) === wantEven) ? n : n - 1;
      left = v.pages.indexOf(l) >= 0 ? l : null;
      right = v.pages.indexOf(l + 1) >= 0 ? l + 1 : null;
      shots = [left, right].filter(function (x) { return x !== null; });
    } else {
      shots = [n];
    }
    var first = shots[0], last = shots[shots.length - 1];
    var prev = v.pages[v.pages.indexOf(first) - 1];
    var next = v.pages[v.pages.indexOf(last) + 1];
    var gridOff = Math.floor(v.pages.indexOf(first) / GRID) * GRID;

    var h = ['<div class="abar">'];
    if (prev !== undefined) h.push('<a class="chip" href="#/page/' + code + '/' + vcode
      + '/' + prev + (two ? '?spread=1' : '') + '">← ' + (two ? '앞' : 'p.' + prev) + '</a>');
    h.push('<a class="chip" href="#/book/' + code + '/' + vcode + qs({ off: gridOff }) + '">격자</a>');
    h.push('<a class="chip' + (two ? '' : ' on') + '" href="#/page/' + code + '/' + vcode
      + '/' + n + '">한 장</a>');
    h.push('<a class="chip' + (two ? ' on' : '') + '" href="#/page/' + code + '/' + vcode
      + '/' + n + '?spread=1">두 쪽</a>');
    if (next !== undefined) h.push('<a class="chip" href="#/page/' + code + '/' + vcode
      + '/' + next + (two ? '?spread=1' : '') + '">' + (two ? '뒤' : 'p.' + next) + ' →</a>');
    h.push('<span class="dim">' + esc(b.label) + ' · ' + esc(v.label) + ' · p.'
      + shots.join('–') + ' <span class="dim">(' + (v.pages.indexOf(first) + 1)
      + '/' + v.pages.length + ')</span></span>');
    h.push('<span class="azoom"><button type="button" id="zo" title="작게 (-)">−</button>'
      + '<span class="lv" id="zlv">×1.0</span>'
      + '<button type="button" id="zi" title="크게 (+)">+</button>'
      + '<button type="button" id="zf" title="화면에 맞춘다 (0)">맞춤</button></span>');
    h.push('</div><div class="akeys">← → 넘긴다 · <kbd>g</kbd> 격자 · <kbd>s</kbd> 보기'
      + ' · 휠 확대 · 끌어서 옮긴다</div>');
    h.push('<div class="aview" id="aview"><div id="acanvas">');
    shots.forEach(function (x) {
      h.push('<img src="' + esc(v.page_dir + 'p' + pad(x) + '.jpg') + '" alt="p.' + x + '">');
    });
    h.push('</div></div>');
    app.innerHTML = h.join('');
    wireZoom(code, vcode, n, two, prev, next, gridOff);
  }

  function wireZoom(code, vcode, n, two, prev, next, gridOff) {
    var view = document.getElementById('aview');
    var canvas = document.getElementById('acanvas');
    var lv = document.getElementById('zlv');
    var dragging = false, sx = 0, sy = 0, stx = 0, sty = 0;

    function apply() {
      canvas.style.transform = 'translate(' + zoom.tx + 'px,' + zoom.ty + 'px) scale('
        + zoom.k + ')';
      view.classList.toggle('zoomed', zoom.k > zoom.fit);
      lv.textContent = '×' + (zoom.k / zoom.fit).toFixed(1);
    }
    function fit() {
      var vw = view.clientWidth, vh = view.clientHeight;
      var cw = canvas.scrollWidth, ch = canvas.scrollHeight;
      if (!cw || !ch) return;
      zoom.fit = Math.min(vw / cw, vh / ch);
      zoom.k = zoom.fit;
      zoom.tx = (vw - cw * zoom.k) / 2;
      zoom.ty = (vh - ch * zoom.k) / 2;
      apply();
    }
    function clamp() {
      var vw = view.clientWidth, vh = view.clientHeight;
      var w = canvas.scrollWidth * zoom.k, hgt = canvas.scrollHeight * zoom.k;
      zoom.tx = w <= vw ? (vw - w) / 2 : Math.min(0, Math.max(vw - w, zoom.tx));
      zoom.ty = hgt <= vh ? (vh - hgt) / 2 : Math.min(0, Math.max(vh - hgt, zoom.ty));
    }
    function zoomAt(nk, cx, cy) {
      nk = Math.max(zoom.fit * 0.5, Math.min(zoom.fit * 24, nk));
      var r = view.getBoundingClientRect();
      var px = cx - r.left, py = cy - r.top;
      zoom.tx = px - (px - zoom.tx) * (nk / zoom.k);
      zoom.ty = py - (py - zoom.ty) * (nk / zoom.k);
      zoom.k = nk;
      clamp(); apply();
    }
    function step(f) {
      var r = view.getBoundingClientRect();
      zoomAt(zoom.k * f, r.left + r.width / 2, r.top + r.height / 2);
    }

    Array.prototype.forEach.call(canvas.querySelectorAll('img'), function (im) {
      if (im.complete) fit(); else im.addEventListener('load', fit);
    });
    fit();

    view.addEventListener('wheel', function (e) {
      e.preventDefault();
      zoomAt(zoom.k * (e.deltaY < 0 ? 1.18 : 1 / 1.18), e.clientX, e.clientY);
    }, { passive: false });
    view.addEventListener('mousedown', function (e) {
      dragging = true; sx = e.clientX; sy = e.clientY; stx = zoom.tx; sty = zoom.ty;
      view.classList.add('grabbing'); e.preventDefault();
    });
    window.addEventListener('mousemove', function (e) {
      if (!dragging) return;
      zoom.tx = stx + (e.clientX - sx); zoom.ty = sty + (e.clientY - sy);
      clamp(); apply();
    });
    window.addEventListener('mouseup', function () {
      dragging = false; view.classList.remove('grabbing');
    });
    window.addEventListener('resize', function () { fit(); });
    document.getElementById('zi').addEventListener('click', function () { step(1.25); });
    document.getElementById('zo').addEventListener('click', function () { step(1 / 1.25); });
    document.getElementById('zf').addEventListener('click', fit);

    // 키. **입력칸에서는 안 먹는다** — 쪽 번호를 치다가 화면이 넘어가면 안 된다.
    document.onkeydown = function (e) {
      var t = e.target.tagName;
      if (t === 'INPUT' || t === 'TEXTAREA' || e.metaKey || e.ctrlKey || e.altKey) return;
      switch (e.key) {
        case 'ArrowLeft': if (prev !== undefined) { e.preventDefault();
          go('/page/' + code + '/' + vcode + '/' + prev, two ? { spread: 1 } : {}); } return;
        case 'ArrowRight': if (next !== undefined) { e.preventDefault();
          go('/page/' + code + '/' + vcode + '/' + next, two ? { spread: 1 } : {}); } return;
        case 'g': go('/book/' + code + '/' + vcode, { off: gridOff }); return;
        case 's': go('/page/' + code + '/' + vcode + '/' + n, two ? {} : { spread: 1 }); return;
        case '+': case '=': e.preventDefault(); step(1.25); return;
        case '-': case '_': e.preventDefault(); step(1 / 1.25); return;
        case '0': e.preventDefault(); fit(); return;
      }
    };
  }

  /* ── 비교 (뷰어 238 · `atlas_compare.html`) ─────────────────── */

  // **표로 놓는다.** 종마다 카드를 따로 세우면 "생태" 가 칸마다 다른 높이에 놓여
  // 옆 종과 같은 줄을 비교할 수 없다. 줄이 곧 항목이고, **한 종이라도 값이 있는
  // 줄만 낸다.** 값이 있는 줄의 빈 칸은 「—」 — 그 종에 그 자료가 없다는 것도 비교다.
  function viewCompare(multi) {
    var keys = [], seen = {};
    (multi.e || []).forEach(function (k) {
      k = (k || '').trim();
      if (k && !seen[k]) { seen[k] = 1; keys.push(k); }
    });
    var over = Math.max(0, keys.length - CMP_MAX);
    keys = keys.slice(0, CMP_MAX);
    var rows = [], missing = [];
    keys.forEach(function (k) { if (BYKEY[k]) rows.push(BYKEY[k]); else missing.push(k); });

    // **보고 있는 비교가 곧 담은 것이다** — 여기서 빼고 돌아갔는데 검색 화면에
    // 그대로 담겨 있으면 무엇을 비교하는지가 두 자리에서 갈린다
    storePicked(rows.map(function (e) { return { k: entryKey(e), n: e.name }; }));

    var h = ['<h1><a href="#/" id="cmpback">도감</a> · 비교 <span class="dim">'
      + rows.length + '종</span></h1>'];
    if (missing.length) {
      h.push('<p class="warn">도감 색인에서 못 찾았습니다(판이 바뀌어 표제어가 고쳐졌을 수'
        + ' 있습니다): ' + missing.map(function (k) { return '<code>' + esc(k) + '</code>'; })
        .join(' · ') + '</p>');
    }
    if (over) h.push('<p class="warn">앞의 다섯 종만 놓았습니다 — ' + over + ' 종은 뺐습니다.</p>');
    if (!rows.length) {
      h.push('<p class="warn">비교할 종이 없습니다. 색인 검색 결과의 바둑판 보기에서 2~'
        + CMP_MAX + '종을 고르세요. <a href="#/">색인 검색으로</a></p>');
      app.innerHTML = h.join('');
      return;
    }
    if (rows.length === 1) h.push('<p class="dim">한 종만 남았습니다 — 바둑판 보기에서 더 고르세요.</p>');

    function drop(e) {
      var rest = rows.filter(function (x) { return x !== e; })
        .map(function (x) { return { k: entryKey(x) }; });
      return compareHash(rest);
    }
    function tax(e) {
      var t = e.binomial ? TAXA[e.binomial] : null;
      return t && t.status === 'synonym' ? t : null;
    }
    function occ(e) { return e.binomial ? (OCC[e.binomial] || []) : []; }
    function bd(e) { return e.binomial ? (BD[e.binomial] || []) : []; }
    function ex(e, k) { return (e.extra || {})[k] || ''; }
    var n = rows.length;
    function sec(label) {
      return '<tr class="sec"><th colspan="' + n + '">' + esc(label) + '</th></tr>';
    }
    function any(fn) { return rows.some(function (e) { return !!fn(e); }); }

    h.push('<div class="cmpwrap"><table class="cmp" id="cmp" style="min-width:'
      + (n * 250) + 'px"><thead><tr>');
    rows.forEach(function (e) {
      var a = atlasMeta(e.atlas);
      h.push('<th><div class="cname"><i>' + esc(e.name) + '</i></div>'
        + '<div class="cmeta dim">' + esc(a.short) + (e.item_no ? ' #' + esc(e.item_no) : '')
        + (e.genus_guess ? ' <span class="chip warnchip">속명 추정</span>' : '')
        + (e.rank === 'genus_only' ? ' <span class="chip">속까지</span>'
          : e.rank === 'unreadable' ? ' <span class="chip warnchip">못 읽음</span>' : '')
        + '</div><a class="cdrop" href="' + esc(drop(e)) + '">빼기</a></th>');
    });
    h.push('</tr></thead><tbody>');

    // 그림 — 자리마다 하나. 크롭이 있으면 크롭, 없으면 도판 한 쪽(바둑판과 같은 규칙)
    h.push(sec('그림') + '<tr>');
    rows.forEach(function (e) {
      var figs = [];
      if (META.images) (e.places || []).forEach(function (pl) {
        var src = pl.crop_rel || (pl.plate_rel && !pl.note ? pl.plate_rel : '');
        if (!src) return;
        var ph = plateHref(pl);
        figs.push((ph ? '<a class="cfig" href="' + esc(ph) + '">' : '<div class="cfig">')
          + '<img loading="lazy" alt="' + esc(e.name) + '" src="' + esc(src) + '">'
          + '<div class="cap">' + (pl.volume ? esc(pl.volume) + ' ' : '') + esc(pl.where)
          + (pl.figures ? ' fig. ' + esc(pl.figures) : '')
          + (pl.pdf_plate_page ? ' · p.' + esc(pl.pdf_plate_page) : '') + '</div>'
          + (ph ? '</a>' : '</div>'));
      });
      h.push('<td>' + (figs.length ? figs.join('') : '<span class="dim">그림 없음</span>') + '</td>');
    });
    h.push('</tr>');

    h.push(sec('자리') + '<tr>');
    rows.forEach(function (e) {
      var ps = (e.places || []).map(function (pl) {
        return '<span>' + (pl.volume ? '<span class="dim">' + esc(pl.volume) + '</span> ' : '')
          + esc(pl.where) + (pl.figures ? ' <span class="dim">fig. ' + esc(pl.figures) + '</span>' : '')
          + (pl.book_page ? ' <span class="dim">책 p.' + esc(pl.book_page) + '</span>' : '')
          + ' ' + pageLink(e.atlas, pl, 'text') + ' ' + pageLink(e.atlas, pl, 'plate')
          + (pl.note ? ' <span class="pnote">' + esc(pl.note) + '</span>' : '') + '</span>';
      });
      h.push('<td><div class="cplaces">' + (ps.length ? ps.join('')
        : '<span class="dim">자리가 안 적혀 있다</span>') + '</div></td>');
    });
    h.push('</tr>');

    if (any(tax)) {
      h.push(sec('현재 통용 학명') + '<tr>');
      rows.forEach(function (e) {
        var t = tax(e);
        h.push('<td>' + (t ? '<span class="chip warnchip" title="AlgaeBase 확인 — 이 표기는 이명이다">이명</span> '
          + '<i>' + esc(t.valid_name) + '</i>'
          + (t.note ? ' <span class="pnote">' + esc(t.note) + '</span>' : '') : '—') + '</td>');
      });
      h.push('</tr>');
    }
    [['ecology', '생태'], ['distribution', '분포'], ['original_note', '원문 표기']]
      .forEach(function (c) {
        if (!any(function (e) { return ex(e, c[0]); })) return;
        h.push(sec(c[1]) + '<tr>');
        rows.forEach(function (e) { h.push('<td>' + (esc(ex(e, c[0])) || '—') + '</td>'); });
        h.push('</tr>');
      });
    if (any(function (e) { return occ(e).length; })) {
      h.push(sec('출현') + '<tr>');
      rows.forEach(function (e) {
        var o = occ(e);
        h.push('<td>' + (o.length ? o.map(function (x) {
          return '<div>' + esc(x.region) + ' <span class="dim">(' + esc(x.authors) + ', '
            + esc(x.year) + ')</span>' + (x.note ? ' <span class="pnote">' + esc(x.note) + '</span>' : '')
            + '</div>';
        }).join('') : '—') + '</td>');
      });
      h.push('</tr>');
    }
    if (any(function (e) { return bd(e).length; })) {
      h.push(sec('기준면') + '<tr>');
      rows.forEach(function (e) {
        var b = bd(e);
        h.push('<td>' + (b.length ? b.map(function (x) {
          return '<div>' + esc(x.datum) + ' ' + esc(x.age)
            + (x.uncertainty ? '±' + esc(x.uncertainty) : '') + ' Ma <span class="dim">('
            + esc(x.ref_label) + (x.via_label ? ' — ' + esc(x.via_label) + ' 경유' : '')
            + (x.infra ? ' · ' + esc(x.infra) : '')
            + (x.variant_label ? ' · ' + esc(x.variant_label) : '') + ')</span></div>';
        }).join('') : '—') + '</td>');
      });
      h.push('</tr>');
    }
    h.push('</tbody></table></div>');
    app.innerHTML = h.join('');
    bindPreview(app);
    bindFigFail(document.getElementById('cmp'), '.cfig', '.cap');

    // 검색 결과에서 왔으면 그 결과로 돌아간다 — 첫 화면으로 보내면 검색을 다시 해야 한다
    document.getElementById('cmpback').addEventListener('click', function (ev) {
      if (lastSearch !== null) { ev.preventDefault(); location.hash = lastSearch; }
    });
  }

  /* ── 학명 대조표 (종 검색) ─────────────────────────────────── */

  function viewNames(p) {
    var q = (p.q || '').trim(), fq = fold(q);
    var only = p.only || '';
    var cols = NAMES.cols, rows = NAMES.rows;
    var iName = cols.indexOf('이름'), iJudge = cols.indexOf('재판정');
    var hits = rows.filter(function (r) {
      if (only && String(r[iJudge] || '') !== only) return false;
      if (!fq) return true;
      for (var i = 0; i < r.length; i++) {
        if (r[i] && fold(r[i]).indexOf(fq) >= 0) return true;
      }
      return false;
    });
    var off = Math.max(0, num(p.off, 0));
    var slice = hits.slice(off, off + 100);

    var judges = {};
    rows.forEach(function (r) { var v = r[iJudge] || '(빈 칸)'; judges[v] = (judges[v] || 0) + 1; });

    var h = ['<h1>종 검색 <span class="dim">학명 대조표 ' + rows.length + '건</span></h1>'];
    h.push('<p class="note">도감 색인의 이름을 WoRMS·AlgaeBase 에 대조한 표다.'
      + ' 어느 칸이든 걸리면 나온다 — 유효명·저자·과·목으로도 찾을 수 있다.</p>');
    h.push('<form class="q" id="nform"><input id="ninput" value="' + esc(q)
      + '" placeholder="이름·유효명·과·목으로 찾는다" aria-label="학명 대조표 검색">'
      + '<button type="submit">찾는다</button>'
      + (q || only ? '<a class="chip" href="#/names">지운다</a>' : '') + '</form>');
    h.push('<div class="chips"><span class="dim">재판정</span>'
      + '<a class="chip' + (only ? '' : ' on') + '" href="#/names' + qs({ q: q }) + '">전체</a>');
    Object.keys(judges).sort(function (a, b) { return judges[b] - judges[a]; })
      .forEach(function (k) {
        if (k === '(빈 칸)') return;
        h.push('<a class="chip' + (only === k ? ' on' : '') + '" href="#/names'
          + qs({ q: q, only: k }) + '">' + esc(k) + ' <span class="dim">' + judges[k]
          + '</span></a>');
      });
    h.push('</div>');
    h.push('<div class="pager"><span class="dim">' + hits.length + '건'
      + (hits.length ? ' 중 ' + (off + 1) + '~' + (off + slice.length) : '') + '</span>');
    if (off > 0) h.push('<a class="chip" href="#/names' + qs({ q: q, only: only,
      off: Math.max(0, off - 100) }) + '">← 앞</a>');
    if (off + 100 < hits.length) h.push('<a class="chip" href="#/names' + qs({ q: q,
      only: only, off: off + 100 }) + '">뒤 →</a>');
    h.push('</div>');

    h.push('<div class="tablewrap"><table class="names"><thead><tr>');
    cols.forEach(function (c) { h.push('<th>' + esc(c) + '</th>'); });
    h.push('</tr></thead><tbody>');
    slice.forEach(function (r) {
      h.push('<tr>');
      cols.forEach(function (c, i) {
        var wide = (c === 'AlgaeBase비고' || c === '근거' || c === '원사유' || c === '내조회');
        var val = r[i] || '';
        var cell = esc(val);
        if (i === iName && val) {
          cell = '<a href="#/' + qs({ q: val }) + '" title="도감 색인에서 찾는다"><i>'
            + esc(val) + '</i></a>';
        }
        h.push('<td' + (wide ? ' class="wrap"' : '') + '>' + cell + '</td>');
      });
      h.push('</tr>');
    });
    h.push('</tbody></table></div>');
    app.innerHTML = h.join('');
    var f = document.getElementById('nform');
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      go('/names', { q: document.getElementById('ninput').value.trim(), only: only });
    });
  }

  /* ── 안내 ──────────────────────────────────────────────────── */

  function viewAbout() {
    var a = META.atlases || [];
    var h = ['<h1>이 꾸러미</h1>'];
    h.push('<p class="note">Diadiction 도감 색인 셋과 학명 대조표를 <b>인터넷도 서버도 없이</b>'
      + ' 볼 수 있게 구운 것이다. <code>index.html</code> 을 브라우저로 열면 된다 —'
      + ' 옆의 <code>data/</code>·<code>pages/</code>·<code>thumbs/</code> 폴더를'
      + ' 함께 들고 다녀야 한다.</p>');
    h.push('<dl class="help">');
    h.push('<dt>판</dt><dd>' + esc(META.version) + ' · 구운 날 ' + esc(META.built) + '</dd>');
    h.push('<dt>도감</dt><dd>');
    a.forEach(function (x) {
      h.push('<div>' + esc(x.title) + ' — 항목 ' + x.count + '개'
        + (x.note ? '<div class="dim">' + mdlite(x.note) + '</div>' : '') + '</div>');
    });
    h.push('</dd>');
    h.push('<dt>도판</dt><dd>' + (META.images
      ? META.page_count + '쪽 · ' + META.dpi + ' dpi JPEG (품질 ' + META.quality + ')'
      : '이 꾸러미에는 없다 (글자만)') + '</dd>');
    if (META.crop_count) {
      h.push('<dt>그림 크롭</dt><dd>' + META.crop_count + '장 — 도판에서 그 종의 그림만 뗀 것.'
        + ' 결과의 <b>그림 보기</b> · 바둑판 칸 · 비교 화면이 쓴다(크롭이 먼저, 없으면 도판 쪽).</dd>');
    }
    h.push('<dt>바둑판 · 비교</dt><dd>색인 결과의 <b>목록 · 바둑판</b> 단추로 오간다.'
      + ' 바둑판 칸의 <b>비교에 담기</b>로 2~' + CMP_MAX + '종을 골라 <b>비교</b>를 누르면'
      + ' 그림·자리·생태·분포·출현·기준면을 한 표에 나란히 놓는다. 담은 것은 검색을 바꿔도 남는다.</dd>');
    h.push('<dt>학명 대조표</dt><dd>' + NAMES.rows.length + '건 · 출처 '
      + esc(META.names_source || '') + '</dd>');
    h.push('<dt>이명 판정 · 출현</dt><dd>학명 유효성 판정 ' + (META.taxa || 0)
      + '건 (AlgaeBase) · 출현 기록 ' + (META.occurrences || 0) + '건.'
      + ' 색인 결과의 항목마다 이명이면 <b>현재 통용 학명</b>을, 분포 문장이 있으면'
      + ' <b>출현</b>(지역 × 문헌)을 함께 낸다 — 서버의 도감 화면과 같다.</dd>');
    h.push('<dt>기준면</dt><dd>생층서 기준면 ' + (META.biodatums || 0) + '행.'
      + ' 종마다 FO·LO 를 어느 문헌이 몇 Ma 로 봤는지 항목 아래에 낸다(전범위 모델은'
      + ' 빼고 평균만). 범위 그림은 서버 화면에만 있다.</dd>');
    h.push('<dt>인용</dt><dd>색인은 OCR 산물이라 <b>표제어를 그대로 인용하지 않는다</b>.'
      + ' 원문 표기가 필요하면 도판 쪽을 열어 눈으로 확인한다.</dd>');
    h.push('<dt>단축키</dt><dd>쪽 보기에서 <kbd>←</kbd> <kbd>→</kbd> 넘기기 ·'
      + ' <kbd>g</kbd> 격자 · <kbd>s</kbd> 한 장/두 쪽 · <kbd>+</kbd> <kbd>-</kbd>'
      + ' <kbd>0</kbd> 확대·맞춤</dd>');
    h.push('</dl>');
    app.innerHTML = h.join('');
  }

  /* ── 라우터 ────────────────────────────────────────────────── */

  function route() {
    hidePreview();
    document.onkeydown = null;
    var r = parseHash();
    var head = r.parts[0] || '';
    window.scrollTo(0, 0);
    if (head === 'book') viewBook(r.parts, r.q);
    else if (head === 'page') viewPage(r.parts, r.q);
    else if (head === 'names') viewNames(r.q);
    else if (head === 'about') viewAbout();
    else if (head === 'compare') viewCompare(r.multi);
    else { lastSearch = location.hash || '#/'; viewSearch(r.q); }
  }
  // 마지막으로 본 검색 결과 — 비교 화면의 「도감」 이 그리로 돌아간다
  var lastSearch = null;

  function start() {
    app = document.getElementById('app');
    preview = document.getElementById('apreview');
    previewImg = document.getElementById('apreview-img');
    previewCap = document.getElementById('apreview-cap');
    document.getElementById('ver').textContent = META.version
      + ' · ' + (META.images ? '완전판' : '글자만');
    // 비교 띠가 머리줄 밑에 붙도록 그 높이를 잰다 — 화면 폭에 따라 줄이 접힌다
    var head = document.querySelector('header.top');
    function headh() {
      if (head) document.documentElement.style.setProperty('--headh', head.offsetHeight + 'px');
    }
    headh();
    window.addEventListener('resize', headh);
    window.addEventListener('hashchange', route);
    route();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else { start(); }
})();
