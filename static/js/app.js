// ── 공용 유틸 ─────────────────────────────────────────────
function showToast(msg){
  const el = document.getElementById('progressToast');
  document.getElementById('toastMsg').textContent = msg;
  if(el) new bootstrap.Toast(el,{delay:3000}).show();
}

// SSE 진행상황 구독
function watchProgress(jobId, onData){
  const es = new EventSource(`/api/progress/${jobId}`);
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if(d.done){ es.close(); onData(d.msg, true); return; }
    onData(d.msg, false);
  };
  return es;
}

// ── 블로그 로직 최신화 ────────────────────────────────────
async function updateLogic(){
  document.getElementById('logicStatus').textContent = '업데이트 중...';
  const res = await fetch('/api/update-logic',{method:'POST'});
  const {job_id} = await res.json();
  watchProgress(job_id, (msg,done) => {
    document.getElementById('logicStatus').textContent = msg;
    if(done) showToast('블로그 로직 최신화 완료!');
  });
}

// ── 글 생성 ───────────────────────────────────────────────
let currentPostId = null;
let currentPost   = {};

async function generateContent(supplement=''){
  const raw = document.getElementById('rawInput')?.value?.trim();
  if(!raw && !(window.attachedFiles?.length)){
    alert('자료 입력란에 내용을 입력하세요.'); return;
  }
  const jobId = 'gen_'+Date.now();
  setGenLoading(true);

  const payload = {
    job_id:           jobId,
    raw_input:        raw || '',
    attached_files:   window.attachedFiles || [],
    tone:             document.querySelector('input[name="tone"]:checked')?.value || '친근하게',
    include_youtube:  document.getElementById('inclYt')?.checked ?? true,
    include_map:      document.getElementById('inclMap')?.checked ?? false,
    image_count:      parseInt(document.getElementById('imgCount')?.value || 5),
    supplement:       supplement,
    previous_content: document.getElementById('postContent')?.value || '',
  };

  await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});

  const logEl = document.getElementById('genStatus');
  watchProgress(jobId, (msg, done)=>{
    try{
      const parsed = JSON.parse(msg);
      if(parsed.error){ logEl.textContent='오류: '+parsed.error; setGenLoading(false); return; }
      if(parsed.result){
        const r = parsed.result;
        currentPostId = r.post_id;
        currentPost   = r;
        document.getElementById('postTitle').value   = r.title   || '';
        document.getElementById('postContent').value = r.content || '';
        document.getElementById('postTags').value    = (r.tags||[]).join(', ');
        document.getElementById('currentPostId').value = r.post_id||'';
        document.getElementById('btnRegen').disabled  = false;
        document.getElementById('btnConfirm').disabled = false;
        logEl.textContent = '생성 완료 ✅';
        setGenLoading(false);
        return;
      }
    }catch(e){}
    logEl.textContent = msg;
  });
}

async function regenerate(){
  const supp = document.getElementById('supplement').value;
  await generateContent(supp);
}

async function confirmPost(){
  const postId = document.getElementById('currentPostId').value;
  const title   = document.getElementById('postTitle').value;
  const content = document.getElementById('postContent').value;
  const tags    = document.getElementById('postTags').value.split(',').map(t=>t.trim()).filter(Boolean);
  await fetch('/api/confirm',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({post_id:postId, title, content, tags})
  });
  // 이미지/저장 섹션 활성화
  document.getElementById('imageSection').style.cssText='';
  document.getElementById('exportSection').style.cssText='';
  showToast('확정 완료! 이미지 생성 또는 저장을 진행하세요.');
}

function setGenLoading(loading){
  document.getElementById('genProgress').style.display = loading ? '' : 'none';
  document.getElementById('btnRegen').disabled  = loading;
}

// ── 이미지 생성 ───────────────────────────────────────────
async function generateImages(){
  const postId  = document.getElementById('currentPostId').value;
  const title   = document.getElementById('postTitle').value;
  const content = document.getElementById('postContent').value;
  const savePath= document.getElementById('imageSavePath').value;

  if(!title){ alert('먼저 글을 확정해주세요.'); return; }
  document.getElementById('imgProgress').style.display = '';
  document.getElementById('imgStatus').textContent = '이미지 생성 중...';

  const jobId = 'img_'+Date.now();
  await fetch('/api/generate-images',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      job_id: jobId, post_id: postId, title, content,
      image_count: parseInt(document.getElementById('imgCount').value||5),
      save_dir: savePath
    })
  });

  const thumbEl = document.getElementById('imgThumbnails');
  watchProgress(jobId, (msg, done)=>{
    try{
      const parsed = JSON.parse(msg);
      if(parsed.images){
        parsed.images.forEach(img=>{
          const chip = document.createElement('span');
          chip.className='badge bg-primary';
          chip.innerHTML=`<i class="bi bi-image me-1"></i>${img.filename}`;
          thumbEl.appendChild(chip);
        });
        document.getElementById('imgStatus').textContent=`${parsed.images.length}장 생성 완료 ✅`;
        document.getElementById('imgProgress').style.display='none';
        return;
      }
      if(parsed.error){ document.getElementById('imgStatus').textContent='오류: '+parsed.error; return; }
    }catch(e){}
    document.getElementById('imgStatus').textContent = msg;
  });
}

// ── 내보내기 & 포스팅 ─────────────────────────────────────
async function exportTxt(){
  const title   = document.getElementById('postTitle').value;
  const content = document.getElementById('postContent').value;
  const tags    = document.getElementById('postTags').value;
  const text    = `[제목]\n${title}\n\n[태그]\n${tags}\n\n${'='.repeat(40)}\n[본문]\n${'='.repeat(40)}\n\n${content}`;
  const blob = new Blob([text],{type:'text/plain;charset=utf-8'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = title.replace(/[^\w가-힣]/g,'-').slice(0,30)+'.txt';
  a.click();
}

async function postToNaver(){
  const postId  = document.getElementById('currentPostId').value;
  const title   = document.getElementById('postTitle').value;
  const content = document.getElementById('postContent').value;
  const tags    = document.getElementById('postTags').value.split(',').map(t=>t.trim());
  if(!confirm('네이버 블로그에 포스팅 하시겠습니까?')) return;

  document.getElementById('postStatus').textContent = '포스팅 중...';
  const res = await fetch('/api/post-to-naver',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({post_id:postId, title, content, tags})
  });
  const {job_id} = await res.json();
  watchProgress(job_id, (msg,done)=>{
    try{
      const r = JSON.parse(msg);
      if(r.ok){ document.getElementById('postStatus').textContent='포스팅 완료! ✅'; showToast('포스팅 완료!'); }
      if(r.error){ document.getElementById('postStatus').textContent='오류: '+r.error; }
    }catch(e){ document.getElementById('postStatus').textContent=msg; }
  });
}
