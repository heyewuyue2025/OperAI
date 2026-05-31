# OperAI Archive OS Redesign Design

Date: 2026-05-31

## Goal

Rebuild OperAI from a plain demo site and Streamlit form into a distinctive product experience: **OperAI Archive OS**, an operations intelligence archive where every task becomes a traceable dossier.

The redesign covers the static frontend, all Agent pages, the Streamlit workbench, and any backend/API/storage changes needed to support the new product model.

## Product Metaphor

OperAI is not presented as a generic AI tool collection. It is a research archive for operations teams.

Core concepts:

- **Task File**: an operations assignment, containing raw material, pack choice, platforms, DAG, and title.
- **Agent Index**: the ten Agent capabilities as searchable research instruments.
- **Run Dossier**: one execution record, with status, steps, generated outputs, timing, and fallback markers.
- **Evidence Chain**: trace from raw input to metrics, insights, drafts, scheduling, validation, and export readiness.
- **Export Vault**: final Markdown/Docx artifacts presented as archived deliverables.

## Aesthetic Direction

Primary direction: **Research Archive**.

Blend three substyles:

- **Dossier Room** for brand surfaces: paper, black rules, case numbers, stamps, annotated file cards.
- **Research Index** for workbench structure: table-like rows, indexes, ledgers, clear navigation and metadata.
- **Evidence Lab** for trace and validation surfaces: dark panels, scan lines, node states, technical proof.

The static pages should feel editorial and memorable. The workbench should feel powerful, dense, and usable.

## Motion Direction

Motion should be visibly technical and expressive, not merely quiet polish.

Motion language: **scan -> assemble -> stamp -> trace**.

Required motion patterns:

- Page load: dossier layers slide in, metadata appears first, titles assemble, red scan line passes through.
- Scroll: paper layer parallax, index lines extend, Agent rows stagger into view.
- Mouse movement: scanning cursor field, subtle card tilt, border light follows pointer, background grid drift.
- Agent/run states: D/C/N nodes light in sequence, evidence chain scans, Verify Gate stamps success/failure.
- Export: artifact moves into vault state with a visible status transition.

Constraints:

- Do not animate input text while the user types.
- Do not cover important content with effects.
- Add `prefers-reduced-motion` fallbacks.
- Keep effects CSS/vanilla JS where possible; no heavy frontend framework unless the existing project changes require it.

## Information Architecture

### Static Frontend

Replace the current long marketing page with an archive entrance:

1. Hero: `OperAI Archive OS`, case number, one-line value proposition, primary action to open the workbench.
2. Archive Overview: Task Files, Agent Index, Run Dossiers, Evidence Chain, Export Vault.
3. Agent Index: ten Agents as archive entries, not marketing cards.
4. Evidence Model: show D/C/N and Verify Gate as a traceable chain.
5. Deployment/API section: present FastAPI, Webhook, Pack, Mock/LLM mode as system capabilities.

### Agent Pages

Each Agent page becomes an **Agent File**:

- Agent code and title.
- Tier/status stamp.
- Role in archive system.
- Inputs accepted.
- Outputs produced.
- Validation rules.
- Example dossier excerpt.
- Related upstream/downstream Agents.
- CTA to open the workbench with that Agent context when feasible.

All ten pages share one visual grammar but may vary accent metadata and example content.

### Streamlit Workbench

Rebuild the workbench around archive navigation:

- **Task File**: raw input, title, platforms, pack/DAG, run button.
- **Agent Index**: select a single Agent or inspect all ten Agent capabilities.
- **Run Dossier**: latest run outputs, step status, duration, fallback warnings.
- **Evidence Chain**: extracted metrics, evidence spans, validation issues, sensitive scan, JSONL trace summary.
- **Export Vault**: Markdown/Docx export, edited copy support, archive status.
- **Settings**: Mock/LLM, model split, temperature, short output, skip review, sensitive words.

Existing functionality should be preserved unless intentionally replaced by the archive model.

## Visual System

### Palette

- Paper: warm parchment base.
- Ink: near-black for primary text and hard rules.
- Archive brown: borders, secondary text, aging surfaces.
- Vermilion red: commands, stamps, risk, Verify Gate, scan line.
- Evidence black: trace panels and technical surfaces.

Avoid generic purple/blue AI gradients and one-note SaaS palettes.

### Typography

- Display headings: Chinese serif/Song style fallback stack.
- Body: readable Chinese sans stack.
- Metadata: monospace for case numbers, run IDs, statuses, timestamps, logs.

No negative letter spacing. Do not scale font size directly with viewport width beyond controlled clamps for hero headings.

### Components

Create reusable CSS classes for:

- Archive navigation.
- File card.
- Index row.
- Dossier panel.
- Stamp.
- Evidence strip.
- Ledger table.
- Trace node.
- Vault action.
- Scan cursor and motion layers.

Avoid nested card stacks. Cards should feel like file surfaces, not floating SaaS panels.

## Backend/Data Changes Allowed

Backend changes are allowed if they help the new product model.

Acceptable changes:

- Add helper functions to query recent runs, tasks, artifacts, and trace summaries for Streamlit.
- Add lightweight view models for Task File, Run Dossier, Evidence Chain, and Export Vault.
- Extend API responses with archive-oriented metadata.
- Add migrations only when needed and keep them idempotent.
- Add tests for any new data transformation or schema behavior.

Avoid unnecessary rewrites:

- Do not replace SQLite unless required.
- Do not replace Streamlit unless explicitly chosen later.
- Do not remove Mock mode; it remains valuable for local operation.

## Implementation Scope

Primary files expected to change:

- `frontend/tokens.css`
- `frontend/styles.css`
- `frontend/main.js`
- `frontend/index.html`
- `frontend/*-agent.html`
- `frontend/streamlit-theme.css`
- `app.py`

Likely backend/support files:

- `src/storage/db.py`
- `src/orchestrator.py`
- `src/export_campaign.py`
- `src/run_compare.py`
- possible new `src/archive_view.py`
- tests under `tests/`

## Testing And Verification

Required verification:

- Run Python tests in Mock mode.
- Start or at least syntax-check Streamlit code paths.
- Open static frontend in a browser and inspect desktop/mobile layouts.
- Verify text does not overflow buttons, navigation, cards, or narrow mobile widths.
- Verify motion does not block reading or form input.
- Verify workbench can still run at least one Mock Agent/run path.
- Verify export paths still work if touched.

Visual verification:

- Desktop homepage.
- Mobile homepage.
- At least one Agent page.
- Streamlit workbench primary Task File screen.
- Run Dossier/Evidence Chain state after a Mock run if feasible.

## Success Criteria

The redesign succeeds when:

- The first viewport no longer feels like a generic SaaS demo or competition deck.
- The product metaphor is obvious within seconds: archive, dossiers, evidence, traceability.
- Static frontend and Streamlit workbench feel like one product system.
- Motion is memorable and technical without damaging usability.
- Existing core capabilities still work: Agent invocation, Mock mode, logs, artifacts, export, settings.
- Tests pass or any remaining failures are clearly explained.

