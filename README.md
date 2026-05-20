# klone-mcp

MCP server for UW Hyak (klone) cluster. Exposes klone as typed tools so
agents can submit jobs, tail logs, and check status without burning tokens
on parsing `squeue` output by hand.

Pairs with the [klone SSH setup](../README.md) — this MCP rides on top of
your existing `ssh klone` ControlMaster.

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

`pip install -e .` puts `klone_mcp` on `sys.path` so the MCP server is
importable from anywhere. Editable mode means changes to the source take
effect without reinstalling.

## Verify it runs

Make sure your SSH session is alive (run `ssh klone whoami` and confirm
it returns your NetID). Then test the MCP server itself:

```bash
mcp dev klone_mcp/server.py
```

This opens the MCP Inspector in a browser tab. You can call each tool
manually:

- `klone_whoami` should return your NetID
- `klone_squeue` should return your current jobs as structured JSON
- `klone_status` should return jobs + recent history + allocations + disk

Kill with Ctrl+C when done.

## Register with Claude Code

Two options.

### Option A: CLI

```bash
claude mcp add klone -- python -m klone_mcp.server
```

The `--` is required because `claude mcp add` would otherwise try to
parse `-m` as its own flag.

If you installed into a venv (not the system Python), point at that
venv's Python explicitly:

```bash
claude mcp add klone -- /path/to/.venv/bin/python -m klone_mcp.server
```

Verify:

```bash
claude mcp list
```

You should see `klone` in the output.

### Option B: settings file

Edit `~/.claude/settings.json` (or a project's `.claude/settings.json`
for project-only scope):

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

If you're in a venv, replace `"python"` with the absolute path to that
venv's python (find it with `which python` after activating).

## Use it

Start Claude Code from any directory:

```bash
claude
```

Then in the session:

> "What klone tools do you have access to?"

You should see `klone_whoami`, `klone_squeue`, `klone_sacct`,
`klone_status`, `klone_log`, `klone_submit`, `klone_cancel`,
`klone_put_file`, `klone_run`.

Try a sanity check:

> "Run `klone_whoami` and `klone_status`."

If both return clean data, you're set. If Duo expired, you'll get a
structured re-auth prompt — open a terminal, do `ssh klone`, complete
Duo, leave that terminal open, and ask the agent to retry.

## Tools at a glance

| Tool | Purpose |
|------|---------|
| `klone_status` | One-shot orientation: jobs + allocations + storage |
| `klone_squeue` | Current jobs as `list[dict]` |
| `klone_sacct` | Job history as `list[dict]` (failed jobs, exit codes, runtime) |
| `klone_log` | Auto-discover stdout/stderr paths for a job and tail them |
| `klone_submit` | Submit a SLURM job from script text |
| `klone_cancel` | scancel a job by ID |
| `klone_put_file` | Safely write content to a remote path (base64-encoded for content, shlex-quoted path) |
| `klone_run` | Escape hatch for arbitrary shell commands |
| `klone_whoami` | NetID sanity check |

Things like `df`, `du`, `sinfo`, `hyakalloc`, `scontrol` aren't separate
tools — the agent invokes them via `klone_run`. See
`klone://docs/commands` for the curated list.

Resources:

- `klone://docs/quickstart` — performance + storage + auth orientation
- `klone://docs/commands` — useful klone-specific shell commands (call via `klone_run`)
- `klone://help/jobs` — salloc/sbatch usage
- `klone://help/arrays` — SLURM job arrays + parameter sweeps
- `klone://help/containers` — apptainer best practices
- `klone://help/python` — miniconda quotas + storage

## Troubleshooting

**`ModuleNotFoundError: klone_mcp`** — the Python being invoked by Claude
isn't the one you ran `pip install -e .` against. Fix by pointing at the
correct Python via absolute path in your config (Option B).

**Tools not appearing in Claude session** — run `claude --debug 2>&1 | head -50`
to see MCP startup logs. Almost always either a wrong `command` path or
the server crashed on import.

**Server crashes on import** — run `python -m klone_mcp.server 2>&1 | head -20`
manually to see the traceback.

**Every tool returns Duo expired** — your SSH ControlMaster socket
expired. From any terminal: `ssh klone`, do Duo, leave open. The MCP
shares whatever socket your normal SSH uses.

**`mcp dev` fails with `ImportError: attempted relative import with no known parent package`** — `pip install -e .` didn't run, or it ran against a different Python than the one `mcp dev` is using. Verify with `which python` and `which mcp` showing the same prefix.

## Validation

See [TODO.md](TODO.md) for a layered test plan (smoke tests, security/injection
tests, Duo expiry handling, full submit/cancel workflow, agent-level
workflow tests).
