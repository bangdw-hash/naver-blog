// ══════════════════════════════════════════════════════════════
//  food_tab.js - 맛집 탐방 탭 전용 스크립트
// ══════════════════════════════════════════════════════════════

// ── 탭 내부 요소 헬퍼 ─────────────────────────────────────────
function getFoodTab(btn) {
  return btn.closest('.food-tab-content');
}

// ── 네이버 장소 검색 ──────────────────────────────────────────
async function searchPlace(btn) {
  const tab   = getFoodTab(btn);
  const query = tab.querySelector('.place-query').value.trim();
  if (!query) { showToast('음식점 이름을 입력하세요.', 'warn'); return; }

  const listEl = tab.querySelector('.place-results');
  listEl.innerHTML = '<div class="place-loading"><i class="bi bi-search"></i> 검색 중...</div>';

  try {
    const res  = await fetch('/api/search-place', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    const data = await res.json();
    const items = data.items || [];

    if (!items.length || items[0].error) {
      listEl.innerHTML = '<div class="place-empty">검색 결과 없음</div>';
      return;
    }

    listEl.innerHTML = items.map((item, i) => `
      <div class="place-item" onclick="selectPlace(this)" data-idx="${i}"
        data-name="${escHtml(item.title)}"
        data-addr="${escHtml(item.address)}"
        data-road="${escHtml(item.road)}"
        data-link="${escHtml(item.link)}"
        data-tel="${escHtml(item.telephone)}"
        data-cat="${escHtml(item.category)}"
        data-mapx="${item.mapx}"
        data-mapy="${item.mapy}">
        <div class="pi-name"><i class="bi bi-shop"></i> ${escHtml(item.title)}</div>
        <div class="pi-meta">
          <span><i class="bi bi-geo-alt"></i>${escHtml(item.road || item.address)}</span>
          ${item.category ? `<span class="nb-tag g">${escHtml(item.category)}</span>` : ''}
          ${item.telephone ? `<span><i class="bi bi-telephone"></i>${escHtml(item.telephone)}</span>` : ''}
        </div>
        ${item.link ? `<a class="map-link" href="${escHtml(item.link)}" target="_blank" onclick="event.stopPropagation()"><i class="bi bi-map"></i> 네이버 지도↗</a>` : ''}
      </div>`).join('');
  } catch(e) {
    listEl.innerHTML = `<div class="place-empty">오류: ${e.message}</div>`;
  }
}

function selectPlace(el) {
  const tab = el.closest('.food-tab-content');
  // 선택 표시
  tab.querySelectorAll('.place-item').forEach(p => p.classList.remove('selected'));
  el.classList.add('selected');

  // 선택된 장소 정보 채우기
  const name = el.dataset.name;
  const addr = el.dataset.road || el.dataset.addr;
  const link = el.dataset.link;
  const tel  = el.dataset.tel;
  const cat  = el.dataset.cat;

  tab.querySelector('.selected-name').textContent  = name || '-';
  tab.querySelector('.selected-addr').textContent  = addr || '-';
  tab.querySelector('.selected-tel').textContent   = tel  || '-';
  tab.querySelector('.selected-cat').textContent   = cat  || '-';
  tab.querySelector('.selected-link').href         = link || '#';
  tab.querySelector('.selected-link').style.display= link ? '' : 'none';

  // hidden inputs
  tab.querySelector('.inp-place-name').value = name || '';
  tab.querySelector('.inp-place-addr').value = el.dataset.addr || '';
  tab.querySelector('.inp-place-road').value = el.dataset.road || '';
  tab.querySelector('.inp-place-link').value = link || '';
  tab.querySelector('.inp-place-tel').value  = tel  || '';
  tab.querySelector('.inp-place-cat').value  = cat  || '';
  tab.querySelector('.inp-mapx').value       = el.dataset.mapx || '';
  tab.querySelector('.inp-mapy').value       = el.dataset.mapy || '';

  tab.querySelector('.place-selected-box').style.display = '';
  showToast(name + ' 선택됨');
}

// ── 별점 입력 ──────────────────────────────────────────────────
function setRating(stars, type) {
  const tab = stars.closest('.food-tab-content');
  const allStars = tab.querySelectorAll(`.star-group[data-type="${type}"] .star`);
  const idx = parseInt(stars.dataset.val);
  tab.querySelector(`.inp-rating-${type}`).value = idx;

  allStars.forEach((s, i) => {
    s.classList.toggle('active', i < idx);
  });
}

function initStars(tab) {
  tab.querySelectorAll('.star-group').forEach(group => {
    const type = group.dataset.type;
    group.querySelectorAll('.star').forEach((star, i) => {
      star.dataset.val = i + 1;
      star.addEventListener('click', () => setRating(star, type));
      star.addEventListener('mouseenter', () => {
        group.querySelectorAll('.star').forEach((s, j) => s.classList.toggle('hover', j <= i));
      });
    });
    group.addEventListener('mouseleave', () => {
      group.querySelectorAll('.star').forEach(s => s.classList.remove('hover'));
    });
  });
}

// ── 사진 업로드 ───────────────────────────────────────────────
const foodPhotoStore = {};  // tabId → [{filename, url, storage}]

async function handleFoodPhotos(input, tabId) {
  const tab      = document.querySelector(`.food-tab-content[data-tab-id="${tabId}"]`);
  const storage  = tab.querySelector('.photo-storage-sel')?.value || 'supabase';
  const placeName= tab.querySelector('.inp-place-name').value || 'food';
  const visitDate= tab.querySelector('.inp-visit-date').value || '';
  const grid     = tab.querySelector('.photo-grid');
  const stat     = tab.querySelector('.photo-status');

  if (!foodPhotoStore[tabId]) foodPhotoStore[tabId] = [];

  const files = Array.from(input.files);
  if (!files.length) return;

  if (stat) stat.textContent = `${files.length}장 업로드 중...`;

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const fd   = new FormData();
    fd.append('file', file);
    fd.append('storage', storage);
    fd.append('place_name', placeName);
    fd.append('visit_date', visitDate);
    fd.append('index', String(foodPhotoStore[tabId].length + 1));

    try {
      const res  = await fetch('/api/upload-photo', { method: 'POST', body: fd });
      const data = await res.json();

      if (data.error) {
        if (stat) stat.textContent = `오류: ${data.error}`;
        continue;
      }

      foodPhotoStore[tabId].push(data);
      addPhotoCard(grid, data, tabId, foodPhotoStore[tabId].length - 1);
      if (stat) stat.textContent = `${i + 1}/${files.length} 업로드 완료`;
    } catch(e) {
      if (stat) stat.textContent = `오류: ${e.message}`;
    }
  }

  updatePhotoHidden(tab, tabId);
  if (stat) stat.innerHTML = `<span style="color:var(--primary)">✓ ${foodPhotoStore[tabId].length}장 업로드 완료</span>`;
  showToast(`사진 ${files.length}장 업로드 완료!`);
}

