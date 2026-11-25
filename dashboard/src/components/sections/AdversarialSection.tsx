import React, {useState} from "react";
import {AdversarialScenario} from "@/types";

export function AdversarialSection({scenarios}: {scenarios:AdversarialScenario[]}) {
 const [filter,setFilter]=useState("ALL");
 const blocked=scenarios.filter(s=>s.infrastructure_verdict.includes("BLOCKED"));
 const untested=scenarios.filter(s=>s.infrastructure_verdict==="NOT TESTED");
 const visible=filter==="BLOCKED"?blocked:filter==="NOT_TESTED"?untested:scenarios;
 return <div className="presentation-page">
  <header className="page-intro"><p className="eyebrow">Local adversarial fixtures</p><h1>Hostile proposals.<br/><em>Independent boundaries.</em></h1><p>Synthetic attacks against broker invariants. Model responses are NOT TESTED; this demo makes no Bedrock calls.</p></header>
  <div className="summary-band"><div><strong>{blocked.length}</strong><span>Blocked · simulated</span></div><div><strong>{untested.length}</strong><span>Cloud probe · not tested</span></div><div><strong>{scenarios.length}</strong><span>Local scenarios</span></div></div>
  <section><div className="section-heading"><h2>Adversarial tests</h2><span className="quiet">Separate from recorded AWS evidence</span></div>
   <div className="quiet-tabs" aria-label="Filter scenarios">{[{id:"ALL",label:"All",count:scenarios.length},{id:"BLOCKED",label:"Blocked",count:blocked.length},{id:"NOT_TESTED",label:"Not tested",count:untested.length}].map(f=><button key={f.id} aria-pressed={filter===f.id} onClick={()=>setFilter(f.id)}>{f.label} <span className="tab-count">{f.count}</span></button>)}</div>
   <div className="ruled-list">{visible.map(s=><details className="disclosure scenario-row" key={s.scenario_id}>
    <summary><span className="scenario-title"><span className="technical-id">{s.scenario_id}</span><span>{s.name}</span></span><span className={s.infrastructure_verdict==="NOT TESTED"?"quiet":"text-emerald-300"}>{s.infrastructure_verdict==="NOT TESTED"?"Not tested":"Blocked · simulated"}</span></summary>
    <div className="disclosure-body space-y-5"><p>{s.description}</p><dl className="detail-grid"><div><dt>Attack vector</dt><dd>{s.attack_vector}</dd></div><div><dt>Fixture model response</dt><dd>{s.model_verdict}</dd><dd className="quiet mt-2">{s.model_verdict_explanation}</dd></div><div><dt>Synthetic test fixture</dt><dd>{s.synthetic_fixture_explanation}</dd></div><div><dt>Simulated Broker Invariant</dt><dd>{s.infrastructure_verdict}</dd><dd className="quiet mt-2">{s.infrastructure_explanation}</dd></div></dl>
     <details className="disclosure"><summary>Inspect injected payload</summary><pre className="code-block">{s.injection_payload}</pre></details>
     <dl className="detail-grid"><div><dt>Enforced rules</dt><dd className="font-mono">{s.enforced_rules.join(" · ")||"None recorded"}</dd></div><div><dt>Test reference</dt><dd className="font-mono break-all">{s.test_reference}</dd></div><div><dt>Live status</dt><dd>{s.live_status}</dd></div></dl>
    </div>
   </details>)}</div>
  </section>
  <details className="disclosure"><summary>How to read these results</summary><p className="disclosure-body">This local demo does not invoke Amazon Bedrock; its records are synthetic. Fixture model verdicts are marked NOT TESTED. Local test suites inject synthetic worst-case payloads assuming a compromised model. A simulated broker block is a local invariant result, not a live model verdict or an AWS penetration test.</p></details>
 </div>;
}
