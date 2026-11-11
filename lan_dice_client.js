/* IBS_DICE_MODAL_CONTROLS_V6_3 */
/* IBS LAN dice v4 - server-authoritative rolls, resilient polling, two-player receipt acknowledgements. */
(() => {
  if (window.__ibsDiceAttached) return;
  window.__ibsDiceAttached = true;
  const css = document.createElement('style');
  css.textContent = `
    #ibs-dice-screen {position:fixed;inset:0;z-index:2147483646;background:rgba(3,10,21,.93);display:none;align-items:flex-start;justify-content:center;padding:3vh 2vw;box-sizing:border-box;color:#f8f5e9;font-family:system-ui,"Microsoft YaHei",sans-serif;backdrop-filter:blur(6px)}
    #ibs-dice-screen.ibs-collapsed {background:transparent;backdrop-filter:none;pointer-events:none}
    #ibs-dice-screen.ibs-collapsed #ibs-dice-shell {height:0;min-height:0;max-height:none;overflow:visible;background:transparent;border:0;box-shadow:none;pointer-events:none}
    #ibs-dice-screen.ibs-collapsed #ibs-dice-shell > :not(#ibs-dice-restore) {display:none}
    #ibs-dice-restore {display:none;position:absolute;right:14px;top:14px;z-index:1;pointer-events:auto;background:#d5b875;color:#14233a;border:2px solid #f2d991;border-radius:12px;padding:11px 17px;font-weight:800;cursor:pointer;box-shadow:0 5px 18px #0009}
    #ibs-dice-screen.ibs-collapsed #ibs-dice-restore {display:block}
    #ibs-dice-toggle {position:absolute;right:14px;top:14px;z-index:1;color:#f8f5e9;border:1px solid #839ab6;border-radius:8px;background:#34506d;padding:7px 12px;cursor:pointer}
    #ibs-dice-shell {position:relative;width:min(1080px,100%);max-height:94vh;overflow:hidden;background:#142339;border:1px solid #8b94ac;border-radius:16px;box-shadow:0 20px 95px #000b;display:flex;flex-direction:column}
    #ibs-dice-banner {position:relative;text-align:center;padding:22px 135px 8px;background:linear-gradient(110deg,#213c59,#142339)}
    #ibs-dice-side {font-size:clamp(30px,4.5vw,51px);font-weight:900;color:#f5d48a;letter-spacing:.06em;line-height:1.25}
    #ibs-dice-detail {font-size:13px;opacity:.9;line-height:1.6;margin:8px 0 2px;overflow-wrap:anywhere}
    #ibs-dice-turn {font-size:12px;opacity:.67;padding-bottom:8px}
    #ibs-dice-connection {display:none;margin:0 auto 8px;max-width:90%;border-radius:6px;padding:7px 12px;background:#713322;color:#fff3eb;font-size:13px}
    #ibs-dice-columns {display:grid;grid-template-columns:minmax(0,1fr) minmax(265px,42%);min-height:0;flex:1}
    #ibs-dice-play {padding:24px;display:flex;flex-direction:column;justify-content:center;align-items:center;min-width:0}
    #ibs-dice-type {font-size:20px;font-weight:800;margin-bottom:8px}
    #ibs-dice-row {display:flex;gap:20px;justify-content:center;margin:19px 0}
    .ibs-die {background:#f7f1e3;border:3px solid #b69e68;border-radius:17px;color:#253448;width:104px;height:104px;display:grid;place-items:center;font-size:77px;box-shadow:0 8px 20px #0009;user-select:none}
    .ibs-die.shake {animation:ibs-jitter .15s infinite alternate}
    @keyframes ibs-jitter {0%{transform:translate(-6px,4px) rotate(-12deg)}100%{transform:translate(7px,-5px) rotate(13deg)}}
    #ibs-dice-result {font-size:23px;min-height:55px;font-weight:800;color:#f5d48a;text-align:center;line-height:1.6;white-space:pre-line}
    #ibs-dice-roll {background:#d5b875;color:#14233a;border:0;border-radius:10px;font-size:18px;font-weight:800;padding:15px 25px;max-width:320px;width:100%;cursor:pointer}
    #ibs-dice-roll:disabled {background:#526379;color:#f5f2e7;cursor:not-allowed}
    #ibs-dice-source {font-size:11px;color:#bac6d8;margin-top:14px;text-align:center}
    #ibs-dice-rules {min-width:0;display:flex;flex-direction:column;border-left:1px solid #43566b;background:#0c192b;padding:16px;overflow:auto;max-height:60vh}
    #ibs-dice-rules h3 {margin:0 0 8px;color:#e5c78d;font-size:18px}
    #ibs-dice-rule-note {font-size:12px;line-height:1.6;color:#aebed3;margin:0 0 12px}
    #ibs-dice-rules-table {border-collapse:collapse;width:100%;font-size:13px}
    #ibs-dice-rules-table td,#ibs-dice-rules-table th {border-bottom:1px solid #30445b;padding:7px 8px;text-align:left;vertical-align:top}
    #ibs-dice-rules-table th:first-child,#ibs-dice-rules-table td:first-child {width:76px;white-space:nowrap;font-weight:700}
    #ibs-dice-rules-table tr.ibs-selected {background:#53441b;outline:2px solid #f6c35f;outline-offset:-2px;color:#fff1cc}
    #ibs-dice-rule-empty {font-size:13px;color:#b5c4d4;line-height:1.7}
    @media(max-width:700px){#ibs-dice-banner{padding:54px 12px 8px}#ibs-dice-shell{max-height:94vh;overflow:auto}#ibs-dice-columns{display:block}#ibs-dice-play{padding:14px}#ibs-dice-rules{border-left:0;border-top:1px solid #43566b;max-height:32vh}.ibs-die{width:78px;height:78px;font-size:58px}#ibs-dice-row{margin:10px 0}}
    @media(prefers-reduced-motion:reduce){.ibs-die.shake{animation:none}}
  `;
  document.head.appendChild(css);
  const root = document.createElement('div'); root.id = 'ibs-dice-screen';
  root.innerHTML = `<div id="ibs-dice-shell" role="dialog" aria-modal="true" aria-labelledby="ibs-dice-side"><button id="ibs-dice-restore" type="button">展开投骰 · 等待判定</button>
      <header id="ibs-dice-banner"><button id="ibs-dice-toggle" type="button" aria-label="收起投骰页面">— 收起</button><div id="ibs-dice-side">等待判定</div><div id="ibs-dice-detail">正在读取裁决信息…</div><div id="ibs-dice-turn"></div><div id="ibs-dice-connection" role="alert"></div></header>
      <div id="ibs-dice-columns"><main id="ibs-dice-play"><div id="ibs-dice-type">D66</div><div id="ibs-dice-row"></div>
        <div id="ibs-dice-result" role="status"></div><button id="ibs-dice-roll" disabled>等待服务器</button>
        <div id="ibs-dice-source"></div></main>
      <aside id="ibs-dice-rules"><h3 id="ibs-dice-rule-title">相关规则</h3><p id="ibs-dice-rule-note"></p>
        <table id="ibs-dice-rules-table" aria-label="判定规则表"><thead><tr><th>骰点</th><th>裁决结果</th></tr></thead><tbody id="ibs-dice-rule-body"></tbody></table>
        <p id="ibs-dice-rule-empty" hidden>当前判定没有可明确定位的结构化规则表，最终以引擎裁决为准。</p></aside></div>
    </div>`;
  document.body.appendChild(root);
  const el = id => root.querySelector(`#${id}`);
  const sideTitle = el('ibs-dice-side'), detail = el('ibs-dice-detail'), turn = el('ibs-dice-turn');
  const diceType = el('ibs-dice-type'), row = el('ibs-dice-row'), result = el('ibs-dice-result');
  const btn = el('ibs-dice-roll'), source = el('ibs-dice-source'), connection = el('ibs-dice-connection');
  const ruleTitle = el('ibs-dice-rule-title'), ruleNote = el('ibs-dice-rule-note'), ruleBody = el('ibs-dice-rule-body');
  const empty = el('ibs-dice-rule-empty'), ruleTable = el('ibs-dice-rules-table');
  const restore = el('ibs-dice-restore'), collapse = el('ibs-dice-toggle');
  let isCollapsed = false;
  function toggleCollapsed(value) {
    isCollapsed = value;
    root.classList.toggle('ibs-collapsed', value);
    collapse.setAttribute('aria-expanded', String(!value));
    restore.setAttribute('aria-expanded', String(!value));
  }
  collapse.addEventListener('click', () => toggleCollapsed(true));
  restore.addEventListener('click', () => toggleCollapsed(false));
  const faces = ['⚀','⚁','⚂','⚃','⚄','⚅'];
  const STATE_TIMEOUT_MS = 4500, POST_TIMEOUT_MS = 4500, ACK_TIMEOUT_MS = 3500;
  let activeId = null, lastStatus = null, timer = null, clockOffset = 0;
  let inFlight = false, sendingId = null, acceptedId = null, sendingStarted = 0;
  let ackId = null, ackInFlight = false, ackTimer = null, ackRetryAt = 0;
  let lastGoodAt = Date.now(), lastError = '';

  function resetMotion() {if(timer !== null) {clearInterval(timer); timer = null;} for(const die of row.children) die.classList.remove('shake');}
  function setupDice(n) {row.replaceChildren();for(let i=0;i<n;i++){const die=document.createElement('div');die.className='ibs-die';die.textContent='⚀';row.append(die);}}
  function motionFrame(startMs) {
    const elapsed = Math.max(0, Date.now()-clockOffset-Number(startMs||Date.now()));
    const frame = Math.floor(elapsed/85);
    for(let i=0;i<row.children.length;i++) row.children[i].textContent=faces[(frame+i*2)%6];
  }
  function startMotion(startMs) {
    if(timer !== null) return;
    for(const die of row.children)die.classList.add('shake');
    motionFrame(startMs);
    timer = setInterval(()=>motionFrame(startMs),85);
  }
  function updateRule(rule) {
    ruleTitle.textContent = rule?.title || '相关规则';ruleNote.textContent = rule?.note || '';
    ruleBody.replaceChildren();
    const rows=Array.isArray(rule?.rows)?rule.rows:[];
    empty.hidden=rows.length>0;ruleTable.hidden=rows.length===0;
    for(const v of rows){const tr=document.createElement('tr');tr.dataset.value=String(v.key);const key=document.createElement('td');key.textContent=String(v.key);const value=document.createElement('td');value.textContent=String(v.value);tr.append(key,value);ruleBody.append(tr);}
  }
  function highlight(adjusted) {
    const target=String(adjusted);
    for(const tr of ruleBody.children){tr.classList.toggle('ibs-selected',tr.dataset.value===target);if(tr.dataset.value===target)tr.scrollIntoView({block:'nearest',behavior:'smooth'});}
  }
  function reveal(d) {
    resetMotion();
    if(Array.isArray(d.dice))for(let i=0;i<row.children.length;i++)row.children[i].textContent=faces[d.dice[i]-1]||'?';
    result.textContent = `${d.notation}：${d.raw}`+(d.adjusted!==undefined&&d.adjusted!==d.raw?`　修正后：${d.adjusted}`:'')+(d.outcome?`\n${d.outcome}`:'');
    highlight(d.adjusted??d.raw);
  }
  function showConnection(message) {connection.style.display=message?'block':'none';connection.textContent=message||'';}

  async function fetchWithTimeout(url, options, timeoutMs) {
    const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),timeoutMs);
    try {return await fetch(url,{...options,signal:controller.signal});}
    finally {clearTimeout(timeout);}
  }
  function resetForNewId(id, d) {
    activeId=id;lastStatus=null;resetMotion();sendingId=null;acceptedId=null;
    ackId=null;ackInFlight=false;ackRetryAt=0;
    if(ackTimer!==null){clearTimeout(ackTimer);ackTimer=null;}
    setupDice(d.notation==='1D6'?1:2);result.textContent='';updateRule(d.rule);
  }
  async function sendAck(id) {
    if(id!==activeId||(lastStatus!=='revealed'&&lastStatus!=='committing')||ackId===id||ackInFlight||Date.now()<ackRetryAt)return;
    ackInFlight=true;
    try {
      const r=await fetchWithTimeout('/lan/dice/ack',{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})},ACK_TIMEOUT_MS);
      if(r.ok||r.status===409)ackId=id; // 409 means that the next roll has already started.
      else ackRetryAt=Date.now()+1200;
    } catch(_e){ackRetryAt=Date.now()+1200;}
    finally {ackInFlight=false;}
  }
  function scheduleAck(id) {
    if(ackId===id||ackTimer!==null)return;
    // Keep the result visible before confirming receipt. No reroll is ever sent.
    ackTimer=setTimeout(()=>{ackTimer=null;sendAck(id);},650);
  }

  btn.addEventListener('click',async()=>{
    if(!activeId||btn.disabled||sendingId||acceptedId)return;
    const id=activeId;
    sendingId=id;sendingStarted=Date.now();btn.disabled=true;btn.textContent='正在发送投骰请求…';
    try {
      const r=await fetchWithTimeout('/lan/dice/roll',{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})},POST_TIMEOUT_MS);
      const payload=await r.json();
      if(!r.ok)throw Error(payload.detail||`HTTP ${r.status}`);
      // Accepted is not proof of the dice face: wait for the authoritative state.
      if(activeId===id)acceptedId=id;
    }catch(e){
      if(activeId===id)result.textContent=`投骰请求未确认（可能已被服务器接收）：${String(e)}\n正在重新读取服务器状态，请勿反复点击。`;
    }finally{if(sendingId===id)sendingId=null;}
  });

  async function refresh(){
    if(inFlight)return;
    inFlight=true;
    try {
      const res=await fetchWithTimeout('/lan/dice/state',{cache:'no-store',credentials:'same-origin'},STATE_TIMEOUT_MS);
      if(!res.ok)throw Error(`HTTP ${res.status}`);
      const d=await res.json();
      lastGoodAt=Date.now();lastError='';showConnection('');
      if(Number.isFinite(d.server_time_ms))clockOffset=Date.now()-d.server_time_ms;
      // Signal a stale browser bundle if the gateway was upgraded while tab remained open.
      if(d.protocol && d.protocol!==4)showConnection('前端与骰子服务器版本不一致，请双方按 Ctrl+F5 刷新。');
      if(d.status==='idle'){
        root.style.display='none';activeId=null;lastStatus=null;resetMotion();
        sendingId=null;acceptedId=null;return;
      }
      root.style.display='flex';
      if(d.status==='calculating'){
        resetMotion();activeId=null;lastStatus=null;sendingId=null;acceptedId=null;
        sideTitle.textContent='正在进行规则裁决';detail.textContent='正在等待下一项判定，请勿关闭联机服务器。';
        if(d.error)detail.textContent+=` ${d.error}`;
        btn.style.display='none';row.style.display='none';result.textContent='';return;
      }
      btn.style.display='block';row.style.display='flex';
      if(activeId!==d.id){
        resetForNewId(d.id,d);
        // A new roll that this browser must operate should not remain hidden.
        if(d.may_roll)toggleCollapsed(false);
      }
      restore.textContent=`展开投骰 · 第 ${d.seq} 次 · ${d.owner==='axis'?'轴心国':'同盟国'}`;
      sideTitle.textContent=`${d.owner==='axis'?'轴心国':'同盟国'} 玩家投掷`;
      detail.textContent=`${d.reason} · ${d.detail||'规则检定'}`;
      turn.textContent=`回合 ${d.turn||'?'} · ${d.phase} · 第 ${d.seq} 次掷骰`;
      diceType.textContent=`判定骰型：${d.notation}`;
      source.textContent=`随机数来源：${d.source==='cpu_rdseed'?'CPU RDSEED':d.source==='cpu_rdrand'?'CPU RDRAND':'操作系统安全随机数'} · 动画不影响结果`;
      if(d.status!=='waiting')acceptedId=null;
      if(d.status!==lastStatus){
        lastStatus=d.status;
        if(d.status==='rolling'){if(sendingId===d.id)sendingId=null;result.textContent='';startMotion(d.animation_start_ms);}
        else if((d.status==='revealed'||d.status==='committing')&&Array.isArray(d.dice)){if(sendingId===d.id)sendingId=null;reveal(d);scheduleAck(d.id);}
        else if(d.status==='waiting'){resetMotion();}
        else if(d.status==='generating'){resetMotion();result.textContent='服务器正在读取 CPU 硬件随机数…';}
      }
      if((d.status==='revealed'||d.status==='committing')&&ackId!==d.id&&ackTimer===null&&!ackInFlight&&Date.now()>=ackRetryAt)scheduleAck(d.id);
      // An accepted POST can have a delayed state response. Never offer a second
      // roll while that acknowledgement is pending; no automatic retry of dice.
      const pending=(sendingId===d.id||acceptedId===d.id);
      btn.disabled=!d.may_roll||pending;
      if(d.status==='waiting'){
        btn.textContent=pending?'请求已发送，等待同步…':(d.may_roll?'点击投掷骰子':'等待指定玩家投掷');
        if(acceptedId===d.id&&Date.now()-sendingStarted>6000){
          // State is still authoritative; allow the *player* to retry the same ID.
          acceptedId=null;btn.disabled=!d.may_roll;
          result.textContent='服务器尚未显示投骰结果。如确认仍在等待，可重试同一骰点请求。';
        }
      } else if(d.status==='generating') btn.textContent='服务器正在读取 CPU 随机数…';
      else btn.textContent=d.status==='rolling'?'双方同步滚动中…':
        (d.status==='committing'?'结果已确定，正在记录战报…':'结果已揭晓，等待短暂展示');
    }catch(err){
      lastError=String(err);
      showConnection(`连接延迟或请求失败：${lastError}。正在自动重连，请勿重复投骰。`);
      btn.disabled=true;
    }finally{inFlight=false;}
  }
  refresh();setInterval(refresh,350);
  setInterval(()=>{
    if(root.style.display==='flex'&&Date.now()-lastGoodAt>5000){
      showConnection('超过 5 秒未收到新的服务器状态，当前骰子画面可能已经过期；正在重连。');
      btn.disabled=true;
    }
  },1000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
})();
