# Tests

## How to run
- Automated tests: `uv run python -m pytest -q` from the `mini-coding-agent` folder
- Demo: run the agent from the Lab 4 folder (see Demo tests below)

## Automated unit tests

| ID | Area | What it checks | Expected result | Result |
|----|------|----------------|-----------------|--------|
| T1 | Discovery | Skills in `skills/` and `.claude/skills/` are found | Both skills listed | PASS|
| T2 | Discovery | A `SKILL.md` missing name or description is skipped | Skipped, no crash | PASS|
| T3 | Discovery | Same skill name in both folders | `skills/` version wins | PASS|
| T4 | Discovery | Workspace with no skill folders | Agent starts normally, no skills | PASS|
| T5 | Similarity | "Validate the grid environment boundaries" | Picks `validate-environment` | PASS|
| T6 | Similarity | "Write a hello world script" | No skill chosen | PASS|
| T7 | Similarity | Word endings ("validating" vs "validates") | Treated as the same word | PASS|
| T8 | Prompt trigger | Matching prompt with the fake model | Skill text appears under "Active skill" in the prompt | |
| T9 | Tool trigger | `use_skill` with a known name | Returns the skill's instructions | |
| T10 | Tool trigger | `use_skill` with an unknown name | Error listing valid names | |
| T11 | Logging | Prompt-triggered decision | Log line has time, prompt, all scores, threshold, chosen skill, trigger `prompt` | PASS|
| T12 | Logging | Tool-triggered decision | Log line has trigger `tool` and empty scores | PASS|

## Regression tests
| ID | What it checks | Expected result | Result |
|----|----------------|-----------------|--------|
| R1 | All original repo tests | All pass | 18 passed, 1 skipped (baseline)|

## Demo tests (Lab 4, qwen3.5:4b)

### D1: Matching prompt
- **Prompt:** "Validate the grid environment in this repo: check its boundaries and terminal states."
- **Expected:** `validate-environment` is triggered; the agent follows its steps on `src/environment.py`.
- **Actual:** _(fill in)_
- **Log excerpt:** _(paste the log line)_

### D2: Unrelated prompt
- **Prompt:** "Write a hello world script."
- **Expected:** No skill triggered; the log shows all scores below the threshold.
- **Actual:** _(fill in)_
- **Log excerpt:** _(paste the log line)_

## Acceptance criteria checklist
| Criterion (from spec.md) | Verified by |
|--------------------------|-------------|
| Skills in both folders are discovered | T1 |
| A grid-validation prompt triggers `validate-environment` | T5, T8, D1 |
| An unrelated prompt triggers nothing | T6, D2 |
| `use_skill` returns instructions; unknown name returns error | T9, T10 |
| Each decision appears in the log with all fields | T11, T12 |
| Existing agent tests still pass | R1 |
| The agent uses the Lab 5 skill in the Lab 4 repo, and the log shows it | D1 |

## Results summary
_(fill in after testing: what passed, what failed, any threshold changes)_
