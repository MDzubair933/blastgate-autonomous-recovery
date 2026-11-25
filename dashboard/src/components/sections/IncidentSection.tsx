import React, { useState } from "react";
import {
  AlertTriangle,
  Search,
  CheckCircle2,
  Clock,
  ShieldAlert,
  FileCode,
  BookOpen,
  ArrowRight,
  Filter,
  Shield,
  Check,
} from "lucide-react";
import { IncidentRecord } from "@/types";

interface IncidentSectionProps {
  incidents: IncidentRecord[];
  selectedIncidentId?: string;
  onSelectIncident?: (incident: IncidentRecord | null) => void;
  onNavigateToDecision?: (incidentId: string) => void;
}

export const IncidentSection: React.FC<IncidentSectionProps> = ({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  onNavigateToDecision,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<"ALL" | "OPEN" | "RESOLVED">("ALL");
  const [internalSelected, setInternalSelected] = useState<IncidentRecord | null>(null);

  const handleSelect = (incident: IncidentRecord) => {
    setInternalSelected(incident);
    if (onSelectIncident) {
      onSelectIncident(incident);
    }
  };

  const filteredIncidents = incidents.filter((inc) => {
    const matchesStatus = statusFilter === "ALL" || inc.status === statusFilter;
    const matchesSearch =
      inc.incident_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.alarm_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.target_short_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      inc.summary.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const activeIncident =
    filteredIncidents.find((inc) => inc.incident_id === selectedIncidentId) ||
    filteredIncidents.find((inc) => inc.incident_id === internalSelected?.incident_id) ||
    filteredIncidents[0] ||
    null;

  return (
    <div className="space-y-5">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#11161D] p-5 rounded-[14px] border border-white/[0.075]">
        <div>
          <h2 className="text-xl font-bold text-[#F5F4F1] flex items-center gap-2.5 tracking-tight font-serif">
            <AlertTriangle className="w-5 h-5 text-[#D8A955]" />
            Incident Investigation & Log Boundaries
          </h2>
          <p className="text-xs text-[#848B95] mt-1">
            CloudWatch Alarm Watchdog ingestion with strict untrusted data sanitization boundaries.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs bg-[#D8A955]/10 text-[#D8A955] border border-[#D8A955]/30 font-medium px-3 py-1 rounded-full flex items-center gap-1.5">
            <ShieldAlert className="w-3.5 h-3.5" />
            Untrusted Boundary Active
          </span>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-[#11161D] p-3 rounded-[12px] border border-white/[0.075]">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 text-[#848B95] absolute left-3 top-2.5" />
            <input
              aria-label="Search incidents" type="text"
              placeholder="Filter by ID, worker, alarm..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-[8px] bg-[#0B0F14] border border-white/[0.08] text-[#F5F4F1] placeholder-[#616874] focus:border-[#D8A955] focus:outline-none"
            />
          </div>
          {searchTerm && (
            <button
              onClick={() => setSearchTerm("")}
              className="text-xs text-[#848B95] hover:text-[#F5F4F1]"
            >
              Clear
            </button>
          )}
        </div>

        <div className="flex items-center space-x-1.5 w-full sm:w-auto justify-end text-xs">
          <Filter className="w-3.5 h-3.5 text-[#848B95]" />
          {(["ALL", "OPEN", "RESOLVED"] as const).map((status) => (
            <button
              key={status}
              aria-pressed={statusFilter === status} onClick={() => setStatusFilter(status)}
              className={`px-3 py-1 rounded-[8px] font-medium transition-colors ${
                statusFilter === status
                  ? "bg-[#181E26] text-[#F5F4F1] border border-white/[0.12]"
                  : "bg-white/[0.02] text-[#848B95] hover:bg-white/[0.05] border border-transparent"
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Main Layout: List & Detail Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Incident List */}
        <div className="lg:col-span-1 space-y-3">
          <div className="flex items-center justify-between text-xs text-[#848B95]">
            <span className="font-semibold text-[#F5F4F1]">Incidents ({filteredIncidents.length})</span>
            <span>Click to inspect details</span>
          </div>

          <div className="space-y-2.5">
            {filteredIncidents.map((incident) => {
              const isSelected = activeIncident?.incident_id === incident.incident_id;
              const isOpen = incident.status === "OPEN";

              return (
                <div
                  key={incident.incident_id}
                  onClick={() => handleSelect(incident)} role="button" tabIndex={0} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleSelect(incident); } } } aria-pressed={isSelected}
                  className={`p-4 rounded-[12px] border cursor-pointer transition-all ${
                    isSelected
                      ? "border-[#D8A955] bg-[#1C1813] shadow-md ring-1 ring-[#D8A955]/20"
                      : "border-white/[0.075] bg-[#11161D] hover:border-white/[0.14]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono font-bold text-xs text-[#D8A955]">
                      {incident.incident_id}
                    </span>
                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                        isOpen
                          ? "bg-[#D8A955]/15 text-[#D8A955] border border-[#D8A955]/30"
                          : "bg-white/[0.04] text-[#848B95] border border-white/[0.08]"
                      }`}
                    >
                      {incident.status}
                    </span>
                  </div>

                  <p className="text-xs font-semibold text-[#F5F4F1] line-clamp-1 mb-1">
                    {incident.alarm_name}
                  </p>
                  <p className="text-[11px] text-[#848B95] line-clamp-2 mb-2 leading-relaxed">
                    {incident.summary}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-[#848B95] border-t border-white/[0.06] pt-2">
                    <span className="font-mono bg-white/[0.04] px-1.5 py-0.5 rounded text-[#B5B8BD] border border-white/[0.06]">
                      Target: {incident.target_short_id}
                    </span>
                    <span className="flex items-center gap-1 font-mono">
                      <Clock className="w-3 h-3" />
                      {new Date(incident.created_at).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                </div>
              );
            })}

            {filteredIncidents.length === 0 && (
              <div className="p-8 text-center bg-[#11161D] rounded-[12px] border border-white/[0.075] text-xs text-[#848B95]">
                No incidents match the active filters.
              </div>
            )}
          </div>
        </div>

        {/* Selected Incident Detail View */}
        <div className="lg:col-span-2">
          {activeIncident ? (
            <div className="bg-[#11161D] rounded-[14px] border border-white/[0.075] p-5 sm:p-6 space-y-5">
              {/* Top Banner */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/[0.06] pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-[#D8A955] bg-[#D8A955]/10 border border-[#D8A955]/30 px-2.5 py-0.5 rounded">
                      {activeIncident.incident_id}
                    </span>
                    <span
                      className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${
                        activeIncident.status === "OPEN"
                          ? "bg-[#D8A955]/15 text-[#D8A955] border border-[#D8A955]/30"
                          : "bg-white/[0.04] text-[#848B95] border border-white/[0.08]"
                      }`}
                    >
                      STATUS: {activeIncident.status}
                    </span>
                    <span
                      className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${
                        activeIncident.state === "ALARM"
                          ? "bg-red-500/10 text-red-400 border border-red-500/30"
                          : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                      }`}
                    >
                      STATE: {activeIncident.state}
                    </span>
                  </div>
                  <h3 className="text-base font-semibold text-[#F5F4F1] mt-2">
                    {activeIncident.alarm_name}
                  </h3>
                </div>

                {onNavigateToDecision && (
                  <button
                    onClick={() => onNavigateToDecision(activeIncident.incident_id)}
                    className="flex items-center gap-1.5 text-xs bg-[#181E26] hover:bg-[#252B34] text-[#F5F4F1] border border-white/[0.12] font-medium px-3.5 py-2 rounded-[8px] transition-colors shrink-0 shadow-sm"
                  >
                    <span>View Decision Timeline</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Summary & Metadata */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3.5 bg-[#161B22] rounded-[10px] border border-white/[0.06]">
                  <span className="text-[#848B95] block text-[11px]">Target ECS Task ARN</span>
                  <span className="font-mono text-[11px] text-[#B5B8BD] break-all block mt-1">
                    {activeIncident.target_task_arn}
                  </span>
                  <span className="text-[11px] font-bold text-[#D8A955] mt-1.5 block">
                    Short ID: {activeIncident.target_short_id}
                  </span>
                </div>

                <div className="p-3.5 bg-[#161B22] rounded-[10px] border border-white/[0.06] space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-[#848B95]">Cluster / Service:</span>
                    <span className="font-mono font-medium text-[#F5F4F1]">
                      {activeIncident.cluster_name} / {activeIncident.service_name}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#848B95]">Ingested At:</span>
                    <span className="font-mono text-[#F5F4F1]">{activeIncident.created_at}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#848B95]">Catalog Runbook:</span>
                    <span className="font-mono font-semibold text-[#D8A955] flex items-center gap-1">
                      <BookOpen className="w-3 h-3" /> {activeIncident.runbook_id}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#848B95]">Approved Action:</span>
                    <span className="font-mono font-semibold text-emerald-400">
                      {activeIncident.approved_action}
                    </span>
                  </div>
                </div>
              </div>

              {/* Incident Summary */}
              <div className="p-3.5 bg-[#161B22] rounded-[10px] border border-white/[0.06]">
                <h4 className="text-xs font-semibold text-[#F5F4F1] mb-1">Watchdog Root Cause Summary</h4>
                <p className="text-xs text-[#848B95] leading-relaxed">{activeIncident.summary}</p>
              </div>

              {/* UNTRUSTED LOG BOUNDARY (Crucial Security Contract) */}
              <div className="space-y-2.5 border-t border-white/[0.06] pt-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-[#D8A955]" />
                    <h4 className="text-xs font-semibold text-[#F5F4F1]">
                      Log Ingestion Boundary (Untrusted Data Source)
                    </h4>
                  </div>
                  <span className="text-[11px] bg-red-500/10 text-red-400 border border-red-500/30 px-2.5 py-0.5 rounded font-mono font-bold">
                    IS_UNTRUSTED_DATA = {activeIncident.untrusted_logs.is_untrusted_data ? "TRUE" : "FALSE"}
                  </span>
                </div>

                {/* Boundary Alert Box */}
                <div className="p-3 bg-[#1C1813] border border-[#D8A955]/30 rounded-[8px] text-[11px] text-[#D8A955] space-y-1">
                  <div className="flex items-center gap-1.5 font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                    <span>Boundary Policy Enforcement (Rule R5):</span>
                  </div>
                  <p className="text-[11px] text-[#848B95] leading-relaxed">
                    {activeIncident.untrusted_logs.boundary_note}
                  </p>
                </div>

                {/* Log Stream Container */}
                <div className="rounded-[8px] border border-white/[0.08] bg-[#0B0F14] p-3 text-xs overflow-hidden">
                  <div className="flex items-center justify-between text-[11px] text-[#848B95] border-b border-white/[0.06] pb-1.5 mb-2 font-mono">
                    <span>CloudWatch Log Stream: /aws/ecs/blastgate-worker</span>
                    <span className="text-emerald-400">Sanitized Stream</span>
                  </div>
                  <div className="font-mono text-[11px] text-[#B5B8BD] space-y-1 overflow-x-auto max-h-60 leading-relaxed">
                    {activeIncident.untrusted_logs.log_lines.map((line, idx) => {
                      const isExploit = line.includes("<UNTRUSTED>");
                      const isError = line.includes("ERROR") || line.includes("HEARTBEAT_MISSING");
                      const isWarn = line.includes("WARN");

                      return (
                        <div
                          key={idx}
                          className={`p-1 rounded ${
                            isExploit
                              ? "bg-red-950/60 text-red-300 border border-red-800/40 font-bold"
                              : isError
                              ? "text-red-400/90"
                              : isWarn
                              ? "text-[#D8A955]"
                              : "text-[#848B95]"
                          }`}
                        >
                          {line}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-[#11161D] rounded-[14px] border border-white/[0.075] p-12 text-center text-xs text-[#848B95]">
              Select an incident from the list to inspect telemetry and untrusted log boundaries.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
