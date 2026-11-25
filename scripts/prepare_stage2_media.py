"""Offline media views from saved evidence. No AWS clients, calls or mutations."""
from pathlib import Path
import hashlib, html, json, re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/submission'
MEDIA=OUT/'media'
MEDIA.mkdir(exist_ok=True)
(OUT/'assets/final').mkdir(parents=True,exist_ok=True)

raw_path=ROOT/'evidence/adversarial_prompts/agentcore_adversarial_raw_evidence.json'
raw=json.loads(raw_path.read_text(encoding='utf-8'))
records=[]
for s in raw['scenarios']:
    prompt=s['prompt']
    replacements={}
    for token in re.findall(r'\bdec-[a-f0-9]{8,36}\b',prompt):
        replacements[token]='decision-historical-01'
        prompt=prompt.replace(token,replacements[token])
    response=re.sub(r'<thinking>.*?</thinking>','',s['full_response_text'],flags=re.S).strip()
    record={k:s[k] for k in ['test_id','scenario_name','timestamp','stop_reason','model_inference_performed','pre_inference_guardrail_block','ecs_mutation_occurred']}
    record.update(prompt=prompt,returned_response=response,tool_requests=s['tool_invocations_requested'],
                  substitution_note='A real historical decision ID in the replay prompt is replaced with an explicit alias.' if replacements else 'Prompt and returned visible text preserved; private thinking blocks omitted.')
    records.append(record)
facts={'kind':'Stage 2 allowlisted media evidence derivative; historical, not live',
       'source_reference':'private evidence/adversarial_prompts/agentcore_adversarial_raw_evidence.json',
       'source_sha256':hashlib.sha256(raw_path.read_bytes()).hexdigest(),
       'recorded_suite_utc':raw['executed_at'],'region':raw['aws_region'],
       'new_harness_prompt_records':len(records),'source_declared_model_activity_count':sum(s['model_inference_performed'] for s in records),
       'returned_end_turn_records':sum(s['stop_reason']=='end_turn' for s in records),
       'returned_guardrail_stop_records':sum(s['stop_reason']=='guardrail_intervened' for s in records),
       'scope':'Five saved runs flag model activity, but four of those end with Guardrail interception. One visible final answer ends end_turn and reports a missing incident. Do not label these five model-generated policy refusals.',
       'records':records}
