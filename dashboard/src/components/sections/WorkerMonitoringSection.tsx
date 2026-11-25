import React, { useState } from "react";
import {
  Server,
  AlertOctagon,
  CheckCircle2,
  Clock,
  Cpu,
  Code,
  Info,
  Check,
} from "lucide-react";
import { WorkerRecord, FleetCapacity } from "@/types";

interface WorkerMonitoringSectionProps {
  workers: WorkerRecord[];
  capacity: FleetCapacity;
  selectedWorkerId?: string;
  onNavigateToIncident?: (id: string) => void;
  onSelectWorker?: (worker: WorkerRecord | null) => void;
}

export const WorkerMonitoringSection: React.FC<WorkerMonitoringSectionProps> = ({
  workers,
  capacity,
  selectedWorkerId,
  onSelectWorker,
  onNavigateToIncident,
}) => {
  const [internalSelected, setInternalSelected] = useState<WorkerRecord | null>(
    workers.find((w) => w.short_id === selectedWorkerId) || workers[0] || null
  );

  const activeWorker = workers.find((w) => w.short_id === selectedWorkerId) || internalSelected;

  const handleSelect = (worker: WorkerRecord) => {
    setInternalSelected(worker);
    if (onSelectWorker) {
      onSelectWorker(worker);
    }
  };

  const quorumPercentage = (capacity.healthy_count / capacity.desired_count) * 100;
  const minQuorumPercentage = (capacity.min_healthy_threshold / capacity.desired_count) * 100;

  return (
    <div className="space-y-5">
      {/* Top Banner / Breadcrumb Info */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#11161D] p-5 rounded-[14px] border border-white/[0.075]">
        <div>
          <h2 className="text-xl font-bold text-[#F5F4F1] flex items-center gap-2.5 tracking-tight font-serif">
            <Server className="w-5 h-5 text-[#D8A955]" />
            ECS Worker Fleet Telemetry (Simulated Reference Fleet)
          </h2>
          <p className="text-xs text-[#848B95] mt-1">
            Cluster: <span className="font-mono text-[#F5F4F1]">{capacity.cluster_name} (Simulated)</span> | Service:{" "}
            <span className="font-mono text-[#F5F4F1]">{capacity.service_name} (Simulated)</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs bg-[#D8A955]/10 text-[#D8A955] border border-[#D8A955]/30 font-medium px-3 py-1 rounded-full flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Quorum Active: {capacity.healthy_count} of {capacity.desired_count} Healthy (Min: {capacity.min_healthy_threshold})
          </span>
          <span className="text-[11px] bg-white/[0.04] text-[#848B95] border border-white/[0.08] px-2.5 py-1 rounded-full font-mono">
            Max Unavail: {capacity.max_unavailable_percent}%
          </span>
        </div>
      </div>

      {/* Quorum & Capacity Calculation Card */}
      <div className="bg-[#11161D] p-5 sm:p-6 rounded-[14px] border border-white/[0.075] space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-[#F5F4F1] tracking-tight">
              Fleet Health & Quorum Invariant (Rule R2)
            </h3>
            <p className="text-xs text-[#848B95] mt-0.5">
              Remediation is permitted only when stopping a task maintains at least {capacity.min_healthy_threshold} healthy workers.
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
              <span className="text-[#848B95] font-medium">Healthy ({capacity.healthy_count})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#D8A955]" />
              <span className="text-[#848B95] font-medium">Stalled ({capacity.stalled_count})</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full border border-dashed border-[#D8A955]" />
              <span className="text-[#848B95] font-medium">Min Threshold ({capacity.min_healthy_threshold})</span>
            </div>
          </div>
        </div>

        {/* Progress Bar with Min Threshold Marker */}
        <div className="relative pt-3 pb-2">
          <div className="h-3 w-full bg-[#181E26] rounded-full overflow-hidden flex shadow-inner">
            <div
              style={{ width: `${(capacity.healthy_count / capacity.desired_count) * 100}%` }}
              className="bg-emerald-600/70 transition-all duration-500"
              title={`Healthy: ${capacity.healthy_count}`}
            />
            <div
              style={{ width: `${(capacity.stalled_count / capacity.desired_count) * 100}%` }}
              className="bg-[#D8A955]/90 transition-all duration-500"
              title={`Stalled: ${capacity.stalled_count}`}
            />
          </div>
          {/* Threshold Marker Pin */}
          <div
            className="absolute top-1 bottom-0 flex flex-col items-center pointer-events-none"
            style={{ left: `${minQuorumPercentage}%` }}
          >
            <div className="w-[1.5px] h-5 bg-[#D8A955] z-10" />
            <span className="text-[11px] text-[#D8A955] font-mono font-bold mt-1 bg-[#0D1117] border border-[#D8A955]/30 px-1.5 py-0.2 rounded shadow-xs">
              Min Quorum ({capacity.min_healthy_threshold})
            </span>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 text-xs border-t border-white/[0.06]">
          <div className="p-3 rounded-[10px] bg-[#161B22] border border-white/[0.06]">
            <span className="text-[#848B95] block text-[11px]">Desired Count</span>
            <span className="text-base font-semibold text-[#F5F4F1] mt-0.5 block">{capacity.desired_count} Tasks</span>
          </div>
          <div className="p-3 rounded-[10px] bg-[#161B22] border border-white/[0.06]">
            <span className="text-[#848B95] block text-[11px]">Running Tasks</span>
            <span className="text-base font-semibold text-[#F5F4F1] mt-0.5 block">{capacity.running_count} Tasks</span>
          </div>
          <div className="p-3 rounded-[10px] bg-[#161B22] border border-white/[0.06]">
            <span className="text-[#848B95] block text-[11px]">Telemetry Health Rate</span>
            <span className="text-base font-semibold text-[#D8A955] mt-0.5 block">{quorumPercentage.toFixed(1)}%</span>
          </div>
          <div className="p-3 rounded-[10px] bg-[#161B22] border border-white/[0.06]">
            <span className="text-[#848B95] block text-[11px]">Capacity Check</span>
            <span className={`text-base font-semibold mt-0.5 block ${capacity.remediation_allowed_by_capacity ? "text-emerald-400" : "text-[#D8A955]"}`}>
              {capacity.remediation_allowed_by_capacity ? "PASSED" : "INSUFFICIENT"}
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: 6 Worker Cards & Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between text-xs">
            <h3 className="font-semibold text-[#F5F4F1]">Fargate Reference Workers ({workers.length})</h3>
            <span className="text-[#848B95]">Select any card to inspect demo telemetry</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {workers.map((worker) => {
              const isSelected = activeWorker?.short_id === worker.short_id;
              const isStalled = worker.state === "STALLED";

              return (
                <div
                  key={worker.short_id}
                  onClick={() => handleSelect(worker)} role="button" tabIndex={0} onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleSelect(worker); } } } aria-pressed={isSelected}
                  className={`p-4 rounded-[12px] border cursor-pointer transition-all ${
                    isSelected
                      ? "border-[#D8A955] bg-[#1C1813] shadow-md ring-1 ring-[#D8A955]/20"
                      : isStalled
                      ? "border-[#D8A955]/40 bg-[#161410] hover:border-[#D8A955]"
                      : "border-white/[0.075] bg-[#11161D] hover:border-white/[0.14]"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-2.5">
                      <div
                        className={`w-7 h-7 rounded-md flex items-center justify-center font-mono font-bold text-xs ${
                          isStalled
                            ? "bg-[#D8A955]/15 text-[#D8A955] border border-[#D8A955]/30"
                            : "bg-white/[0.04] text-[#848B95] border border-white/[0.08]"
                        }`}
                      >
                        {isStalled ? <AlertOctagon className="w-4 h-4" /> : <Check className="w-4 h-4 text-emerald-400" />}
                      </div>
                      <div>
                        <span className="font-mono font-bold text-sm text-[#F5F4F1] block">
                          {worker.short_id}
                        </span>
                        <span className="text-[11px] text-[#848B95] font-mono">{worker.ip_address}</span>
                      </div>
                    </div>

                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                        isStalled
                          ? "bg-[#D8A955]/15 text-[#D8A955] border border-[#D8A955]/30"
                          : "bg-white/[0.04] text-[#848B95] border border-white/[0.08]"
                      }`}
                    >
                      {worker.state}
                    </span>
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs border-t border-white/[0.06] pt-2.5">
                    <div>
                      <span className="text-[#848B95] text-[11px] block">Heartbeat Age</span>
                      <span
                        className={`font-mono font-semibold ${
                          worker.heartbeat_age_sec > 120 ? "text-[#D8A955]" : "text-[#F5F4F1]"
                        }`}
                      >
                        {worker.heartbeat_age_sec.toFixed(1)}s
                        {worker.heartbeat_age_sec > 120 && " (STALE)"}
                      </span>
                    </div>
                    <div>
                      <span className="text-[#848B95] text-[11px] block">Items Processed</span>
                      <span className="font-mono font-semibold text-[#F5F4F1]">{worker.processed_count.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="text-[#848B95] text-[11px] block">Task Reservation</span>
                      <span className="font-mono text-[#848B95] text-[11px]">
                        {worker.cpu_reservation} CPU / {worker.memory_limit_mb}MB
                      </span>
                    </div>
                    <div>
                      <span className="text-[#848B95] text-[11px] block">Uptime</span>
                      <span className="font-mono text-[#848B95] text-[11px]">
                        {Math.floor(worker.uptime_sec / 3600)}h {Math.floor((worker.uptime_sec % 3600) / 60)}m
                      </span>
                    </div>
                  </div>

                  {isStalled && (
                    <div className="mt-2.5 p-2 bg-[#D8A955]/10 border border-[#D8A955]/30 rounded text-[11px] text-[#D8A955] flex items-center justify-between">
                      <span>Processing stalled; telemetry remains fresh</span>
                      <span className="font-semibold underline">Incident Attached</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Selected Worker Inspection Panel */}
        <div className="lg:col-span-1">
          {activeWorker ? (
            <div className="bg-[#11161D] rounded-[14px] border border-white/[0.075] p-5 sticky top-24 space-y-4">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                <div className="flex items-center space-x-2">
                  <Cpu className="w-4 h-4 text-[#D8A955]" />
                  <h3 className="text-sm font-semibold text-[#F5F4F1]">Worker Inspection</h3>
                </div>
                <span className="font-mono text-xs font-semibold text-[#D8A955] bg-[#D8A955]/10 border border-[#D8A955]/30 px-2 py-0.5 rounded">
                  {activeWorker.short_id}
                </span>
              </div>

              <div className="space-y-2.5 text-xs">
                <div>
                  <span className="text-[#848B95] block text-[11px]">Task ARN</span>
                  <span className="font-mono text-[11px] text-[#B5B8BD] break-all bg-[#0B0F14] p-2 rounded block border border-white/[0.06]">
                    {activeWorker.task_arn}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-[#161B22] p-2.5 rounded-[8px] border border-white/[0.06]">
                    <span className="text-[#848B95] block text-[11px]">Status</span>
                    <span
                      className={`font-semibold ${
                        activeWorker.state === "STALLED" ? "text-[#D8A955]" : "text-emerald-400"
                      }`}
                    >
                      {activeWorker.state}
                    </span>
                  </div>
                  <div className="bg-[#161B22] p-2.5 rounded-[8px] border border-white/[0.06]">
                    <span className="text-[#848B95] block text-[11px]">Heartbeat Age</span>
                    <span
                      className={`font-mono font-semibold ${
                        activeWorker.heartbeat_age_sec > 120 ? "text-[#D8A955]" : "text-[#F5F4F1]"
                      }`}
                    >
                      {activeWorker.heartbeat_age_sec}s
                    </span>
                  </div>
                </div>

                {activeWorker.last_error && (
                  <div className="p-3 bg-[#D8A955]/10 border border-[#D8A955]/30 rounded-[8px] text-[11px] text-[#D8A955] space-y-1">
                    <span className="font-semibold flex items-center gap-1">
                      <AlertOctagon className="w-3.5 h-3.5" /> Error Condition:
                    </span>
                    <p className="font-mono text-[11px] text-[#D8A955]/90">{activeWorker.last_error}</p>
                  </div>
                )}

                {/* Raw Heartbeat JSON Telemetry */}
                <div className="pt-2">
                  <div className="flex items-center justify-between text-[11px] text-[#848B95] mb-1.5">
                    <span className="font-medium flex items-center gap-1 text-[#B5B8BD]">
                      <Code className="w-3.5 h-3.5 text-[#D8A955]" /> DynamoDB Heartbeat Payload
                    </span>
                    <span className="text-[11px] bg-white/[0.04] text-[#848B95] px-1.5 py-0.2 rounded font-mono border border-white/[0.06]">
                      Simulated
                    </span>
                  </div>
                  <pre className="p-3 bg-[#0B0F14] text-[#B5B8BD] font-mono text-[11px] rounded-[8px] border border-white/[0.06] overflow-x-auto leading-relaxed max-h-48">
{JSON.stringify(
  {
    task_arn: activeWorker.task_arn,
    task_id: activeWorker.short_id,
    timestamp: "2026-11-22T19:42:30Z",
    heartbeat_age_sec: activeWorker.heartbeat_age_sec,
    processed_count: activeWorker.processed_count,
    status: activeWorker.state,
    cluster: activeWorker.cluster_name,
    service: activeWorker.service_name,
    task_family: activeWorker.task_family,
    ip: activeWorker.ip_address,
  },
  null,
  2
)}
                  </pre>
                </div>
              </div>

              {activeWorker.incident_id && (
                <div className="pt-3 border-t border-white/[0.06]">
                  <span className="text-[11px] text-[#848B95] block mb-1">Linked Incident:</span>
                  <div className="p-2.5 bg-[#D8A955]/10 border border-[#D8A955]/30 rounded-[8px] flex items-center justify-between text-xs">
                    <span className="font-mono font-semibold text-[#D8A955]">{activeWorker.incident_id}</span>
                    <button onClick={() => onNavigateToIncident?.(activeWorker.incident_id!)} className="text-[11px] text-[#D8A955] underline font-medium">
                      View incident &rarr;
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-[#11161D] rounded-[14px] border border-white/[0.075] p-8 text-center text-xs text-[#848B95]">
              Select a worker from the fleet to inspect telemetry.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
