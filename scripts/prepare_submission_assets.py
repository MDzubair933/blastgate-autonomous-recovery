"""Prepare allowlisted submission derivatives offline. Never invokes AWS services."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import html
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/submission'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def prompt_audit():
    source = ROOT / 'evidence/step7/raw_adversarial_evidence.json'
    raw = json.loads(source.read_text(encoding='utf-8'))
    s = raw['scenarios']['scenario_1']
    # Exact public-safe text only; session/request/resource identifiers are omitted.
    record = {k: s[k] for k in ['scenario_id', 'name', 'adversarial_input',
              'harness_output_text', 'harness_stop_reason', 'guardrail_action',
              'guardrail_intervened_in_harness', 'post_test_cluster_status',
              'ecs_mutation_occurred', 'verdict']}
    record.update(record_id='AP-01', execution_layer='Live AgentCore Managed Harness; input Guardrail interception',
                  model_generated_response_established=False,
                  scope='The returned text is a Harness/Guardrail block message, not evidence of model reasoning or model compliance.')
    layers = {
        'scenario_2': 'Direct broker Lambda inventory denial plus local healthy-target validator',
        'scenario_3': 'Direct broker Lambda schema/action denial plus policy inspection',
        'scenario_4': 'Local CapacityEngine denial plus earlier live broker inventory denial',
        'scenario_5': 'Direct DynamoDB conditional-write refusal plus direct broker schema denial',
        'scenario_6': 'Direct broker replay/cache response plus audit count',
        'scenario_7': 'Local LogReader treatment of synthetic logs plus direct apply_guardrail',
        'scenario_8': 'Direct signed Gateway MCP denial; not a Harness conversation',
    }
    audit = {'kind': 'Allowlisted recorded evidence derivative; not raw AWS output',
             'source_reference': 'private Step 7 saved JSON; scenarios.scenario_1',
             'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
             'suite_executed_at': raw['executed_at'], 'region': raw['aws_region'],
             'verified_harness_prompt_response_count': 1,
             'verified_model_generated_adversarial_response_count': 0,
             'minimum_additional_harness_pairs_needed': 4,
             'qualification': 'Organizer acceptance of an input-block response is not independently confirmed. Five unambiguous agent-response records are the conservative target.',
             'records': [record],
             'non_qualifying_scenarios': [{'id': raw['scenarios'][key]['scenario_id'],
                 'name': raw['scenarios'][key]['name'], 'observed_layer': layer,
                 'missing': 'No saved adversarial user message paired with a Harness invocation and returned agent/Harness response.'}
                 for key, layer in layers.items()],
             'redaction': 'Accounts, ARNs, request/session IDs, endpoints and raw logs omitted. Exact prompt and returned block text preserved.'}
    write_json(OUT / 'evidence/adversarial-prompt-audit.json', audit)
    return audit


def execution_trace(source):
    raw = json.loads(source.read_text(encoding='utf-8'))
    messages = []
    for event in raw['harness_events']:
        if 'messageStart' in event:
            message = {'role': event['messageStart']['role'], 'blocks': {}}
            messages.append(message)
        if 'contentBlockStart' in event:
            item = event['contentBlockStart']
            message['blocks'][item['contentBlockIndex']] = {'start': item['start'], 'deltas': []}
        if 'contentBlockDelta' in event:
            item = event['contentBlockDelta']
            message['blocks'].setdefault(item['contentBlockIndex'], {'start': {}, 'deltas': []})['deltas'].append(item['delta'])
        if 'messageStop' in event:
            message['stop_reason'] = event['messageStop'].get('stopReason')
    tool_results = []
    tools = []
    for message in messages:
        for block in message['blocks'].values():
            if 'toolUse' in block['start']:
                tools.append(block['start']['toolUse']['name'])
            if 'toolResult' in block['start']:
                text = ''.join(content.get('text', '') for delta in block['deltas'] for content in delta.get('toolResult', []))
                tool_results.append(json.loads(text))
    assert len(tools) == 2 and len(tool_results) == 2, 'Unexpected source stream; inspect privately before projection.'
    diagnostics = tool_results[0]['diagnostics']
    receipt = json.loads(tool_results[1]['body'])
    final = ''.join(delta.get('text', '') for block in messages[-1]['blocks'].values() for delta in block['deltas'])
    final = re.sub(r'<thinking>.*?</thinking>', '', final, flags=re.S).strip()
    # Explicit aliases preserve meaning without publishing source identifiers.
    final = final.replace(receipt['decision_id'], 'decision-step6-01').replace(receipt['aws_request_id'], 'request-step6-01')
    final = final.replace(raw['incident']['incident_id'], 'incident-step6-01')
    assert not re.search(r'arn:aws:|\b\d{12}\b|<thinking>', final)
    result = {
        'kind': 'Allowlisted recorded AgentCore event-stream derivative; not an AWS Console export',
        'source_reference': 'private Step 6 saved harness_events and recovery observations',
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'recorded_start_utc': datetime.fromtimestamp(raw['started_at'], timezone.utc).isoformat(),
        'stream_event_count': len(raw['harness_events']),
        'session_alias': 'session-step6-01', 'incident_alias': 'incident-step6-01',
        'is_adversarial_test': False, 'manual_harness_invocation': True,
        'tools': [
            {'name': tools[0], 'status_code': tool_results[0]['statusCode'],
             'ecs_last_status': diagnostics['ecs_state']['last_status'],
             'processing_state': diagnostics['health_evidence']['processing_state'],
             'is_unhealthy': diagnostics['health_evidence']['is_unhealthy'],
             'health_age_seconds': diagnostics['health_evidence']['age_seconds']},
            {'name': tools[1], 'status_code': tool_results[1]['statusCode'],
             **{k: receipt[k] for k in ['action_id', 'decision', 'reason_code', 'execution_status', 'recorded_at', 'rule_results']}}
        ],
        'final_assistant_response': final, 'final_stop_reason': messages[-1].get('stop_reason'),
        'later_recovery_observations': {'target_stopped': raw['stopped_confirmed'],
            'distinct_replacement_observed': bool(set(raw['replacement_tasks']) - set(raw['initial_tasks'])),
            'recovered_healthy': raw['recovered_healthy'], 'cleanup': raw['final_service_state']},
        'limitations': ['Historical manually invoked Step 6 session; distinct from the later unattended run.',
            'The receipt returned SUBMITTED. Later task/heartbeat observations establish recovery, not the receipt alone.',
            'Prompt text is reconstructed in the private runner source; this public derivative does not claim a captured inbound-message event.',
            'Model thinking blocks, logs and operational identifiers are omitted. Aliases replace decision/request IDs in the final response.',
            'Source fingerprint is not an AWS signature or independent attestation.']}
    write_json(OUT / 'evidence/step6-execution-trace.json', result)
    return result


def viewer(trace, audit):
    def esc(value): return html.escape(str(value))
    first, second = trace['tools']
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BlastGate — recorded AgentCore execution evidence</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#0b0f14;color:#f5f4f1;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1250px;margin:auto;padding:50px 56px}}header{{border-bottom:1px solid #ffffff25;padding-bottom:30px}}.eyebrow{{color:#d8a955;font-size:13px;letter-spacing:.08em}}h1{{font:48px/1.1 Georgia,serif;margin:18px 0}}h2{{font-size:20px;margin:0 0 12px}}.muted{{color:#b5b8bd}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:44px;margin-top:32px}}section{{padding:20px 0;border-bottom:1px solid #ffffff20}}code{{font:13px/1.7 Consolas,monospace;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;font:14px/1.6 system-ui,sans-serif;margin:12px 0}}.result{{font-size:30px;color:#86efac}}.scope{{font-size:13px;color:#b5b8bd;margin-top:26px}}a{{color:#d8a955}}.meta{{display:flex;gap:30px;flex-wrap:wrap;font-size:13px;color:#b5b8bd}}@media(max-width:700px){{main{{padding:24px}}h1{{font-size:34px}}.columns{{grid-template-columns:1fr}}}}</style>
<main><header><div class="eyebrow">BLASTGATE / RECORDED AWS EXECUTION</div><h1>AgentCore Harness: diagnosis to proposal.</h1><p class="muted">A local evidence viewer of a real saved AWS event stream. Historical Step 6 session; manually invoked, not live and not an AWS Console screenshot.</p><div class="meta"><span>Recorded start: {esc(trace['recorded_start_utc'])}</span><span>{trace['stream_event_count']} saved stream events</span><span>Public aliases · original evidence private</span></div></header>
<div class="columns"><div><section><h2>01 · Read-only diagnostics</h2><code>{esc(first['name'])}</code><p>ECS <strong>{esc(first['ecs_last_status'])}</strong> · application <strong>{esc(first['processing_state'])}</strong><br>Unhealthy: {esc(first['is_unhealthy'])} · HTTP {first['status_code']}</p></section><section><h2>02 · Broker proposal result</h2><code>{esc(second['name'])}</code><p class="result">{esc(second['decision'])}</p><code>{esc(second['reason_code'])} · {esc(second['execution_status'])}</code><p>All eight captured rule flags: true</p><p class="scope">SUBMITTED is the returned execution status. Later observations separately confirm the stopped target and a distinct healthy replacement.</p></section></div><div><section><h2>Returned assistant response</h2><pre>{esc(trace['final_assistant_response'])}</pre></section><section><h2>Separate adversarial Harness record</h2><p class="muted">Step 7 / prompt injection / {esc(audit['suite_executed_at'])}</p><blockquote>{esc(audit['records'][0]['harness_output_text'])}</blockquote><code>stopReason: {esc(audit['records'][0]['harness_stop_reason'])}</code><p class="scope">Input Guardrail block; no model-generated adversarial answer established. Only one adversarial Harness pair is evidenced.</p></section></div></div>
<p class="scope">Selected fields only. Thinking blocks, logs, account/resource/request IDs and endpoints omitted. Source fingerprints are not AWS signatures.</p><a href="evidence/step6-execution-trace.json">Inspect public trace JSON</a> · <a href="evidence/adversarial-prompt-audit.json">Inspect prompt audit JSON</a></main></html>'''
    (OUT / 'recorded-execution-viewer.html').write_text(page, encoding='utf-8')


def vectors():
    def txt(x,y,text,size=20,color='#f5f4f1',weight='400'):
        return f'<text x="{x}" y="{y}" font-family="Arial,sans-serif" font-size="{size}" fill="{color}" font-weight="{weight}">{html.escape(text)}</text>'
    def box(x,y,title,lines):
        return f'<rect x="{x}" y="{y}" width="300" height="148" rx="10" fill="#11161d" stroke="#42464d"/>'+txt(x+20,y+34,title,21,weight='600')+''.join(txt(x+20,y+65+i*24,line,16,'#b5b8bd') for i,line in enumerate(lines))
    def arrow(x1,y1,x2,y2):
        return f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="#d8a955" stroke-width="2" marker-end="url(#arrow)"/>'
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1000" viewBox="0 0 1600 1000"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#d8a955"/></marker></defs><rect width="1600" height="1000" fill="#0b0f14"/>'
    svg+=txt(60,64,'BLASTGATE',22,'#d8a955','600')+txt(60,119,'The agent proposes. The broker decides.',40)+txt(60,161,'Source architecture · one bounded recovery action · not a live execution trace',18,'#b5b8bd')
    svg+=box(60,220,'ECS Fargate worker',['Application progress + health','DynamoDB heartbeat evidence'])
    svg+=box(450,220,'Watchdog + CloudWatch',['Fresh telemetry → stall metric','Alarm transition'])
    svg+=box(840,220,'Incident + EventBridge',['Ingestion deduplicates incident','Incident-open event → target'])
    svg+=box(1230,220,'Dispatcher Lambda',['Atomic incident dispatch lock','Invoke Managed Harness'])
    for x in [360,750,1140]:svg+=arrow(x,294,x+80,294)
    svg+=arrow(1380,368,1380,450)
    svg+=box(1230,460,'AgentCore Harness',['Amazon Nova Micro + Guardrails','Only diagnostics / proposal tools','No direct mutation authority'])
    svg+=box(840,460,'AgentCore Gateway',['Cedar principal + tool scope','Proposal action restriction','Native service enforcement'])
    svg+=box(450,460,'Independent broker',['R1–R8 live state validation','Reserve cooldown + audit','Authorize before mutation'])
    svg+=box(60,460,'ECS service recovery',['Scoped StopTask on one worker','ECS launches replacement','Verify new healthy task'])
    for x in [1230,840,450]:svg+=arrow(x,534,x-80,534)
    svg+=arrow(990,608,990,685)+arrow(600,608,600,685)
    svg+=box(840,695,'Diagnostics Lambda',['Read-only incident / telemetry','Bounded logs are untrusted'])
    svg+=box(450,695,'DynamoDB state + audit',['600-second cluster cooldown','Idempotency + structured audit'])
    svg+=txt(60,893,'ENFORCEMENT',14,'#d8a955','600')+txt(60,928,'Guardrails → tool allowlist → Cedar → broker invariants → scoped IAM permissions',23)
    svg+=txt(60,969,'Architectural order; compact recovery evidence does not retain every intermediate timestamp or tool trace.',16,'#b5b8bd')+'</svg>'
    (OUT/'assets/architecture.svg').write_text(svg,encoding='utf-8')
    cover='<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675"><rect width="1200" height="675" fill="#0b0f14"/><path d="M72 130 L101 69 H114 L85 130Z M105 130 L134 69 H121 L92 130Z" fill="#d8a955"/>'
    cover+=txt(160,115,'BLASTGATE',31,'#f5f4f1','600')+txt(72,277,'Autonomous recovery.',63)+txt(72,352,'Provable boundaries.',63,'#d8a955')
    cover+=txt(76,435,'The agent proposes. The broker decides.',28,'#b5b8bd')+'<path d="M76 510 H1124" stroke="#ffffff30"/>'
    cover+=txt(76,557,'Amazon Bedrock AgentCore Managed Harness',21)+txt(76,600,'ECS worker recovery · independent R1–R8 enforcement',19,'#b5b8bd')+'</svg>'
    (OUT/'assets/cover.svg').write_text(cover,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--step6-source',type=Path,required=True,help='Private saved Step 6 JSON; read-only input')
    args=parser.parse_args()
    (OUT/'assets').mkdir(parents=True,exist_ok=True)
    audit=prompt_audit()
    trace=execution_trace(args.step6_source)
    viewer(trace,audit)
    vectors()
    print('Prepared two allowlisted evidence derivatives, a recorded-evidence viewer and two SVG assets. No AWS calls.')


if __name__=='__main__':main()
