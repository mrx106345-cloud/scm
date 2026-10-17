# Continue Work Guide

This file is the operational checkpoint for all AI agents and contributors working on this project.

Important rules:
- Always read this file first before starting work.
- After every completed item, update this file and the project todo list.
- Before beginning a task, review the project documents in this repository to understand the current requirements and constraints.
- Do not skip ahead to later work unless the current item is fully complete and marked as such.

## Required project references

Read these files before making changes or continuing implementation:
- [plan.md](./plan.md)
- [architecture-plan.md](./architecture-plan.md)
- [prd.md](./prd.md)
- [architecture.md](./architecture.md)
- [api-spec.md](./api-spec.md)
- [tech-stack.md](./tech-stack.md)
- [security-guardrails.md](./security-guardrails.md)
- [DEVELOPMENT_SPEC_scm_agent.md](./DEVELOPMENT_SPEC_scm_agent.md)
- [agents.md](./agents.md)
- [instructions.md](./instructions.md)

If a project requirement conflicts across documents, follow the most restrictive or specific source, and note the conflict here.

## Working instructions for AI agents

1. Read continue.md.
2. Read the current project docs relevant to the task.
3. Update the task status in [todo.md](./todo.md).
4. Start from the next uncompleted step.
5. Complete one discrete unit of work at a time.
6. After each successful item, update:
   - this file's "Current status" section,
   - the matching item in [todo.md](./todo.md),
   - the notes / blockers / next step section.
7. If a task is blocked, record the blocker, the attempted solution, and the exact next action needed.
8. Never claim a task is complete without evidence from a test, validation, or clear repository requirement.

## Project progress workflow

Use this exact process for every round of work:
- Review current status in continue.md.
- Check the next pending item in todo.md.
- Read the related implementation/spec documents.
- Perform the work.
- Validate the result.
- Update continue.md with the result.
- Update todo.md with the new status.

## Current status

Current phase: Phase 3 complete (P3-01 through P3-07 all done)

Last updated: 2026-10-16

Status summary:
- Phase 1 foundation complete + acceptance A1-A3 PASS on 200 and 5000 items; egress test 2/2 green
- Phase 2 LLM explainer + chat complete (all 20+ tests green)
- Phase 3 complete: P3-01 supplier agent, P3-02 logistics agent, P3-03 recommendations, P3-04 approval workflow, P3-05 outbox export, P3-06 notes inbox, P3-07 supplier and item pages + charts
- Backend: 119/119 tests pass; ruff clean; mypy clean
- Frontend: tsc clean; vitest 4/4 green

Active next task: None (Phase 3 complete)

Scope:
- P3-07 Supplier and item pages, charts — DONE (suppliers API, items API, frontend pages with routing)

## Completion log

### Latest update
- Date: 2026-10-16
- Action: P3-07 Supplier and item pages, charts completed. Backend APIs (GET /suppliers, GET /suppliers/{id}, GET /items/{id}) implemented and tested. Frontend pages (SupplierPage, ItemPage) with routing added. Backend 119/119 green, ruff clean, mypy clean, frontend tsc/vitest clean.
- Result: Phase 3 fully complete.
- Next action: Phase 4 deferred (connectors, action agent, autonomy — out of scope). Real auth and model file/license choice deferred, awaiting owner decision.

## Blockers / notes

- No major blockers at this stage.
- Follow the repo specification and security policy exactly.
- Keep work traceable through both continue.md and todo.md.

## Final instruction to future agents

Before starting anything in this project, read all relevant MD files and then check this file. After finishing a single task, update this file and the todo list immediately. Do not continue to the next work item until the previous one is logged as complete.
