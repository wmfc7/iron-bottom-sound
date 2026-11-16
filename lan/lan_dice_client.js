/* IBS_DICE_MODAL_CONTROLS_V6_3 */
/* IBS LAN dice v4 - server-authoritative rolls, resilient polling, two-player receipt acknowledgements. */
(() => {
  if (window.__ibsDiceAttached) return;
  window.__ibsDiceAttached = true;
  const css = document.createElement('style');
  css.textContent = `
    /* The map stays interactive: this is a non-modal, pointer-transparent HUD. */
    #ibs-dice-screen {position:fixed;inset:0;z-index:2147483646;display:none;pointer-events:none;box-sizing:border-box;color:#f2eddf;font-family:Inter,system-ui,"Microsoft YaHei",sans-serif;font-size:14px}
    #ibs-dice-screen * {box-sizing:border-box}
    #ibs-dice-sidebar {position:absolute;top:0;right:0;bottom:0;width:var(--ibs-dice-rail,440px);display:flex;flex-direction:column;overflow:hidden;padding:0;border-left:1px solid #947a4c;background:linear-gradient(155deg,#1d3135 0%,#112127 45%,#09161c 100%);box-shadow:-12px 0 35px #0008;pointer-events:auto}
    #ibs-dice-banner {position:relative;flex:none;padding:21px 54px 18px 23px;border-bottom:1px solid #3d575c;background:radial-gradient(circle at right top,#b99d5833,transparent 58%)}
    #ibs-dice-kicker {font-size:11px;color:#b6a77d;letter-spacing:.2em;font-weight:750}
    #ibs-dice-side {font-size:clamp(22px,2.3vw,31px);font-weight:900;color:#f6dfa3;letter-spacing:.04em;line-height:1.24;margin:8px 0}
    #ibs-dice-detail {font-size:13px;line-height:1.6;color:#d0d9d6;overflow-wrap:anywhere}
    #ibs-dice-turn {font-size:13px;color:#b5c8c4;margin-top:12px;line-height:1.5}
    #ibs-dice-result {margin-top:7px;font-size:16px;font-weight:600;line-height:1.55;color:#f0d393;white-space:pre-line;overflow-wrap:anywhere}
    #ibs-dice-result:empty {display:none}
    #ibs-dice-connection {display:none;margin-top:12px;padding:10px 12px;border:1px solid #d48a71;border-radius:9px;background:#6b3028;color:#fff4ec;line-height:1.5}
    #ibs-dice-toggle {position:absolute;right:14px;top:16px;width:32px;height:32px;display:grid;place-items:center;background:#253c43;border:1px solid #72888b;border-radius:9px;color:#f0dfb5;font-size:18px;cursor:pointer;padding:0;min-height:0}
    #ibs-dice-toggle:hover,#ibs-dice-restore:hover {background:#3c5556}
    #ibs-dice-drawer {min-height:0;overflow:auto;flex:1;scrollbar-color:#6f7f80 #152327;padding:13px 22px 26px}
    #ibs-dice-rules {margin-top:19px;border-top:1px solid #3e5355;padding-top:17px}
    #ibs-dice-rules h3 {margin:0 0 9px;font-size:17px;color:#e4c988}
    #ibs-dice-rule-note {font-size:12px;line-height:1.65;color:#aebfbd;margin:0 0 13px;white-space:pre-line;overflow-wrap:anywhere}
    #ibs-dice-rules-table {display:block;width:100%;font-size:12px;border-collapse:collapse}
    #ibs-dice-rules-table thead {position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
    #ibs-dice-rule-body {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}
    #ibs-dice-rule-body tr {display:grid;grid-template-columns:38px minmax(0,1fr);align-items:start;gap:7px;border:1px solid #354a50;border-radius:7px;background:#1a2d31;min-width:0}
    #ibs-dice-rule-body td {padding:8px 6px;text-align:left;line-height:1.5;overflow-wrap:anywhere;min-width:0}
    #ibs-dice-rule-body td:first-child {font-weight:800;color:#e1c98f;text-align:center;border-right:1px solid #354a50;white-space:nowrap}
    #ibs-dice-rule-body tr.ibs-selected {background:#65512e;border-color:#edc270;color:#fff4d5}
    #ibs-dice-rule-empty {font-size:12px;color:#aebfbd;line-height:1.7}
    #ibs-dice-restore {position:absolute;top:12px;right:12px;display:none;padding:11px 14px;min-height:0;background:#223c44;color:#eed38e;border:1px solid #cfb16e;border-radius:10px;box-shadow:0 8px 27px #000a;pointer-events:auto;cursor:pointer;font-weight:750}
    #ibs-dice-screen.ibs-collapsed #ibs-dice-sidebar {display:none}
    #ibs-dice-screen.ibs-collapsed #ibs-dice-restore {display:block}
    /* Compact floating 3D dice window, movable and resizable across the full viewport. */
    #ibs-dice-float {--die-side:89px;--die-half:44.5px;--die-button-side:100px;--die-pip:13px;--die-radius:16px;position:fixed;left:0;top:0;display:flex;flex-direction:column;align-items:stretch;gap:4px;width:282px;height:210px;min-width:184px;min-height:145px;max-width:calc(100vw - 4px);max-height:calc(100dvh - 4px);padding:10px 11px 12px;border:1px solid #c0ac7b88;border-radius:16px;background:linear-gradient(145deg,#172a32f2,#0c1924f0);box-shadow:0 15px 38px #00131ac7,inset 0 1px #ffffff24;pointer-events:auto;touch-action:none;user-select:none;visibility:hidden;overflow:hidden}
    #ibs-dice-float.ibs-positioned {visibility:visible}
    #ibs-dice-float-head {display:flex;justify-content:center;align-items:center;min-height:21px;cursor:grab;touch-action:none;font-size:10px;font-weight:800;letter-spacing:.14em;color:#d1ba81;line-height:1.3}
    #ibs-dice-float-head:active {cursor:grabbing}
    #ibs-dice-row {display:flex;flex:1 1 auto;gap:6px;justify-content:center;align-items:center;min-height:0;min-width:0}
    #ibs-dice-float-label {font-size:11px;color:#a9bdc1;line-height:1.35;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    #ibs-dice-resize {position:absolute;right:0;bottom:0;width:27px;height:27px;cursor:nwse-resize;touch-action:none;z-index:2;background:repeating-linear-gradient(135deg,transparent 0 6px,#c7aa70 7px 9px,transparent 10px 12px) right 5px bottom 5px/13px 13px no-repeat;border:0;border-bottom-right-radius:15px;opacity:.85}
    #ibs-dice-resize:focus-visible {outline:2px solid #f5d38b;outline-offset:-3px}
    .ibs-die {display:grid;place-items:center;flex:none;width:var(--die-button-side);height:var(--die-button-side);min-height:0;margin:0;padding:0;border:0;background:none;outline:none;cursor:grab;touch-action:none;-webkit-tap-highlight-color:transparent;user-select:none}
    .ibs-die:active {cursor:grabbing}
    .ibs-die:focus-visible {outline:3px solid #eec66b;outline-offset:0;border-radius:15px}
    .ibs-die-scene {display:block;position:relative;width:var(--die-side);height:var(--die-side);perspective:670px;filter:drop-shadow(2px 12px 9px #0009)}
    .ibs-die-cube {display:block;position:relative;width:100%;height:100%;transform-style:preserve-3d;transform:rotateX(-17deg) rotateY(-23deg);transition:transform .65s cubic-bezier(.15,.88,.2,1);will-change:transform}
    .ibs-die.spinning .ibs-die-cube {transition:transform .082s linear}
    .ibs-die-face {position:absolute;inset:0;display:grid;grid-template:repeat(3,1fr)/repeat(3,1fr);align-items:center;justify-items:center;padding:14%;border:2px solid #c6c1b5;border-radius:var(--die-radius);background:linear-gradient(137deg,#fffef7 0%,#f2efe5 53%,#c4c6c5 100%);box-shadow:inset 3px 4px 12px #fff,inset -9px -11px 15px #34465825,0 0 0 1px #151f2155;backface-visibility:hidden}
    .ibs-die-face::before {content:'';position:absolute;inset:4px;border:2px solid #ffffffa0;border-radius:calc(var(--die-radius) - 4px);pointer-events:none}
    .ibs-die-face[data-face="1"] {transform:translateZ(var(--die-half))}
    .ibs-die-face[data-face="2"] {transform:rotateX(90deg) translateZ(var(--die-half))}
    .ibs-die-face[data-face="3"] {transform:rotateY(90deg) translateZ(var(--die-half))}
    .ibs-die-face[data-face="4"] {transform:rotateY(-90deg) translateZ(var(--die-half))}
    .ibs-die-face[data-face="5"] {transform:rotateX(-90deg) translateZ(var(--die-half))}
    .ibs-die-face[data-face="6"] {transform:rotateY(180deg) translateZ(var(--die-half))}
    .ibs-die-pip {width:var(--die-pip);height:var(--die-pip);border-radius:50%;background:radial-gradient(circle at 30% 24%,#344a55,#14222c 65%,#060c14);box-shadow:inset 2px 2px 3px #0b0e1f,1px 1px 1px #fff9}
    .ibs-die[data-rollable="true"] .ibs-die-scene {filter:drop-shadow(2px 12px 9px #0009) drop-shadow(0 0 9px #e2ba6045)}
    .ibs-die[data-rollable="false"] {cursor:grab}
    /* Existing desktop map is a middle grid column: reserve an actual right grid rail, never cover map. */
    @media(min-width:1101px) {body.ibs-dice-docked .workspace:not(.report-workspace) {--orders-width:var(--ibs-dice-rail,440px)!important}}
    /* On tablets/phones reserve a right strip instead of covering the map. */
    @media(max-width:1100px) {body.ibs-dice-docked .workspace>.map-column,body.ibs-dice-docked .workspace>.move-editor {right:var(--ibs-dice-rail,440px)!important;width:calc(100% - var(--ibs-dice-rail,440px))!important}}
    @media(max-width:850px) {
      #ibs-dice-sidebar {width:min(38vw,330px)}
      #ibs-dice-banner {padding:13px 42px 11px 13px}
      #ibs-dice-side {font-size:19px}
      #ibs-dice-drawer {padding:13px}
      #ibs-dice-rule-body {gap:5px}
      #ibs-dice-rule-body tr {grid-template-columns:31px minmax(0,1fr);gap:3px}
      #ibs-dice-rule-body td {padding:6px 3px}
      body.ibs-dice-docked .workspace>.map-column,body.ibs-dice-docked .workspace>.move-editor {right:min(38vw,330px)!important;width:calc(100% - min(38vw,330px))!important}
    }
    @media(max-width:550px) {
      #ibs-dice-sidebar {top:auto;left:0;right:0;bottom:0;width:100%;height:43dvh;border-left:0;border-top:1px solid #947a4c;box-shadow:0 -12px 40px #0009}
      #ibs-dice-banner {padding:9px 44px 8px 13px}
      #ibs-dice-side {font-size:17px;margin:2px 0}
      #ibs-dice-turn {margin-top:4px}
      #ibs-dice-result {font-size:15px;margin-top:4px}
      #ibs-dice-drawer {padding:9px 13px 14px}
      #ibs-dice-rules {margin-top:11px;padding-top:9px}
      body.ibs-dice-docked .workspace>.map-column,body.ibs-dice-docked .workspace>.move-editor {right:0!important;width:100%!important;bottom:43dvh!important}
      #ibs-dice-float-head {font-size:9px}
      #ibs-dice-float-label {font-size:10px}
    }
    @media(max-width:350px) {#ibs-dice-rule-body {grid-template-columns:minmax(0,1fr)}}
    @media(prefers-reduced-motion:reduce) {.ibs-die.spinning .ibs-die-cube {transition:none}}
  `;
  document.head.appendChild(css);
  const root = document.createElement('div'); root.id = 'ibs-dice-screen';
  root.innerHTML = `<aside id="ibs-dice-sidebar" role="complementary" aria-labelledby="ibs-dice-side"><header id="ibs-dice-banner"><span id="ibs-dice-kicker">IRON BOTTOM SOUND · DICE</span><button id="ibs-dice-toggle" type="button" aria-label="收起规则侧栏" aria-expanded="true">−</button><div id="ibs-dice-side">等待判定</div><div id="ibs-dice-detail">正在读取裁决信息…</div><div id="ibs-dice-turn"></div><div id="ibs-dice-result" role="status" aria-live="polite"></div><div id="ibs-dice-connection" role="alert"></div></header><div id="ibs-dice-drawer"><section id="ibs-dice-rules" aria-label="判定规则"><h3 id="ibs-dice-rule-title">相关规则</h3><p id="ibs-dice-rule-note"></p><table id="ibs-dice-rules-table" aria-label="判定规则表"><thead><tr><th>骰点</th><th>裁决结果</th></tr></thead><tbody id="ibs-dice-rule-body"></tbody></table><p id="ibs-dice-rule-empty" hidden>当前判定没有可明确定位的结构化规则表，最终以引擎裁决为准。</p></section></div></aside><div id="ibs-dice-float" role="group" aria-label="可移动、可缩放的 3D 骰子窗口"><div id="ibs-dice-float-head">INTERACTIVE DICE</div><div id="ibs-dice-row"></div><div id="ibs-dice-float-label">拖动移动 · 点击骰子投掷 · 右下角缩放</div><div id="ibs-dice-resize" role="separator" aria-label="拖动调整骰子窗口大小" aria-orientation="horizontal" tabindex="0" title="拖动调整骰子窗口大小"></div></div><button id="ibs-dice-restore" type="button">展开投骰规则</button>`;
  document.body.appendChild(root);
  const el = id => root.querySelector(`#${id}`);
  const sideTitle = el('ibs-dice-side'), detail = el('ibs-dice-detail'), turn = el('ibs-dice-turn');
  const row = el('ibs-dice-row'), result = el('ibs-dice-result');
  const connection = el('ibs-dice-connection');
  const ruleTitle = el('ibs-dice-rule-title'), ruleNote = el('ibs-dice-rule-note'), ruleBody = el('ibs-dice-rule-body');
  const empty = el('ibs-dice-rule-empty'), ruleTable = el('ibs-dice-rules-table');
  const restore = el('ibs-dice-restore'), collapse = el('ibs-dice-toggle');
  const float = el('ibs-dice-float'), floatLabel = el('ibs-dice-float-label');
  const floatHead = el('ibs-dice-float-head'), resizeHandle = el('ibs-dice-resize');
  let isCollapsed = false;
  function syncDock() {
    document.body.classList.toggle('ibs-dice-docked', root.style.display==='flex' && !isCollapsed);
    clampFloat();
  }
  function toggleCollapsed(value) {
    isCollapsed = value;
    root.classList.toggle('ibs-collapsed', value);
    collapse.setAttribute('aria-expanded', String(!value));
    restore.setAttribute('aria-expanded', String(!value));
    syncDock();
  }
  collapse.addEventListener('click', () => toggleCollapsed(true));
  restore.addEventListener('click', () => toggleCollapsed(false));
  const STATE_TIMEOUT_MS = 4500, POST_TIMEOUT_MS = 4500, ACK_TIMEOUT_MS = 3500;
  let activeId = null, lastStatus = null, timer = null, clockOffset = 0;
  let inFlight = false, sendingId = null, acceptedId = null, sendingStarted = 0;
  let ackId = null, ackInFlight = false, ackTimer = null, ackRetryAt = 0;
  let lastGoodAt = Date.now(), lastError = '';
  const PIPS = {1:[4],2:[0,8],3:[0,4,8],4:[0,2,6,8],5:[0,2,4,6,8],6:[0,2,3,5,6,8]};
  // Face layout: opposing sides sum to seven. Values are orientations, not RNG.
  const STOP = {1:[0,0],2:[-90,0],3:[0,-90],4:[0,90],5:[90,0],6:[0,180]};
  let floatX = null, floatY = null, suppressNextClick = false;
  let rollEnabled = false;
  const MIN_FLOAT_WIDTH = 184, MIN_FLOAT_HEIGHT = 145;
  function setRollEnabled(enabled) {
    rollEnabled = Boolean(enabled);
    for(const die of row.children) {
      die.dataset.rollable=String(rollEnabled);
      die.title=rollEnabled?'点击投骰；拖动可移动窗口':'当前不可投骰；仍可拖动窗口';
    }
  }
  function clampFloat() {
    const maxW=Math.max(1,window.innerWidth-4), maxH=Math.max(1,window.innerHeight-4);
    if(float.offsetWidth>maxW)float.style.width=`${maxW}px`;
    if(float.offsetHeight>maxH)float.style.height=`${maxH}px`;
    if(floatX===null||floatY===null)return;
    floatX=Math.min(Math.max(floatX,0),Math.max(0,window.innerWidth-float.offsetWidth));
    floatY=Math.min(Math.max(floatY,0),Math.max(0,window.innerHeight-float.offsetHeight));
    float.style.left=`${floatX}px`;float.style.top=`${floatY}px`;
  }
  function fitDice() {
    const n=Math.max(1,row.children.length);
    const usableW=float.clientWidth-36-(n-1)*6;
    const usableH=float.clientHeight-floatHead.offsetHeight-floatLabel.offsetHeight-38;
    const size=Math.max(34,Math.floor(Math.min(150,usableW/n-7,usableH-7)));
    float.style.setProperty('--die-side',`${size}px`);
    float.style.setProperty('--die-half',`${size/2}px`);
    float.style.setProperty('--die-button-side',`${size+7}px`);
    float.style.setProperty('--die-pip',`${Math.max(6,Math.round(size*.142))}px`);
    float.style.setProperty('--die-radius',`${Math.max(8,Math.round(size*.18))}px`);
  }
  function positionFloat() {
    if(floatX===null || floatY===null) {
      // Compact initial position near the top-left of the map, not the screen center.
      const map=document.querySelector('.map-frame')?.getBoundingClientRect();
      floatX=Math.round(Math.min(window.innerWidth-float.offsetWidth-10,Math.max(10,(map?.left??0)+28)));
      floatY=Math.round(Math.min(window.innerHeight-float.offsetHeight-10,Math.max(10,(map?.top??0)+28)));
    }
    clampFloat();fitDice();float.classList.add('ibs-positioned');
  }
  window.addEventListener('resize',()=>{clampFloat();fitDice();});
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(()=>{clampFloat();fitDice();}).observe(float);
  function createDie(index) {
    const die=document.createElement('button');die.type='button';die.className='ibs-die';die.dataset.die=String(index);
    die.setAttribute('aria-label',`第 ${index+1} 枚骰子，点击投掷，拖动移动位置`);
    const scene=document.createElement('span');scene.className='ibs-die-scene';
    const cube=document.createElement('span');cube.className='ibs-die-cube';
    for(let face=1;face<=6;face++) {
      const side=document.createElement('span');side.className='ibs-die-face';side.dataset.face=String(face);
      for(const cell of PIPS[face]) {const pip=document.createElement('span');pip.className='ibs-die-pip';pip.style.gridArea=`${Math.floor(cell/3)+1} / ${cell%3+1}`;side.append(pip);}
      cube.append(side);
    }
    scene.append(cube);die.append(scene);return die;
  }
  function resetMotion() {if(timer!==null){clearInterval(timer);timer=null;}for(const die of row.children)die.classList.remove('spinning');}
  function setupDice(n) {
    row.replaceChildren();for(let i=0;i<n;i++)row.append(createDie(i));
    setRollEnabled(false);requestAnimationFrame(positionFloat);
  }
  function startMotion(startMs) {
    if(timer!==null)return;
    if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    for(const die of row.children)die.classList.add('spinning');
    const draw=()=>{
      const frame=Math.floor((Date.now()-clockOffset-Number(startMs||Date.now()))/85);
      for(let i=0;i<row.children.length;i++) {
        const cube=row.children[i].querySelector('.ibs-die-cube');
        // Visual spin only; this value is NEVER used as the game result.
        const x=((frame*117+i*83)%1440)-720;
        const y=((frame*163+i*137)%1440)-720;
        cube.style.transform=`rotateX(${x}deg) rotateY(${y}deg) rotateZ(${frame*41}deg)`;
      }
    };
    draw();timer=setInterval(draw,85);
  }
  function settleDie(die,value) {
    const cube=die.querySelector('.ibs-die-cube');
    const [x,y]=STOP[Number(value)]??STOP[1];
    cube.style.transform=`rotateX(-17deg) rotateY(-23deg) rotateX(${x}deg) rotateY(${y}deg)`;
  }
  let dragging=null, sizing=null;
  float.addEventListener('pointerdown',event=>{
    if(event.button!==0 || event.target.closest('#ibs-dice-resize'))return;
    if(floatX===null)positionFloat();
    dragging={id:event.pointerId,x:event.clientX,y:event.clientY,startX:floatX,startY:floatY,moved:false};
    const capture=event.target.closest('.ibs-die')||event.target.closest('#ibs-dice-float-head')||float;
    capture.setPointerCapture(event.pointerId);
  });
  float.addEventListener('pointermove',event=>{
    if(!dragging||dragging.id!==event.pointerId)return;
    const dx=event.clientX-dragging.x,dy=event.clientY-dragging.y;
    if(!dragging.moved&&Math.hypot(dx,dy)>7)dragging.moved=true;
    if(dragging.moved){floatX=dragging.startX+dx;floatY=dragging.startY+dy;clampFloat();}
  });
  function finishDrag(event){
    if(!dragging||dragging.id!==event.pointerId)return;
    if(dragging.moved){suppressNextClick=true;setTimeout(()=>{suppressNextClick=false;},300);}
    dragging=null;
  }
  float.addEventListener('pointerup',finishDrag);
  float.addEventListener('pointercancel',event=>{if(dragging&&dragging.id===event.pointerId){dragging=null;suppressNextClick=true;}});
  resizeHandle.addEventListener('pointerdown',event=>{
    if(event.button!==0)return;
    event.stopPropagation();event.preventDefault();
    if(floatX===null)positionFloat();
    sizing={id:event.pointerId,x:event.clientX,y:event.clientY,width:float.offsetWidth,height:float.offsetHeight};
    resizeHandle.setPointerCapture(event.pointerId);
  });
  resizeHandle.addEventListener('pointermove',event=>{
    if(!sizing||sizing.id!==event.pointerId)return;
    const maxW=Math.max(MIN_FLOAT_WIDTH,window.innerWidth-floatX),maxH=Math.max(MIN_FLOAT_HEIGHT,window.innerHeight-floatY);
    const w=Math.max(MIN_FLOAT_WIDTH,Math.min(maxW,sizing.width+event.clientX-sizing.x));
    const h=Math.max(MIN_FLOAT_HEIGHT,Math.min(maxH,sizing.height+event.clientY-sizing.y));
    float.style.width=`${w}px`;float.style.height=`${h}px`;fitDice();
  });
  resizeHandle.addEventListener('pointerup',event=>{if(sizing?.id===event.pointerId)sizing=null;});
  resizeHandle.addEventListener('pointercancel',()=>{sizing=null;});
  resizeHandle.addEventListener('keydown',event=>{
    if(!['ArrowRight','ArrowLeft','ArrowDown','ArrowUp'].includes(event.key))return;
    event.preventDefault();
    const step=event.shiftKey?40:12;
    const change=event.key==='ArrowRight'||event.key==='ArrowDown'?step:-step;
    if(event.key==='ArrowLeft'||event.key==='ArrowRight')
      float.style.width=`${Math.max(MIN_FLOAT_WIDTH,Math.min(window.innerWidth-floatX,float.offsetWidth+change))}px`;
    else float.style.height=`${Math.max(MIN_FLOAT_HEIGHT,Math.min(window.innerHeight-floatY,float.offsetHeight+change))}px`;
    fitDice();
  });
  row.addEventListener('click',event=>{
    const die=event.target.closest('.ibs-die');if(!die)return;
    if(suppressNextClick){suppressNextClick=false;return;}
    requestRoll();
  });
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
    if(Array.isArray(d.dice))for(let i=0;i<row.children.length;i++)settleDie(row.children[i],d.dice[i]);
    result.textContent = `结果：${d.raw}`+(d.adjusted!==undefined&&d.adjusted!==d.raw?`　修正后：${d.adjusted}`:'')+(d.outcome?`\n${d.outcome}`:'');
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

  async function requestRoll(){
    if(!activeId||!rollEnabled||sendingId||acceptedId)return;
    const id=activeId;
    sendingId=id;sendingStarted=Date.now();setRollEnabled(false);startMotion(Date.now());
    try {
      const r=await fetchWithTimeout('/lan/dice/roll',{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})},POST_TIMEOUT_MS);
      const payload=await r.json();
      if(!r.ok)throw Error(payload.detail||`HTTP ${r.status}`);
      // Accepted is not proof of the dice face: wait for the authoritative state.
      if(activeId===id)acceptedId=id;
    }catch(e){
      resetMotion();
      if(activeId===id)result.textContent=`投骰请求未确认（可能已被服务器接收）：${String(e)}\n正在重新读取服务器状态，请勿反复点击。`;
    }finally{if(sendingId===id)sendingId=null;}
  }

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
        root.style.display='none';syncDock();activeId=null;lastStatus=null;resetMotion();setRollEnabled(false);
        sendingId=null;acceptedId=null;return;
      }
      root.style.display='flex';syncDock();
      if(d.status==='calculating'){
        resetMotion();activeId=null;lastStatus=null;sendingId=null;acceptedId=null;
        sideTitle.textContent='正在进行规则裁决';detail.textContent='正在等待下一项判定，请勿关闭联机服务器。';
        if(d.error)detail.textContent+=` ${d.error}`;
        setRollEnabled(false);float.style.display='none';result.textContent='';return;
      }
      float.style.display='flex';
      if(activeId!==d.id){
        resetForNewId(d.id,d);
        // A new roll that this browser must operate should not remain hidden.
        if(d.may_roll)toggleCollapsed(false);
        requestAnimationFrame(positionFloat);
      }
      restore.textContent=`展开投骰 · 第 ${d.seq} 次 · ${d.owner==='axis'?'轴心国':'同盟国'}`;
      sideTitle.textContent=`${d.owner==='axis'?'轴心国':'同盟国'} 玩家投掷`;
      detail.textContent=`${d.reason} · ${d.detail||'规则检定'}`;
      turn.textContent=`回合 ${d.turn||'?'} · ${d.phase} · 第 ${d.seq} 次掷骰 · ${d.notation}`;
      floatLabel.textContent=d.status==='waiting'?(d.may_roll?'拖动可移动位置 · 点击骰子投掷':'拖动可移动位置 · 等待指定阵营'):(d.status==='revealed'||d.status==='committing'?'服务器骰点已揭晓 · 可拖动查看地图':'骰子快速转动中 · 以服务器结果为准');
      if(d.status!=='waiting')acceptedId=null;
      if(d.status!==lastStatus){
        lastStatus=d.status;
        if(d.status==='rolling'){if(sendingId===d.id)sendingId=null;result.textContent='';startMotion(d.animation_start_ms);}
        else if((d.status==='revealed'||d.status==='committing')&&Array.isArray(d.dice)){if(sendingId===d.id)sendingId=null;reveal(d);scheduleAck(d.id);}
        else if(d.status==='waiting'){resetMotion();}
        else if(d.status==='generating'){startMotion(Date.now());result.textContent='服务器正在读取 CPU 硬件随机数…';}
      }
      if((d.status==='revealed'||d.status==='committing')&&ackId!==d.id&&ackTimer===null&&!ackInFlight&&Date.now()>=ackRetryAt)scheduleAck(d.id);
      // An accepted POST can have a delayed state response. Never offer a second
      // roll while that acknowledgement is pending; no automatic retry of dice.
      const pending=(sendingId===d.id||acceptedId===d.id);
      setRollEnabled(d.status==='waiting'&&d.may_roll&&!pending);
      if(d.status==='waiting'){
        if(acceptedId===d.id&&Date.now()-sendingStarted>6000){
          // State is still authoritative; allow the *player* to retry the same ID.
          acceptedId=null;setRollEnabled(Boolean(d.may_roll));
          result.textContent='服务器尚未显示投骰结果。如确认仍在等待，可重试同一骰点请求。';
        }
      }
    }catch(err){
      lastError=String(err);
      showConnection(`连接延迟或请求失败：${lastError}。正在自动重连，请勿重复投骰。`);
      setRollEnabled(false);
    }finally{inFlight=false;}
  }
  refresh();setInterval(refresh,350);
  setInterval(()=>{
    if(root.style.display==='flex'&&Date.now()-lastGoodAt>5000){
      showConnection('超过 5 秒未收到新的服务器状态，当前骰子画面可能已经过期；正在重连。');
      setRollEnabled(false);
    }
  },1000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
})();