function addPhotoCard(grid, photo, tabId, idx) {
  const card = document.createElement('div');
  card.className = 'photo-card';
  card.innerHTML = `
    <div class="photo-thumb" style="background:var(--bg);display:flex;align-items:center;justify-content:center;height:90px;border-radius:8px;overflow:hidden;margin-bottom:6px;">
      ${photo.url ? `<img src="${escHtml(photo.url)}" alt="food" style="width:100%;height:100%;object-fit:cover;">`
                  : `<i class="bi bi-image" style="font-size:28px;color:var(--text-xs)"></i>`}
    </div>
    <div class="photo-filename" title="${escHtml(photo.filename)}" style="font-size:11px;color:var(--text-xs);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:4px;">${escHtml(photo.filename)}</div>
    <div style="display:flex;gap:4px;">
      <button class="nb-btn nb-btn-outline nb-btn-sm" style="flex:1;font-size:11px;padding:4px 6px;" onclick="copyPhotoUrl('${escHtml(photo.url)}')">
        <i class="bi bi-link-45deg"></i> 링크
      </button>
      <button class="nb-btn nb-btn-outline nb-btn-sm" style="flex:1;font-size:11px;padding:4px 6px;" onclick="downloadPhoto('${escHtml(photo.url)}','${escHtml(photo.filename)}')">
        <i class="bi bi-download"></i>
      </button>
      <button class="nb-btn nb-btn-danger nb-btn-sm" style="padding:4px 7px;font-size:11px;" onclick="removePhoto(this,'${tabId}',${idx})">
        <i class="bi bi-x"></i>
      </button>
    </div>`;
  grid.appendChild(card);
}

