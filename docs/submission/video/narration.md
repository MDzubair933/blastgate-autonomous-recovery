# BlastGate demo narration

Offline synthesized narration; no paid service or third-party music.

## 000–007 seconds · intro

BlastGate investigates stalled workers while keeping execution authority outside the model.

## 007–015 seconds · problem

A container can keep running after its application stops making progress. Restarting the wrong worker can make an incident worse.

## 015–027 seconds · architecture-detect

Workers publish application health. The watchdog, CloudWatch alarm and EventBridge route an incident to a dispatcher, which invokes the managed Harness.

## 027–040 seconds · architecture-authority

Amazon Nova Micro reasons inside AgentCore. Gateway and Cedar scope its tools. An independent broker checks eight rules before a scoped ECS task stop.

## 040–052 seconds · dispatch

The recorded unattended run correlates an incident with a dispatch session. The runner did not manually call the Harness or broker, but could accelerate the watchdog.

## 052–065 seconds · authorization

The broker recorded ALLOW with all eight rule flags true. The captured reason field contains the action identifier. We preserve it without inventing a normalized result.

## 065–080 seconds · recovery

The original target stopped. A distinct replacement published healthy telemetry. Cleanup recorded zero desired, running and pending workers. Intermediate timestamps and a complete tool transcript are not retained.

## 080–092 seconds · adversarial

This adversarial request targets an external service. The agent attempts diagnostics and reports that the incident is missing. That is the observed answer, not proof of a reached scope-validation branch.

## 092–105 seconds · guardrail

This request asks for an unapproved infrastructure modification. The saved Harness response is a Guardrail block. Model activity, blocked inputs and model-generated answers remain distinct evidence categories.

## 105–113 seconds · dashboard

The dashboard separates interactive simulated operations from recorded AWS evidence, making each result and its limitations inspectable.

## 113–120 seconds · outro

Independent authorization. A healthy replacement. BlastGate.
