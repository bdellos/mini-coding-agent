# Spec

## Overview
- Adds a skills component to `mini_coding_agent.py` that discovers, triggers, executes, and logs skills.

## Scope
**In:** 
- skill discovery
- prompt-based triggering (similarity check)
- a `use_skill` tool for triggering skills mid-task
- logging
- unit tests
- Lab 4 demo

**Out:**
- the agent creating or editing skills
- embedding models or other external libraries
- Q-learning
- changes to unrelated parts of the agent

## Skill format
- One folder per skill, each containing a `SKILL.md` file
- The top of the `SKILL.md` file contains the name and description between `---` lines
- All text following that contains the instructions

## Discovery
- When the agent starts, look in `skills/` and `.claude/skills/` at the workspace root.
- Initially, read only the `name` and `description` and load the full instructions when that skill is chosen for use.
- Skip any folder that does not contain `SKILL.md`
- **Edge cases:**
    - Skip a `SKILL.md` file that does not contain a name or description
    - If two skills share a name, the one in `skills/` trumps `.claude/skills`
- Discovered skills are listed on the agent's welcome screen.

## Prompt-triggered skills (the similarity check)
- Compare the user's prompt to the name and description of each skill using **word overlap**: lowercase everything, split into words, ignore common words such as "the" and "a", then score how many words they share, from 0 to 1. 
    - score = (number of shared words) / (number of unique words in the skill's name and description)
- If the best score is at or above **0.2**, that skill is triggered
- **Only one skill is triggered per prompt**, so if multiple skills are above the threshold, choose the skill with the highest score.
- If every skill's score is below the threshold, do not execute any skills.

## Agent-triggered skills (mid-task)
- A new tool, `use_skill`, lets the agent load a skill on its own during a task.
- This tool takes one argument: `name`, which is the name of the skill to load
- Names and descriptions of all available skills are listed in the agent's instructions, so the agent is aware of which skills exist.
- On success, the tool returns the skill's instructions from its `SKILL.md`
- If the name does not match any skill, the tool returns an error that lists the valid skill names.
- The tool is marked "safe" and does not require approval, it only reads a file.
- Each time `use_skill` is called, it is logged with trigger type `tool`.
- The `use_skill` tool and the Skills list only appear when at least one skill exists.
- Skill names are matched without regard to capitalisation.
- A skill loaded with `use_skill` becomes the Active skill for the rest of the request, replacing any prompt-triggered skill.
- Each skill description in the list is capped at 200 characters.

## Executing a skill
- A skill's instructions are added to the agent's prompt under the heading "Active skill".
- The agent follows the instructions with its existing tools.
- Any risky step (e.g. running a command) requires user approval.
- Instructions are capped at 2,000 characters.
- The active skill is reset at the start of every request.

## Logging
- **Where:** `.mini-coding-agent/skills.log.jsonl`
- **Format:** one line per decision. Each line holds:
    - the time
    - the prompt
    - the score for every skill
    - the threshold
    - the chosen skill (or none)
    - how it was triggered (prompt or tool)
- Additionally, print a one-line summary in the terminal, e.g. `[skill] validate-environment (score 0.42, prompt)`.
- For tool-triggered entries, the prompt is the current user request and scores are left empty.
- `skill_path`: the path of the executed `SKILL.md`, or NULL if no skill was chosen
- `requested`: for tool entries, the skill name the model asked for (recorded even if it does not exist).
- If the workspace has no skills, no decision is logged.

## Constraints
- Run on a small local model (qwen3.5:4b using Ollama)
- Keep the single-file design of `mini_coding_agent.py`

## Acceptance criteria
- [ ] Skills in both folders are discovered.
- [ ] A grid-validation prompt triggers `validate-environment`.
- [ ] An unrelated prompt (e.g. "write a hello world script") triggers nothing.
- [ ] `use_skill` returns the instructions; an unknown name returns an error.
- [ ] Each decision appears in the log with all the fields above.
- [ ] Existing agent tests still pass.
- [ ] The agent uses the Lab 5 skill in the Lab 4 repo, and the log shows it.    