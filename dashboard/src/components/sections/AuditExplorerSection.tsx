import React, { useState } from "react";
import {
  FileText,
  Download,
  Copy,
  Check,
  Shield,
  Hash,
  Link as LinkIcon,
  ShieldCheck,
} from "lucide-react";
import { AuditEvent } from "@/types";

interface AuditExplorerSectionProps {
  auditEvents: AuditEvent[];
}

export const AuditExplorerSection: React.FC<AuditExplorerSectionProps> = ({ auditEvents }) => {
  const [selectedEventType, setSelectedEventType] = useState<string>("ALL");
  const [selectedActor, setSelectedActor] = useState<string>("ALL");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copiedAll, setCopiedAll] = useState(false);

  const handleCopyHash = async (hash: string, id: string) => {
    try { await navigator.clipboard.writeText(hash); } catch { return; }
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleExportJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(auditEvents, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `blastgate_SIMULATED_audit_log_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();

    setCopiedAll(true);
    setTimeout(() => setCopiedAll(false), 2000);
  };

  const filteredEvents = auditEvents.filter((evt) => {
    const matchesType = selectedEventType === "ALL" || evt.event_type === selectedEventType;
    const matchesActor = selectedActor === "ALL" || evt.actor_type === selectedActor;
    return matchesType && matchesActor;
  });

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#11161D] p-5 rounded-xl border border-white/[0.075] shadow-sm">
        <div>
          <div className="text-[11px] font-mono tracking-widest uppercase text-[#848B95] mb-1">
            SIMULATED AUDIT RECORDS
          </div>
          <h2 className="text-xl font-serif text-[#F5F4F1] flex items-center gap-2">
            <FileText className="w-5 h-5 text-[#D8A955]" />
            Audit Evidence Explorer & Hash Chaining
          </h2>
          <p className="text-xs text-[#848B95] mt-1">
            Cryptographically structured, append-only transaction ledger emitted before and during remediation.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleExportJson}
            className="flex items-center space-x-1.5 text-xs bg-[#D8A955] text-[#0B0F14] font-medium px-4 py-2 rounded-lg hover:bg-[#C29543] transition-colors shadow-sm"
          >
            {copiedAll ? <Check className="w-3.5 h-3.5" /> : <Download className="w-3.5 h-3.5" />}
            <span>{copiedAll ? "Exported!" : "Export Audit JSON"}</span>
          </button>
        </div>
      </div>

      {/* Mandatory Tamper-Evidence & Integrity Notice */}
      <div className="p-4 bg-[#0D1117] border border-white/[0.075] rounded-xl space-y-1.5 text-xs text-[#848B95]">
        <div className="flex items-center space-x-2 text-[#F5F4F1] font-medium">
          <Shield className="w-4 h-4 text-[#D8A955]" />
          <span>Integrity & Audit Scope (Rule R6)</span>
        </div>
        <p className="leading-relaxed text-[11px]">
          BlastGate audit events are structured JSON objects adhering to the audit schema contract. 
          In local verification mode, records represent simulated append-only items with parent SHA-256 hash chaining.
          <span className="block mt-1 text-[#B5B8BD]">
            <strong className="text-[#D8A955]">Honest Engineering Disclosure:</strong> In live AWS deployment, these records are stored in DynamoDB under IAM Deny on <code className="text-[#D8A955] bg-black/40 px-1 py-0.5 rounded font-mono">DeleteItem</code> and <code className="text-[#D8A955] bg-black/40 px-1 py-0.5 rounded font-mono">UpdateItem</code>. It provides tamper-evidence within the writer boundary. Hash chains are per execution context, not a globally checkpointed ledger.
          </span>
        </p>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#11161D] p-3.5 rounded-xl border border-white/[0.075] shadow-sm text-xs">
        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <span className="text-[#848B95] font-medium">Event Type:</span>
          <select
            aria-label="Filter audit event type" value={selectedEventType}
            onChange={(e) => setSelectedEventType(e.target.value)}
            className="p-1.5 rounded-lg border border-white/[0.075] bg-[#161B22] text-[#F5F4F1] text-xs focus:outline-none focus:border-[#D8A955]"
          >
            <option value="ALL">All Types ({auditEvents.length})</option>
            <option value="AUTHORIZATION_DECISION">AUTHORIZATION_DECISION</option>
            <option value="SYSTEM_REFUSAL">SYSTEM_REFUSAL</option>
            <option value="COOLDOWN_RESERVATION">COOLDOWN_RESERVATION</option>
          </select>
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto justify-end">
          <span className="text-[#848B95] font-medium">Actor:</span>
          <select
            aria-label="Filter audit actor" value={selectedActor}
            onChange={(e) => setSelectedActor(e.target.value)}
            className="p-1.5 rounded-lg border border-white/[0.075] bg-[#161B22] text-[#F5F4F1] text-xs focus:outline-none focus:border-[#D8A955]"
          >
            <option value="ALL">All Actors</option>
            <option value="LAMBDA_BROKER">LAMBDA_BROKER</option>
            <option value="AGENT_GATEWAY">AGENT_GATEWAY</option>
            <option value="SYSTEM_WATCHDOG">SYSTEM_WATCHDOG</option>
          </select>
        </div>
      </div>

      {/* Event Timeline Stream */}
      <div className="space-y-4">
        {filteredEvents.map((evt) => {
          const isAllow = evt.authorization_decision === "ALLOW";

          return (
            <div
              key={evt.event_id}
              className="bg-[#11161D] rounded-xl border border-white/[0.075] shadow-sm p-4 sm:p-5 space-y-3.5 text-xs transition-colors hover:border-white/[0.12]"
            >
              {/* Event Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/[0.05] pb-3">
                <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                  <span className="font-mono text-xs bg-white/[0.04] text-[#D8A955] px-2 py-0.5 rounded border border-white/[0.06]">
                    {evt.event_id}
                  </span>
                  <span className="font-mono text-xs font-semibold text-[#F5F4F1]">
                    {evt.event_type}
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-[#161B22] text-[#848B95] border border-white/[0.06]">
                    {evt.actor_type}
                  </span>
                </div>

                <div className="flex items-center space-x-2">
                  <span
                    className={`font-mono text-[11px] px-2.5 py-0.5 rounded ${
                      isAllow
                        ? "bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/25"
                        : "bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/25"
                    }`}
                  >
                    AUTH: {evt.authorization_decision} ({evt.execution_status})
                  </span>
                  <span className="text-[11px] text-[#848B95] font-mono">{evt.timestamp}</span>
                </div>
              </div>

              {/* Event Body: Action & Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-[#0D1117] border border-white/[0.05] space-y-1.5">
                  <span className="text-[#848B95] text-[11px] block">Requested Catalog Action</span>
                  <span className="font-mono font-semibold text-[#F5F4F1] block">
                    {evt.requested_action}
                  </span>
                  <div className="text-[11px] text-[#848B95] pt-1">
                    Incident: <span className="font-mono text-[#D8A955]">{evt.incident_id}</span> | Decision:{" "}
                    <span className="font-mono text-[#D8A955]">{evt.decision_id}</span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-[#0D1117] border border-white/[0.05] space-y-1.5">
                  <span className="text-[#848B95] text-[11px] block">Event Execution Context</span>
                  <pre className="font-mono text-[11px] text-[#B5B8BD] overflow-x-auto p-1 bg-black/30 rounded">
                    {JSON.stringify(evt.details, null, 2)}
                  </pre>
                </div>
              </div>

              {/* Cryptographic Hash Lineage Bar */}
              <div className="p-3 rounded-lg bg-[#0B0F14] text-[#848B95] font-mono text-[11px] space-y-2 border border-white/[0.06]">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="flex items-center gap-1.5 font-medium text-[#F5F4F1]">
                    <Hash className="w-3.5 h-3.5 text-[#D8A955]" /> Canonical Event Hash (SHA-256)
                  </span>
                  <button
                    onClick={() => handleCopyHash(evt.sha256_hash, evt.event_id)}
                    className="flex items-center gap-1 text-[#D8A955] hover:text-[#F5F4F1] transition-colors"
                  >
                    {copiedId === evt.event_id ? (
                      <Check className="w-3 h-3 text-[#10B981]" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                    <span>{copiedId === evt.event_id ? "Copied" : "Copy"}</span>
                  </button>
                </div>
                <div className="text-[#10B981] text-[11px] break-all">{evt.sha256_hash}</div>

                <div className="flex items-center space-x-1.5 text-[11px] text-[#848B95] pt-1.5 border-t border-white/[0.06]">
                  <LinkIcon className="w-3 h-3 text-[#D8A955]" />
                  <span>Parent Hash:</span>
                  <span className="text-[#848B95] text-[11px] break-all">{evt.parent_hash}</span>
                </div>
              </div>
            </div>
          );
        })}

        {filteredEvents.length === 0 && (
          <div className="p-8 text-center bg-[#11161D] rounded-xl border border-white/[0.075] text-xs text-[#848B95]">
            No audit events matched the selected filters.
          </div>
        )}
      </div>
    </div>
  );
};
