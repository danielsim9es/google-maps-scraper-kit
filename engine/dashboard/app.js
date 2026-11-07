'use strict';

// The same local engine and optional X-API-Key as the original interface.
const el = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat('pt-BR');
const state = { page: 1, limit: 20, busy: false, revision: 0, map: null, markers: null,
  categoryOptions: [], jobOptions: [], city: null, suggestionsRevision: 0 };
let apiKey = '';
try { apiKey = localStorage.getItem('gmskit-key') || ''; } catch (_) { /* storage disabled */ }

function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'ico');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', '#i-' + name);
  svg.append(use);
  return svg;
}

function notice(message, isError) {
  const box = el('notice');
  if (!message) { box.hidden = true; box.textContent = ''; return; }
  box.hidden = false;
  box.className = 'notice' + (isError ? ' error' : '');
  box.textContent = message;
}

async function request(path, options) {
  const headers = Object.assign({}, options && options.headers);
  if (apiKey) headers['X-API-Key'] = apiKey;
  if (options && options.body) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(path, Object.assign({}, options || {}, { headers }));
  } catch (_) {
    throw new Error('Não foi possível conectar ao motor. Inicie-o em scripts/engine.py start.');
  }
  if (response.status === 401) {
    const dlg = el('key-dialog');
    if (!dlg.open) dlg.showModal();
    throw new Error('Chave da API obrigatória. Informe a chave configurada no motor.');
  }
  if (!response.ok) {
    let message = 'Erro HTTP ' + response.status;
    try { const data = await response.json(); message = data.message || message; } catch (_) { /* not JSON */ }
    throw new Error(message);
  }
  return response;
}

function makeQuery() {
  const params = new URLSearchParams();
  const query = el('q').value.trim();
  const category = el('category').value;
  const job = el('job').value;
  const rating = el('min-rating').value;
  if (query) params.set('q', query);
  if (category) params.set('category', category);
  if (job) params.set('job', job);
  if (rating !== '0') params.set('min_rating', rating);
  if (el('only-email').checked) params.set('email', '1');
  if (el('only-phone').checked) params.set('phone', '1');
  if (el('only-web').checked) params.set('website', '1');
  params.set('sort', el('sort').value);
  params.set('page', String(state.page));
  params.set('limit', String(state.limit));
  return params.toString();
}

function setOptions(select, items, keyName, labelName) {
  const selected = select.value;
  select.replaceChildren();
  const initial = document.createElement('option');
  initial.value = '';
  initial.textContent = keyName === 'id' ? 'Todas as coletas' : 'Todos os segmentos';
  select.append(initial);
  items.forEach((item) => {
    const opt = document.createElement('option');
    opt.value = keyName ? item[keyName] : item;
    opt.textContent = labelName ? item[labelName] : item;
    select.append(opt);
  });
  if ([...select.options].some((opt) => opt.value === selected)) select.value = selected;
}

function renderKPIs(s) {
  el('kpi-total').textContent = fmt.format(s.total);
  el('kpi-email').textContent = fmt.format(s.with_email);
  el('kpi-phone').textContent = fmt.format(s.with_phone);
  el('kpi-web').textContent = fmt.format(s.with_website);
  el('email-pct').textContent = String(s.email_coverage).replace('.', ',') + '%';
  el('phone-pct').textContent = String(s.phone_coverage).replace('.', ',') + '%';
  el('kpi-rating').textContent = s.average_rating === null ? 'Sem' : String(s.average_rating).replace('.', ',') + '/5';
  el('table-count').textContent = fmt.format(s.total);
  if (s.partial) {
    notice('Visualização parcial: o painel analisou os primeiros ' + fmt.format(s.scanned) +
      ' registros. Refine os filtros ou divida as pesquisas em projetos menores.', false);
  }
  if (!state.categoryOptions.length && s.options.categories.length) {
    state.categoryOptions = s.options.categories;
    setOptions(el('category'), state.categoryOptions);
  }
  if (!state.jobOptions.length && s.options.jobs.length) {
    state.jobOptions = s.options.jobs;
    setOptions(el('job'), state.jobOptions, 'id', 'name');
  }
}

function renderCategoryChart(categories) {
  const target = el('category-chart');
  target.replaceChildren();
  if (!categories.length) {
    const p = document.createElement('p'); p.className = 'empty-mini';
    p.textContent = 'Sem segmentos nos resultados filtrados.'; target.append(p); return;
  }
  const maximum = Math.max(...categories.map((item) => item.count), 1);
  categories.forEach(({ name, count }) => {
    const row = document.createElement('div'); row.className = 'cat-row';
    const meta = document.createElement('div'); meta.className = 'cat-meta';
    const title = document.createElement('span'); title.className = 'cat-name';
    title.textContent = name; title.title = name;
    const number = document.createElement('strong'); number.className = 'cat-count';
    number.textContent = fmt.format(count);
    meta.append(title, number);
    const track = document.createElement('div'); track.className = 'cat-track';
    const fill = document.createElement('div'); fill.className = 'cat-fill';
    fill.style.width = (count / maximum * 100).toFixed(1) + '%';
    track.append(fill); row.append(meta, track); target.append(row);
  });
}

