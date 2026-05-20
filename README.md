# klone-mcp

A minimal MCP server for UW Hyak (klone). Exposes two tools — `klone_run`
and `klone_put_file` — plus documentation resources covering klone's
filesystem layout, SLURM conventions, and curated shell commands.

Agents already know how to use `squeue`, `sacct`, `sbatch`, `du`, etc.
This MCP doesn't wrap them. It just gives the agent a safe way to run
commands on klone, write files, and find out what klone-specific
utilities exist.

If you want pre-typed wrappers around SLURM (`klone_squeue`, `klone_log`,
`klone_submit`, …) checkout the [`structured-tools`](https://github.com/aurasoph/hyak-mcp/tree/structured-tools) branch.

## Prerequisites

- Python 3.10+
- The [parent `~/klone` SSH setup](../README.md) done (`ssh klone` succeeds without re-prompting Duo)

## Install

```bash
cd ~/klone/klone-mcp
pip install -e .
```

Or with `uv`:

```bash
cd ~/klone/klone-mcp
uv venv && source .venv/bin/activate && uv pip install -e .
```

## Verify it runs

```bash
ssh klone whoami        # must return your NetID — seed the SSH session first
mcp dev klone_mcp/server.py
```

The MCP Inspector opens in a browser tab. Call:

- `klone_run` with `cmd="whoami"` — should return your NetID
- Read resource `klone://docs/quickstart` — should return the storage/safety overview

Kill with Ctrl+C when done.

## Register with Claude Code

```bash
claude mcp add klone -- python -m klone_mcp.server
```

The `--` is required because `claude mcp add` would otherwise try to
parse `-m` as its own flag.

If you installed into a venv, point at that venv's Python:

```bash
claude mcp add klone -- /path/to/.venv/bin/python -m klone_mcp.server
```

Or edit `~/.claude/settings.json` directly:

```json
{
  "mcpServers": {
    "klone": {
      "command": "python",
      "args": ["-m", "klone_mcp.server"]
    }
  }
}
```

## Use it

```bash
claude
```

Inside the session:

> "Run `klone_run` with `whoami`."

Should return your NetID. If Duo expired, you'll get a structured re-auth
prompt — open a terminal, do `ssh klone`, complete Duo, leave that
terminal open, and ask the agent to retry.

## Surface

**Tools:**

| Tool | Purpose |
|------|---------|
| `klone_run(cmd, timeout=60)` | Run any shell command on klone. Returns stdout. |
| `klone_put_file(path, content)` | Write content to a remote path. Content piped via SSH stdin (no ARG_MAX limit). |

**Resources** (read by the agent when relevant; sourced from official Hyak docs):

- `klone://docs/quickstart` — storage hierarchy, SSD-staging performance pattern, Duo behavior, **index of the other resources**
- `klone://docs/commands` — curated klone-specific shell commands (hyakalloc, hyakstorage, squeue, sacct, sbatch, scontrol, sinfo, apptainer, …)
- `klone://help/jobs` — salloc/sbatch usage, partition catalog, arbiter2/login-node rule, pending reasons
- `klone://help/checkpoint` — ckpt partitions: preemption, requeue, requeue intervals
- `klone://help/monitoring` — watch running jobs, diagnose failures, post-mortem
- `klone://help/arrays` — SLURM job arrays + parameter sweeps
- `klone://help/containers` — apptainer best practices
- `klone://help/modules` — LMOD module system
- `klone://help/gpus` — GPU types, partitions, requesting in sbatch, NVIDIA NGC
- `klone://help/python` — miniconda quotas + storage
- `klone://help/r` — R / RStudio (containers, library paths)
- `klone://help/matlab` — MATLAB (module, batch, parallel)
- `klone://help/jupyter` — Jupyter (OOD, sbatch, manual conda)
- `klone://help/ood` — Open OnDemand web portal

Each `klone://help/*` resource carries a `*Reference: https://hyak.uw.edu/...*` link to its source page in the official Hyak docs so users (and agents) can follow up there for depth beyond what the resource summarizes.

## Examples

```python
# Check the queue
klone_run("squeue --me -o '%i|%j|%T|%M|%L'")

# Submit a SLURM job (write the script, then sbatch it)
klone_put_file("/gscratch/scrubbed/me/job.sh", """#!/bin/bash
#SBATCH --account=mygroup
#SBATCH --partition=ckpt-all
#SBATCH --time=01:00:00
#SBATCH --mem=4G
echo hello from klone
sleep 5
""")
klone_run("sbatch /gscratch/scrubbed/me/job.sh")

# Tail a job log
klone_run("scontrol show job 12345678 | grep -E 'StdOut|StdErr'")
klone_run("tail -n 200 /path/to/slurm-12345678.out")
```

## Troubleshooting

**`ModuleNotFoundError: klone_mcp`** — the Python being invoked by Claude
isn't the one you ran `pip install -e .` against. Fix by pointing at the
correct Python via absolute path in your config.

**Tools not appearing in Claude session** — run `claude --debug 2>&1 | head -50`
to see MCP startup logs. Almost always either a wrong `command` path or
the server crashed on import.

**Server crashes on import** — run `python -m klone_mcp.server 2>&1 | head -20`
manually to see the traceback.

**Every call returns Duo expired** — your SSH ControlMaster socket
expired. From any terminal: `ssh klone`, do Duo, leave open. The MCP
shares whatever socket your normal SSH uses.

**`mcp dev` fails with `ImportError: attempted relative import with no known parent package`** — `pip install -e .` didn't run, or against a different Python than `mcp dev`. Verify with `which python` and `which mcp` showing the same prefix.