(MEDIA/'media-evidence.json').write_text(json.dumps(facts,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
trace=json.loads((OUT/'evidence/step6-execution-trace.json').read_text(encoding='utf-8'))
run=json.loads((ROOT/'evidence/public/recorded-evidence.json').read_text(encoding='utf-8'))['unattended']
def e(s):return html.escape(str(s))
def fact(label,value):return f'<div class="fact"><span>{e(label)}</span><strong>{e(value)}</strong></div>'
def pane(title,body):return f'<section><h2>{e(title)}</h2>{body}</section>'
pages={}
pages['harness']=('AgentCore Harness execution','Earlier Step 6 · recorded AWS stream · manually invoked',
    pane('Read-only diagnosis',fact('ECS state','RUNNING')+fact('Application state',trace['tools'][0]['processing_state'])+'<code>'+e(trace['tools'][0]['name'])+'</code>')+
    pane('Returned broker result',fact('Decision',trace['tools'][1]['decision'])+fact('Reason / status',trace['tools'][1]['reason_code']+' / '+trace['tools'][1]['execution_status'])+'<p>Recovery still required independent verification after this response.</p>'),
    'Actual saved event-stream fields in a local viewer. Not AWS Console; not the later unattended run.')
s=next(r for r in records if r['test_id']=='ADV-03')
pages['prompt']=('An actual adversarial request and reply','ADV-03 · '+s['timestamp']+' · stopReason '+s['stop_reason'],
    pane('Submitted prompt','<blockquote>'+e(s['prompt'])+'</blockquote>')+pane('Returned agent answer','<blockquote>'+e(s['returned_response'])+'</blockquote><p class="note">The answer reports a missing incident. It does not establish a reached live target-scope enforcement branch.</p>'),
    'Recorded AWS Execution · visible final answer, with private thinking omitted. No invented refusal text.')
s=next(r for r in records if r['test_id']=='ADV-04')
pages['guardrail']=('The request stops at the perimeter','ADV-04 · '+s['timestamp']+' · recorded Guardrail result',
    pane('Submitted prompt','<blockquote>'+e(s['prompt'])+'</blockquote>')+pane('Returned Harness block','<blockquote>'+e(s['returned_response'])+'</blockquote>'+fact('Stop reason',s['stop_reason'])+fact('Pre-inference block',s['pre_inference_guardrail_block'])+'<p class="note">A Guardrail block is not a model-generated refusal.</p>'),
    'Recorded AWS Execution · real saved prompt and block message. No new model call or AWS test.')
pages['dispatch']=('The incident reaches the dispatcher','Unattended recovery · '+run['executed_at'],
    pane('Correlated recording',fact('Incident alias',run['incident_alias'])+fact('Dispatch session alias',run['session_alias'])+fact('Dispatch session observed',run['dispatch_session_observed']))+
    pane('Experimental scope','<p>The runner did not manually invoke the Harness or broker.</p><p>The runner could invoke the watchdog to accelerate detection.</p><p class="note">Intermediate timestamps and a complete tool transcript are absent. The session observation is not a full dispatcher log.</p>'),
    'Recorded AWS Execution · allowlisted saved observations in a local viewer; not an AWS Console capture.')
pages['recovery']=('A distinct replacement reports healthy','Unattended recovery · '+run['executed_at'],
    pane('Captured decision',fact('Broker',run['decision'])+fact('All eight rule flags',all(run['rule_results'].values()))+'<code>Captured reason_code: '+e(run['captured_reason_code'])+'</code><p class="note">Captured field contains the action ID; it is not normalized to AUTH_APPROVED.</p>')+
    pane('Recovery observations',fact('Original target stopped',run['target_stopped'])+fact('Distinct replacement',run['distinct_replacement'])+fact('Replacement healthy',run['replacement_healthy'])+'<p>Cleanup: 0 desired / 0 running / 0 pending<br><span class="note">'+e(run['cleanup_verified_at'])+' · historical state</span></p>'),
    'Recorded AWS Execution · saved recovery results, not current telemetry. Public worker aliases preserve correlation.')
css='''*{box-sizing:border-box}html,body{margin:0;background:#0b0f14;color:#f5f4f1;font:24px/1.5 "Segoe UI",Arial,sans-serif}main{width:1600px;min-height:900px;padding:54px 68px}header{border-bottom:1px solid #34404c;padding-bottom:26px}.label{color:#d8a955;background:#0b0f14;font-size:17px;letter-spacing:.1em}h1{font:52px/1.1 Georgia,serif;margin:20px 0 18px}.metadata,.note{color:#b5b8bd;background:#0b0f14;font-size:18px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:62px;margin-top:34px}h2{font-size:25px;font-weight:600;margin:0 0 22px}section{min-width:0}blockquote{margin:0 0 22px;font-size:25px;line-height:1.55}p{color:#b5b8bd;background:#0b0f14;margin:18px 0;line-height:1.6}.fact{border-bottom:1px solid #25303b;padding:13px 0;display:flex;flex-direction:column;gap:5px}.fact span{color:#b5b8bd;background:#0b0f14;font-size:18px}.fact strong{font-size:28px;font-weight:500;overflow-wrap:anywhere}code{font:17px/1.6 Consolas,monospace;display:block;margin-top:22px;overflow-wrap:anywhere}footer{margin-top:34px;border-top:1px solid #34404c;padding-top:18px;font-size:17px;color:#b5b8bd;background:#0b0f14}'''
for key,(title,meta,body,foot) in pages.items():
    page=f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BlastGate — {e(title)}</title><style>{css}</style><main><header><div class="label">BLASTGATE / RECORDED AWS EXECUTION</div><h1>{e(title)}</h1><div class="metadata">{e(meta)}</div></header><div class="grid">{body}</div><footer>{e(foot)}</footer></main></html>'
    (MEDIA/(key+'.html')).write_text(page,encoding='utf-8')
print('Prepared five recorded-evidence media views and a minimal new-run derivative. No original evidence changed.')
