import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { createHash } from "node:crypto";
import { DemoDataProvider } from "@/lib/data-provider";
import { OverviewSection } from "@/components/sections/OverviewSection";
import { DecisionConsoleSection } from "@/components/sections/DecisionConsoleSection";
import { WorkerMonitoringSection } from "@/components/sections/WorkerMonitoringSection";
const provider = new DemoDataProvider();
describe("Demo consistency and security semantics", () => {
  it("shows the same stalled worker, incident IDs and rules in the overview", async () => {
    const [capacity, workers, incidents, receipts, rules] = await Promise.all([provider.getFleetCapacity(),provider.getWorkers(),provider.getIncidents(),provider.getDecisionReceipts(),provider.getSecurityRules()]);
    const selected=vi.fn();
    render(<OverviewSection {...{capacity,workers,incidents,receipts,rules}} onNavigateTab={vi.fn()} onSelectWorker={selected}/>);
    const stalled=workers.find(w=>w.state==="STALLED")!;
    fireEvent.click(screen.getByRole("button",{name:new RegExp(`${stalled.short_id} stalled`)}));
    expect(selected).toHaveBeenCalledWith(stalled.short_id);
    rules.forEach(r=>expect(screen.getByText(r.name)).toBeInTheDocument());
    incidents.forEach(i=>expect(screen.getByText(i.incident_id)).toBeInTheDocument());
    receipts.forEach(r=>expect(incidents.some(i=>i.incident_id===r.incident_id)).toBe(true));
    expect(screen.queryByText("INC-2026-003")).not.toBeInTheDocument();
  });
  it("uses fresh STALLED telemetry instead of approving stale evidence", async () => {
    const target=(await provider.getWorkers()).find(w=>w.state==="STALLED")!;
    expect(target.heartbeat_age_sec).toBeLessThanOrEqual(120);
    expect(target.is_unhealthy).toBe(true);
    expect((await provider.getDecisionReceipts())[0].rule_results.R3_telemetry.message).toMatch(/Fresh/);
  });
  it("never substitutes another incident's receipt", async () => {
    render(<DecisionConsoleSection receipts={await provider.getDecisionReceipts()} activeIncidentId="inc-no-receipt"/>);
    expect(screen.getByText(/No decision recorded/)).toBeInTheDocument();
    expect(screen.queryByText("AUTH_APPROVED")).not.toBeInTheDocument();
  });
  it("navigates from the worker to its linked incident", async () => {
    const nav=vi.fn();
    render(<WorkerMonitoringSection workers={await provider.getWorkers()} capacity={await provider.getFleetCapacity()} selectedWorkerId="task-0001" onNavigateToIncident={nav}/>);
    fireEvent.click(screen.getByRole("button",{name:/View incident/}));
    expect(nav).toHaveBeenCalledWith("inc-00000001");
    expect(screen.getByText("Capacity Check")).toBeInTheDocument();
  });
  it("exports honest demo hashes matching their displayed canonical strings", async () => {
    for(const event of await provider.getAuditEvents()) expect(createHash("sha256").update(event.canonical_string).digest("hex")).toBe(event.sha256_hash);
  });
});
