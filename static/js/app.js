// ══════════════════════════════════════════════════════════════
//  app.js  —  N블로그 자동화 공통 스크립트
// ══════════════════════════════════════════════════════════════

// ── 토스트 ──────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const wrap = document.getElementById('toastWrap');
  if (!wrap) return;
  const iconMap = { success: 'bi-check-circle-fill', warn: 'bi-exclamation-circle', error: 'bi-x-circle' };
  const icon = iconMap[type] || iconMap.success;
  const el = document.createElement('div');
  el.className = 'nb-toast';
  el.innerHTML = `<i class="bi ${icon} t-ico"></i><span>${msg}</span>`;
  wrap.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0'; el.style.transition = 'opacity .3s';
    setTimeout(() => el.remove(), 300);
  }, 3200);
}

// ── SSE 진행상황 구독 ────────────────────────────────────────
function watchProgress(jobId, onData) {
  const es = new EventSource(`/api/progress/${jobId}`);
  es.onmessage = e => {
    try {
      const d = JSON.parse(e.data);
      if (d.done) { es.close(); onData(d.msg, true); return; }
      onData(d.msg, false);
    } catch(ex) { onData(e.data, false); }
  };
  es.onerror = () => es.close();
  return es;
}

// ── 블로그 로직 상태 로드 ────────────────────────────────────
async function loadLogicStatus() {
  try {
    const res  = await fetch('/api/logic-status');
    const data = await res.json();
    const el   = document.getElementById('logicStatus');
    if (!el) return;
    if (data.updated_at && data.updated_at !== '미설정') {
      el.className = 'logic-pill ok';
      el.innerHTML = `<i class="bi bi-check-circle-fill"></i> 최근 최신화: <strong>${data.updated_at}</strong>`;
    } else {
      el.className = 'logic-pill warn';
      el.innerHTML = `<i class="bi bi-exclamation-circle"></i> 아직 최신화되지 않았습니다`;
    }
  } catch(e) {}
}