function copyPhotoUrl(url) {
  navigator.clipboard.writeText(url).then(() => showToast('링크 복사됨!'));
}

async function downloadPhoto(url, filename) {
  try {
    const a = document.createElement('a');
    a.href     = `/api/download-photo?url=${encodeURIComponent(url)}&name=${encodeURIComponent(filename)}`;
    a.download = filename;
    a.click();
    showToast('다운로드 시작!');
  } catch(e) { showToast('다운로드 오류', 'error'); }
}

function removePhoto(btn, tabId, idx) {
  foodPhotoStore[tabId].splice(idx, 1);
  const tab  = document.querySelector(`.food-tab-content[data-tab-id="${tabId}"]`);
  const grid = tab.querySelector('.photo-grid');
  // 그리드 재렌더
  grid.innerHTML = '';
  foodPhotoStore[tabId].forEach((p, i) => addPhotoCard(grid, p, tabId, i));
  updatePhotoHidden(tab, tabId);
}

function updatePhotoHidden(tab, tabId) {
  const inp = tab.querySelector('.inp-photos');
  if (inp) inp.value = JSON.stringify(foodPhotoStore[tabId] || []);
}

async function copyAllPhotoUrls(btn) {
  const tab   = getFoodTab(btn);
  const tabId = tab.dataset.tabId;
  const photos= foodPhotoStore[tabId] || [];
  if (!photos.length) { showToast('업로드된 사진이 없습니다.', 'warn'); return; }
  const text  = photos.map((p, i) => `[사진${i+1}] ${p.url}`).join('\n');
  navigator.clipboard.writeText(text).then(() => showToast(`${photos.length}개 링크 복사됨!`));
}

async function downloadAllPhotos(btn) {
  const tab   = getFoodTab(btn);
  const tabId = tab.dataset.tabId;
  const photos= foodPhotoStore[tabId] || [];
  if (!photos.length) { showToast('다운로드할 사진이 없습니다.', 'warn'); return; }

  for (const p of photos) {
    await downloadPhoto(p.url, p.filename);
    await new Promise(r => setTimeout(r, 400)); // 연속 다운로드 딜레이
  }
}

