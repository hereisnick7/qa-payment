# QA HTML checklist

The `qa-payment` checklist is delivered as an interactive HTML file
(`<details>` cards per TC, live checkboxes with `localStorage` progress,
P0/P1/P2/BLOCKED filters, a free-text comment field per TC).

## Template + fill script

`.claude/skills/qa-payment/assets/qa-checklist-template.html` holds the
CSS/JS; it is never regenerated or hand-edited. `fill_checklist.py` (same
folder) extracts its `<style>`/`<script>` blocks and stamps the data from
`checklist-data.json` into the placeholder sections. The agent only writes the
JSON — that keeps its output proportional to the test content, not to ~26 KB
of markup.

```bash
python3 .claude/skills/qa-payment/assets/fill_checklist.py \
  --data tasks/qa/<KEY>/checklist-data.json \
  --output tasks/qa/<KEY>/checklist.html
```

The script verifies balanced `<details>` tags and that no `{{placeholder}}` is
left, and exits non-zero otherwise — fix the JSON, never the template.
Self-tests: `python3 -m pytest .claude/skills/qa-payment/assets/tests -v`.

**Checkbox/comment state is localStorage-only until exported.** Ticks and
comments live in the browser, keyed per task; they never travel with the file.
The «⬇ Скачать с отметками» button bakes the current state into the markup and
downloads a self-contained copy — that exported file is what gets attached to
the tracker / read back, not the originally generated one.

### Data schema (`checklist-data.json`)

Required top-level: `task_key`, `title`, `checklist`. Everything else optional
(omit a key or pass an empty list — the corresponding section is dropped, e.g.
no `blockers`/`open_questions`/`dev_po_questions` at all removes the whole
Блокеры section).

```json
{
  "task_key": "PAY-101",
  "title": "короткое название задачи",
  "sub_meta": "MR backend!512 · собрано 2026-09-15",
  "summary_rows": [["Test Cases", "12 (P0: 5, P1: 4, P2: 3)"]],
  "summary_key_point": "одна мысль, что меняет план",
  "checklist": {
    "code_touches": "...", "essence": "...",
    "items": [{"text": "...", "note": "← подозреваемый баг (optional)"}]
  },
  "blockers": ["что и почему"],
  "open_questions": ["вопрос, не тест-кейс"],
  "dev_po_questions": [{"who": "Dev", "text": "...", "ref": "TC-03"}],
  "test_cases": [{
    "id": "TC-01", "type": "Positive", "title": "...",
    "priority": "P0", "blocked": "false", "blocked_reason": "(if blocked/partial)",
    "ac_ref": "...", "category": "...", "covers": "[FACT] file.py:88 — ...",
    "intro": "...", "accounts": ["..."], "preconditions": ["..."],
    "steps": [{"action": "...", "expected": "...", "note": "(optional)"}],
    "where": "...", "cleanup": "..."
  }],
  "scenarios": [{
    "id": "SC-01", "title": "...", "priority": "P0", "blocked": "false",
    "ac_ref": "...", "category": "...", "shared": "общий таймер/стенд",
    "intro": "...",
    "instances": [{"label": "A", "path": "...", "desc": "...", "covers": "..."}],
    "steps": [{"tags": ["A", "B"], "action": "...", "expected": "...", "note": "(optional)"}],
    "where": "...", "cleanup": "..."
  }],
  "appendices": [{"title": "...", "content": "..."}],
  "sources": "analysis.md, MR ...",
  "jira_note": "если Jira не трогалась — сказать явно"
}
```

`type` for a TC is free text (`Positive`/`Negative`/`RBAC`/`API` per Step 10's
own format) — only `Positive`/`Negative`/`Regression` get a colored badge from
the template's CSS today; `RBAC`/`API` render as a plain badge (cosmetic gap,
not a rendering error — extend `.badge.*` in the template's `<style>` if this
needs closing later).

## Delivery to the tracker

Jira comments do not render arbitrary HTML — attach the exported file
(`workflow jira-attach <KEY> <file> --dry-run` → confirm → real call, requires
`JIRA_WRITE_ENABLED=true`). The Jira comment itself stays thin; the detail
lives in the annotated checklist.
