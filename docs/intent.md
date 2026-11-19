# Intent
## Problem
- The current mini coding agent has no skills component. There is no way for the agent to discover skill folders, decide when a skill is applicable, or follow a skill's instructions.

## Goal
- The agent should be able to find skills, trigger the appropriate one to use, and follow its instructions. This may occur from a prompt or if the agent deems it necessary mid-task.  
- Using the new component, log the prompt that triggers the skill, a similarity check between that prompt and all available skills, and the skill that is executed.

## Success criteria
- A prompt about validating the grid triggers `validate-environment`
- An unrelated prompt triggers no skill
- Each decision is written to a log with prompt, scores, and chosen skill
- The agent uses the Lab 5 skill to solve Lab 4

## Constraints
- Run on a small local model (qwen3.5:4b using Ollama)
- Keep the single-file design of `mini_coding_agent.py`

## Demo task (Lab 4)
- Run the upgraded agent in the Lab 4 repository and have it use the Lab 5 validate-environment skill on this grid environment:

|       | Col 0 | Col 1 | Col 2 | Col 3 |
|-------|-------|-------|-------|-------|
| Row 0 | START | 0     | 0     | 0     |
| Row 1 | 0     | X     | 0     | 0     |
| Row 2 | 0     | 0     | 0     | 0     |
| Row 3 | 0     | -1    | 0     | 10    |

- Assumptions: "X" indicates a fail state, numbers indicate the reward for that space.