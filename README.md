# klone-mcp (structured-tools branch)

Same setup as [main](https://github.com/aurasoph/hyak-mcp/tree/main) (install,
SSH config, Claude registration, resources). Difference: this branch
ships seven additional typed tools that wrap SLURM and inspection
commands so the agent doesn't have to parse text output.

Use this branch if you're building agent workflows that submit and
monitor many jobs and want structured `list[dict]` returns. Relatively experimental. 

## Tools

| Tool | Purpose |
|------|---------|
| `klone_run(cmd, timeout=60)` | Run any shell command. Returns stdout. *(also on main)* |
| `klone_put_file(path, content)` | Write content via SSH stdin (no ARG_MAX limit). *(also on main)* |
| `klone_whoami()` | Returns your NetID. Trivial — useful as a connection probe. |
| `klone_status()` | Aggregated dict: your jobs, accounts/allocations, storage quotas. One call instead of three. |
| `klone_squeue(user=None, state=None, partition=None)` | Your current jobs as `list[dict]`. Filter by state (`R`/`PD`/`CG`), partition, or another user's NetID. Cluster-wide is intentionally not supported — use `klone_run("sinfo ...")` for that. |
| `klone_sacct(job_id=None, days=1, limit=10)` | Job history as `list[dict]`. Capped at 10 by default to prevent context bloat — bump `limit` for more. |
| `klone_log(job_id, lines=200)` | Auto-discovers `StdOut`/`StdErr` paths via `scontrol show job` and tails both. Returns 8 KB-capped per stream so context doesn't blow up. |
| `klone_submit(script_text, working_dir=None)` | sbatch a script. Script is piped via SSH stdin (no ARG_MAX limit on script size). Returns "Submitted batch job <ID>". |
| `klone_cancel(job_id)` | scancel by job ID. |