// ── 블로그 로직 최신화 (updateLogic은 index.html 인라인에도 있지만 history 등에서도 쓸 수 있도록) ──
async function updateLogic() {
  const el = document.getElementById('logicStatus');
  if (el) { el.className = 'logic-pill'; el.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 업데이트 중...'; }
  const res    = await fetch('/api/update-logic', { method: 'POST' });
  const { job_id } = await res.json();
  watchProgress(job_id, (msg, done) => {
    try {
      const p = JSON.parse(msg);
      if (p.updated_at && el) {
        el.className = 'logic-pill ok';
        el.innerHTML = `<i class="bi bi-check-circle-fill"></i> 최근 최신화: <strong>${p.updated_at}</strong>`;
        showToast('블로그 로직 최신화 완료!');
        return;
      }
    } catch(e) {}
    if (el) el.innerHTML = `<i class="bi bi-arrow-clockwise"></i> ${msg}`;
  });
}

// ══════════════════════════════════════════════════════════════
//  탭 시스템 (index 페이지 전용)
// ══════════════════════════════════════════════════════════════

// 재사용 데이터는 index.html 인라인 스크립트에서 REUSE_POST 로 전달됨

// ─── 탭 생성 ───────────────────────────────────────────────
let tabCounter   = 0;
let activeTabId  = null;
const tabAttachments = {};   // tabId → [{name, type, content, path}]

function getTabEl(btn) {
  return btn.closest('.tab-content');
}
function getTabId(tabEl) {
  return tabEl?.dataset?.tabId || '';
}

function addTab(label, reuseData) {
  tabCounter++;
  const id = 'tab' + tabCounter;
  tabAttachments[id] = [];

  /* ── 탭 버튼 ── */
  const pill = document.createElement('div');
  pill.className   = 'tab-pill';
  pill.dataset.tabId = id;
  const safeLabel  = label || ('새 글 ' + tabCounter);
  pill.innerHTML   = `
    <span class="tab-label" onclick="switchTab('${id}')">${safeLabel}</span>
    <span class="tab-close" onclick="closeTab('${id}')">×</span>`;
  document.getElementById('tabList').appendChild(pill);

  /* ── 탭 컨텐츠 복제 ── */
  const tmpl    = document.getElementById('tabTemplate').content.cloneNode(true);
  const content = tmpl.querySelector('.tab-content');
  content.dataset.tabId = id;

  // name 속성 격리
  content.querySelectorAll('[name*="__TAB__"]').forEach(el => {
    el.name = el.name.replace('__TAB__', id);
  });

  document.getElementById('tabContents').appendChild(content);

  /* ── 파일 첨부 이벤트 ── */
  const fi = document.querySelector(`.tab-content[data-tab-id="${id}"] .file-input`);
  if (fi) {
    fi.addEventListener('change', async function () {
      for (const file of this.files) {
        const fd = new FormData(); fd.append('file', file);
        try {
          const res  = await fetch('/api/upload', { method: 'POST', body: fd });
          const data = await res.json();
          tabAttachments[id].push(data);
          updateAttachList(id);
        } catch(e) { showToast('업로드 오류: ' + e.message, 'error'); }
      }
    });
  }

  /* ── 재사용 데이터 채우기 ── */
  if (reuseData) fillTabWithPost(id, reuseData);

  switchTab(id);
  return id;
}

function fillTabWithPost(tabId, post) {
  const tab = document.querySelector(`.tab-content[data-tab-id="${tabId}"]`);
  if (!tab || !post) return;

  // 탭 레이블
  const pill = document.querySelector(`.tab-pill[data-tab-id="${tabId}"] .tab-label`);
  if (pill && post.title) pill.textContent = truncate(post.title, 14);

  // 필드 채우기
  if (post.raw_input)     tab.querySelector('.raw-input').value      = post.raw_input;
  if (post.title)         tab.querySelector('.post-title').value     = post.title;
  if (post.content)       tab.querySelector('.post-content').value   = post.content;
  if (post.tags) {
    const tagStr = Array.isArray(post.tags) ? post.tags.join(', ') : post.tags;
    tab.querySelector('.post-tags').value = tagStr;
  }
  if (post.id)            tab.querySelector('.post-id-hidden').value      = post.id;
  if (post.main_keyword)  tab.querySelector('.main-keyword-hidden').value = post.main_keyword;

  // 어투
  if (post.tone) {
    const r = tab.querySelector(`input[value="${post.tone}"]`);
    if (r) r.checked = true;
  }

  // 버튼/섹션 활성화
  tab.querySelector('.regen-btn').disabled  = false;
  tab.querySelector('.confirm-btn').disabled = false;
  tab.querySelector('.img-section')?.classList.remove('sec-locked');
  tab.querySelector('.export-section')?.classList.remove('sec-locked');

  tab.querySelector('.gen-status').innerHTML =
    '<span style="color:var(--primary)">✓ 기존 글 불러옴 — 보완 요청 후 재생성하세요</span>';
}

function switchTab(id) {
  document.querySelectorAll('.tab-pill').forEach(p  => p.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');

  document.querySelector(`.tab-pill[data-tab-id="${id}"]`)?.classList.add('active');
  const c = document.querySelector(`.tab-content[data-tab-id="${id}"]`);
  if (c) c.style.display = '';
  activeTabId = id;
}

function closeTab(id) {
  if (document.querySelectorAll('.tab-pill').length <= 1) {
    showToast('마지막 탭은 닫을 수 없습니다.', 'warn'); return;
  }
  document.querySelector(`.tab-pill[data-tab-id="${id}"]`)?.remove();
  document.querySelector(`.tab-content[data-tab-id="${id}"]`)?.remove();
  delete tabAttachments[id];

  const first = document.querySelector('.tab-pill');
  if (first) switchTab(first.dataset.tabId);
}

function updateAttachList(tabId) {
  const tab = document.querySelector(`.tab-content[data-tab-id="${tabId}"]`);
  if (!tab) return;
  const el = tab.querySelector('.attach-list');
  const files = tabAttachments[tabId] || [];
  el.innerHTML = files.map((f, i) =>
    `<span class="attach-item">
      <i class="bi bi-paperclip"></i>${f.name}
      <span style="cursor:pointer;color:var(--danger);margin-left:4px"
        onclick="removeAttach('${tabId}',${i})">×</span>
    </span>`).join('');
}

function removeAttach(tabId, i) {
  tabAttachments[tabId].splice(i, 1);
  updateAttachList(tabId);
}

function clearTab(btn) {
  const tab = getTabEl(btn);
  const id  = getTabId(tab);
  tab.querySelector('.raw-input').value = '';
  tabAttachments[id] = [];
  updateAttachList(id);
}

async function pasteClip(btn) {
  const tab = getTabEl(btn);
  const id  = getTabId(tab);
  try {
    const items = await navigator.clipboard.read();
    for (const item of items) {
      const imgType = item.types.find(t => t.startsWith('image/'));
      if (imgType) {
        const blob = await item.getType(imgType);
        const fd   = new FormData(); fd.append('file', blob, 'clipboard.png');
        const res  = await fetch('/api/upload', { method: 'POST', body: fd });
        const data = await res.json();
        tabAttachments[id].push({ ...data, type: 'image' });
        updateAttachList(id);
        showToast('클립보드 이미지 추가됨');
        return;
      }
    }
    showToast('클립보드에 이미지가 없습니다.', 'warn');
  } catch(e) { showToast('클립보드 오류: ' + e.message, 'warn'); }
}

// ── 글 생성 ─────────────────────────────────────────────────
async function generateContent(btn, supplement) {
  const tab   = getTabEl(btn);
  const tabId = getTabId(tab);
  supplement  = supplement ?? '';

  const raw = tab.querySelector('.raw-input').value.trim();
  if (!raw && !(tabAttachments[tabId]?.length)) {
    showToast('자료 입력란에 내용을 입력하세요.', 'warn'); return;
  }

  const jobId = 'gen_' + tabId + '_' + Date.now();
  const prog  = tab.querySelector('.gen-progress');
  const stat  = tab.querySelector('.gen-status');
  prog.style.display = '';
  stat.textContent   = '';
  tab.querySelector('.gen-btn').disabled   = true;
  tab.querySelector('.regen-btn').disabled = true;

  const toneEl = tab.querySelector(`input[name^="tone-"]:checked`);
  const payload = {
    job_id:           jobId,
    raw_input:        raw,
    attached_files:   tabAttachments[tabId] || [],
    tone:             toneEl?.value || '친근하게',
    include_youtube:  tab.querySelector('.incl-yt')?.checked ?? true,
    include_map:      tab.querySelector('.incl-map')?.checked ?? false,
    image_count:      parseInt(tab.querySelector('.img-count-range')?.value || 5),
    supplement:       supplement,
    previous_content: tab.querySelector('.post-content').value || '',
  };

  await fetch('/api/generate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  watchProgress(jobId, (msg, done) => {
    try {
      const p = JSON.parse(msg);
      if (p.error) {
        stat.textContent = '오류: ' + p.error;
        prog.style.display = 'none';
        tab.querySelector('.gen-btn').disabled = false;
        return;
      }
      if (p.result) {
        const r = p.result;
        tab.querySelector('.post-title').value         = r.title   || '';
        tab.querySelector('.post-content').value       = r.content || '';
        tab.querySelector('.post-tags').value          = (r.tags || []).join(', ');
        tab.querySelector('.post-id-hidden').value     = r.post_id || '';
        tab.querySelector('.main-keyword-hidden').value= r.main_keyword || '';
        tab.querySelector('.regen-btn').disabled  = false;
        tab.querySelector('.confirm-btn').disabled = false;
        stat.innerHTML = '<span style="color:var(--primary)">✓ 생성 완료</span>';
        prog.style.display = 'none';
        tab.querySelector('.gen-btn').disabled = false;

        // 탭 레이블 업데이트
        const pill = document.querySelector(`.tab-pill[data-tab-id="${tabId}"] .tab-label`);
        if (pill && r.title) pill.textContent = truncate(r.title, 14);

        showToast('글 생성 완료!');
        return;
      }
    } catch(e) {}
    if (stat) stat.textContent = msg;
  });
}

async function regenerateContent(btn) {
  const tab  = getTabEl(btn);
  const supp = tab.querySelector('.supplement-input').value;
  const genBtn = tab.querySelector('.gen-btn');
  await generateContent(genBtn, supp);
}

async function confirmContent(btn) {
  const tab     = getTabEl(btn);
  const postId  = tab.querySelector('.post-id-hidden').value;
  const title   = tab.querySelector('.post-title').value;
  const content = tab.querySelector('.post-content').value;
  const tags    = tab.querySelector('.post-tags').value
    .split(',').map(t => t.trim()).filter(Boolean);

  await fetch('/api/confirm', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ post_id: postId, title, content, tags })
  });

  tab.querySelector('.img-section')?.classList.remove('sec-locked');
  tab.querySelector('.export-section')?.classList.remove('sec-locked');
  showToast('확정 완료! 이미지 생성 또는 저장을 진행하세요.');
}

