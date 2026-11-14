(function () {
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  var btn = $('.menu-btn'), nav = $('#nav');
  if (btn) btn.addEventListener('click', function () {
    var open = nav.classList.toggle('open'); btn.setAttribute('aria-expanded', open);
  });

  function label(el) {
    var l = $('label[for="' + el.id + '"]'); return l ? l.textContent.replace('*', '').trim() : 'This field';
  }
  function message(el) {
    var v = el.validity, n = label(el);
    if (el.dataset.match && el.value !== $('[name="' + el.dataset.match + '"]', el.form).value) return 'Passwords do not match.';
    if (v.valueMissing) return n + ' is required.';
    if (v.typeMismatch) return 'Enter a valid ' + (el.type === 'email' ? 'email address.' : 'value.');
    if (v.patternMismatch) return el.dataset.hint || 'Invalid format.';
    if (v.tooShort) return n + ' must be at least ' + el.minLength + ' characters.';
    if (v.rangeUnderflow || v.rangeOverflow) return n + ' must be between ' + el.min + ' and ' + el.max + '.';
    if (v.badInput) return 'Enter a valid value.';
    return '';
  }
  function check(el) {
    var msg = message(el), box = $('.err[data-for="' + el.name + '"]', el.form);
    if (box) box.textContent = msg;
    if (el.parentNode) el.parentNode.classList.toggle('has-error', !!msg);
    return !msg;
  }
  $$('form.form').forEach(function (f) {
    var fields = $$('input:not([type=hidden]), select, textarea', f);
    f.addEventListener('submit', function (e) {
      var first = null;
      fields.forEach(function (el) { if (!check(el) && !first) first = el; });
      if (first) { e.preventDefault(); first.focus(); }
    });
    fields.forEach(function (el) {
      el.addEventListener('blur', function () { if (el.value) check(el); });
      el.addEventListener('input', function () { if (el.parentNode.classList.contains('has-error')) check(el); });
    });
  });

  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (f.dataset && f.dataset.confirm && !confirm(f.dataset.confirm)) e.preventDefault();
  });

  function fillDemo(row) {
    var f = $('form.authform'); if (!f) return;
    f.elements.email.value = row.dataset.email; f.elements.password.value = row.dataset.password;
    $$('tr.pick').forEach(function (r) { r.classList.toggle('picked', r === row); });
    f.scrollIntoView({ behavior: 'smooth', block: 'center' }); f.elements.password.focus();
  }
  document.addEventListener('click', function (e) { var r = e.target.closest && e.target.closest('tr.pick'); if (r) fillDemo(r); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Enter' && e.target.classList && e.target.classList.contains('pick')) fillDemo(e.target); });

  $$('select[data-autosubmit]').forEach(function (s) { s.addEventListener('change', function () { s.form.submit(); }); });

  $$('[data-live]').forEach(function (box) {
    var ms = parseInt(box.dataset.interval, 10) || 10000;
    setInterval(function () {
      var a = document.activeElement;
      if (document.hidden || box.querySelector('details[open]') || (a && box.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName))) return;
      fetch(box.dataset.live, { credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
        .then(function (r) { return r.ok && r.headers.get('X-Live') === '1' ? r.text() : null; })
        .then(function (html) { if (html !== null) box.innerHTML = html; })
        .catch(function () {});
    }, ms);
  });

  $$('.filter').forEach(function (inp) {
    inp.addEventListener('input', function () {
      var t = inp.value.toLowerCase();
      $$(inp.dataset.table + ' tbody tr').forEach(function (r) { r.style.display = r.textContent.toLowerCase().indexOf(t) > -1 ? '' : 'none'; });
    });
  });

  // disable the submit button after the first click so a request is never sent twice
  $$('form[data-once]').forEach(function (f) {
    f.addEventListener('submit', function (e) {
      if (e.defaultPrevented) return;
      var b = $('button:not([type=button])', f); if (b) setTimeout(function () { b.disabled = true; }, 0);
    });
  });

  // show the fixed price of the chosen Ayushman package
  $$('select[data-rate]').forEach(function (s) {
    var out = $('#pkg-rate');
    function show() { var o = s.options[s.selectedIndex]; out.textContent = o && o.dataset.rate ? '\u20b9' + Number(o.dataset.rate).toLocaleString('en-IN') : '\u2013'; }
    s.addEventListener('change', show); show();
  });

  // discharge page: who pays what, while typing (nothing is saved)
  $$('form[data-preview]').forEach(function (f) {
    var box = $('#split'), warn = $('#split-warn'), err = $('#split-err'), timer, seq = 0;
    if (!box) return;
    function money(v) { return '\u20b9' + Number(v).toLocaleString('en-IN'); }
    function run() {
      var bill = f.elements.finalBill.value.trim(), non = (f.elements.nonPayable.value.trim() || '0');
      if (!/^\d+$/.test(bill) || +bill < 1 || !/^\d+$/.test(non)) { box.hidden = true; err.textContent = ''; return; }
      var mine = ++seq;
      fetch(f.dataset.preview + '?finalBill=' + bill + '&nonPayable=' + non, { credentials: 'same-origin' })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (mine !== seq) return;
          if (!res.ok) { box.hidden = true; err.textContent = res.d.error || 'Could not calculate the split.'; return; }
          err.textContent = '';
          $$('[data-split]', box).forEach(function (el) { var v = res.d[el.dataset.split]; el.textContent = el.dataset.suffix ? v + el.dataset.suffix : money(v); });
          warn.hidden = !res.d.provisional; box.hidden = false;
        }).catch(function () { if (mine === seq) { box.hidden = true; err.textContent = 'Could not reach the claims service.'; } });
    }
    f.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 400); });
  });

  setTimeout(function () { $$('.flash.ok, .flash.info').forEach(function (f) { f.style.display = 'none'; }); }, 7000);
})();
