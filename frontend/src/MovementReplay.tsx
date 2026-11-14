import {useEffect, useMemo, useState} from "react";
import {HexMap} from "./HexMap";
import type {HexCoord, Observation, Ship, TorpedoTrack} from "./types";

/** Private, post-adjudication movement frames. These contain only the player's own units.
 * The authoritative engine resolves all contacts BEFORE this purely visual replay.
 */
export interface IBSMovementFrame {
  interval: number;
  ships: {id: string; position: HexCoord | null; heading: number}[];
  torpedoes: TorpedoTrack[];
}

export function IBSMovementReplay({view, frames, onClose}: {
  view: Observation;
  frames: IBSMovementFrame[];
  onClose: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const frame = frames[Math.min(index, frames.length - 1)];
  useEffect(() => {
    if (paused || index >= frames.length - 1) return;
    const handle = window.setTimeout(() => setIndex(previous => previous + 1), 720);
    return () => window.clearTimeout(handle);
  }, [paused, index, frames.length]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {if (event.key === "Escape") onClose();};
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [onClose]);
  const ownShips: Ship[] = useMemo(() => {
    const positions = new Map((frame?.ships ?? []).map(entry => [entry.id, entry]));
    // Do not put final positions of unobserved enemy ships in a historical frame.
    return view.ships.filter(ship => ship.side === view.side).map(ship => {
      const current = positions.get(ship.id);
      return current ? {...ship, position: current.position, heading: current.heading} : ship;
    });
  }, [frame, view.ships, view.side]);
  if (!frame) return null;
  const count = frame.interval;
  const torpedoProgress = frame.torpedoes.map(track => {
    const first = frames.flatMap(item => item.torpedoes).find(item => item.id === track.id);
    return {id:track.id, moved: Math.max(0, track.distance_travelled - (first?.distance_travelled ?? 0))};
  });
  return <div role="dialog" aria-modal="true" aria-label="同步移动逐格回放"
    style={{position:"fixed",inset:0,zIndex:99980,background:"rgba(6,12,24,.94)",display:"flex",flexDirection:"column",padding:"clamp(8px,2vw,22px)"}}>
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:12,color:"#f6f7fa",marginBottom:10}}>
      <div><strong>同步移动逐格回放 · 第 {view.turn} 回合</strong>
        <span style={{marginLeft:14,color:"#c7d8f7"}}>MF {count}/{frames.length - 1}</span>
        <small style={{display:"block",color:"#abb8cf"}}>逐MF显示本方舰船与鱼雷；裁决结果不变。隐蔽的敌方单位不在此回放中公开。</small>
        <small style={{display:"block",color:"#e3bb67"}}>{torpedoProgress.length
          ? torpedoProgress.map(item => `${item.id}: 本回合实走 ${item.moved} 格`).join(" · ")
          : "当前MF没有本方活跃鱼雷"}</small>
      </div>
      <div style={{display:"flex",gap:8}}>
        <button type="button" onClick={() => setPaused(value => !value)}>{paused ? "继续" : "暂停"}</button>
        <button type="button" onClick={() => setIndex(Math.min(index + 1, frames.length - 1))} disabled={index >= frames.length - 1}>下一格</button>
        <button type="button" onClick={onClose}>完成 / 跳过回放</button>
      </div>
    </div>
    <div style={{flex:1,minHeight:0,overflow:"hidden",border:"1px solid #586c86",borderRadius:12,background:"#112238"}}>
      <HexMap dims={view} environment={view.environment} terrain={view.terrain}
        ships={ownShips} torpedoTracks={frame.torpedoes} markers={[]}
        onSelect={() => {}} viewerSide={view.side} visibility={view.visibility}/>
    </div>
    <div style={{height:5,marginTop:10,background:"#31475d",borderRadius:5}}>
      <div style={{height:"100%",width:`${(index / Math.max(1, frames.length - 1)) * 100}%`,background:"#e3bb67",borderRadius:5}}/>
    </div>
  </div>;
}
