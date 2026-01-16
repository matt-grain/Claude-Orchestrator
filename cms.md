Anima, let's continue on PR 5 of @docs\UI_LOGIC_SEPARATION_PLAN.md, please:
0. look carefully at the doc, details are there 
1. implement the task
2. add unit / integration tests
3. validate using pyright, ruff and ty
4. apply ruff check --fix and run pytests with coverage
5. update the status table in the plan
6. commit (only)
7. remember the achievement
8. tell me and I'll reset to start on next task


cd /tmp/test-orchestrator && rm -rf notes .debussy/state.db src tests 2>/dev/null && uv add --dev "claude-debussy[ltm] @ file:///C:/Projects/Claude-Orchestrator" && uv run debussy run docs/test-master.md --no-interactive --model haiku