// ── AI 맛집 글 생성 ───────────────────────────────────────────
async function generateFoodContent(btn) {
  const tab   = getFoodTab(btn);
  const tabId = tab.dataset.tabId;

  const placeName = tab.querySelector('.inp-place-name').value;
  if (!placeName) { showToast('음식점을 검색하고 선택해주세요.', 'warn'); return; }

  const jobId = 'food_' + tabId + '_' + Date.now();
  const prog  = tab.querySelector('.food-gen-progress');
  const stat  = tab.querySelector('.food-gen-status');
  if (prog) prog.style.display = '';
  if (stat) stat.textContent = '';
  btn.disabled = true;

  const payload = {
    job_id:       jobId,
    place_name:   placeName,
    place_addr:   tab.querySelector('.inp-place-addr').value,
    place_road:   tab.querySelector('.inp-place-road').value,
    place_link:   tab.querySelector('.inp-place-link').value,
    place_tel:    tab.querySelector('.inp-place-tel').value,
    place_cat:    tab.querySelector('.inp-place-cat').value,
    mapx:         tab.querySelector('.inp-mapx').value,
    mapy:         tab.querySelector('.inp-mapy').value,
    visit_date:   tab.querySelector('.inp-visit-date').value,
    rating_taste: parseInt(tab.querySelector('.inp-rating-taste').value || 3),
    rating_mood:  parseInt(tab.querySelector('.inp-rating-mood').value  || 3),
    price_range:  tab.querySelector('.inp-price-range').value,
    revisit:      tab.querySelector('.inp-revisit').value,
    party_size:   tab.querySelector('.inp-party-size').value,
    memo:         tab.querySelector('.inp-memo').value,
    photos:       foodPhotoStore[tabId] || [],
  };

  await fetch('/api/generate-food', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  watchProgress(jobId, (msg, done) => {
    try {
      const p = JSON.parse(msg);
      if (p.error) {
        if (stat) stat.textContent = '오류: ' + p.error;
        if (prog) prog.style.display = 'none';
        btn.disabled = false;
        return;
      }
      if (p.result) {
        const r = p.result;
        tab.querySelector('.food-title').value   = r.title   || '';
        tab.querySelector('.food-content').value = r.content || '';
        tab.querySelector('.food-tags').value    = (r.tags || []).join(', ');
        tab.querySelector('.food-post-id').value = r.post_id || '';
        if (stat) stat.innerHTML = '<span style="color:var(--primary)">✓ 글 생성 완료</span>';
        if (prog) prog.style.display = 'none';
        btn.disabled = false;

        // 탭 레이블 업데이트
        const pill = document.querySelector(`.tab-pill[data-tab-id="${tabId}"] .tab-label`);
        if (pill && r.title) pill.textContent = '🍜 ' + (r.title.slice(0, 12) || placeName);

        // 섹션 잠금 해제
        tab.querySelector('.food-export-section')?.classList.remove('sec-locked');
        showToast('맛집 블로그 글 생성 완료!');
        return;
      }
    } catch(e) {}
    if (stat) stat.textContent = msg;
  });
}

// ── 저장 ──────────────────────────────────────────────────────
async function saveFoodToFolder(btn) {
  const tab     = getFoodTab(btn);
  const title   = tab.querySelector('.food-title').value;
  const content = tab.querySelector('.food-content').value;
  const tags    = tab.querySelector('.food-tags').value.split(',').map(t=>t.trim()).filter(Boolean);
  const folder  = tab.querySelector('.food-export-path').value || './uploads';
  const fmt     = tab.querySelector(`input[name^="food-fmt-"]:checked`)?.value || 'txt';
  const stat    = tab.querySelector('.food-post-status');
  const photos  = foodPhotoStore[tab.dataset.tabId] || [];

  if (!title) { showToast('먼저 글을 생성해주세요.', 'warn'); return; }
  if (stat) stat.textContent = '저장 중...';

  // 사진 URL 목록 본문에 추가
  let finalContent = content;
  if (photos.length) {
    const photoList = '\n\n[사진 링크]\n' + photos.map((p, i) => `사진${i+1}: ${p.url}`).join('\n');
    finalContent += photoList;
  }

  const res  = await fetch('/api/save-file', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, content: finalContent, tags, folder, format: fmt })
  });
  const data = await res.json();
  if (data.ok) {
    if (stat) stat.innerHTML = `<span style="color:var(--primary)">✓ 저장: ${data.filename}</span>`;
    showToast('저장 완료! ' + data.filename);
  } else {
    if (stat) stat.textContent = '저장 오류: ' + data.error;
  }
}

// ── 유틸 ──────────────────────────────────────────────────────
function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── 동기화 UI ─────────────────────────────────────────────────
async function loadSyncStatus() {
  try {
    const res  = await fetch('/api/sync-status');
    const data = await res.json();
    const el   = document.getElementById('syncStatus');
    if (!el) return;
    if (data.last_sync) {
      el.innerHTML = `<i class="bi bi-check-circle-fill"></i> 마지막 동기화: <strong>${data.last_sync}</strong>`;
      el.className = 'logic-pill ok';
    } else {
      el.innerHTML = `<i class="bi bi-exclamation-circle"></i> 동기화 기록 없음`;
      el.className = 'logic-pill warn';
    }
  } catch(e) {}
}

async function runSync(direction) {
  const el = document.getElementById('syncStatus');
  if (el) { el.className = 'logic-pill'; el.innerHTML = '<i class="bi bi-arrow-repeat"></i> 동기화 중...'; }

  const res    = await fetch('/api/sync', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction })
  });
  const { job_id } = await res.json();

  watchProgress(job_id, (msg, done) => {
    try {
      const p = JSON.parse(msg);
      if (p.sync_done) {
        if (el) {
          el.className = 'logic-pill ok';
          el.innerHTML = `<i class="bi bi-check-circle-fill"></i> 동기화 완료 (가져옴:${p.pulled||0} 올림:${p.pushed||0})`;
        }
        showToast('동기화 완료!');
        return;
      }
    } catch(e) {}
    if (el) el.innerHTML = `<i class="bi bi-arrow-repeat"></i> ${msg}`;
  });
}