// ── 이미지 생성 ──────────────────────────────────────────────
async function generateImagesTab(btn) {
  const tab     = getTabEl(btn);
  const tabId   = getTabId(tab);
  const title   = tab.querySelector('.post-title').value;
  const content = tab.querySelector('.post-content').value;
  const postId  = tab.querySelector('.post-id-hidden').value;
  const keyword = tab.querySelector('.main-keyword-hidden').value;
  const tags    = tab.querySelector('.post-tags').value
    .split(',').map(t => t.trim()).filter(Boolean);
  const savePath= tab.querySelector('.img-save-path')?.value || './uploads/images';

  if (!title) { showToast('먼저 글을 확정해주세요.', 'warn'); return; }

  const jobId = 'img_' + tabId + '_' + Date.now();
  const prog  = tab.querySelector('.img-progress');
  const stat  = tab.querySelector('.img-status');
  if (prog) prog.style.display = '';
  if (stat) stat.textContent = '이미지 생성 중...';

  await fetch('/api/generate-images', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      job_id: jobId, post_id: postId, title, content,
      image_count: parseInt(tab.querySelector('.img-count-range')?.value || 5),
      save_dir: savePath, main_keyword: keyword, tags
    })
  });

  const thumbEl = tab.querySelector('.img-thumbnails');
  watchProgress(jobId, (msg, done) => {
    try {
      const p = JSON.parse(msg);
      if (p.images) {
        if (thumbEl) p.images.forEach(img => {
          const chip = document.createElement('span');
          chip.className = 'img-chip';
          chip.innerHTML = `<i class="bi bi-image"></i>${img.filename}`;
          thumbEl.appendChild(chip);
        });
        if (stat) stat.innerHTML = `<span style="color:var(--primary)">✓ ${p.images.length}장 생성 완료</span>`;
        if (prog) prog.style.display = 'none';
        showToast(`이미지 ${p.images.length}장 생성 완료!`);
        return;
      }
      if (p.error) { if (stat) stat.textContent = '오류: ' + p.error; return; }
    } catch(e) {}
    if (stat) stat.textContent = msg;
  });
}

