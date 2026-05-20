import sys
import logging
import shlex
import re
import functools
from mcp.server.fastmcp import FastMCP

# Local imports
from klone_mcp.ssh import run_ssh, DuoExpiredError, SSHCommandError
from klone_mcp.slurm import get_squeue, get_sacct

# Initialize FastMCP server
mcp = FastMCP("klone_mcp")

# Configure logging to stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("klone_mcp")


# --- Resources (Documentation) ---

@mcp.resource("klone://docs/quickstart")
def get_quickstart() -> str:
    """Essential knowledge for working on Klone."""
    return """
# Klone (Hyak) Quickstart for AI Agents

## CRITICAL: DATA SAFETY
- **NO BACKUPS:** All data on Klone (including `/gscratch`) is a single copy. 
- **PURGE POLICY:** Files in `/gscratch/scrubbed/` not accessed for 21 days are **permanently deleted**.
- **ACTION:** Always remind the user that they are responsible for backing up important data to external storage.

## STORAGE HIERARCHY
1. **Home ($HOME):** `/mmfs1/home/<netid>/`
   - Limit: **10GB**. Configs and small scripts only. All users have these.
2. **Project (/gscratch):** `/gscratch/<lab>/`
   - High-performance NVMe storage. Use for active research. Ask the user if they have access to any of these.
3. **Scrubbed:** `/gscratch/scrubbed/<netid>/`
   - Community storage. 10TB per-user limit. 21-day auto-purge. All users have these.

## PERFORMANCE — STAGE TO LOCAL SSD
Klone's `/gscratch` is GPFS (network-attached). Reading many small files
from it is **10-100x slower** than local disk. Each compute node has
350GB+ of local NVMe SSD at `/scr` and `/tmp` (per-node, ephemeral).

**For I/O-heavy work** (builds, compilation, thousands of small files,
apptainer container operations): inside your SLURM script, stage data
from `/gscratch` to local SSD at the start, work there, then copy
results back at the end.

```bash
# Inside your SLURM script:
LOCAL=/tmp/$SLURM_JOB_ID
mkdir -p $LOCAL
cp -a /gscratch/lab/me/project $LOCAL/
cd $LOCAL/project
# ... do work, read/write many files ...
cp -a results /gscratch/lab/me/project/
```

Symptoms that mean you should have staged to local SSD: build/extract
phases taking 10x longer than expected, `cp -a` of many small files
through a FUSE mount, `lake exe cache get` slow.

## RUNNING COMPUTE
- **Interactive:** Use `klone_run("salloc ...")` to get a compute node for real-time work/debugging.
- **Batch:** Use `klone_submit` to deploy `.sh` scripts.
- **Discovery:** Run `klone_status` to see which accounts and partitions you can use.

## AUTHENTICATION (DUO)
If a tool raises a DuoExpiredError, you must immediately stop and provide the re-authentication instructions to the human.
"""

@mcp.resource("klone://help/jobs")
def help_jobs() -> str:
    """Guidance on SLURM Job Scheduling (salloc, sbatch, GPUs)."""
    return """
# SLURM Job Scheduling on Klone

- **Interactive (`salloc`):** Use for debugging. 
  `salloc --partition=ckpt-all --cpus-per-task=1 --mem=10G --time=2:00:00`

- **Batch (`sbatch`):** Write a script and submit it using `klone_submit`.
```bash
#!/bin/bash
#SBATCH --job-name=my_job
#SBATCH --partition=compute
#SBATCH --account=my_account
#SBATCH --nodes=1
#SBATCH --mem=10G
#SBATCH --time=04:00:00
#SBATCH -o log/%x_%j.out  # %x=name, %j=jobID
```

- **GPUs:** 
  Find idle GPUs: `sinfo -p ckpt-all -O nodehost,gres,gresused`
  Request GPU: `salloc --partition=ckpt-all --gpus-per-node=a40:1`
"""

@mcp.resource("klone://help/arrays")
def help_arrays() -> str:
    """Guidance on SLURM Job Arrays & Parameter Sweeps."""
    return """
# SLURM Job Arrays & Parameter Sweeps

- **Job Arrays:** Run the same script on many files.
```bash
#SBATCH --array=0-9
FILE_LIST=($(ls -1 data/input_*))
FILE=${FILE_LIST[${SLURM_ARRAY_TASK_ID}]}
python process.py --input ${FILE}
```

- **Parameter Sweeps:** Map one array ID to multiple variables using math.
```bash
#SBATCH --array=0-14 # 5 files * 3 dropouts
FILEINDEX=$((${SLURM_ARRAY_TASK_ID} / 3))
DROPOUT=(0.25 0.5 0.75)
CURRENT_DROPOUT=${DROPOUT[${SLURM_ARRAY_TASK_ID} % 3]}
```
"""

