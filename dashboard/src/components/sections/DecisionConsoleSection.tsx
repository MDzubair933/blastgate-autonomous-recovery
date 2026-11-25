import React, {useEffect,useState} from "react";
import {DecisionReceipt} from "@/types";

export function DecisionConsoleSection({receipts,activeIncidentId}:{receipts:DecisionReceipt[];activeIncidentId?:string}) {
 const [selected,setSelected]=useState(receipts.find(r=>r.incident_id===activeIncidentId)?.decision_id||receipts[0]?.decision_id||"");
 const [stepIndex,setStepIndex]=useState(0);
 const [copied,setCopied]=useState(false);
 useEffect(()=>{setSelected(receipts.find(r=>r.incident_id===activeIncidentId)?.decision_id||(activeIncidentId?"":receipts[0]?.decision_id||""));setStepIndex(0);},[activeIncidentId,receipts]);
 const receipt=receipts.find(r=>r.decision_id===selected);
 async function copyReceipt(){if(!receipt)return;try{await navigator.clipboard.writeText(JSON.stringify(receipt,null,2));setCopied(true);setTimeout(()=>setCopied(false),2000);}catch{setCopied(false);}}
 if(!receipt)return <div className="panel p-12 text-center quiet">No decision recorded for this incident. Return to Incidents to select another investigation.</div>;
 const step=receipt.timeline_steps[stepIndex];
 return <div className="presentation-page">
  <header className="page-intro"><p className="eyebrow">Agent console · simulated lifecycle</p><h1>The agent proposes.<br/><em>The broker decides.</em></h1><p>Reasoning, authorization and mutation remain separate. The agent has no mutation authority (R7).</p></header>
  <div className="quiet-tabs receipt-tabs" aria-label="Select decision">{receipts.map(r=><button key={r.decision_id} aria-pressed={selected===r.decision_id} onClick={()=>{setSelected(r.decision_id);setStepIndex(0);}}><span className="font-mono">{r.decision_id}</span><span className={r.decision==="ALLOW"?"text-emerald-300":"text-red-300"}>{r.decision}</span><span className="quiet font-mono">{r.target_short_id}</span></button>)}</div>
  <section className="outcome-surface"><div><p className="eyebrow">Broker outcome</p><h2 className={receipt.decision==="ALLOW"?"text-emerald-300":"text-red-300"}>{receipt.decision}</h2><p className="font-mono text-sm mt-3 break-all">{receipt.reason_code}</p></div><dl className="outcome-facts"><div><dt>Execution</dt><dd className="font-mono">{receipt.execution_status}</dd></div><div><dt>Simulated recovery</dt><dd>{receipt.recovery_verified?"LOCAL QUORUM 6/6":"REFUSED"}</dd></div><div><dt>Target</dt><dd className="font-mono">{receipt.target_short_id}</dd></div></dl></section>
  <section><div className="section-heading"><h2>Decision lifecycle</h2><span className="quiet">Authorization precedes mutation</span></div>
   <ol className="lifecycle">{receipt.timeline_steps.map((s,i)=><li key={s.step_number}><button aria-pressed={stepIndex===i} onClick={()=>setStepIndex(i)}><span className="step-index">{s.step_number.toString().padStart(2,"0")}</span><span>{s.name}</span><span className={`step-status ${s.status==="DENIED"?"text-red-300":"quiet"}`}>{s.status.toLowerCase()}</span>{s.step_number===6&&<span className="boundary-label">AUTH GATE</span>}{s.step_number===7&&<span className="boundary-label">MUTATION</span>}</button></li>)}</ol>
   {step&&<div className="step-detail" aria-live="polite"><div className="section-heading"><h3>{step.name}</h3><time className="technical-id">{step.timestamp}</time></div><p className="quiet leading-relaxed">{step.description}</p><details className="disclosure mt-4"><summary>Step evidence</summary><p className="disclosure-body">{step.details}</p></details></div>}
  </section>
  <details className="disclosure"><summary>Independent rule evaluations <span className="quiet">R1–R8</span></summary><div className="disclosure-body ruled-list">{Object.values(receipt.rule_results).map(r=><div className="rule-result" key={r.rule_id}><span className="technical-id">{r.rule_id}</span><div><h3>{r.name}</h3><p className="quiet mt-1">{r.message}</p></div><span className={!r.evaluated?"quiet":r.passed?"text-emerald-300":"text-red-300"}>{!r.evaluated?"Not evaluated":r.passed?"Passed":"Failed"}</span></div>)}</div></details>
  <details className="disclosure"><summary>Receipt metadata & boundary</summary><div className="disclosure-body space-y-4"><dl className="detail-grid"><div><dt>Simulated Request ID</dt><dd className="font-mono break-all">{receipt.aws_request_id}</dd></div><div><dt>Versions</dt><dd>Catalog v{receipt.catalog_version} · Policy v{receipt.policy_version}</dd></div></dl><p>The agent proposes. Cedar authorizes. The independent broker validates R1–R8 before invoking ECS StopTask. This console illustrates a simulated execution.</p></div></details>
  <details className="disclosure" key={receipt.decision_id}><summary>Raw decision receipt JSON</summary><div className="disclosure-body"><button className="text-link mb-4" onClick={copyReceipt}>{copied?"Copied!":"Copy JSON"}</button><pre className="code-block">{JSON.stringify(receipt,null,2)}</pre></div></details>
 </div>;
}
