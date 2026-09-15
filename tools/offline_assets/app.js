/* Diadiction 오프라인 꾸러미 — 화면 하나(`index.html`)가 해시로 갈린다.
 *
 * **자료는 `<script src>` 로 온다.** `file://` 에서는 `fetch` 가 막혀
 * (브라우저가 로컬 파일을 다른 출처로 본다) JSON 을 못 읽는다 — 그래서
 * `data/*.js` 가 전역에 값을 놓는 모양이다. 웹서버 없이 열리는 것이 이
 * 꾸러미의 존재 이유라 여기서 물러설 수 없다.
 *
 * 규칙은 뷰어에서 그대로 가져왔다 — 검색 셋(표제어·이명법·속) · 이명의 현재
 * 학명으로도 찾기(P24) · 권역(한국·남극·전역, 196) · 속 고르는 목록 · 자동완성 ·
 * 한 판 50줄 · 격자 60칸 · 펼침의 좌우 판정. **굽는 쪽(`tools/build_offline_atlas.py`)이
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
    var p = {};
    if (i >= 0) {
      h.slice(i + 1).split('&').forEach(function (pair) {
        if (!pair) return;
        var j = pair.indexOf('=');
        var k = decodeURIComponent(j < 0 ? pair : pair.slice(0, j));
        p[k] = decodeURIComponent(j < 0 ? '' : pair.slice(j + 1).replace(/\+/g, ' '));
      });
    }
    return { parts: path.split('/').filter(Boolean), q: p };
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
        + '>' + esc(g) + ' (' + gc[g] + ')</option>');
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
    h.push(pager);
    if (!rows.length) {
      h.push('<p class="warn">찾은 것이 없습니다. <b>도감에 없는 것</b>일 수도, '
        + '<b>표기가 달라 안 걸린 것</b>일 수도 있습니다 — 도감은 옛 표기를 쓰고'
        + ' (<i>Actinocyclus Ehrenbergii</i>) Schmidt 는 전량 OCR 입니다.'
        + ' 속만으로 다시 찾아 보세요.</p>');
    }
    rows.forEach(function (e) { h.push(entryHtml(e)); });
    h.push(pager);
    app.innerHTML = h.join('');
    wireSearchForm(akey, genus, area);
    bindPreview(app);
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
    h.push('<dt>학명 대조표</dt><dd>' + NAMES.rows.length + '건 · 출처 '
      + esc(META.names_source || '') + '</dd>');
    h.push('<dt>이명 판정 · 출현</dt><dd>학명 유효성 판정 ' + (META.taxa || 0)
      + '건 (AlgaeBase) · 출현 기록 ' + (META.occurrences || 0) + '건.'
      + ' 색인 결과의 항목마다 이명이면 <b>현재 통용 학명</b>을, 분포 문장이 있으면'
      + ' <b>출현</b>(지역 × 문헌)을 함께 낸다 — 서버의 도감 화면과 같다.</dd>');
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
    else viewSearch(r.q);
  }

  function start() {
    app = document.getElementById('app');
    preview = document.getElementById('apreview');
    previewImg = document.getElementById('apreview-img');
    previewCap = document.getElementById('apreview-cap');
    document.getElementById('ver').textContent = META.version
      + ' · ' + (META.images ? '완전판' : '글자만');
    window.addEventListener('hashchange', route);
    route();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else { start(); }
})();
