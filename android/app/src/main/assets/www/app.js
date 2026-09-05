/* RAW — social media for actual life. Android client.
   The rules are the product and they are enforced here, same as on the server:
   posts must name a state, reactions are not likes, counts are private,
   the feed is chronological, posts cannot be edited. */

const STATES = {
  rough:     {label:'rough day',       emoji:'🌧', c:'#46577d', l:'#a8b6d6'},
  grinding:  {label:'grinding',        emoji:'⚙️', c:'#6d5733', l:'#d6c093'},
  mundane:   {label:'nothing special', emoji:'🥣', c:'#4a6650', l:'#a8c4ae'},
  small_win: {label:'small win',       emoji:'🌱', c:'#2f7a55', l:'#8ed6ae'},
  spiraling: {label:'spiraling',       emoji:'🌀', c:'#71386b', l:'#d3a4cd'},
  healing:   {label:'healing',         emoji:'🩹', c:'#2c6377', l:'#9ccfe0'},
  angry:     {label:'angry',           emoji:'🔥', c:'#a03f28', l:'#f0a58c'},
  numb:      {label:'numb',            emoji:'🌫', c:'#4f4f5c', l:'#b4b4c2'},
  okay:      {label:'okay, actually',  emoji:'☀️', c:'#8d6f24', l:'#ecd18a'},
};
const REACTIONS = {
  been_there:{label:'been there', emoji:'🫱'},
  seen:      {label:'i see you',  emoji:'👁'},
  held:      {label:'holding this',emoji:'🤲'},
  proud:     {label:'proud of you',emoji:'🪧'},
  same:      {label:'same',       emoji:'🪞'},
};
const PROMPTS = [
  'How is it actually going?', "What did today cost you?",
  'What is the unglamorous part?', 'What are you avoiding?',
  'What went fine? Just fine is fine.', "What would you not post anywhere else?",
  "What's the thing you keep not saying?",
];
const PALETTE = ['#e08a6f','#7fc79a','#7d8fb3','#c48fbb','#e3c778','#8fc0d4','#c2a878'];


/* ── photos ───────────────────────────────────────────────────────────────────
   Pictures are the point of a real profile, but base64 in localStorage fills a
   5MB quota in a handful of posts. Blobs live in IndexedDB instead; the model
   only ever holds an id. Every photo is downscaled on the way in — no filters,
   no beautifying, just enough resizing that a 12MP camera file is storable. */

const PHOTO_DB = 'raw.photos';
let idb = null, photoURLs = {};

function openPhotos(){
  return new Promise(res => {
    let req;
    try { req = indexedDB.open(PHOTO_DB, 1); } catch(e){ return res(null); }
    req.onupgradeneeded = () => req.result.createObjectStore('photos', {keyPath:'id'});
    req.onsuccess = () => res(req.result);
    req.onerror = () => res(null);
  });
}

function loadPhotoURLs(){
  return new Promise(res => {
    if(!idb) return res();
    let tx;
    try { tx = idb.transaction('photos','readonly'); } catch(e){ return res(); }
    const cur = tx.objectStore('photos').openCursor();
    cur.onsuccess = () => {
      const c = cur.result;
      if(!c) return res();
      try { photoURLs[c.value.id] = URL.createObjectURL(c.value.blob); } catch(e){}
      c.continue();
    };
    cur.onerror = () => res();
  });
}

/* Downscale to `max` on the long edge and re-encode. Returns a Blob. */
function shrink(file, max){
  return new Promise((res, rej) => {
    const img = new Image(), url = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement('canvas');
      c.width = Math.round(img.width * scale);
      c.height = Math.round(img.height * scale);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      c.toBlob(b => b ? res(b) : rej(new Error('encode failed')), 'image/jpeg', 0.72);
    };
    img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('not an image')); };
    img.src = url;
  });
}

async function putPhoto(file, max){
  const blob = await shrink(file, max || 1280);
  const pid = 'p' + Date.now() + Math.random().toString(36).slice(2,7);
  if(idb){
    await new Promise(res => {
      const tx = idb.transaction('photos','readwrite');
      tx.objectStore('photos').put({id:pid, blob});
      tx.oncomplete = res; tx.onerror = res; tx.onabort = res;
    });
  }
  photoURLs[pid] = URL.createObjectURL(blob);
  return pid;
}