function renderRatings(buckets) {
  const target = el('rating-chart'); target.replaceChildren();
  const max = Math.max(1, ...buckets.map((v) => v.count));
  buckets.forEach((bucket) => {
    const bar = document.createElement('div'); bar.className = 'rating-bar';
    bar.style.setProperty('--height', Math.max(bucket.count ? 7 : 3, (bucket.count / max) * 100) + '%');
    bar.title = bucket.bucket + ' estrela(s): ' + fmt.format(bucket.count);
    bar.setAttribute('aria-label', bar.title);
    target.append(bar);
  });
}

function validWebsite(url) {
  if (!url) return null;
  const raw = String(url).trim();
  if (!raw || /[\u0000-\u001f]/.test(raw)) return null;
  try {
    const candidate = new URL(/^https?:\/\//i.test(raw) ? raw : 'https://' + raw);
    return ['https:', 'http:'].includes(candidate.protocol) && candidate.hostname ? candidate.href : null;
  } catch (_) { return null; }
}

function textCell(tr, text, className) {
  const td = document.createElement('td');
  if (className) td.className = className;
  td.textContent = text;
  tr.append(td);
  return td;
}

function appendContact(target, value, kind) {
  const line = document.createElement('div'); line.className = 'contact-line';
  line.append(icon(kind));
  if (!value) {
    const label = document.createElement('span'); label.className = 'missing';
    label.textContent = 'Não informado'; line.append(label);
  } else {
    const text = kind === 'mail' ? String(value).split(/[;,]/)[0].trim() : String(value).trim();
    const link = document.createElement('a'); link.textContent = text;
    if (kind === 'phone') {
      const phone = text.replace(/[^\d+]/g, '');
      if (phone.length >= 6 && phone.length <= 20) link.href = 'tel:' + phone;
    } else if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text)) {
      link.href = 'mailto:' + encodeURIComponent(text).replace('%40', '@');
    }
    line.append(link);
  }
  target.append(line);
}

function renderLeads(result) {
  const target = el('leads-body'); target.replaceChildren();
  const total = result.total;
  if (!result.items.length) {
    const tr = document.createElement('tr');
    textCell(tr, total ? 'Nenhum resultado nesta página.' : 'Nenhuma empresa encontrada. Faça uma nova coleta ou ajuste os filtros.', 'table-empty').colSpan = 5;
    target.append(tr);
  }
  result.items.forEach((lead) => {
    const tr = document.createElement('tr');
    const company = document.createElement('td');
    const name = document.createElement('div'); name.className = 'company-name';
    name.textContent = lead.title || 'Empresa sem nome';
    const sub = document.createElement('div'); sub.className = 'company-sub'; sub.textContent = lead.source_job || 'Coleta';
    company.append(name, sub); tr.append(company);
    const segment = document.createElement('td');
    const pill = document.createElement('span'); pill.className = 'category-badge';
    pill.textContent = lead.category || 'Não informado';
    const address = document.createElement('div'); address.className = 'address';
    address.textContent = lead.address || 'Endereço não informado';
    segment.append(pill, address); tr.append(segment);
    const contact = document.createElement('td');
    appendContact(contact, lead.phone, 'phone');
    appendContact(contact, lead.emails, 'mail');
    tr.append(contact);
    const rating = document.createElement('td');
    if (lead.review_rating !== null) {
      const stars = document.createElement('span'); stars.className = 'star-rating';
      stars.append(icon('star'));
      const value = document.createElement('span'); value.textContent = lead.review_rating.toFixed(1).replace('.', ',');
      stars.append(value); rating.append(stars);
      const count = document.createElement('div'); count.className = 'review-count';
      count.textContent = fmt.format(lead.review_count) + ' avaliações'; rating.append(count);
    } else { rating.textContent = '—'; rating.className = 'missing'; }
    tr.append(rating);
    const website = document.createElement('td'); const url = validWebsite(lead.website);
    if (url) {
      const link = document.createElement('a'); link.href = url; link.target = '_blank';
      link.rel = 'noopener noreferrer'; link.className = 'website-link';
      link.textContent = 'Visitar site ↗'; website.append(link);
    } else { website.textContent = 'Não informado'; website.className = 'missing'; }
    tr.append(website); target.append(tr);
  });
  const pages = Math.max(1, Math.ceil(total / state.limit));
  el('page-label').textContent = state.page + ' / ' + pages;
  el('prev').disabled = state.page <= 1;
  el('next').disabled = !result.has_more;
  const from = total ? (state.page - 1) * state.limit + 1 : 0;
  const to = Math.min(total, state.page * state.limit);
  el('table-meta').textContent = 'Exibindo ' + fmt.format(from) + '–' + fmt.format(to) +
    ' de ' + fmt.format(total) + ' empresas';
}

