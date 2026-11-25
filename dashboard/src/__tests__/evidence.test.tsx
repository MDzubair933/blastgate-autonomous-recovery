import React from "react";
import {describe,it,expect} from "vitest";
import {render,screen,fireEvent} from "@testing-library/react";
import DashboardPage from "@/app/page";
import {RecordedEvidenceSection} from "@/components/sections/RecordedEvidenceSection";
import evidence from "@/data/recorded-evidence.json";
describe("Recorded evidence provenance",()=>{
 it("preserves Scenario 4's earlier live denial without claiming live quorum execution",()=>{
  render(<RecordedEvidenceSection/>);
  expect(screen.getByText(/Scenario 4 establishes local quorum refusal/)).toBeVisible();
  expect(screen.getByText(/no live broker quorum-branch denial/)).not.toBeVisible();
  fireEvent.click(screen.getByText("SCENARIO-4"));
  expect(screen.getByText(/no live broker quorum-branch denial/)).toBeVisible();
  fireEvent.click(screen.getByText("Sources, correlation & limitations"));
  expect(screen.getByText(/runner can invoke the watchdog/)).toBeVisible();
  expect(evidence.unattended.captured_reason_code).toBe("REPLACE_UNHEALTHY_ECS_WORKER");
 });
 it("switches mode without replacing demo data with fabricated live telemetry",async()=>{
  render(<DashboardPage/>);
  fireEvent.click(screen.getByRole("button",{name:"Recorded AWS evidence"}));
  expect(await screen.findByRole("heading",{name:/A healthy replacement/})).toBeInTheDocument();
  expect(screen.getByText("Recorded AWS Evidence")).toBeInTheDocument();
  expect(screen.getByRole("button",{name:"Overview",exact:true})).not.toHaveAttribute("aria-current");
  expect(screen.queryByText("Healthy worker share")).not.toBeInTheDocument();
 });
 it("omits deployment endpoints and uses explicit correlated aliases",()=>{
  const text=JSON.stringify(evidence);
  expect(text).not.toMatch(/arn:aws:|https:\/\/.*amazonaws\.com|AROA[A-Z0-9]{16}/);
  expect(evidence.unattended.incident_alias).toBe("incident-unattended-01");
  expect(evidence.unattended.distinct_replacement).toBe(true);
  expect(evidence.unattended.cleanup.ecs_running_count).toBe(0);
 });
});