// ── Google Drive 연결 ─────────────────────────────────────────
async function connectGDrive() {
  const res  = await fetch('/api/gdrive-auth');
  const data = await res.json();
  if (data.error) { showToast(data.error, 'error'); return; }
  if (data.auth_url) {
    window.open(data.auth_url, 'gdrive_auth', 'width=600,height=700');
    showToast('Google 계정으로 로그인 후 이 창을 닫으세요.', 'warn');
    // 연결 완료 폴링
    const check = setInterval(async () => {
      const r = await fetch('/api/gdrive-status');
      const d = await r.json();
      if (d.connected) {
        clearInterval(check);
        showToast('Google Drive 연결 완료!');
        document.getElementById('gdriveStatus')?.classList.replace('warn','ok');
        document.getElementById('gdriveStatus').innerHTML = '<i class="bi bi-check-circle-fill"></i> Google Drive 연결됨';
      }
    }, 2000);
    setTimeout(() => clearInterval(check), 120000); // 2분 후 타임아웃
  }
}

// ── 맛집 로직 상태 ────────────────────────────────────────────
async function loadFoodLogicStatus(tab) {
  const el = tab ? tab.querySelector('.food-logic-status') : null;
  if (!el) return;
  try {
    const res  = await fetch('/api/food-logic-status');
    const data = await res.json();
    if (data.updated_at && data.updated_at !== '미설정') {
      el.className = 'food-logic-status logic-pill ok';
      el.innerHTML = `<i class="bi bi-check-circle-fill"></i> 맛집 로직 최신화: <strong>${data.updated_at}</strong>`;
    } else {
      el.className = 'food-logic-status logic-pill warn';
      el.innerHTML = `<i class="bi bi-exclamation-circle"></i> 아직 최신화되지 않았습니다`;
    }
  } catch(e) {
    if (el) { el.className='food-logic-status logic-pill warn'; el.innerHTML='<i class="bi bi-exclamation-circle"></i> 로직 상태 불러오기 실패'; }
  }
}

async function updateFoodLogic(btn) {
  const tab = getFoodTab(btn);
  const el  = tab ? tab.querySelector('.food-logic-status') : null;
  if (el) { el.className='food-logic-status logic-pill'; el.innerHTML='<i class="bi bi-arrow-clockwise"></i> 최신화 중...'; }
  btn.disabled = true;

  try {
    const res = await fetch('/api/update-food-logic', { method: 'POST' });
    const { job_id } = await res.json();

    watchProgress(job_id, (msg, done) => {
      try {
        const p = JSON.parse(msg);
        if (p.updated_at && el) {
          el.className = 'food-logic-status logic-pill ok';
          el.innerHTML = `<i class="bi bi-check-circle-fill"></i> 맛집 로직 최신화: <strong>${p.updated_at}</strong>`;
          showToast('맛집 로직 최신화 완료!');
          btn.disabled = false;
          return;
        }
      } catch(e) {}
      if (el) el.innerHTML = `<i class="bi bi-arrow-clockwise"></i> ${msg}`;
    });
  } catch(e) {
    if (el) el.innerHTML = `<i class="bi bi-x-circle"></i> 오류: ${e.message}`;
    btn.disabled = false;
  }
}

// ── Google Drive 경로 토글/적용 ───────────────────────────────
function toggleGdrivePath(sel) {
  const tab = getFoodTab(sel);
  if (!tab) return;
  const row = tab.querySelector('.gdrive-path-row');
  if (!row) return;
  const show = sel.value === 'gdrive' || sel.value === 'both';
  row.style.display = show ? '' : 'none';
}

function applyGdrivePath(btn) {
  const tab    = getFoodTab(btn);
  const path   = tab.querySelector('.gdrive-folder-path')?.value?.trim();
  if (path) {
    showToast('Google Drive 경로 설정: ' + path);
  } else {
    showToast('경로가 비어있으면 자동 생성됩니다.', 'warn');
  }
}

