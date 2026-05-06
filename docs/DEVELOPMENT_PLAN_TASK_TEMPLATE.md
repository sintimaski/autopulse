# Development Plan and Task Specification Template

Use this template to convert a development goal into executable tasks with clear ownership, validation, and production-safe behavior.

## 1) Plan header

- **Plan name:**
- **Owner:**
- **Date:**
- **Status:** Draft | In Progress | Blocked | Done
- **Scope summary (2-4 lines):**
- **Out of scope:**

## 2) Context / background

- Problem statement:
- Why now:
- Current behavior (as-is):
- Desired behavior (to-be):
- User impact:
- Technical impact:

## 3) Domain rules and constraints

- Product/domain rules:
- Security/privacy rules:
- Performance/SLO constraints:
- Compliance/governance constraints:
- Non-goals:

## 4) Inputs, outputs, and dependencies

- **Inputs:** APIs, schemas, configs, docs, data sources
- **Outputs:** code artifacts, docs, runbooks, migrations, dashboards
- **Dependencies:** internal services, external systems, people approvals
- **Tools available:** IDE, scripts, CI jobs, test suites, deployment tools

## 5) Task breakdown

Copy this task card for each task in the plan.

### Task `<ID>`: `<Task name>`

- **Description:**
- **Priority:** P0 | P1 | P2 | P3
- **Acceptance criteria (AC):**
  - AC1:
  - AC2:
  - AC3:
- **Inputs:**
- **Outputs:**
- **Dependencies:**
- **Constraints:**
- **Tools available:**
- **Steps / plan:**
  1.
  2.
  3.
- **Error handling:**
  - Expected failure modes:
  - Recovery steps:
  - Rollback/backout conditions:
- **Validation / verification:**
  - Automated checks:
  - Manual checks:
  - Observed evidence:
- **Idempotency (re-run safety):**
  - Safe to re-run? Yes | No | Partial
  - If partial/no, guardrails required:
- **State / progress tracking:**
  - Status: Todo | In Progress | Blocked | Done
  - % complete:
  - Last update:
  - Owner:
- **Related documents:**
- **References / examples:**
- **Ambiguity handling:**
  - If requirement is unclear:
  - If data conflicts:
  - Escalation owner:
- **Observability (logs, tracking):**
  - Logs/metrics/traces to add:
  - Alert thresholds:
  - Success signals:

## 6) Plan-level execution strategy

- Delivery sequence:
- Parallelization opportunities:
- Risk register (top 3-5):
- Decision log:
  - Decision:
  - Why:
  - Date:
  - Owner:

## 7) Validation gate before completion

Mark each item before closing the plan:

- [ ] All tasks have explicit AC.
- [ ] All tasks define validation (automated + manual).
- [ ] Idempotency is documented for each task.
- [ ] Domain rules and constraints are mapped to tasks.
- [ ] Observability updates are included where behavior changed.
- [ ] Related docs are updated or explicitly deferred.
- [ ] Remaining ambiguity is logged with owner and due date.
