/* IBS LAN dice UI v2.1: collapsible, non-blocking minimized mode; server alone generates dice. */
(() => {
  if (window.__ibsDiceAttached) return;
  window.__ibsDiceAttached = true;
  const css = document.createElement('style');
  css.textContent = `
    #ibs-dice-screen {position:fixed;inset:0;z-index:2147483646;background:rgba(3,10,21,.90);display:none;align-items:center;justify-content:center;color:#f8f5e9;font-family:system-ui,"Microsoft YaHei",sans-serif}
    #ibs-dice-shell {width:min(1080px,96vw);max-height:94vh;overflow:hidden;background:#142339;border:1px solid #8b94ac;border-radius:16px;box-shadow:0 20px 95px #000b;display:flex;flex-direction:column}
    #ibs-dice-banner {position:relative;text-align:center;padding:22px 140px 8px;background:linear-gradient(110deg,#213c59,#142339)}
    #ibs-dice-collapse {position:absolute;top:13px;right:14px;background:#2c4561;color:#fff;border:1px solid #8094a8;border-radius:9px;padding:9px 13px;font-size:14px;font-weight:700;cursor:pointer}
    #ibs-dice-collapse:focus-visible,#ibs-dice-mini:focus-visible{outline:3px solid #ffd477;outline-offset:2px}
    #ibs-dice-mini {position:fixed;bottom:20px;right:20px;z-index:2147483646;display:none;align-items:center;gap:10px;max-width:min(420px,calc(100vw - 24px));color:#fff;background:#1a314b;border:2px solid #e3bd70;border-radius:14px;box-shadow:0 8px 30px #000a;padding:13px 17px;font:700 15px/1.45 system-ui,"Microsoft YaHei",sans-serif;cursor:pointer;text-align:left}
    #ibs-dice-mini.ibs-dice-my-turn{background:#493316;border-color:#ffd477}
    #ibs-dice-mini-status{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    #ibs-dice-mini-expander{flex-shrink:0;color:#ffdf98;font-size:13px}
    #ibs-dice-side {font-size:clamp(30px,4.5vw,51px);font-weight:900;color:#f5d48a;letter-spacing:.06em;line-height:1.25}
    #ibs-dice-detail {font-size:13px;opacity:.9;line-height:1.6;margin:8px 0 2px;overflow-wrap:anywhere}
    #ibs-dice-turn {font-size:12px;opacity:.67;padding-bottom:8px}
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
    @media(max-width:700px){#ibs-dice-banner{padding:53px 13px 8px}#ibs-dice-collapse{top:9px;right:9px}#ibs-dice-shell{max-height:94vh;overflow:auto}#ibs-dice-columns{display:block}#ibs-dice-play{padding:14px}#ibs-dice-rules{border-left:0;border-top:1px solid #43566b;max-height:32vh}.ibs-die{width:78px;height:78px;font-size:58px}#ibs-dice-row{margin:10px 0}}
    @media(prefers-reduced-motion:reduce){.ibs-die.shake{animation:none}}
  `;
  document.head.appendChild(css);
  const root = document.createElement('div'); root.id = 'ibs-dice-screen';
  root.innerHTML = `<div id="ibs-dice-shell" role="dialog" aria-modal="true" aria-labelledby="ibs-dice-side">
      <header id="ibs-dice-banner"><button id="ibs-dice-collapse" type="button" aria-label="收起骰子页面">— 收起</button><div id="ibs-dice-side">等待判定</div><div id="ibs-dice-detail">正在读取裁决信息…</div><div id="ibs-dice-turn"></div></header>
      <div id="ibs-dice-columns"><main id="ibs-dice-play"><div id="ibs-dice-type">D66</div><div id="ibs-dice-row"></div>
        <div id="ibs-dice-result" role="status"></div><button id="ibs-dice-roll" disabled>等待服务器</button>
        <div id="ibs-dice-source"></div></main>
      <aside id="ibs-dice-rules"><h3 id="ibs-dice-rule-title">相关规则</h3><p id="ibs-dice-rule-note"></p>
        <table id="ibs-dice-rules-table" aria-label="判定规则表"><thead><tr><th>骰点</th><th>裁决结果</th></tr></thead><tbody id="ibs-dice-rule-body"></tbody></table>
        <p id="ibs-dice-rule-empty" hidden>当前判定没有可明确定位的结构化规则表，最终以引擎裁决为准。</p></aside></div>
    </div>`;
  document.body.appendChild(root);
  const mini = document.createElement('button');
  mini.type = 'button';
  mini.id = 'ibs-dice-mini';
  mini.setAttribute('aria-label', '展开骰子判定页面');
  mini.innerHTML = '<span aria-hidden="true">⚄</span><span id="ibs-dice-mini-status">骰子判定</span><span id="ibs-dice-mini-expander">展开 ↗</span>';
  document.body.appendChild(mini);
  const el = id => root.querySelector(`#${id}`);
  const sideTitle = el('ibs-dice-side'), detail = el('ibs-dice-detail'), turn = el('ibs-dice-turn');
  const diceType = el('ibs-dice-type'), row = el('ibs-dice-row'), result = el('ibs-dice-result');
  const btn = el('ibs-dice-roll'), source = el('ibs-dice-source');
  const collapseBtn = el('ibs-dice-collapse'), miniStatus = mini.querySelector('#ibs-dice-mini-status');
  const ruleTitle = el('ibs-dice-rule-title'), ruleNote = el('ibs-dice-rule-note'), ruleBody = el('ibs-dice-rule-body');
  const empty = el('ibs-dice-rule-empty'), ruleTable = el('ibs-dice-rules-table');
  const faces = ['⚀','⚁','⚂','⚃','⚄','⚅'];
  let activeId = null, lastStatus = null, timer = null, sending = false, tick = 0, inFlight = false;
  let collapsed = false, isActive = false, latest = null, pollHandle = null;
  function updateMini(d) {
    if (!d) return;
    let label = '骰子判定进行中';
    if (d.status === 'calculating') label = d.error ? '裁决异常 · 点击展开查看' : '规则裁决中 · 点击展开';
    else if (d.status === 'waiting') label = d.may_roll ? `轮到你投掷 ${d.notation} · 点击展开` : `等待${d.owner === 'axis' ? '轴心国' : '同盟国'}投掷 · 点击展开`;
    else if (d.status === 'rolling') label = '骰子滚动中 · 点击展开';
    else if (d.status === 'revealed') label = `${d.notation} 结果已揭晓 · 点击展开`;
    miniStatus.textContent = label;
    mini.classList.toggle('ibs-dice-my-turn', d.status === 'waiting' && !!d.may_roll);
  }
  function setCollapsed(value) {
    collapsed = !!value;
    root.style.display = isActive && !collapsed ? 'flex' : 'none';
    mini.style.display = isActive && collapsed ? 'flex' : 'none';
    if (collapsed) resetMotion();
    else if (latest?.status === 'rolling') startMotion();
    else if (latest?.status === 'revealed') reveal(latest);
    updateMini(latest);
  }
  collapseBtn.addEventListener('click', () => setCollapsed(true));
  mini.addEventListener('click', () => setCollapsed(false));
  function resetMotion() { if(timer !== null) {clearInterval(timer); timer = null;} for (const die of row.children) die.classList.remove('shake'); }
  function setupDice(n) {row.replaceChildren(); for(let i=0;i<n;i++){let die=document.createElement('div');die.className='ibs-die';die.textContent='⚀';row.append(die);}}
  function startMotion() {
    if (timer !== null) return;
    for(const die of row.children) die.classList.add('shake');
    timer = setInterval(()=>{tick++; for(let i=0;i<row.children.length;i++)row.children[i].textContent=faces[(tick+i*2)%6];}, 85);
  }
  function updateRule(rule) {
    ruleTitle.textContent = rule?.title || '相关规则';
    ruleNote.textContent = rule?.note || '';
    ruleBody.replaceChildren();
    const rows = Array.isArray(rule?.rows) ? rule.rows : [];
    empty.hidden = rows.length > 0; ruleTable.hidden = rows.length === 0;
    for(const v of rows) {
      const tr = document.createElement('tr');tr.dataset.value=String(v.key);
      const key=document.createElement('td');key.textContent=String(v.key);
      const value=document.createElement('td');value.textContent=String(v.value);
      tr.append(key,value);ruleBody.appendChild(tr);
    }
  }
  function highlight(adjusted) {
    const target=String(adjusted);
    for(const tr of ruleBody.children) {
      tr.classList.toggle('ibs-selected', tr.dataset.value === target);
      if (tr.dataset.value === target && !collapsed) tr.scrollIntoView({block:'nearest'});
    }
  }
  function reveal(d) {
    resetMotion();
    if (Array.isArray(d.dice)) {
      for(let i=0;i<row.children.length;i++) row.children[i].textContent=faces[d.dice[i]-1] || '?';
    }
    result.textContent = `${d.notation}：${d.raw}` + (d.adjusted!==undefined && d.adjusted!==d.raw?`　修正后：${d.adjusted}`:'') + (d.outcome?`\n${d.outcome}`:'');
    highlight(d.adjusted ?? d.raw);
  }
  btn.addEventListener('click', async()=>{
    if (!activeId || btn.disabled || sending) return;
    const id=activeId;
    sending=true;btn.disabled=true;btn.textContent='已发送，等待服务器…';
    try {
      const r=await fetch('/lan/dice/roll',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
      const payload=await r.json();
      if(!r.ok)throw Error(payload.detail || `HTTP ${r.status}`);
    } catch(e) { if(activeId===id)result.textContent=`投骰失败：${String(e)}`; }
    finally {sending=false;}
  });
  async function refresh() {
    if(inFlight) return;
    inFlight=true;
    try {
      const res=await fetch('/lan/dice/state',{cache:'no-store',credentials:'same-origin'});
      if(!res.ok) {detail.textContent=`无法同步骰子：HTTP ${res.status}`;return;}
      const d=await res.json();
      if(d.status==='idle') {
        isActive=false; root.style.display='none'; mini.style.display='none';
        activeId=null;lastStatus=null;latest=null;resetMotion();sending=false;collapsed=false;return;
      }
      isActive=true; latest=d;
      root.style.display=collapsed?'none':'flex';
      mini.style.display=collapsed?'flex':'none';
      updateMini(d);
      if(d.status==='calculating') {
        sideTitle.textContent='正在进行规则裁决';
        detail.textContent='下一次骰点即将显示，请不要关闭联机服务器。';
        if(d.error)detail.textContent+=` ${d.error}`;
        btn.style.display='none';row.style.display='none';result.textContent='';return;
      }
      btn.style.display='block';row.style.display='flex';
      if(activeId!==d.id) {
        activeId=d.id;lastStatus=null;tick=0;resetMotion();sending=false;
        setupDice(d.notation==='1D6'?1:2);result.textContent='';updateRule(d.rule);
      }
      sideTitle.textContent = `${d.owner==='axis'?'轴心国':'同盟国'} 玩家投掷`;
      detail.textContent = `${d.reason} · ${d.detail || '规则检定'}`;
      turn.textContent = `回合 ${d.turn || '?'} · ${d.phase} · 第 ${d.seq} 次掷骰`;
      diceType.textContent = `判定骰型：${d.notation}`;
      source.textContent = `随机数来源：${d.source==='cpu_rdseed'?'CPU RDSEED':d.source==='cpu_rdrand'?'CPU RDRAND':'操作系统安全随机数'} · 动画不影响结果`;
      if(d.status!==lastStatus) {
        lastStatus=d.status;
        if(d.status==='rolling' && !collapsed)startMotion();
        if(d.status==='revealed' && Array.isArray(d.dice))reveal(d);
      }
      btn.disabled = !d.may_roll || sending;
      btn.textContent = d.status==='waiting'?(d.may_roll?'点击投掷骰子':'等待指定玩家投掷'):
        d.status==='rolling'?'投掷动画进行中…':'结果已揭晓，裁决继续';
    } catch(err) {detail.textContent=`同步异常：${String(err)}`;}
    finally {inFlight=false;}
  }
  // Schedule after completion: never pile up requests. 300ms polling caused
  // unnecessary updates in two browser tabs during long multi-dice battles.
  async function poll() {
    await refresh();
    pollHandle = setTimeout(poll, isActive ? 850 : 1500);
  }
  poll();
})();