// ── 저장 & 포스팅 ────────────────────────────────────────────
async function saveToFolderTab(btn) {
  const tab    = getTabEl(btn);
  const title  = tab.querySelector('.post-title').value;
  const content= tab.querySelector('.post-content').value;
  const tags   = tab.querySelector('.post-tags').value
    .split(',').map(t => t.trim()).filter(Boolean);
  const folder = tab.querySelector('.export-path')?.value || './uploads';
  const fmtEl  = tab.querySelector(`input[name^="fmt-"]:checked`);
  const fmt    = fmtEl?.value || 'txt';
  const stat   = tab.querySelector('.post-status');

  if (!title) { showToast('먼저 글을 확정해주세요.', 'warn'); return; }
  if (stat) stat.textContent = '저장 중...';

  const res  = await fetch('/api/save-file', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, content, tags, folder, format: fmt })
  });
  const data = await res.json();

  if (data.ok) {
    if (stat) stat.innerHTML = `<span style="color:var(--primary)">✓ 저장: ${data.filename}</span>`;
    showToast('저장 완료! ' + data.filename);
  } else {
    if (stat) stat.textContent = '저장 오류: ' + (data.error || '알 수 없음');
    showToast('저장 오류', 'error');
  }
}

function downloadTxtTab(btn) {
  const tab    = getTabEl(btn);
  const title  = tab.querySelector('.post-title').value  || '블로그';
  const content= tab.querySelector('.post-content').value|| '';
  const tags   = tab.querySelector('.post-tags').value   || '';
  const text   = `[제목]\n${title}\n\n[태그]\n${tags}\n\n${'='.repeat(40)}\n[본문]\n${'='.repeat(40)}\n\n${content}`;
  const blob   = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const a      = document.createElement('a');
  a.href       = URL.createObjectURL(blob);
  a.download   = (title.replace(/[^\w가-힣]/g, '-').slice(0, 30) || 'blog') + '.txt';
  a.click();
  showToast('다운로드 완료!');
}

