import React, {useEffect, useRef, useState} from "react";
import {Home, Layers, AlertTriangle, Zap, ShieldCheck, FlaskConical, FileText, Cloud} from "lucide-react";
import {TabId} from "@/types";
interface Props {recorded?:boolean;activeTab:TabId;onSelectTab:(id:TabId)=>void;openIncidentCount?:number;isMobileOpen?:boolean;onCloseMobile?:()=>void;}
export const Sidebar: React.FC<Props> = ({recorded=false,activeTab,onSelectTab,openIncidentCount=0,isMobileOpen=false,onCloseMobile}) => {
  const [desktop,setDesktop]=useState(false);
  const ref=useRef<HTMLElement>(null);
  useEffect(()=>{const mq=window.matchMedia("(min-width: 1024px)");const update=()=>setDesktop(mq.matches);update();mq.addEventListener("change",update);return()=>mq.removeEventListener("change",update);},[]);
  useEffect(()=>{
    if(!isMobileOpen || desktop)return;
    const previous=document.activeElement as HTMLElement;
    const controls=()=>Array.from(ref.current?.querySelectorAll<HTMLButtonElement>("button")||[]);
    controls()[0]?.focus();
    const handle=(e:KeyboardEvent)=>{if(e.key==="Escape"){onCloseMobile?.();return;}if(e.key==="Tab"){const all=controls();const first=all[0],last=all[all.length-1];if(e.shiftKey && document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first?.focus();}}};
    const oldOverflow=document.body.style.overflow;document.body.style.overflow="hidden";
    document.addEventListener("keydown",handle);return()=>{document.body.style.overflow=oldOverflow;document.removeEventListener("keydown",handle);previous?.focus();};
  },[isMobileOpen,desktop,onCloseMobile]);
  const items=[{id:"overview",label:"Overview",icon:Home},{id:"workers",label:"Workers",icon:Layers},{id:"incidents",label:"Incidents",icon:AlertTriangle},{id:"decision-console",label:"Agent Console",icon:Zap},{id:"security-rules",label:"Security Rules",icon:ShieldCheck},{id:"adversarial",label:"Adversarial Tests",icon:FlaskConical},{id:"audit-explorer",label:"Audit Explorer",icon:FileText},{id:"deployment-cost",label:"Deployment",icon:Cloud}] as const;
  return <>{isMobileOpen && <button aria-label="Dismiss navigation backdrop" tabIndex={-1} onClick={onCloseMobile} className="fixed inset-0 bg-black/70 z-40 lg:hidden"/>}
    <aside ref={ref} id="dashboard-navigation" aria-label="Dashboard navigation" aria-hidden={!desktop&&!isMobileOpen} className={`fixed top-[68px] sm:top-[72px] bottom-0 left-0 w-[240px] bg-[#0D1117] border-r border-white/10 flex flex-col justify-between overflow-y-auto p-3 py-5 z-40 transition-transform duration-200 ${isMobileOpen?"translate-x-0":"-translate-x-full lg:translate-x-0"}`}>
      <nav aria-label="Dashboard views" className="space-y-1"><button tabIndex={isMobileOpen?0:-1} className="lg:hidden w-full text-left px-4 py-3 text-[#D8A955]" onClick={onCloseMobile}>Close navigation</button>{items.map(item=><button key={item.id} tabIndex={desktop||isMobileOpen?0:-1} aria-current={!recorded&&activeTab===item.id?"page":undefined} onClick={()=>{onSelectTab(item.id);onCloseMobile?.();}} className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm text-left ${!recorded&&activeTab===item.id?"bg-[#181E26] text-[#F5F4F1]":"text-[#A1A8B2] hover:bg-white/5"}`}><item.icon size={17}/><span className="flex-1">{item.label}</span>{item.id==="incidents"&&openIncidentCount>0&&<span className="badge">{openIncidentCount}</span>}</button>)}</nav>
      <p className="text-xs text-[#848B95] border-t border-white/10 pt-4 px-4 mt-6">BlastGate · Evidence dashboard<br/><span className="block mt-1">Offline demonstration</span></p>
    </aside></>;
};