@mcp.resource("klone://help/containers")
def help_containers() -> str:
    """Guidance on Apptainer (Singularity) usage."""
    return """
# Apptainer (Singularity) on Klone

- **Usage:** Hyak uses Apptainer. No sudo required. Must be run on a compute node (via `salloc`), NOT the login node.

- **Commands:**
  - Pull: `apptainer pull docker://python:3.9-slim`
  - Shell: `apptainer shell image.sif`
  - Execute: `apptainer exec --cleanenv --bind /gscratch image.sif python script.py`

- **Best Practice:** The Home dir is only 10GB. Build/pull containers in `/gscratch/` and set `export APPTAINER_CACHEDIR=/scr` to prevent quota errors.
"""

@mcp.resource("klone://help/python")
def help_python() -> str:
    """Guidance on Python & Miniconda best practices."""
    return """
# Python & Miniconda on Klone

- **Critical Risk:** Conda environments create thousands of files. DO NOT store them in `$HOME` (inode limit: 256k).

- **Best Practice:** Configure `.condarc` to put envs/pkgs in `/gscratch/`.
```bash
mkdir -p /gscratch/YOUR_LAB/YOUR_NETID/conda_envs
conda config --add envs_dirs /gscratch/YOUR_LAB/YOUR_NETID/conda_envs
```

- **Using in Scripts:**
  `module load miniconda` (or source your own) -> `conda activate my_env`
"""


@mcp.resource("klone://docs/commands")
def get_commands() -> str:
    """Useful klone-specific shell commands. Call them via klone_run."""
    return """
# Useful Klone-Specific Shell Commands

These aren't dedicated tools — invoke them with `klone_run("...")`. They're
listed here so an agent knows what's available without having to discover
each command by trial and error.

## Discovery / orientation
- `whoami` — your UW NetID
- `hyakalloc` — your accounts and partition access
- `hyakstorage` — quotas for home and gscratch (updated hourly)
- `sshare -U` — your fairshare priority across accounts

## Disk + filesystem
- `df -h /gscratch/lab/me` — disk free for a path
- `du -sh /gscratch/lab/me/project` — directory size (slow for big dirs;
  consider `klone_run("du -sh ...", timeout=300)`)
- `find /path -type f | wc -l` — file count (helpful when inode-limited)

## SLURM (use the typed tools for these where possible)
- `sinfo -o '%20P %.5a %.10l %.12F %G'` — partition availability across cluster
- `sinfo -p ckpt-all -O nodehost,gres,gresused` — find idle GPUs
- `scontrol show job <ID>` — full SLURM job details (logs paths, node, account)
- `scontrol show node <hostname>` — node specs (CPUs, RAM, features)
- `scancel --me` — cancel all your jobs at once
- `sacctmgr show user $USER --parsable2 -n` — your account associations

## Interactive sessions
- `salloc --partition=ckpt-all --cpus-per-task=1 --mem=10G --time=2:00:00` —
  grab a compute node for debugging (no Duo, runs in current SSH session)

## Containers
- `apptainer pull docker://python:3.9-slim` — fetch an image
- `apptainer exec --cleanenv --bind /gscratch image.sif python script.py`
- Always run apptainer on a compute node (via `salloc`), not the login node.

## Modules
- `module avail` — list available modules
- `module load miniconda` — activate miniconda
- `module list` — currently loaded
"""


# --- Tools (Actions) ---

# Helper decorator/wrapper to catch SSH errors and return them gracefully
def handle_ssh_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DuoExpiredError as e:
            # If the function expects a dict, return a dict. Otherwise return a string.
            if func.__annotations__.get('return') == dict or func.__annotations__.get('return') == list[dict]:
                return {"error": "DuoExpiredError", "message": str(e)}
            return str(e)
        except SSHCommandError as e:
            if func.__annotations__.get('return') == dict or func.__annotations__.get('return') == list[dict]:
                return {"error": "SSHCommandError", "message": str(e)}
            return str(e)
        except TimeoutError as e:
            if func.__annotations__.get('return') == dict or func.__annotations__.get('return') == list[dict]:
                return {"error": "TimeoutError", "message": str(e)}
            return str(e)
        except Exception as e:
            if func.__annotations__.get('return') == dict or func.__annotations__.get('return') == list[dict]:
                return {"error": "UnexpectedError", "message": str(e)}
            return f"Unexpected Error: {str(e)}"
    return wrapper

@mcp.tool()
@handle_ssh_errors
def klone_status() -> dict:
    """
    Aggregate status of the user's Klone environment.
    Use this to orient yourself to the user's current jobs, disk quotas, and allocations.
    """
    try:
        allocations = run_ssh("hyakalloc").strip()
    except Exception:
        allocations = "Failed to fetch allocations."

    try:
        storage = run_ssh("hyakstorage").strip()
    except Exception:
        storage = "Failed to fetch storage usage."

    jobs = get_squeue()
    return {
        "jobs": jobs,
        "job_count": len(jobs),
        "allocations": allocations,
        "storage": storage,
    }

