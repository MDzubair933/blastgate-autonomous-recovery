import React from "react";

import { describe, it, expect, beforeEach, vi } from "vitest";

import { render, screen, fireEvent, waitFor } from "@testing-library/react";



// Components

import DashboardPage from "@/app/page";

import { TopHeader } from "@/components/layout/TopHeader";

import { Sidebar } from "@/components/layout/Sidebar";

import { WorkerMonitoringSection } from "@/components/sections/WorkerMonitoringSection";

import { IncidentSection } from "@/components/sections/IncidentSection";

import { DecisionConsoleSection } from "@/components/sections/DecisionConsoleSection";

import { SecurityRulesSection } from "@/components/sections/SecurityRulesSection";

import { AdversarialSection } from "@/components/sections/AdversarialSection";

import { AuditExplorerSection } from "@/components/sections/AuditExplorerSection";

import { DeploymentCostSection } from "@/components/sections/DeploymentCostSection";



// Fixtures

import { DemoDataProvider } from "@/lib/data-provider";



const provider = new DemoDataProvider();



describe("BlastGate Evidence Dashboard Test Suite", () => {

  let capacity: any;

  let workers: any;

  let incidents: any;

  let receipts: any;

  let rules: any;

  let scenarios: any;

  let auditEvents: any;

  let costStatus: any;



  beforeEach(async () => {

    capacity = await provider.getFleetCapacity();

    workers = await provider.getWorkers();

    incidents = await provider.getIncidents();

    receipts = await provider.getDecisionReceipts();

    rules = await provider.getSecurityRules();

    scenarios = await provider.getAdversarialScenarios();

    auditEvents = await provider.getAuditEvents();

    costStatus = await provider.getDeploymentCostStatus();

  });



  describe("1. TopHeader & Sidebar Layout", () => {

    it("renders the top header with brand identity, hackathon label, and simulation badge", () => {

      render(<TopHeader />);

      expect(screen.getAllByText("BlastGate").length).toBeGreaterThanOrEqual(1);

      expect(screen.getByText("AWS Startup Hackathon")).toBeInTheDocument();

      expect(screen.getByText("Simulated Data")).toBeInTheDocument();

      expect(screen.queryByText(/AWS Deployment:/i)).not.toBeInTheDocument();

    });



    it("renders sidebar with all 8 operational views and incident badge", () => {

      const onSelect = vi.fn();

      render(<Sidebar activeTab="overview" onSelectTab={onSelect} openIncidentCount={1} />);



      expect(screen.getByText("Overview")).toBeInTheDocument();

      expect(screen.getByText("Workers")).toBeInTheDocument();

      expect(screen.getByText("Incidents")).toBeInTheDocument();

      expect(screen.getByText("Agent Console")).toBeInTheDocument();

      expect(screen.getByText("Security Rules")).toBeInTheDocument();

      expect(screen.getByText("Adversarial Tests")).toBeInTheDocument();

      expect(screen.getByText("Audit Explorer")).toBeInTheDocument();

      expect(screen.getByText("Deployment")).toBeInTheDocument();



      // Check incident badge count

      expect(screen.getByText("1")).toBeInTheDocument();



      // Click tab

      fireEvent.click(screen.getByText("Workers"));

      expect(onSelect).toHaveBeenCalledWith("workers");

    });

  });



  describe("2. ECS Worker Fleet Monitoring (Section B)", () => {

    it("displays the 6 reference workers and calculates quorum capacity", () => {

      render(<WorkerMonitoringSection workers={workers} capacity={capacity} />);

      expect(screen.getByText(/ECS Worker Fleet Telemetry/i)).toBeInTheDocument();



      // Check all 6 workers exist

      expect(screen.getAllByText("task-0001").length).toBeGreaterThanOrEqual(1);

      expect(screen.getAllByText("task-0002").length).toBeGreaterThanOrEqual(1);

      expect(screen.getAllByText("task-0003").length).toBeGreaterThanOrEqual(1);

      expect(screen.getAllByText("task-0004").length).toBeGreaterThanOrEqual(1);

      expect(screen.getAllByText("task-0005").length).toBeGreaterThanOrEqual(1);

      expect(screen.getAllByText("task-0006").length).toBeGreaterThanOrEqual(1);



      // Health state verification

      expect(screen.getAllByText("STALLED").length).toBeGreaterThanOrEqual(1);

      expect(screen.getAllByText("HEALTHY").length).toBeGreaterThanOrEqual(5);



      // Quorum invariant check

      expect(screen.getByText(/Quorum Active: 5 of 6 Healthy/i)).toBeInTheDocument();

    });



    it("displays raw telemetry JSON when a worker is selected", () => {

      render(<WorkerMonitoringSection workers={workers} capacity={capacity} selectedWorkerId="task-0001" />);

      expect(screen.getByText("Worker Inspection")).toBeInTheDocument();

      expect(screen.getByText(/DynamoDB Heartbeat Payload/i)).toBeInTheDocument();

      expect(screen.getByText(/WORKER_STALL_DETECTED/i)).toBeInTheDocument();

    });

  });



  describe("3. Incident Investigation & Untrusted Boundaries (Section C)", () => {

    it("renders incidents and enforces untrusted log boundaries", () => {

      render(<IncidentSection incidents={incidents} />);

      expect(screen.getByText(/Incident Investigation & Log Boundaries/i)).toBeInTheDocument();

      expect(screen.getAllByText("inc-00000001").length).toBeGreaterThanOrEqual(1);

      expect(screen.getByText(/IS_UNTRUSTED_DATA = TRUE/i)).toBeInTheDocument();

      expect(screen.getByText(/Log Ingestion Boundary/i)).toBeInTheDocument();

      expect(screen.getByText("RB-ECS-001")).toBeInTheDocument();

    });



    it("filters incidents by status correctly", () => {

      render(<IncidentSection incidents={incidents} />);

      const resolvedBtn = screen.getByRole("button", { name: "RESOLVED" });

      fireEvent.click(resolvedBtn);

      expect(screen.getAllByText("inc-00000002").length).toBeGreaterThanOrEqual(1);

      expect(screen.queryByText("inc-00000001")).not.toBeInTheDocument();

    });

  });



  describe("4. Agent Decision Console & 8-Step Lifecycle (Section D)", () => {

    it("distinguishes authorization gate (Step 6) from sovereign execution (Step 7)", () => {

      render(<DecisionConsoleSection receipts={receipts} activeIncidentId="inc-00000001" />);

      expect(screen.getByRole("heading", {name:/The agent proposes/i})).toBeInTheDocument();

      expect(screen.getAllByText(/AUTH GATE/i).length).toBeGreaterThanOrEqual(1);

      expect(screen.getAllByText(/MUTATION/i).length).toBeGreaterThanOrEqual(1);



      // Verify receipt summary

      expect(screen.getByText("AUTH_APPROVED")).toBeInTheDocument();

      expect(screen.getByText("sim-broker-cf49e18b-contract")).not.toBeVisible();
      fireEvent.click(screen.getByText("Receipt metadata & boundary"));
      expect(screen.getByText("sim-broker-cf49e18b-contract")).toBeVisible();
      expect(screen.getByText("Raw decision receipt JSON").closest("details")).not.toHaveAttribute("open");

    });



    it("inspects adversarial refusal receipt with Rule R3 rejection", () => {

      render(<DecisionConsoleSection receipts={receipts} activeIncidentId="inc-00000011" />);

      const denyTab = screen.getByText("dec-00000002");

      fireEvent.click(denyTab);

      expect(screen.getByText("ERR_TARGET_NOT_UNHEALTHY")).toBeInTheDocument();

      expect(screen.getByText("SIMULATED_REFUSAL")).toBeInTheDocument();

    });

  });



  describe("5. Security Enforcement Panel (Section E)", () => {

    it("displays all 8 rules (R1 to R8) with plain language meanings", () => {

      render(<SecurityRulesSection rules={rules} />);

      expect(screen.getByText(/Security Enforcement Panel \(Rules R1–R8\)/i)).toBeInTheDocument();

      expect(screen.getByText("8 operational rules · canonical definitions")).toBeInTheDocument();



      // Check R1 to R8 IDs exist

      ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"].forEach((ruleId) => {

        expect(screen.getByText(ruleId)).toBeInTheDocument();

      });



      // Check plain meaning is visible

      expect(screen.getAllByText(/The agent can only request task replacements/i).length).toBeGreaterThanOrEqual(1);

    });

  });



  describe("6. Adversarial Robustness & Jailbreak Evidence (Section F)", () => {

    it("displays separate Model and Infrastructure verdicts across all scenarios", () => {

      render(<AdversarialSection scenarios={scenarios} />);

      expect(screen.getByText(/Hostile proposals/i)).toBeInTheDocument();



      // Verify Model verdict vs Infrastructure verdict

      expect(screen.getAllByText("Fixture model response").length).toBeGreaterThan(0);

      expect(screen.getAllByText("Simulated Broker Invariant").length).toBeGreaterThan(0);



      // Verify ADV-006 is truthfully marked NOT TESTED

      expect(screen.getAllByText("NOT TESTED").length).toBeGreaterThanOrEqual(1);



      // Expand ADV-006 to inspect payload and live status

      const adv006Header = screen.getByText("ADV-006");

      fireEvent.click(adv006Header);

      expect(screen.getByText("NOT TESTED IN CLOUD")).toBeVisible();
      expect(screen.getByText("ADV-001").closest("details")).not.toHaveAttribute("open");

    });

  });



  describe("7. Audit Evidence Explorer & SHA-256 Hashes (Section G)", () => {

    it("renders cryptographic hash chain and append-only notice", () => {

      render(<AuditExplorerSection auditEvents={auditEvents} />);

      expect(screen.getByText(/Audit Evidence Explorer & Hash Chaining/i)).toBeInTheDocument();

      expect(screen.getByText(/Integrity & Audit Scope/i)).toBeInTheDocument();



      // Verify SHA-256 hashes are displayed

      expect(screen.getAllByText(auditEvents[0].sha256_hash).length).toBeGreaterThanOrEqual(1);

      expect(screen.getByText(/Export Audit JSON/i)).toBeInTheDocument();

    });

  });



  describe("8. Deployment & Cost Status", () => {
    it("shows timestamped recorded cleanup and avoids fabricated billing", () => {
      render(<DeploymentCostSection status={costStatus}/>);
      expect(screen.getByText(/Historical deployment record/)).toBeInTheDocument();
      expect(screen.getByText(/Not measured/)).toBeInTheDocument();
      expect(screen.queryByText(/AWAITING HUMAN BOOTSTRAP/)).not.toBeInTheDocument();
    });
  });

  describe("9. Full Dashboard Integration & Navigation", () => {

    it("renders the entire app and switches between tabs", async () => {

      render(<DashboardPage />);

      expect(screen.getAllByText("BlastGate").length).toBeGreaterThanOrEqual(1);



      // Initial tab is Overview

      await waitFor(() => {

        expect(screen.getByRole("heading", { name: /Autonomous recovery/i })).toBeInTheDocument();

      });



      // Switch to Workers tab

      const workersTab = screen.getByRole("button", { name: /Workers/i });

      fireEvent.click(workersTab);

      await waitFor(() => {

        expect(screen.getByText(/ECS Worker Fleet Telemetry/i)).toBeInTheDocument();

      });



      // Switch to Security Rules tab

      const rulesTab = screen.getByRole("button", { name: /Security Rules/i });

      fireEvent.click(rulesTab);

      await waitFor(() => {

        expect(screen.getByText(/Security Enforcement Panel \(Rules R1–R8\)/i)).toBeInTheDocument();

      });

    });

  });

});

