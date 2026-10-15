---
name: qa-payment
description: End-to-end QA of a payment-method integration (new provider / currency / method) — analysis via qa-payment-agent (method card, MR suspects, lean checklist from the lead's two standing checklists), then a guided multi-session live run on the DEV stand one step at a time with a tracker, synthetic signed webhooks via `workflow pay-hook`, and final deliverables (Jira comment + annotated HTML checklist + lead report). Resumes from the tracker in a fresh session. The prod release run itself is the user's; on request the skill checks prod transactions (the user's and other players') through qa-logs-agent (P6; requires the separate qa-logs agent installed alongside). Use when: "протестируй платёжку", "новый платёжный метод", "qa-payment DEV-XXXX", "интеграция ПМ", "платёжка <провайдер> <валюта>", "продолжи тест платёжки", "сгенери хук", "отчёт по платёжке лиду", "релизная проверка платёжки", "проверь платёжку на проде".
---

# /qa-payment — payment-method testing

The orchestrator runs this skill. `qa-payment-agent` does only the one-shot
analysis (P1); the live run, hooks, tracker and deliverables are done here,
with the user, step by step.

Knowledge: `config/qa-payment/payment-context.md`, `lead-checklists.md`,
`providers/<provider>.md` — read them before P2 if the agent was not run in this
session. Working folder: `tasks/qa/<BE-KEY>/` (`analysis.md`, `checklist-data.json`,
`checklist.html`, `tracker.md`).

**Tracker — always on the Desktop, always complete.** Primary copy:
`~/Desktop/<provider>-<cur>/tracker.md` (lowercase, e.g. `acmepay-usd`);
`tasks/qa/<BE-KEY>/tracker.md` is a symlink to it. Created at the start of
every run, no exceptions — it is the only memory between sessions, so nothing
lives only in chat. Log as it happens, append-only, with UTC time:
- every operation: user id, our id + provider id, amount, method, status, balance;
- every answer from the dev / lead / provider (near-verbatim, who, when) and
  every decision taken on it;
- hypotheses and how they ended (confirmed / dropped, by what evidence);
- messages sent to the provider TG chat / dev, and their replies;
- key-swap flag, open tails, bugs (with evidence);
- the prod release check after P4 continues in the same tracker.
Every stop ends with a «Продолжить отсюда (<date>)» block: exact next step,
open questions, what the user brings.

## Usage

```
/qa-payment PAY-101 [PAY-102]       ← BE and/or FE key; the agent finds the pair
/qa-payment PAY-101                 ← tracker exists → resume
```

## Phases

```
P0 Intake / resume → P1 Analysis (agent) → P2 Live run ⇄ P3 Synthetic hooks
→ P4 Deliverables → P5 Learning
(after release, on request) P6 Release check — prod logs via qa-logs-agent
```

### P0 — Intake / resume

1. Check `workflow` health only if a Jira/GitLab call fails — no upfront ritual.
2. Tracker exists (Desktop folder or the `tasks/qa/<KEY>/` symlink) → read Шапка + Покрытие + Следующий шаг,
   show a 3–5 line status (phase, done/total, **key swapped on DEV?**, next step)
   and continue from «Следующий шаг». Do not re-run P1 unless the user asks or
   the BE MR got new commits that touch the provider package (then offer re-analysis).
3. No tracker → P1.

### P1 — Analysis

```
Agent(subagent_type="qa-payment-agent", prompt="""
Keys: <keys from user>
Working folder: <absolute path>/tasks/qa/<BE-KEY>/
Run the full analysis per your contract. Return the short chat summary.
""")
```

If the agent returned the analysis as text (its `.md` write was refused),
save it to `tasks/qa/<BE-KEY>/analysis.md` yourself; same for an unseeded tracker.
Then move the seeded tracker to `~/Desktop/<provider>-<cur>/tracker.md` and
leave a symlink at `tasks/qa/<BE-KEY>/tracker.md` (`mv` + `ln -s`); the agent
seeds into `tasks/` because a sub-agent can be refused Desktop access.

Validate: `analysis.md` has «Карточка метода», «Подозрения», «Покрытие
чек-листов лида» with every L-ID, `checklist.html` rendered, tracker seeded and on the Desktop.
Missing → resume the same agent with the gap, don't re-launch.

Show the user: method line, TC count, lead coverage x/total, top suspects,
questions for dev, what to arrange before the run (key swap, test users,
commission read-out). Then: **"Начинаем прогон с <first TC>?"** — wait.

If `adapter: no` → before any hook step, write the adapter from the agent's
Signing Spec (infra work, done by the orchestrator directly):
`modules/payhook/adapters/<provider>.py` + test with a throwaway key, register in
`PROVIDERS`, run `python3 -m pytest modules/payhook`. Shared-secret scheme
(MD5/HMAC over a key in our config) → no DEV key swap is needed, skip the swap
steps of P3. Unknown scheme → ask the lead how they want hooks for this
provider before improvising.

### P2 — Live run (one step at a time)

Order = checklist order (FE → deposits → withdrawals → limits → commission →
return URL). For every step:

1. **Announce:** TC + step, expected result, exactly what the user should bring
   (screenshot of status / balance / balance history / admin log entry, ids).
2. **Wait** for the user's facts. Never run ahead with several steps.
3. **Verdict** ✅ / ❌ / ⚠️ / ⏩ against the expected. Judge by status +
   balance + balance history, not by a log entry existing. An error on DEV is
   read (tooltip / error text), never dismissed as "dev noise".
4. **Log** one row to the tracker Журнал (UTC time, ids, expected, fact,
   verdict) and update Покрытие + Следующий шаг. Append-only for Журнал.
5. **❌ on a money path** → stop the sequence, write a bug block in the tracker
   (steps, expected, actual, balance-history evidence, suspected code `file:line`,
   consequence on prod), tell the user; continue only on their call. Retest after
   a fix = new operation, never reuse the failed one.

Rules of the run:
- Suspects from P1 are confirmed or dropped **only** by the stand; record which.
- Withdrawals: balance via admin credit; one pending withdrawal per user →
  sequential; approve in admin first (hook acts only on PROCESSING /
  ERROR_PROCESSING); `payment_id` in the hook = our withdrawal id.
- Limits bypassing the form: ask the user for «Copy as cURL» of the cashier
  request and send it **immediately** (JWT lives minutes); min−1, min, max, max+1.
- Final statuses (success / decline): first ask organically — give the user a
  ready message for the provider TG chat with the transaction id and the wanted
  status; synthetic hook (P3) when the provider doesn't respond, and always for
  negatives / repeats.
- Commission / anything DB-only on DEV: give the user a ready message for the
  developer with the operation ids. Withdrawal fee is filled by a scheduled
  job — ask after it ran.
- Behavior settled in `payment-context.md` §2 «Принципы обработки» or in the
  «Эталоны» blocks is the expected result — never re-ask it. Only behavior with
  no settled expectation → ask the lead/dev, record the answer as settled in the
  tracker (and later P5 — if it is general for all methods, propose it for §2).
- Dev curls from Jira can be used as a shortcut; the TC verdict stays on
  observable state.

### P3 — Synthetic hooks

Used for negatives / repeats (bad signature, repeat final, late opposite
status, unknown operation) and when the provider TG chat doesn't send hooks.

Prerequisite (asymmetric signature only): the dev swapped the verification key
on DEV. Shared-secret providers skip the swap and the flag. Give the user a
ready message for the dev (what to swap to what, why, that real provider hooks
will 400 meanwhile). When confirmed → tracker Шапка `Ключ подменён на DEV: да (<date>)`.

Per hook:
1. `workflow pay-hook <provider> deposit|withdrawal --status=<s> --request-id=<id>
   --payment-id=<id> --amount=<minor> [--initial=<minor>] --ref=<BE source branch>
   [--bad-sig]` — amounts in provider units; show the conversion.
2. Require `# local verify … OK` on stderr (with `--bad-sig` the self-check is
   still OK — the corruption happens after it). FAIL → stop, the key/config is wrong.
3. **Preview** (endpoint, status, ids, amount both units) → wait for «да» → send
   the curl via Bash. pay-hook refuses non-DEV hosts; never work around it.
4. Show HTTP code + body verbatim, then ask the user for the admin-side facts
   (status, balance, balance history) — the HTTP 200 alone is not a verdict.

When the last hook-based TC is done → give the user the "please revert the key"
message for the dev; on confirmation set `Ключ подменён на DEV: нет (<date>)`.
At every resume while the flag is `да`, remind first.

### P4 — Deliverables (when all TCs have a verdict or an explicit skip)

1. **Annotated checklist.** Give the user per-TC comment texts (one block per
   TC, ready to paste into the checklist's comment fields), the user ticks and
   exports «⬇ Скачать с отметками» and attaches the exported file. The real
   detail lives there; the Jira comment stays thin.
2. **Jira comment** on the BE task (and a short one on FE if it was tested
   separately): verdict line, per-TC one-liners with ✅/❌/⏩, bug in its own
   block (or link), the reference to the attached checklist. Format: `##`
   headers, `---` separators, `1️⃣ **TC-01 — …**` anchors; ≤ ~10 000 chars by
   `len()`; write to a file, `workflow jira-comment <KEY> --from-file=<f> --dry-run`,
   show, confirm, real call (`JIRA_WRITE_ENABLED=true`). Attach via
   `workflow jira-attach <KEY> <file> --dry-run` → confirm → real.
   No test-account emails / credentials in Jira.
3. **Lead report** (Artifact, private; user shares): verdict; «что прошу
   подтвердить» block; coverage map L1 + L2 → TC → result (gaps visible, not
   hidden); bug(s) in their own block with balance-history evidence and fix /
   retest status; per-TC tables; method (synthetic hooks, what was organic);
   test data. Settled lead answers shown as settled, not as open questions.
4. Tracker Шапка → `Фаза: P4 ✅`. Ask before any Jira transition.
5. Hand the user the **prod-check memo** — `payment-context.md` §7 (order,
   how to read signals, TG-chat message templates) with the method's placeholders
   pre-filled where known (method, currency, provider). The prod run itself is the user's.

### P5 — Learning

Propose (do not write without «да»):
- `providers/<provider>.md`: create/update the card (endpoints, statuses, codes,
  stand quirks, «Прод» section from the release check, history line with bugs +
  uncovered items).
- `payment-context.md`: new bug class, «Доказано» updates, new stand facts;
  dev answers that hold for **all** methods → §2 «Принципы обработки» (and
  retire matching catalog classes as by-design).
- `lead-checklists.md` → «Эталоны»: answers the lead/dev settled during the run.

### P6 — Release check via prod logs (on request only)

Trigger: the user brings prod transactions after release or asks «проверь на
проде» / «всё ли ок у других юзеров». The user makes the payments and talks to
the provider; the skill reads prod logs. Sub-agents don't spawn sub-agents →
the skill (orchestrator) launches `qa-logs-agent` itself, Grafana default
account = prod. Two modes, either or both:

- **A. Specific transactions** — the user's test payments (admin screenshot /
  ids from the tracker).
- **B. Sweep across players** — all webhooks of this provider since the release
  (or since the last config/key change): response codes, any non-2xx, signature
  errors, decline reasons by count, duplicated finals, stuck intermediates
  (`processing`/`dispute` with no final). The goal is "is it ok for real players",
  not just for our test user.

Build the hand-off from the tracker + `providers/<provider>.md` (prod section):

```python
Agent(subagent_type="qa-logs-agent", prompt="""
Release check of a payment-method integration on PRODUCTION (default Grafana account, no --account flag).
Provider / method / currency: <…>; released: <date/time UTC>; last key/config change: <time UTC or none>.
Mode: <A: ids … (user id, our payment_id, provider request_id, amount, UI time + offset) | B: sweep <window UTC>>.
Expected flow: create request → provider 201/processing → webhook(s) → handler → final status.
Log markers (from providers/<p>.md / qa-logs-context.md): <create / webhook / handler-start / signature-error strings>.
Settled behavior — do not re-derive: <payment-context §2 + §7 lines that apply>.
Questions: <what we want to know — e.g. all callbacks 200? any invalid signature after <time>? decline reasons? duplicate success?>.
For B: aggregate by response/status/reason, list the outliers with ids, compare before/after <change time>.
Then follow your standard Step 0–6 workflow and report format.
""")
```

After the report:
- Log the result to the tracker (window, counts, ids of outliers, verdict).
- Duplicate `success` or a money doubt → offer `qa-database-agent` (prod DB) to
  confirm the balance was credited exactly once — ask first, never auto.
- Provider-side finding (decline reason, stuck status, "not delivered") → draft
  the TG message from `payment-context.md` §7 with the real ids filled in.
- New prod facts → P5 proposals (`providers/<p>.md` → «Прод», `qa-logs-context.md` markers).

## Rules

- One step at a time in P2; the user drives the admin, I drive hooks and reading.
- Nothing lives only in chat: every fact, answer and decision goes to the Desktop tracker the moment it appears.
- No webhook, Jira write or admin action without preview + explicit «да».
- pay-hook output is DEV-only; signing keys are never written to disk or chat
  beyond the curl itself.
- Every lead item ends with a verdict, `n/a (reason)` or an open question —
  report gaps, never drop them.
- The prod release run is the user's (payments, provider chat); the skill only
  hands over the §7 memo (P4 step 5) and, on request, reads prod logs (P6). No
  synthetic hooks to prod — ever.
- Sub-agents don't spawn sub-agents: `qa-payment-agent` never launches anything.

## Fail-fast

- Agent returns `BLOCKED_*` → relay reason + «Needed from user», stop.
- `pay-hook` prints `FAIL` / refuses host → stop hooks, explain, don't bypass.
- Key swap not confirmed → do not send synthetic success/decline hooks
  (they'd 400 and be misread); offer organic flow via the provider TG-chat instead.