// ── 영수증 리뷰 ───────────────────────────────────────────────
async function generateReceiptReview(btn) {
  const tab = getFoodTab(btn);

  const placeName  = tab.querySelector('.inp-place-name').value;
  const placeAddr  = tab.querySelector('.inp-place-addr').value || tab.querySelector('.inp-place-road').value;
  const visitDate  = tab.querySelector('.receipt-date').value  || tab.querySelector('.inp-visit-date').value;
  const menuItems  = tab.querySelector('.receipt-menu').value.trim();
  const totalAmt   = tab.querySelector('.receipt-amount').value.trim();
  const ratingTaste= parseInt(tab.querySelector('.inp-rating-taste').value || 3);
  const ratingMood = parseInt(tab.querySelector('.inp-rating-mood').value  || 3);
  const memo       = tab.querySelector('.inp-memo').value;

  if (!placeName) { showToast('먼저 음식점을 검색하고 선택해주세요.', 'warn'); return; }
  if (!menuItems)  { showToast('주문 메뉴를 입력해주세요.', 'warn'); return; }

  const jobId = 'receipt_' + Date.now();
  const prog  = tab.querySelector('.receipt-progress');
  const stat  = tab.querySelector('.receipt-gen-status');
  if (prog) prog.style.display = '';
  if (stat) stat.textContent = '영수증 리뷰 생성 중...';
  btn.disabled = true;

  await fetch('/api/generate-receipt-review', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      job_id: jobId, place_name: placeName, place_addr: placeAddr,
      visit_date: visitDate, menu_items: menuItems, total_amount: totalAmt,
      rating_taste: ratingTaste, rating_mood: ratingMood, memo
    })
  });

  watchProgress(jobId, (msg, done) => {
    try {
      const p = JSON.parse(msg);
      if (p.error) {
        if (stat) stat.textContent = '오류: ' + p.error;
        if (prog) prog.style.display = 'none';
        btn.disabled = false;
        return;
      }
      if (p.result) {
        const r = p.result;
        const textEl   = tab.querySelector('.receipt-text');
        const kwEl     = tab.querySelector('.receipt-keywords');
        const countEl  = tab.querySelector('.receipt-char-count');

        if (textEl) {
          textEl.value = r.review_text || '';
          if (countEl) countEl.textContent = `(${(r.review_text||'').length}자)`;
        }
        if (kwEl && r.keywords) {
          kwEl.innerHTML = r.keywords.map(k =>
            `<span class="nb-tag" style="cursor:pointer;background:#eff6ff;color:#1e40af;" onclick="appendKeyword(this,'${escHtml(k)}')">${escHtml(k)}</span>`
          ).join('');
        }
        if (stat) stat.innerHTML = `<span style="color:var(--primary)">✓ 리뷰 생성 완료 (${(r.review_text||'').length}자)</span>`;
        if (prog) prog.style.display = 'none';
        btn.disabled = false;
        showToast('영수증 리뷰 생성 완료!');
        return;
      }
    } catch(e) {}
    if (stat) stat.textContent = msg;
  });
}

function updateReceiptCount(textarea) {
  const countEl = textarea.closest('.nb-card-body').querySelector('.receipt-char-count');
  if (countEl) countEl.textContent = `(${textarea.value.length}자)`;
}

function appendKeyword(span, kw) {
  const tab    = getFoodTab(span);
  const textEl = tab.querySelector('.receipt-text');
  if (!textEl) return;
  textEl.value += ' ' + kw;
  updateReceiptCount(textEl);
  showToast(`"${kw}" 추가됨`);
}

async function copyReceiptReview(btn) {
  const tab  = getFoodTab(btn);
  const text = tab.querySelector('.receipt-text')?.value || '';
  if (!text) { showToast('리뷰 내용이 없습니다.', 'warn'); return; }
  await navigator.clipboard.writeText(text);
  showToast('리뷰 복사됨!');
}

function openNaverReview(btn) {
  const tab  = getFoodTab(btn);
  const link = tab.querySelector('.inp-place-link')?.value;
  if (link) {
    window.open(link, '_blank');
  } else {
    window.open('https://map.naver.com', '_blank');
    showToast('네이버 지도에서 영수증 리뷰를 작성해주세요.', 'warn');
  }
}

// ── 초기화 ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadSyncStatus();
});