@mcp.tool()
@handle_ssh_errors
def klone_run(cmd: str, timeout: int = 60) -> str:
    """
    Run an arbitrary shell command on klone (escape hatch).
    Use for simple commands. Do NOT use for long builds or sbatch submissions.
    """
    return run_ssh(cmd, timeout=timeout)

@mcp.tool()
@handle_ssh_errors
def klone_whoami() -> str:
    """Get the current UW NetID of the user logged into klone."""
    return run_ssh("whoami").strip()

@mcp.tool()
@handle_ssh_errors
def klone_put_file(path: str, content: str) -> str:
    """
    Safely create or overwrite a file on klone with the provided content.

    Content is piped via SSH stdin (not embedded in the command string),
    so files of arbitrary size work — no ARG_MAX limit.
    """
    safe_path = shlex.quote(path)
    return run_ssh(f"cat > {safe_path}", stdin=content)

@mcp.tool()
@handle_ssh_errors
def klone_submit(script_text: str, working_dir: str = None) -> str:
    """
    Submit a SLURM job using sbatch.
    Provide the raw script text (including #SBATCH headers).

    Script is piped via SSH stdin so it works regardless of size.
    """
    if working_dir:
        cmd = f"cd {shlex.quote(working_dir)} && sbatch"
    else:
        cmd = "sbatch"
    return run_ssh(cmd, stdin=script_text).strip()

@mcp.tool()
@handle_ssh_errors
def klone_cancel(job_id: str) -> str:
    """Cancel a SLURM job by ID."""
    return run_ssh(f"scancel {shlex.quote(job_id)}").strip()

@mcp.tool()
@handle_ssh_errors
def klone_log(job_id: str, lines: int = 200) -> dict:
    """
    Auto-discovers and tails the stdout and stderr logs for a given job.
    If the job is still pending, returns a message indicating that.
    """
    safe_id = shlex.quote(job_id)
    try:
        # Info pulls are fast, 30s is generous
        info = run_ssh(f"scontrol show job {safe_id}", timeout=30)
    except DuoExpiredError:
        raise
    except Exception as e:
        return {"error": f"Failed to fetch job info for {job_id}. It may be too old, or invalid.", "details": str(e)}

    # Robust parsing of scontrol key=value output
    m_out = re.search(r"StdOut=(\S+)", info)
    m_err = re.search(r"StdErr=(\S+)", info)
    stdout_path = m_out.group(1) if m_out else None
    stderr_path = m_err.group(1) if m_err else None
        
    result = {"job_id": job_id}
    
    def safe_tail(path):
        try:
            # File reads might hang on bad IO, give it a bit more time
            content = run_ssh(f"tail -n {lines} {shlex.quote(path)}", timeout=120)
            if len(content) > 8000:
                return "...[truncated]...\n" + content[-8000:]
            return content
        except DuoExpiredError:
            raise
        except Exception as e:
            return f"Could not read log: {e}"

    if stdout_path:
        result["stdout_path"] = stdout_path
        result["stdout_tail"] = safe_tail(stdout_path)

    if stderr_path:
        result["stderr_path"] = stderr_path
        result["stderr_tail"] = safe_tail(stderr_path)

    if not stdout_path and not stderr_path:
        result["message"] = "No log paths found. Job may still be pending."

    return result

@mcp.tool()
@handle_ssh_errors
def klone_squeue(user: str = None, state: str = None, partition: str = None) -> list[dict]:
    """List a user's current SLURM jobs on klone.

    Defaults to your own queue (`--me`). Pass `user="netid"` to inspect
    someone else's. Cluster-wide queue is not supported — it's thousands
    of rows that blow up agent context. For overall cluster state, use
    `klone_run("sinfo -o ...")` instead.

    Optional filters:
    - `state`: SLURM state code, e.g. 'R' (running), 'PD' (pending), 'CG' (completing)
    - `partition`: e.g. 'ckpt-all', 'cpu-g2'

    Each returned dict has id, name, state, time, time_left, reason,
    nodes, partition, user.
    """
    return get_squeue(user=user, state=state, partition=partition)

@mcp.tool()
@handle_ssh_errors
def klone_sacct(job_id: str = None, days: int = 1, limit: int = 10) -> list[dict]:
    """
    Check job history. Returns structured JSON data.
    Use 'limit' to control how many recent jobs are returned (defaults to 10) to prevent context bloat.
    """
    return get_sacct(job_id, days, limit)

if __name__ == "__main__":
    mcp.run()