function mapPopup(point) {
  const block = document.createElement('div');
  const strong = document.createElement('strong'); strong.textContent = point.title || 'Empresa'; block.append(strong);
  const category = document.createElement('p'); category.textContent = point.category || 'Sem segmento'; block.append(category);
  if (point.address) {
    const address = document.createElement('p'); address.textContent = point.address; block.append(address);
  }
  const website = validWebsite(point.website);
  if (website) {
    const link = document.createElement('a'); link.href = website; link.target = '_blank';
    link.rel = 'noopener noreferrer'; link.textContent = 'Abrir website ↗'; block.append(link);
  }
  return block;
}

function renderMap(data) {
  el('map-count').textContent = fmt.format(data.total);
  const empty = el('map-empty');
  if (!data.points.length) { empty.hidden = false; if (state.markers) state.markers.clearLayers(); return; }
  if (!window.L) {
    empty.hidden = false;
    empty.querySelector('strong').textContent = 'Mapa indisponível';
    empty.querySelector('p').textContent = 'A biblioteca Leaflet requer acesso à internet. A lista de empresas continua disponível.';
    return;
  }
  empty.hidden = true;
  if (!state.map) {
    state.map = L.map('map', { zoomControl: true, scrollWheelZoom: false, preferCanvas: true });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '© OpenStreetMap contributors', updateWhenIdle: true,
    }).addTo(state.map);
    state.markers = L.layerGroup().addTo(state.map);
  }
  state.markers.clearLayers();
  const coords = [];
  const pin = L.divIcon({ className: '', html: '<div class="lead-pin"></div>', iconSize: [17, 17], iconAnchor: [8, 8] });
  data.points.forEach((p) => {
    const latLng = [p.latitude, p.longitude];
    coords.push(latLng);
    L.marker(latLng, { icon: pin }).bindPopup(mapPopup(p), { maxWidth: 265 }).addTo(state.markers);
  });
  if (coords.length === 1) state.map.setView(coords[0], 12);
  else state.map.fitBounds(coords, { padding: [32, 32], maxZoom: 13 });
  state.map.invalidateSize();
}

function renderJobs(jobs) {
  const area = el('jobs-list'); area.replaceChildren();
  const health = el('engine-status');
  health.textContent = jobs.some((job) => job.Status === 'working') ? 'Coleta em andamento' : 'Conectado e pronto';
  if (!jobs.length) { const p = document.createElement('p'); p.className = 'empty-mini'; p.textContent = 'Ainda não há coletas. Use “Nova pesquisa” para começar.'; area.append(p); return; }
  const translate = { ok: 'Concluída', working: 'Executando', pending: 'Na fila', failed: 'Falhou' };
  jobs.slice(0, 7).forEach((job) => {
    const row = document.createElement('div'); row.className = 'job-item';
    const copy = document.createElement('div');
    const title = document.createElement('div'); title.className = 'job-title'; title.textContent = job.Name;
    const progress = job.Progress || {};
    const date = new Date(job.Date);
    const meta = document.createElement('div'); meta.className = 'job-meta';
    meta.textContent = (Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('pt-BR') + ' · ') +
      (progress.places || 0) + ' empresas' + (job.Error ? ' · ' + job.Error : '');
    copy.append(title, meta);
    const badge = document.createElement('span'); badge.className = 'job-status ' + (job.Status || '');
    badge.textContent = translate[job.Status] || job.Status;
    const track = document.createElement('div'); track.className = 'job-progress';
    const fill = document.createElement('span'); fill.style.width =
      String(Math.max(0, Math.min(100, Number(progress.percent) || 0))) + '%';
    track.append(fill); row.append(copy, badge, track); area.append(row);
  });
}

async function refresh() {
  const version = ++state.revision;
  const refreshBtn = el('refresh-btn');
  refreshBtn.disabled = true;
  try {
    const [dataResponse, jobsResponse] = await Promise.all([
      request('/api/v1/dashboard?' + makeQuery()), request('/api/v1/jobs')
    ]);
    const [data, jobs] = await Promise.all([dataResponse.json(), jobsResponse.json()]);
    if (version !== state.revision) return;
    notice('');
    renderKPIs(data.summary); renderCategoryChart(data.summary.categories);
    renderRatings(data.summary.rating_distribution); renderLeads(data.leads); renderMap(data.map);
    renderJobs(jobs || []);
    el('engine-status').parentElement.parentElement.querySelector('.status-indicator').classList.remove('off');
  } catch (err) {
    if (version !== state.revision) return;
    notice(err.message || 'Falha ao carregar os dados.', true);
    el('engine-status').textContent = 'Sem conexão';
    el('engine-status').parentElement.parentElement.querySelector('.status-indicator').classList.add('off');
  } finally { refreshBtn.disabled = false; }
}

