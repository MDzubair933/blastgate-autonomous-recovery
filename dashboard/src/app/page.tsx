"use client";



import React, { useState, useEffect } from "react";

import { TopHeader } from "@/components/layout/TopHeader";

import { Sidebar } from "@/components/layout/Sidebar";

import { TabId } from "@/types";



// Sections

import { RecordedEvidenceSection } from "@/components/sections/RecordedEvidenceSection";
import { OverviewSection } from "@/components/sections/OverviewSection";

import { WorkerMonitoringSection } from "@/components/sections/WorkerMonitoringSection";

import { IncidentSection } from "@/components/sections/IncidentSection";

import { DecisionConsoleSection } from "@/components/sections/DecisionConsoleSection";

import { SecurityRulesSection } from "@/components/sections/SecurityRulesSection";

import { AdversarialSection } from "@/components/sections/AdversarialSection";

import { AuditExplorerSection } from "@/components/sections/AuditExplorerSection";

import { DeploymentCostSection } from "@/components/sections/DeploymentCostSection";



// Data Provider & Types

import { defaultDataProvider } from "@/lib/data-provider";

import {

  WorkerRecord,

  IncidentRecord,

  DecisionReceipt,

  SecurityRule,

  AdversarialScenario,

  AuditEvent,

  FleetCapacity,

  DeploymentCostStatus,

} from "@/types";



export default function DashboardPage() {

  const [recorded, setRecorded] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [activeTab, recorded]);



  const [loadError, setLoadError] = useState(false);

  // Telemetry & Records State

  const [capacity, setCapacity] = useState<FleetCapacity | null>(null);

  const [workers, setWorkers] = useState<WorkerRecord[]>([]);

  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);

  const [receipts, setReceipts] = useState<DecisionReceipt[]>([]);

  const [rules, setRules] = useState<SecurityRule[]>([]);

  const [adversarialScenarios, setAdversarialScenarios] = useState<AdversarialScenario[]>([]);

  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);

  const [costStatus, setCostStatus] = useState<DeploymentCostStatus | null>(null);



  // Active selection state

  const [selectedIncidentId, setSelectedIncidentId] = useState<string>("inc-00000001");

  const [selectedWorkerId, setSelectedWorkerId] = useState<string>("task-0001");



  // Load deterministic contract data

  useEffect(() => {

    async function loadData() {

      try {

      const [cap, wrks, incs, rcpts, rls, adv, evts, cst] = await Promise.all([

        defaultDataProvider.getFleetCapacity(), defaultDataProvider.getWorkers(), defaultDataProvider.getIncidents(), defaultDataProvider.getDecisionReceipts(), defaultDataProvider.getSecurityRules(), defaultDataProvider.getAdversarialScenarios(), defaultDataProvider.getAuditEvents(), defaultDataProvider.getDeploymentCostStatus()

      ]);

      setCapacity(cap);

      setWorkers(wrks);

      setIncidents(incs);

      setReceipts(rcpts);

      setRules(rls);

      setAdversarialScenarios(adv);

      setAuditEvents(evts);

      setCostStatus(cst);

      } catch { setLoadError(true); }

    }

    loadData();

  }, []);



  const handleNavigateToDecision = (incidentId: string) => {

    setSelectedIncidentId(incidentId);

    setActiveTab("decision-console");

  };



  const openIncidentCount = incidents.filter((i) => i.status === "OPEN").length;



  return (

    <div className="min-h-screen bg-[#0B0F14] text-[#F5F4F1] flex flex-col font-sans">

      <a className="skip-link" href="#main-content">Skip to dashboard</a>

      {/* 1. Sleek Dark Global Top Header */}

      <TopHeader

        recorded={recorded}
        isMobileMenuOpen={isMobileMenuOpen}

        onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}

      />



      {/* 2. Main Body with Fixed Sidebar & Operations Canvas */}

      <div className="flex-1 flex">

        {/* Left Navigation Sidebar */}

        <Sidebar recorded={recorded}

          activeTab={activeTab}

          onSelectTab={(tab) => { setRecorded(false); setActiveTab(tab); }}

          openIncidentCount={openIncidentCount}

          isMobileOpen={isMobileMenuOpen}

          onCloseMobile={() => setIsMobileMenuOpen(false)}

        />



        {/* Right Main Operations Canvas */}

        <main id="main-content" tabIndex={-1} className="flex-1 lg:ml-[240px] p-4 sm:p-6 lg:p-7 max-w-[1700px] min-w-0 w-full min-h-[calc(100vh-72px)]">

          <div className="quiet-tabs mb-6" role="group" aria-label="Evidence mode">
            <button aria-pressed={!recorded} onClick={()=>setRecorded(false)}>Simulated operations</button>
            <button aria-pressed={recorded} onClick={()=>setRecorded(true)}>Recorded AWS evidence</button>
          </div>
          {recorded ? <RecordedEvidenceSection/> : <>
          {loadError && <div role="alert" className="panel p-6">Unable to load demo records. <button className="text-link" onClick={() => window.location.reload()}>Reload dashboard</button></div>}

          {!capacity && !loadError && <p role="status" className="p-6 text-[#B5B8BD]">Loading dashboard records…</p>}

          {activeTab === "overview" && capacity && (

            <OverviewSection

              capacity={capacity}

              workers={workers}

              incidents={incidents}

              receipts={receipts}

              rules={rules}

              onNavigateTab={(tabId) => setActiveTab(tabId as TabId)}

              onSelectWorker={(wId) => {

                setSelectedWorkerId(wId);

                setActiveTab("workers");

              }}

              onSelectIncident={(incId) => {

                setSelectedIncidentId(incId);

                setActiveTab("incidents");

              }}

            />

          )}



          {activeTab === "workers" && capacity && (

            <WorkerMonitoringSection

              workers={workers}

              capacity={capacity}

              onNavigateToIncident={(id) => { setSelectedIncidentId(id); setActiveTab("incidents"); }}

              selectedWorkerId={selectedWorkerId}

              onSelectWorker={(w) => {

                if (w) setSelectedWorkerId(w.short_id);

              }}

            />

          )}



          {activeTab === "incidents" && (

            <IncidentSection

              incidents={incidents}

              selectedIncidentId={selectedIncidentId}

              onSelectIncident={(inc) => {

                if (inc) setSelectedIncidentId(inc.incident_id);

              }}

              onNavigateToDecision={handleNavigateToDecision}

            />

          )}



          {activeTab === "decision-console" && (

            <DecisionConsoleSection

              receipts={receipts}

              activeIncidentId={selectedIncidentId}

            />

          )}



          {activeTab === "security-rules" && (

            <SecurityRulesSection rules={rules} />

          )}



          {activeTab === "adversarial" && (

            <AdversarialSection scenarios={adversarialScenarios} />

          )}



          {activeTab === "audit-explorer" && (

            <AuditExplorerSection auditEvents={auditEvents} />

          )}



          {activeTab === "deployment-cost" && costStatus && (

            <DeploymentCostSection status={costStatus} />

          )}

          </>}
        </main>

      </div>

    </div>

  );

}