function dropPhoto(pid){
  if(!pid) return;
  if(photoURLs[pid]){ try{ URL.revokeObjectURL(photoURLs[pid]); }catch(e){} delete photoURLs[pid]; }
  if(idb){
    try { idb.transaction('photos','readwrite').objectStore('photos').delete(pid); } catch(e){}
  }
}

const photoSrc = pid => (pid && photoURLs[pid]) || null;

/* ── store ────────────────────────────────────────────────────── */
const KEY = 'raw.v1';
let db, me = null, tab = 'feed', view = null;

function blank(){ return {users:[],posts:[],comments:[],reactions:[],follows:[],seq:1}; }
function load(){
  try { db = JSON.parse(localStorage.getItem(KEY)) || null; } catch(e){ db = null; }
  if(!db || !db.users) { db = blank(); seed(); save(); }
}
function save(){ try{ localStorage.setItem(KEY, JSON.stringify(db)); }catch(e){} }
function id(){ return db.seq++; }
const now = () => new Date().toISOString();
const colorFor = s => PALETTE[[...(s||'x')].reduce((a,c)=>a+c.charCodeAt(0),0) % PALETTE.length];

function seed(){
  const p = (h,n,st,bio,deal,ok,bad) => {
    const u = {id:id(),handle:h,name:n,pass:null,state:st,color:colorFor(h),
      bio,dealing:deal,okay:ok,bad,pronouns:'',loc:'',joined:now()};
    db.users.push(u); return u;
  };
  const mins = m => new Date(Date.now()-m*60000).toISOString();
  const a = p('mara','Mara Quinn','rough','not doing a bit on here','my mom is sick and i am the only one nearby','the dog still gets walked','asking anyone for anything');
  const b = p('devin','Devin Stewart','grinding','third shift, fourth year','a job i cannot leave yet','i am reading again','sleeping before 2am');
  const c = p('sienna','Sienna Voss','small_win','recovering perfectionist','the two year anniversary of quitting','i cooked twice this week','rest without earning it');
  const d = p('lys','Lysander Thorne','numb','','a divorce that is taking longer than the marriage','','feeling things on schedule');
  const e = p('freya','Freya Sinclair','healing','loud on purpose','six months out of a bad place','therapy on tuesdays','being alone in a quiet room');
  const post = (u,body,st,mn) => db.posts.push({id:id(),user:u.id,body,state:st,at:mins(mn)});
  post(a,'Did not get out of bed until 2. Ate cereal for dinner standing up. That was the whole day and I am not going to dress it up.','rough',14);
  post(b,'Paid one bill. One. Out of four. Still counting it.','small_win',52);
  post(c,'Two years today since I quit. Nobody in my life knows what that date is except me, so I am telling you.','small_win',180);
  post(d,'Nothing happened today. I keep waiting to feel something about that.','numb',320);
  post(e,'Told my therapist the real version instead of the tidy version. Cried in a parking garage after. Worth it, I think.','healing',600);
  post(a,'Third night in a row of four hours sleep. I am not tired anymore, I am something else.','grinding',1500);
  db.comments.push({id:id(),post:db.posts[0].id,user:b.id,body:'the standing up part. i know exactly that kind of day.',at:mins(9)});
  db.comments.push({id:id(),post:db.posts[2].id,user:e.id,body:'i know what that date is now. two years.',at:mins(120)});
  db.reactions.push({id:id(),post:db.posts[0].id,user:c.id,kind:'been_there'});
  db.reactions.push({id:id(),post:db.posts[0].id,user:e.id,kind:'held'});
  db.reactions.push({id:id(),post:db.posts[2].id,user:b.id,kind:'proud'});
}

/* ── queries ──────────────────────────────────────────────────── */
const user = i => db.users.find(u=>u.id===i);
const byHandle = h => db.users.find(u=>u.handle===String(h||'').toLowerCase());
const following = i => db.follows.filter(f=>f.a===i).map(f=>f.b);
const followers = i => db.follows.filter(f=>f.b===i).map(f=>f.a);
const isFollowing = (a,b) => db.follows.some(f=>f.a===a&&f.b===b);
const rxOf = p => db.reactions.filter(r=>r.post===p);
const cmOf = p => db.comments.filter(c=>c.post===p).sort((x,y)=>x.at<y.at?-1:1);
const newest = list => [...list].sort((x,y)=>x.at<y.at?1:-1);