function resetPageAndRefresh() { state.page = 1; refresh(); }
let filterTimer;
el('filters').addEventListener('submit', (event) => event.preventDefault());
el('q').addEventListener('input', () => { clearTimeout(filterTimer); filterTimer = setTimeout(resetPageAndRefresh, 320); });
for (const id of ['category', 'job', 'min-rating', 'only-email', 'only-phone', 'only-web', 'sort']) {
  el(id).addEventListener('change', resetPageAndRefresh);
}
el('clear-filters').addEventListener('click', () => {
  el('q').value = ''; el('category').value = ''; el('job').value = '';
  el('min-rating').value = '0'; el('sort').value = 'newest';
  for (const id of ['only-email', 'only-phone', 'only-web']) el(id).checked = false;
  resetPageAndRefresh();
});
el('prev').addEventListener('click', () => { if (state.page > 1) { state.page--; refresh(); } });
el('next').addEventListener('click', () => { state.page++; refresh(); });
el('refresh-btn').addEventListener('click', refresh);

async function download(format) {
  try {
    const response = await request('/api/v1/dashboard/export?' + makeQuery() + '&format=' + format);
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = objectUrl;
    link.download = 'prospect-intelligence-' + new Date().toISOString().slice(0, 10) + '.' + format;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 5000);
  } catch (err) { notice(err.message, true); }
}
el('export-csv').addEventListener('click', () => download('csv'));
el('export-json').addEventListener('click', () => download('json'));

function showCreate() { el('new-search-dialog').showModal(); el('search-keyword').focus(); }
for (const id of ['top-create', 'jobs-new']) el(id).addEventListener('click', showCreate);
for (const id of ['dialog-close', 'dialog-cancel']) {
  el(id).addEventListener('click', () => el('new-search-dialog').close());
}

function createMessage(text, isError) {
  el('create-msg').textContent = text;
  el('create-msg').style.color = isError ? '#ffb5b5' : '#a4f3cb';
}
let cityTimer;
el('search-city').addEventListener('input', () => {
  state.city = null;
  const value = el('search-city').value.trim();
  clearTimeout(cityTimer);
  if (value.length < 2) { el('city-suggestions').hidden = true; return; }
  const current = ++state.suggestionsRevision;
  cityTimer = setTimeout(async () => {
    try {
      const response = await request('/api/v1/cities?q=' + encodeURIComponent(value));
      const results = await response.json();
      if (current !== state.suggestionsRevision) return;
      const list = el('city-suggestions'); list.replaceChildren();
      (results || []).slice(0, 7).forEach((city) => {
        const btn = document.createElement('button'); btn.type = 'button'; btn.textContent = city.label;
        btn.addEventListener('click', () => {
          state.city = city; el('search-city').value = city.label;
          list.hidden = true; createMessage('Cidade selecionada: ' + city.label, false);
        });
        list.append(btn);
      });
      list.hidden = !list.childElementCount;
    } catch (err) { createMessage(err.message, true); }
  }, 250);
});

el('new-search-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const keyword = el('search-keyword').value.trim();
  if (!keyword || !state.city) { createMessage('Informe o segmento e escolha uma cidade sugerida.', true); return; }
  const city = state.city;
  const submit = el('dialog-submit'); submit.disabled = true;
  const body = {
    name: keyword + ' · ' + city.label,
    keywords: [keyword + ' in ' + city.label],
    lat: String(city.lat), lon: String(city.lon),
    country: city.country || '', lang: 'pt',
    depth: Number(el('search-depth').value),
    max_time: Number(el('search-time').value),
    email: el('search-emails').checked,
    socials: el('search-socials').checked,
  };
  try {
    await request('/api/v1/jobs', { method: 'POST', body: JSON.stringify(body) });
    el('new-search-dialog').close(); el('new-search-form').reset(); state.city = null;
    el('city-suggestions').hidden = true;
    notice('Coleta iniciada. Os resultados aparecerão à medida que o motor finalizar os registros.', false);
    await refresh();
  } catch (err) { createMessage(err.message, true); }
  finally { submit.disabled = false; }
});

el('key-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  apiKey = el('key-input').value.trim();
  try { localStorage.setItem('gmskit-key', apiKey); } catch (_) { /* optional */ }
  el('key-dialog').close();
  await refresh();
});

refresh();
setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, 20000);