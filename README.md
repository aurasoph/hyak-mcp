# klone-mcp

A minimal MCP server for UW Hyak (klone). Exposes two tools —
`klone_run` (any shell command) and `klone_compute` (run commands on a
named, reusable compute allocation) — plus documentation resources
covering klone's filesystem layout, SLURM conventions, and curated shell
commands.

Agents already know how to use `squeue`, `sacct`, `sbatch`, `du`, etc.,
and they know bash (heredocs to write files, pipes, etc). This MCP
doesn't wrap any of it. It just gives the agent a convenient way to run
commands on klone and find out what klone-specific utilities exist.

The SSH host can be overridden via the `KLONE_SSH_HOST` env var
(default: `klone`). Useful for alternate aliases, a test cluster, or
parallel configs.

If you want pre-typed wrappers around SLURM (`klone_squeue`, `klone_log`,
`klone_submit`, …) checkout the [`structured-tools`](https://github.com/aurasoph/hyak-mcp/tree/structured-tools) branch.

## Prerequisites

- Python 3.10+
- A working SSH alias `klone` on your machine. Add this block to `~/.ssh/config` if you don't have it (replace `YOUR_UWNETID`):

  ```
  Host klone
      HostName klone.hyak.uw.edu
      User YOUR_UWNETID
      ControlMaster auto
      ControlPath ~/.ssh/cm-%r@%h:%p
      ControlPersist 10h
      ServerAliveInterval 60
  ```

  Then run `ssh klone` once, complete the Duo push, and leave the
  terminal open. The persistent connection means `ssh klone <cmd>` from
  any other terminal won't re-prompt for the next 10 hours. The MCP
  reuses this same connection.

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
```
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

## Tools

| Tool | Purpose |
|------|---------|
| `klone_run(cmd, timeout=60, stdin=None)` | Run any shell command on klone. Returns stdout + (on success) stderr, capped at 1 MB per stream. Pipe large content via `stdin=`. |
| `klone_compute(name, cmd, salloc_args=..., timeout=120)` | Run `cmd` on a named, reusable salloc allocation. First call allocates; subsequent calls with the same name reuse the same node and share it via `srun --overlap`. Release with `klone_run("scancel -n <name>")` or let walltime expire. |

Things like `df`, `du`, `sinfo`, `hyakalloc`, `scontrol`, `squeue`, `sacct`, `sbatch` are not separate tools — invoke them via `klone_run`. See the `klone://docs/commands` resource for a curated list. To write a file, use a heredoc or `stdin=`: `klone_run("cat > /tmp/x", stdin=body)`.