async function postToNaverTab(btn) {
  const tab    = getTabEl(btn);
  const postId = tab.querySelector('.post-id-hidden').value;
  const title  = tab.querySelector('.post-title').value;
  const content= tab.querySelector('.post-content').value;
  const tags   = tab.querySelector('.post-tags').value
    .split(',').map(t => t.trim()).filter(Boolean);
  const stat   = tab.querySelector('.post-status');

  if (!confirm('네이버 블로그에 포스팅 하시겠습니까?')) return;
  if (stat) stat.textContent = '포스팅 중...';

  const res    = await fetch('/api/post-to-naver', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ post_id: postId, title, content, tags })
  });
  const { job_id } = await res.json();

  watchProgress(job_id, (msg) => {
    try {
      const r = JSON.parse(msg);
      if (r.ok)    { if (stat) stat.innerHTML = '<span style="color:var(--primary)">✓ 포스팅 완료!</span>'; showToast('포스팅 완료!'); }
      if (r.error) { if (stat) stat.textContent = '오류: ' + r.error; }
    } catch(e) { if (stat) stat.textContent = msg; }
  });
}

function setFolderPath(input) {
  if (input.files && input.files.length > 0) {
    const path   = input.files[0].webkitRelativePath || input.files[0].name;
    const folder = path.split('/')[0];
    const tab    = input.closest('.tab-content');
    const el     = tab?.querySelector('.export-path') || document.querySelector('.export-path');
    if (el) el.value = './uploads/' + folder;
    showToast('폴더 선택: ' + folder);
  }
}

// ── 유틸 ─────────────────────────────────────────────────────
function truncate(str, len) {
  return str && str.length > len ? str.slice(0, len) + '…' : str;
}

// ── 맛집 탭 생성 ─────────────────────────────────────────────
let foodTabCounter = 0;   // 맛집 탭 전용 카운터 (별도 번호 표시용)

function addFoodTab() {
  tabCounter++;
  foodTabCounter++;
  const id        = 'tab' + tabCounter;
  const foodLabel = '🍜 맛집 ' + foodTabCounter;
  foodPhotoStore && (foodPhotoStore[id] = []);  // food_tab.js 전역

  // 탭 버튼
  const pill = document.createElement('div');
  pill.className   = 'tab-pill food-pill';
  pill.dataset.tabId = id;
  pill.innerHTML   = `
    <span class="tab-label" onclick="switchTab('${id}')">${foodLabel}</span>
    <span class="tab-close" onclick="closeTab('${id}')">×</span>`;
  document.getElementById('tabList').appendChild(pill);

  // 컨텐츠 복제
  const tmpl    = document.getElementById('foodTabTemplate')?.content.cloneNode(true);
  if (!tmpl) { showToast('맛집 탭 템플릿이 없습니다.', 'error'); return; }
  const content = tmpl.querySelector('.food-tab-content');
  content.dataset.tabId = id;

  // radio name 격리
  content.querySelectorAll('[name*="__TAB__"]').forEach(el => {
    el.name = el.name.replace('__TAB__', id);
  });

  // 오늘 날짜 기본값
  const today = new Date().toISOString().slice(0,10);
  const dateEl = content.querySelector('.inp-visit-date');
  if (dateEl) dateEl.value = today;

  document.getElementById('tabContents').appendChild(content);

  // 파일 첨부 이벤트 (사진)
  const fi = document.querySelector(`.food-tab-content[data-tab-id="${id}"] .food-photo-input`);
  if (fi) {
    fi.addEventListener('change', function() {
      if (typeof handleFoodPhotos === 'function') handleFoodPhotos(this, id);
    });
  }

  // 별점 초기화 (food_tab.js)
  const tabEl = document.querySelector(`.food-tab-content[data-tab-id="${id}"]`);
  if (tabEl && typeof initStars === 'function') initStars(tabEl);

  // 맛집 로직 상태 로드 (food_tab.js)
  if (tabEl && typeof loadFoodLogicStatus === 'function') loadFoodLogicStatus(tabEl);

  switchTab(id);
  return id;
}

// ── 페이지 로드 ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // 로직 상태 로드
  if (document.getElementById('logicStatus')) loadLogicStatus();

  // 탭 초기화 (index 페이지에만 해당 요소 있음)
  if (document.getElementById('tabList')) {
    // REUSE_POST 는 index.html 인라인 스크립트에서 선언됨
    const reuseData = typeof REUSE_POST !== 'undefined' ? REUSE_POST : null;
    if (reuseData) {
      addTab(truncate(reuseData.title || '재생성', 14), reuseData);
    } else {
      addTab('새 글 1');
    }
  }
});