function ago(iso){
  const s = (Date.now()-new Date(iso).getTime())/1000;
  if(s<60) return 'just now';
  if(s<3600) return Math.floor(s/60)+'m ago';
  if(s<86400) return Math.floor(s/3600)+'h ago';
  if(s<604800) return Math.floor(s/86400)+'d ago';
  return new Date(iso).toLocaleDateString(undefined,{month:'short',day:'numeric'});
}

/* ── helpers ──────────────────────────────────────────────────── */
const esc = s => String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const el = document.getElementById.bind(document);
let toastT;
function toast(msg){
  const t = el('toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(toastT); toastT = setTimeout(()=>t.classList.remove('show'), 2200);
}
function initial(u){ return (u.name||u.handle||'?')[0].toUpperCase(); }
function pfp(u,cls){
  const src = photoSrc(u.photo);
  return src
    ? `<div class="pfp ${cls||''}" style="background:${u.color}"><img src="${src}" alt=""></div>`
    : `<div class="pfp ${cls||''}" style="background:${u.color}">${initial(u)}</div>`;
}

/* ── post card ────────────────────────────────────────────────── */
function postCard(p, opts){
  opts = opts || {};
  const u = user(p.user), s = STATES[p.state] || STATES.mundane;
  const rs = rxOf(p.id), cs = cmOf(p.id);
  const mine = me && p.user === me.id;
  const long = p.body.length > 88;

  const pills = Object.entries(REACTIONS).map(([k,r])=>{
    const on = me && rs.some(x=>x.user===me.id && x.kind===k);
    // Counts are the author's business only.
    const n = mine ? rs.filter(x=>x.kind===k).length : 0;
    return `<button class="${on?'on':''}" data-rx="${p.id}" data-kind="${k}">${r.emoji} ${r.label}${n?` <span class="n">${n}</span>`:''}</button>`;
  }).join('');

  const thread = opts.thread === false ? '' : `
    <div class="thread">
      ${cs.map(c=>{const cu=user(c.user);return `<div class="cmt"><b>${esc(cu?cu.name:'—')}</b> · ${ago(c.at)}<span>${esc(c.body)}</span></div>`;}).join('')}
      <div class="cbox">
        <input placeholder="Say something true, or nothing." data-cin="${p.id}" maxlength="600">
        <button data-csend="${p.id}">Send</button>
      </div>
    </div>`;

  return `<article class="post" style="background:${s.c}">
    <div class="who">
      ${pfp(u)}
      <b data-go="u:${u.handle}">${esc(u.name)}</b>
      <span class="st">${s.emoji} ${s.label}</span>
    </div>
    ${photoSrc(p.photo) ? `<div class="shot"><img src="${photoSrc(p.photo)}" alt=""></div>` : ''}
    <p class="txt ${long?'long':''}">${esc(p.body)}</p>
    <div class="when">${ago(p.at)}${cs.length?` · ${cs.length} ${cs.length===1?'reply':'replies'}`:''}</div>
    <div class="rx">${pills}</div>
    ${mine?`<div class="acts"><button data-del="${p.id}">Delete — you cannot edit it</button></div>`:''}
    ${thread}
  </article>`;
}

/* ── screens ──────────────────────────────────────────────────── */
function chrome(body, activeTab){
  const unseen = me ? newest(db.posts).filter(p=>p.user!==me.id).length : 0;
  return `
  <div class="top">
    <div class="mark">R</div>
    <div class="circ" data-go="people">🔍</div>
    <div class="spacer"></div>
    <div class="circ" data-go="settings">⚙</div>
    <div class="circ">🔔${unseen?`<span class="dot">${unseen>99?'99+':unseen}</span>`:''}</div>
  </div>${body}`;
}

function feedScreen(all){
  const ids = all ? null : [...following(me.id), me.id];
  const posts = newest(all ? db.posts : db.posts.filter(p=>ids.includes(p.user)));
  const rail = newest(db.posts).reduce((acc,p)=>{ if(!acc.some(x=>x.user===p.user)) acc.push(p); return acc; },[])
    .slice(0,10).map(p=>{
      const u=user(p.user), s=STATES[u.state]||STATES.mundane;
      return `<div class="rail-item" data-go="u:${u.handle}">
        <div class="ring" style="background:${s.l}"><span>${s.emoji}</span></div>
        <small>${esc(u.name.split(' ')[0])}</small></div>`;
    }).join('');

  return chrome(`
    <div class="tabs">
      <button class="tab ${all?'':'on'}" data-tab="feed">Your feed</button>
      <button class="tab ${all?'on':''}" data-tab="everyone">Everyone</button>
    </div>
    <div class="pad">
      <div class="h2">Right now<span class="more">where people are at</span></div>
      <div class="rail">${rail}</div>
      <div class="h2">${all?'Everything, newest first':'Newest first — that is the whole ranking'}</div>
      ${posts.length ? posts.map(p=>postCard(p)).join('')
        : `<div class="empty">Nothing here yet.<br>Follow some people, or post the first one.</div>`}
    </div>`, all?'everyone':'feed');
}

function peopleScreen(){
  const others = db.users.filter(u=>u.id!==me.id);
  const tiles = others.map((u,i)=>{
    const s = STATES[u.state]||STATES.mundane, wide = i===0;
    const on = isFollowing(me.id,u.id);
    return `<div class="tile ${wide?'wide':''}" style="background:${s.l}" data-go="u:${u.handle}">
      ${pfp(u)}
      <button class="fol ${on?'on':''}" data-fol="${u.id}">${on?'Following':'Follow'}</button>
      <b>${esc(u.name)}</b>
      <small>${s.emoji} ${s.label}</small>
    </div>`;
  }).join('');
  return chrome(`
    <div class="pad">
      <div class="h1">People</div>
      <div class="sub">Everyone who is here. No suggestions, no ranking — just the list.</div>
      <div class="mosaic">${tiles || '<div class="empty">Nobody else yet. You are early.</div>'}</div>
    </div>`, 'people');
}

function profileScreen(handle){
  const u = byHandle(handle); if(!u) return feedScreen(false);
  const s = STATES[u.state]||STATES.mundane, mine = u.id===me.id;
  const posts = newest(db.posts.filter(p=>p.user===u.id));
  const qa = [['What I am actually dealing with',u.dealing],['What is going okay',u.okay],
              ['What I am bad at',u.bad]].filter(x=>x[1]);
  return chrome(`
    <div class="pad">
      <div class="phead" style="background:${s.l}">
        ${pfp(u)}
        <h2>${esc(u.name)}</h2>
        <div class="meta">@${esc(u.handle)}${u.pronouns?' · '+esc(u.pronouns):''}${u.loc?' · '+esc(u.loc):''} · ${s.emoji} ${s.label}</div>
        ${u.bio?`<p class="bio">${esc(u.bio)}</p>`:''}
        ${qa.length?`<dl class="qa">${qa.map(([k,v])=>`<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>`:''}
        <div class="priv">${
          mine ? `${followers(u.id).length} follow you · you follow ${following(u.id).length}. Only you can see these.`
               : `${isFollowing(u.id,me.id)?'Follows you. ':''}${isFollowing(me.id,u.id)?'You follow them.':''}`
        }</div>
      </div>
      ${mine ? `<button class="ghost-btn" data-go="settings">Edit profile</button>`
             : `<button class="solid-btn" data-fol="${u.id}">${isFollowing(me.id,u.id)?'Following':'Follow'}</button>`}
      <div class="h2">${mine?'Your posts':'Posts'}</div>
      ${posts.length?posts.map(p=>postCard(p)).join(''):'<div class="empty">Nothing posted yet.</div>'}
    </div>`, mine?'you':'people');
}

let draftState = 'mundane', draftPhoto = null, draftBody = '';
function composeScreen(){
  const prompt = PROMPTS[new Date().getDate() % PROMPTS.length];
  return `<div class="top"><div class="mark">R</div>
      <div class="spacer"></div><div class="circ" data-go="back">✕</div></div>
    <div class="pad">
      <div class="h1">Post it</div>
      <div class="sub">${prompt}</div>
      <textarea class="inp" id="body" rows="7" maxlength="1200"
        placeholder="No filter, no caption voice. Just what is happening.">${esc(draftBody)}</textarea>
      <div class="states">${Object.entries(STATES).map(([k,s])=>
        `<button data-st="${k}" class="${k===draftState?'on':''}"
          style="${k===draftState?`background:${s.c};border-color:${s.c}`:''}">${s.emoji} ${s.label}</button>`).join('')}</div>
      ${photoSrc(draftPhoto)
        ? `<div class="pick"><img src="${photoSrc(draftPhoto)}" alt="">
             <button class="pick-x" id="unpick">Remove photo</button></div>`
        : `<label class="pick-btn">Add a photo
             <input type="file" accept="image/*" id="postpic" hidden></label>`}
      <button class="solid-btn" id="send">Post it</button>
      <div class="sub" style="margin-top:14px;font-size:12.5px;color:var(--faint)">
        You can delete this later. You cannot edit it.</div>
    </div>`;
}

function settingsScreen(){
  const f = (l,k,v,ta) => `<label class="field">${l}</label>${
    ta ? `<textarea class="inp" rows="3" maxlength="400" data-f="${k}">${esc(v||'')}</textarea>`
       : `<input class="inp" maxlength="60" data-f="${k}" value="${esc(v||'')}">`}`;
  return `<div class="top"><div class="mark">R</div><div class="spacer"></div>
      <div class="circ" data-go="back">✕</div></div>
    <div class="pad">
      <div class="h1">Your profile</div>
      <div class="sub">Answer what you want. Blank is an honest answer too.</div>
      <label class="field">Profile picture</label>
      <div class="avatar-row">
        ${photoSrc(me.photo)
          ? `<div class="pfp lg" style="background:${me.color}"><img src="${photoSrc(me.photo)}" alt=""></div>`
          : `<div class="pfp lg" style="background:${me.color}">${initial(me)}</div>`}
        <div>
          <label class="pick-btn sm">${me.photo?'Change':'Choose a photo'}
            <input type="file" accept="image/*" id="avatarpic" hidden></label>
          ${me.photo?`<button class="pick-x sm" id="unavatar">Remove</button>`:''}
          <div class="tiny faint" style="margin-top:8px">No filters. That is the point.</div>
        </div>
      </div>
      ${f('Name','name',me.name)}
      ${f('Pronouns','pronouns',me.pronouns)}
      ${f('Where you are','loc',me.loc)}
      ${f('Bio — not a résumé','bio',me.bio,1)}
      ${f('What you are actually dealing with','dealing',me.dealing,1)}
      ${f('What is going okay','okay',me.okay,1)}
      ${f('What you are bad at','bad',me.bad,1)}
      <label class="field">Where you are at right now</label>
      <div class="states">${Object.entries(STATES).map(([k,s])=>
        `<button data-st2="${k}" class="${k===me.state?'on':''}"
          style="${k===me.state?`background:${s.c};border-color:${s.c}`:''}">${s.emoji} ${s.label}</button>`).join('')}</div>
      <button class="solid-btn" id="savep">Save</button>
      <button class="ghost-btn" id="logout">Sign out</button>
    </div>`;
}

let authMode = 'in', authDraft = {name:'',handle:'',who:''};
function authScreen(err){
  const up = authMode === 'up';
  return `<div class="auth">
    <div class="top" style="padding-left:0;padding-right:0">
      <div class="mark">R</div><div class="spacer"></div>
      <button class="circ" data-auth="swap" style="width:auto;padding:0 18px;border-radius:22px;font-size:13.5px;font-weight:600;color:#fff">
        ${up?'Sign In':'Sign Up'}</button>
    </div>
    <h1>${up?'Sign Up':'Sign In'}</h1>
    <svg class="wave" viewBox="0 0 320 70" preserveAspectRatio="none" aria-hidden="true">
      <path d="M0 46 C 60 8, 110 66, 168 34 S 268 6, 320 22" fill="none"
        stroke="#e0533a" stroke-width="2.5" stroke-linecap="round"/></svg>
    ${up?`<label class="field">Name</label>
          <input class="inp" id="a_name" autocapitalize="words" value="${esc(authDraft.name)}">
          <label class="field">Handle</label>
          <input class="inp" id="a_handle" autocapitalize="none" placeholder="lowercase, 3–20" value="${esc(authDraft.handle)}">`:''}
    <label class="field">${up?'Email':'Handle or email'}</label>
    <input class="inp" id="a_who" autocapitalize="none" ${up?'type="email"':''} value="${esc(authDraft.who)}">
    <label class="field">Password</label>
    <input class="inp" id="a_pass" type="password">
    ${err?`<div class="err">${esc(err)}</div>`:''}
    <button class="grad-btn" data-auth="go"><span>${up?'Create it':'Sign In'} →</span></button>
    <div class="swap" data-auth="swap">${up?'Already here? <b>Sign in</b>':'No account? <b>Make one</b>'}</div>
    <div class="or">No Google, no Apple, no Facebook. Signing in with them tells them
      you were here, and this is not a place that reports back.</div>
  </div>`;
}

/* ── render ───────────────────────────────────────────────────── */
function nav(active){
  const items = [['feed','⌂','Feed'],['everyone','◎','Everyone'],['people','◍','People'],['you','☺','You']];
  return `<div class="nav">${items.map(([k,i,l])=>
    `<button data-tab="${k}" class="${k===active?'on':''}"><i>${i}</i>${l}</button>`).join('')}</div>
    <div class="fabs">
      <div class="fab primary" data-go="compose">＋</div>
    </div>`;
}

function render(){
  const s = el('screen');
  if(!me){ s.innerHTML = authScreen(view && view.err); s.scrollTop = 0; return; }
  if(view && view.name === 'compose'){ s.innerHTML = composeScreen(); s.scrollTop=0; return; }
  if(view && view.name === 'settings'){ s.innerHTML = settingsScreen(); s.scrollTop=0; return; }

  let body, active = tab;
  if(view && view.name === 'profile'){ body = profileScreen(view.handle); active = view.handle===me.handle?'you':'people'; }
  else if(tab === 'people') body = peopleScreen();
  else if(tab === 'you') { body = profileScreen(me.handle); }
  else body = feedScreen(tab === 'everyone');

  s.innerHTML = body + nav(active);
  s.scrollTop = 0;
}

/* ── actions ──────────────────────────────────────────────────── */
function go(dest){
  if(dest === 'back'){
    if(view && view.name === 'compose'){ dropPhoto(draftPhoto); draftPhoto = null; draftBody = ''; }
    view = null; render(); return;
  }
  if(dest === 'compose'){ view = {name:'compose'}; render(); return; }
  if(dest === 'settings'){ view = {name:'settings'}; render(); return; }
  if(dest === 'people'){ view = null; tab = 'people'; render(); return; }
  if(dest.startsWith('u:')){ view = {name:'profile',handle:dest.slice(2)}; render(); return; }
}

function doAuth(){
  const pass = el('a_pass').value, who = el('a_who').value.trim().toLowerCase();
  const nameEl = el('a_name'), handleEl = el('a_handle');
  authDraft = {who, name:nameEl?nameEl.value:'', handle:handleEl?handleEl.value:''};
  if(authMode === 'up'){
    const name = authDraft.name.trim();
    const handle = authDraft.handle.trim().toLowerCase().replace(/^@/,'');
    if(!/^[a-z0-9_]{3,20}$/.test(handle)) return fail('Handle needs 3–20 characters: lowercase letters, numbers, underscores.');
    if(byHandle(handle)) return fail('That handle is taken.');
    if(!who.includes('@')) return fail('That email does not look like an email.');
    if(pass.length < 8) return fail('Password needs at least 8 characters.');
    me = {id:id(),handle,name:name||handle,email:who,pass,state:'mundane',color:colorFor(handle),
          bio:'',dealing:'',okay:'',bad:'',pronouns:'',loc:'',photo:null,joined:now()};
    db.users.push(me); save();
    localStorage.setItem(KEY+'.me', me.id); authDraft = {name:'',handle:'',who:''};
    view = {name:'settings'}; render(); toast('Welcome. Tell us the real version.'); return;
  }
  const u = db.users.find(x => (x.handle===who || x.email===who) && x.pass);
  if(!u || u.pass !== pass) return fail('That combination did not work.');
  me = u; localStorage.setItem(KEY+'.me', me.id); view = null; tab='feed'; render();
}
function fail(msg){ view = {err:msg}; render(); }

function post(){
  const body = (el('body') ? el('body').value : draftBody).trim();
  if(!body) return toast('Nothing to say is fine. Blank posts are not.');
  db.posts.push({id:id(),user:me.id,body,state:draftState,at:now(),photo:draftPhoto});
  me.state = draftState;            // your profile follows your last post
  draftPhoto = null; draftBody = '';
  save(); view = null; tab='feed'; render(); toast('Posted. You can delete it, not edit it.');
}

document.addEventListener('click', e => {
  const t = e.target.closest('[data-go],[data-tab],[data-rx],[data-csend],[data-fol],[data-del],[data-st],[data-st2],[data-auth],#send,#savep,#logout,#unpick,#unavatar');
  if(!t) return;

  if(t.dataset.auth){
    if(t.dataset.auth === 'swap'){ authMode = authMode==='in'?'up':'in'; view=null; render(); }
    else doAuth();
    return;
  }
  if(t.dataset.go) return go(t.dataset.go);
  if(t.dataset.tab){ view = null; tab = t.dataset.tab; render(); return; }

  if(t.dataset.rx){
    const p = +t.dataset.rx, k = t.dataset.kind;
    const i = db.reactions.findIndex(r=>r.post===p&&r.user===me.id&&r.kind===k);
    if(i>=0) db.reactions.splice(i,1);
    else db.reactions.push({id:id(),post:p,user:me.id,kind:k});
    save(); render(); return;
  }
  if(t.dataset.csend){
    const p = +t.dataset.csend, inp = document.querySelector(`[data-cin="${p}"]`);
    const body = inp.value.trim();
    if(!body) return toast('Empty comment.');
    db.comments.push({id:id(),post:p,user:me.id,body,at:now()});
    save(); render(); return;
  }
  if(t.dataset.fol){
    e.stopPropagation();
    const b = +t.dataset.fol;
    const i = db.follows.findIndex(f=>f.a===me.id&&f.b===b);
    if(i>=0) db.follows.splice(i,1); else db.follows.push({a:me.id,b});
    save(); render(); return;
  }
  if(t.dataset.del){
    const p = +t.dataset.del;
    const gone = db.posts.find(x=>x.id===p);
    if(gone) dropPhoto(gone.photo);
    db.posts = db.posts.filter(x=>x.id!==p);
    db.comments = db.comments.filter(c=>c.post!==p);
    db.reactions = db.reactions.filter(r=>r.post!==p);
    save(); render(); toast('Deleted. That is different from editing.'); return;
  }
  if(t.dataset.st){ draftState = t.dataset.st; render(); return; }
  if(t.dataset.st2){ me.state = t.dataset.st2; save(); render(); return; }
  if(t.id === 'unpick'){ dropPhoto(draftPhoto); draftPhoto = null; render(); return; }
  if(t.id === 'unavatar'){ dropPhoto(me.photo); me.photo = null; save(); render(); return; }
  if(t.id === 'send') return post();
  if(t.id === 'savep'){
    document.querySelectorAll('[data-f]').forEach(i => me[i.dataset.f] = i.value.trim());
    if(!me.name) me.name = me.handle;
    save(); view = null; tab='you'; render(); toast('Profile saved.'); return;
  }
  if(t.id === 'logout'){ me=null; localStorage.removeItem(KEY+'.me'); view=null; render(); }
});

document.addEventListener('input', e => {
  if(e.target.id === 'body') draftBody = e.target.value;
});

document.addEventListener('change', async e => {
  const t = e.target;
  if(t.id !== 'avatarpic' && t.id !== 'postpic') return;
  const file = t.files && t.files[0];
  if(!file) return;
  if(!/^image\//.test(file.type)) return toast('That is not an image.');
  toast('Adding the photo…');
  try {
    if(t.id === 'avatarpic'){
      const old = me.photo;
      me.photo = await putPhoto(file, 512);
      dropPhoto(old);
      save();
    } else {
      dropPhoto(draftPhoto);
      draftPhoto = await putPhoto(file, 1280);
    }
    render();
  } catch(err){
    toast('Could not read that image.');
  }
});

document.addEventListener('keydown', e => {
  if(e.key === 'Enter' && e.target.dataset && e.target.dataset.cin){
    document.querySelector(`[data-csend="${e.target.dataset.cin}"]`).click();
  }
});

// Hardware back button, handed over from the Android shell. Pops our own screen
// stack; when there is nothing left to pop, ask the host to close the app.
window.rawBack = function(){
  if(view){ view = null; render(); return true; }
  if(me && tab !== 'feed'){ tab = 'feed'; render(); return true; }
  if(window.RawHost && window.RawHost.exitApp) window.RawHost.exitApp();
  return false;
};

(async function boot(){
  idb = await openPhotos();
  await loadPhotoURLs();
  load();
  const savedId = +localStorage.getItem(KEY+'.me');
  if(savedId){ const u = user(savedId); if(u && u.pass) me = u; }
  render();
})();
