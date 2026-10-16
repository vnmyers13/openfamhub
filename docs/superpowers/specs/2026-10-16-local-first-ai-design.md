# Local-First Voice Agent Design

## Intent

Let a signed-in family member speak or type a request to add or edit an event, chore, or to-do without sending household data to a cloud service by default.

## Decisions

- The server talks only to a configured Ollama-compatible endpoint on the LAN.
- The browser supplies speech-to-text through its local browser capability; typed input remains available.
- The model returns a constrained draft action, never executes application writes directly.
- The member reviews and confirms every draft before OpenFamHub invokes the existing authenticated create/update API.
- The endpoint is disabled until an admin configures it. Cloud providers are out of scope.

## Goals

- Draft event, chore, and to-do creates and edits from natural language.
- Preserve existing role, family scoping, date, and validation rules by reusing current APIs.
- Show clear unavailable/error states when the local model cannot be reached.

## Non-goals

- Wake-word listening, background recording, direct Home Assistant control, or autonomous writes.
- Sending family data to a hosted model.

## Constraints

- All model requests require an authenticated user and use their family context only.
- The model endpoint receives the minimal request context needed to produce a draft.
- Existing API routes remain the source of truth for validation and permissions.
