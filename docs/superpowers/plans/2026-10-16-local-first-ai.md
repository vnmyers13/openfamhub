# Local-First AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a confirmed, local-only conversational draft flow for events, chores, and to-dos.

**Architecture:** A backend AI service calls an admin-configured Ollama-compatible LAN endpoint with a strict JSON schema. A new authenticated draft endpoint validates the returned action and returns a reviewable draft; frontend confirmation calls existing domain APIs rather than granting the model write access.

**Tech Stack:** FastAPI, httpx, Pydantic, React, React Query, browser SpeechRecognition where available.

**Spec:** `docs/superpowers/specs/2026-10-16-local-first-ai-design.md`

## Global Constraints

- Local Ollama-compatible endpoint only; no cloud fallback.
- No model-generated write executes without explicit member confirmation.
- Reuse existing permission, family-scope, and date-validation paths.

## Review Focus

- Model output must not cross family boundaries or choose an unauthorized target.
- Invalid or malformed model JSON must become a safe draft error.
- Unreachable model must not break normal app operation.
- Confirmation must use existing API permissions and validation.
- Speech input must remain optional and never record in the background.

### Task 1: Server configuration and safe AI draft contract

**Files:** `backend/app/services/ai.py`, `backend/app/routers/ai.py`, schemas, config, tests.

- [ ] Write failing tests for disabled/unavailable service, malformed model output, and a valid event/chores/to-do draft.
- [ ] Add admin-controlled Ollama URL/model configuration and an authenticated `POST /api/ai/draft` endpoint.
- [ ] Constrain model output to supported action schemas, inject only caller/family context, and return a reviewable draft.
- [ ] Verify backend tests and commit.

### Task 2: Confirmed voice/text draft interface

**Files:** `frontend/src/api/ai.ts`, dashboard/component files, tests.

- [ ] Write failing component tests for text draft, unavailable service, review, confirmation, and optional browser speech entry.
- [ ] Add a modal/panel that sends typed or transcribed text, renders the draft, and calls the existing domain mutation only after confirmation.
- [ ] Verify frontend coverage, lint, and production build; commit.

### Task 3: Documentation and release readiness

- [ ] Document LAN Ollama setup, privacy behavior, and supported utterances.
- [ ] Tick the Phase 12 AI TODO item after all tests pass.
- [ ] Run full backend/frontend suites and release checks.
