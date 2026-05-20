import sys
import logging
import shlex
import functools
from mcp.server.fastmcp import FastMCP

from klone_mcp.ssh import run_ssh, DuoExpiredError, SSHCommandError

mcp = FastMCP("klone_mcp")

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
This MCP exposes a single tool, `klone_run`, that runs any shell command
on klone. You have all of bash and the klone-specific utilities listed
in `klone://docs/commands` available.

- **Interactive:** `klone_run("salloc --partition=ckpt-all --cpus-per-task=1 --mem=10G --time=2:00:00")`
- **Batch submit:** Use `klone_put_file` to write the script, then `klone_run("sbatch /path/to/script.sh")`.
- **Discovery:** `klone_run("hyakalloc")` for accounts, `klone_run("hyakstorage")` for quotas.

## AUTHENTICATION (DUO)
If a tool raises a DuoExpiredError, you must immediately stop and provide
the re-authentication instructions to the human. The error message
itself contains the instructions to surface.

## OTHER RESOURCES AVAILABLE
Topic-specific resources you can read on demand:
- `klone://docs/commands` — useful klone-specific shell commands
- `klone://help/jobs` — sbatch / salloc / GPU requests + partition catalog + pending reasons
- `klone://help/checkpoint` — ckpt partitions: preemption, requeue, when to use
- `klone://help/monitoring` — watch running jobs, diagnose failures, post-mortem
- `klone://help/arrays` — SLURM job arrays + parameter sweeps
- `klone://help/containers` — apptainer
- `klone://help/modules` — LMOD module system
- `klone://help/gpus` — GPU partitions, types, requesting, NVIDIA NGC
- `klone://help/python` — Python + miniconda quotas/storage
- `klone://help/r` — R + RStudio (containers, library paths)
- `klone://help/matlab` — MATLAB (module, batch, parallel)
- `klone://help/jupyter` — Jupyter (OOD, sbatch, manual conda)
- `klone://help/ood` — Open OnDemand web portal

## OFFICIAL DOCS
- Hyak docs root: https://hyak.uw.edu/docs/
- Storage optimization (the SSD-staging pattern above):
  https://hyak.uw.edu/blog/klone-users-storage-optimizations/
- Storage layout & quotas: https://hyak.uw.edu/docs/storage/
- Account setup: https://hyak.uw.edu/docs/setup/intracluster-keys/

## TUTORIAL CURRICULA
For learning klone end-to-end (read these once if you're new to klone or SLURM):
- Linux basics: https://hyak.uw.edu/docs/hyak101/basics/syllabus
- SLURM basics: https://hyak.uw.edu/docs/hyak101/basics/syllabus_slurm
- SLURM advanced: https://hyak.uw.edu/docs/hyak101/basics/syllabus_advanced
- Containers: https://hyak.uw.edu/docs/hyak101/containers/syllabus
- Jupyter: https://hyak.uw.edu/docs/hyak101/python/syllabus
"""


@mcp.resource("klone://docs/commands")
def get_commands() -> str:
    """Useful klone-specific shell commands. Call them via klone_run."""
    return """
# Useful Klone-Specific Shell Commands

Invoke these with `klone_run("...")`. The agent already knows standard
Linux commands; this list covers klone-specific tools and conventions.

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

## SLURM
- `squeue --me -o '%i|%j|%T|%M|%L|%R|%N|%P'` — your jobs in parseable form
- `squeue -u <netid> -t R` — running jobs for a specific user
- `sacct -X -P -n --format=JobID,JobName,State,ExitCode,Elapsed -S now-1day` — recent job history
- `sacct -j <id> -X -P -n --format=JobID,State,ExitCode,MaxRSS,Elapsed` — one job's details
- `scontrol show job <id>` — full job info (log paths, node, account)
- `scancel <id>` — cancel a job
- `scancel --me` — cancel all your jobs
- `sinfo -o '%20P %.5a %.10l %.12F %G'` — partition availability
- `sinfo -p ckpt-all -O nodehost,gres,gresused` — find idle GPUs

## Reading job logs
- `scontrol show job <id> | grep -E 'StdOut|StdErr'` — find log paths
- `tail -n 200 /path/to/slurm-NNN.out` — get recent output
- Logs only exist after a job starts; pending jobs have no log paths yet.

## Interactive sessions
- `salloc --partition=ckpt-all --cpus-per-task=1 --mem=10G --time=2:00:00` —
  grab a compute node for debugging.

## Containers
- `apptainer pull docker://python:3.9-slim` — fetch an image
- `apptainer exec --cleanenv --bind /gscratch image.sif python script.py`
- Always run apptainer on a compute node (via `salloc`), not the login node.

## Modules
- `module avail` — list available modules
- `module load miniconda` — activate miniconda
- `module list` — currently loaded
"""


@mcp.resource("klone://help/jobs")
def help_jobs() -> str:
    """Guidance on SLURM Job Scheduling (salloc, sbatch, GPUs)."""
    return """
# SLURM Job Scheduling on Klone

- **Interactive (`salloc`):** Use for debugging.
  `salloc --partition=ckpt-all --cpus-per-task=1 --mem=10G --time=2:00:00`

- **Batch (`sbatch`):** Write a script via `klone_put_file`, then submit.
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
Then: `klone_run("sbatch /path/to/job.sh")`

- **GPUs:**
  Find idle GPUs: `sinfo -p ckpt-all -O nodehost,gres,gresused`
  Request GPU: `salloc --partition=ckpt-all --gpus-per-node=a40:1`

## See also
- `klone://help/checkpoint` — when to use ckpt partitions vs your own account's
- `klone://help/monitoring` — diagnose why a job failed (OOM? walltime?
  preempted?), read `sacct`/`sstat` properly
- `klone://help/arrays` — submit many similar jobs at once
- `klone://help/gpus` — GPU partitions, the `--gpus` flag, NVIDIA NGC

## Partition catalog (typical)
- `compute` — standard CPU partition, 40 cores/node
- `compute-bigmem`, `compute-hugemem`, `compute-ultramem` — high-RAM nodes
- `gpu-a100`, `gpu-a40`, `gpu-l40`, `gpu-l40s`, `gpu-p100`, `gpu-rtx6k`,
  `gpu-2080ti`, `gpu-titan` — GPU partitions, access depends on your group
- `ckpt`, `ckpt-g2`, `ckpt-all` — checkpoint (preemptible) across groups.
  See `klone://help/checkpoint` for the trade-offs.
- `<partition>-int` — interactive variants used for salloc on some partitions.
- Use `hyakalloc` to see which your account can use.

## Login node rule (don't ignore this)
Never run heavy compute on login nodes. Klone monitors with **arbiter2**
which throttles or kills runaway processes. Login is for: editing
files, submitting jobs, light data transfer, and very small queries
(< a few seconds). For anything else, get a compute node with `salloc`
or submit via `sbatch`.

## A few SLURM flags worth knowing
- `--ntasks-per-node N` — for MPI / multiprocess; must match what your
  code actually starts.
- `--time DD-HH:MM:SS` or `HH:MM:SS` — accepts either format.
- `--mail-type=END,FAIL --mail-user=netid@uw.edu` — get emails on
  job-completion / failure.

## Why a job sits in PENDING
The `reason` field of `squeue` tells you. Common ones:
- `Resources` — waiting for the requested resources to free up
- `Priority` — higher-fairshare jobs are queued ahead of yours
- `QOSGrpCpuLimit` / `QOSMaxJobs...` — your group's QOS quota is full
- `AssocGrpCpuLimit` — your individual quota is full
- `ReqNodeNotAvail` — the partition is in a maintenance window; pick
  a shorter `--time` to slot before maintenance or wait

## References
- https://hyak.uw.edu/docs/hyak101/basics/jobs — concise jobs intro
- https://hyak.uw.edu/docs/compute/scheduling-jobs — partitions, fairshare, pending reasons
- https://hyak.uw.edu/docs/hyak101/basics/syllabus_slurm — beginner
  SLURM tutorial (accounts, partitions, ckpt, GPU requests, queue monitoring)
- https://hyak.uw.edu/docs/hyak101/basics/syllabus_advanced — advanced
  SLURM tutorial (interactive vs batch, parallelism, parameter sweep)
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

## See also
- `klone://help/jobs` — sbatch/salloc fundamentals, partition catalog
- `klone://help/monitoring` — collect array-job results, find which task failed

## References
- https://hyak.uw.edu/docs/hyak101/basics/nn_sweep — neural-network
  parameter sweep walkthrough
- https://hyak.uw.edu/docs/hyak101/basics/syllabus_advanced — advanced
  SLURM tutorial that covers parameter sweeps in depth
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

## See also
- `klone://help/gpus` — for GPU work, see the NVIDIA NGC section; you must
  pass `--nv` to apptainer to access host GPUs from inside the container
- `klone://help/modules` — modules vs containers tradeoff (containers are
  the Hyak-recommended default for new software)
- `klone://help/r`, `klone://help/jupyter` — container-based R/Jupyter setups

*Reference: https://hyak.uw.edu/docs/hyak101/containers/background*
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

## See also
- `klone://help/containers` — for ML stacks (PyTorch, TF), apptainer is
  often simpler than conda; see also NGC images in `klone://help/gpus`
- `klone://help/jupyter` — three ways to get a notebook running

*Reference: https://hyak.uw.edu/docs/tools/python*
"""


@mcp.resource("klone://help/r")
def help_r() -> str:
    """R and RStudio on klone."""
    return """
# R and RStudio on Klone

## Loading R
- **Preferred: apptainer containers** from rocker project
  - `apptainer pull docker://rocker/r-base` (base R)
  - `apptainer pull docker://rocker/tidyverse` (with ggplot2, dplyr, etc.)
  - `apptainer pull docker://rocker/rstudio` (for the IDE)
- Legacy `module load r` exists but is unsupported; containers are the way.

## Installing packages (avoid quota disaster)
The 10 GB home directory + 256k inode limit makes default R package
install paths a footgun. Redirect to gscratch:

```bash
mkdir -p /gscratch/scrubbed/YOUR_NETID/R/4.4.0
echo 'R_LIBS="/gscratch/scrubbed/YOUR_NETID/R/4.4.0/"' >> ~/.Renviron
```

Use versioned subdirs (`R/4.4.0/`, `R/4.5.0/`) so packages don't collide
across R versions. When running R via container, bind gscratch:

```bash
apptainer run --bind /gscratch r-base.sif R
```

## RStudio
- Either via Open OnDemand (`klone://help/ood`) — easiest
- Or via `sbatch rstudio-server.job` then SSH-tunnel to `localhost:8787`.
  Credentials are generated per-session in the job output file.

## Gotchas
- **Don't `apptainer pull` on the login node** — use `salloc` first; pulls
  are I/O-heavy and slow down logins for everyone.
- **Always `--bind /gscratch`** when running an R container, otherwise it
  can't see your data or library path.

## See also
- `klone://help/containers` — general apptainer setup (the rocker pulls
  use the same patterns)
- `klone://help/ood` — RStudio launch via Open OnDemand is usually
  simpler than the sbatch-tunnel dance

*Reference: https://hyak.uw.edu/docs/tools/r*
"""


@mcp.resource("klone://help/matlab")
def help_matlab() -> str:
    """MATLAB on klone."""
    return """
# MATLAB on Klone

## Loading
- `module load matlab` (current version: R2023b / 23.2.0.2365128)
- UW institutional license — no extra setup needed once module is loaded.

## Running
- **Batch / non-interactive:**
  `matlab -nodisplay -batch "your_function(args)"`
  Embed in an sbatch script with `#SBATCH --cpus-per-task=N` etc.
- **Interactive (CLI):** SSH with `-Y` for X11, then `matlab -nodisplay`
- **GUI:** via Open OnDemand → MATLAB app (`klone://help/ood`)

## Example sbatch
```bash
#!/bin/bash
#SBATCH --account=YOUR_ACCOUNT
#SBATCH --partition=ckpt-all
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=02:00:00

module load matlab
matlab -nodisplay -batch "addpath('/gscratch/lab/me/code'); my_analysis"
```

## Parallel MATLAB
- `parpool` works; size it to your SLURM allocation (`--cpus-per-task`).
- Don't request more workers than you allocated CPUs.

## Gotchas
- Forgetting `-nodisplay` on a non-X11 session will hang.
- License-server contention shows up as "license checkout failed";
  retrying after a few minutes usually fixes it.

## See also
- `klone://help/modules` — `module load matlab` is how MATLAB enters scope
- `klone://help/ood` — for the GUI version, use Open OnDemand

*Reference: https://hyak.uw.edu/docs/tools/matlab*
"""


@mcp.resource("klone://help/jupyter")
def help_jupyter() -> str:
    """Jupyter notebooks on klone."""
    return """
# Jupyter on Klone

Three ways to get a notebook running. In order of recommended:

## 1. Open OnDemand (easiest)
https://ondemand.hyak.uw.edu/ → launch Jupyter from the Interactive Apps menu.
Handles compute node allocation and port forwarding for you. Best for
exploratory work.

## 2. Container-based sbatch job
```bash
wget https://hyak.uw.edu/files/jupyter-server.job
# Edit JUPYTER_CWD (working dir) and JUPYTER_SIF (container path)
sbatch jupyter-server.job
```
Pre-built containers at `/sw/ondemand/containers/jupyter/sifs/`.
The job's stdout will print the SSH tunnel command and the URL+token to
hit from your laptop.

## 3. Manual conda
```bash
salloc -A YOUR_ACCOUNT -p ckpt-all --time=4:00:00 --mem=10G -c 4
module load miniconda
conda create -n jupyter-notebook -c conda-forge notebook
conda activate jupyter-notebook
jupyter notebook password
# Pick a port between 4096 and 16384:
jupyter notebook --port 8888 --ip 0.0.0.0 --no-browser
```
Then from your laptop: `ssh -L 8888:nXXXX:8888 klone` (nXXXX = compute node hostname).

## Notes
- Notebook ports must be in [4096, 16384].
- OOD persists best across disconnects; sbatch is next; manual conda is
  fragile if your SSH drops.
- Don't run notebooks on the login node.

## See also
- `klone://help/ood` — the recommended path for interactive notebooks
- `klone://help/python` — managing conda envs without blowing home quota
- `klone://help/containers` — pre-built notebook containers at `/sw/ondemand/containers/jupyter/sifs/`

*Reference: https://hyak.uw.edu/docs/tools/jupyter*
"""


@mcp.resource("klone://help/modules")
def help_modules() -> str:
    """LMOD module system on klone."""
    return """
# Modules (LMOD) on Klone

Klone uses LMOD (TACC's enhanced Lua-based module system) to expose
pre-installed software. Use modules on **compute nodes** (allocated via
`salloc` or in sbatch scripts), not the login node — module commands
will warn or no-op there.

## Commands
- `module avail` — list available modules
- `module list` — show currently loaded
- `module load <name>` — load
- `module unload <name>` — unload
- `module purge` — unload everything
- `module spider <name>` — search for modules by name/prefix

## What's available
- Compilers: `gcc`, `g++`, `gfortran`, Intel equivalents
- MPI libraries
- Language runtimes: `matlab`, `miniconda` (Python), legacy `r`
- Community / lab-contributed modules — prefixed by group name and shown
  in a lower section of `module avail`

## Personal / lab modules
- Load a personal modulefile path: `module use /path/to/modulefiles`
- Lab convention: shared modules in `/sw/contrib/<lab>-src` with
  modulefiles at `/sw/contrib/modulefiles/<lab>`

## Modules vs apptainer containers
The Hyak team prefers **apptainer** for new software because containers
are portable and reproducible across versions. Use modules for:
- Compiler toolchains where module-loaded MPI is needed
- Pre-installed Hyak-maintained software (MATLAB, miniconda)
- Lab-contributed software your group has packaged

For everything else (custom Python/R/conda envs, ML frameworks), use
apptainer (`klone://help/containers`).

## See also
- `klone://help/containers` — apptainer setup (the Hyak-recommended default)
- `klone://help/matlab` — `module load matlab` is the standard path for MATLAB

*Reference: https://hyak.uw.edu/docs/tools/modules*
"""


@mcp.resource("klone://help/gpus")
def help_gpus() -> str:
    """GPU partitions and SBATCH on klone."""
    return """
# GPUs on Klone

## Available GPU types
| GPU | Memory | Partition examples |
|-----|--------|---------------------|
| L40 / L40s | 48 GB GDDR6 | account-specific |
| A40 | 48 GB GDDR6 | various |
| RTX 6000 | 48 GB GDDR6 | gpu-rtx6k |
| 2080 Ti | 11 GB GDDR6 | various |
| Titan | 24 GB GDDR6 | various |
| A100 | 40 GB HBM2 | account-specific |
| P100 | 16 GB HBM2 | older |

## Requesting GPUs

**Checkpoint (preemptible, no account needed):**
```bash
salloc --partition=ckpt-all --gpus-per-node=2080ti:1 --mem=10G --time=2:00:00
```

**Reserved partition (your account):**
```bash
salloc --account=YOUR_ACCOUNT --partition=gpu-rtx6k --gpus=1 --mem=10G --time=2:00:00
```

In sbatch scripts:
```
#SBATCH --gpus=a40:2          # 2 A40 GPUs
#SBATCH --gpus-per-node=1     # 1 GPU per node
```

## Finding idle GPUs
```bash
sinfo -p ckpt-all -O nodehost,cpusstate,freemem,gres,gresused -S nodehost | grep -v null
```

## NVIDIA NGC containers
NVIDIA's container registry has pre-built, GPU-optimized images for
PyTorch, TensorFlow, RAPIDS, CUDA, HPC SDK, etc. On klone, pull and run
via apptainer:

```bash
# pull (do this on a compute node via salloc; pulls are heavy)
apptainer pull docker://nvcr.io/nvidia/pytorch:24.01-py3

# run with GPU access — note the --nv flag is REQUIRED
apptainer run --nv -B /gscratch:/gscratch pytorch_24.01-py3.sif python train.py
```

Key flags:
- `--nv` — bind host GPU drivers into the container. Without this you'll
  get "CUDA driver not found" even on a GPU node.
- `-B <host>:<container>` — bind mount data/code into the container.
- `--pwd /path` — set working directory inside the container.

Common gotchas:
- CUDA version in the image must be compatible with klone's host drivers.
  If you see "CUDA driver version is insufficient", pick an older image tag.
- First pull is slow (several GB); cache the .sif on `/gscratch` and reuse.
- Pull on a compute node (`salloc` first), never the login node.

## Notes
- ckpt-all jobs are preemptible. Use `--requeue` or checkpoint your work.
- `hyakalloc` shows which GPU partitions your account has access to.
- Test on a single GPU before scaling. Multi-GPU jobs have NCCL setup
  considerations beyond the scope of SLURM allocation.

## See also
- `klone://help/containers` — apptainer fundamentals (NGC is one source of containers)
- `klone://help/checkpoint` — ckpt partitions include GPU nodes; expect preemption
- `klone://help/monitoring` — `nvidia-smi` on the allocated node, sacct for diagnosing OOM

## References
- https://hyak.uw.edu/docs/gpus/gpu_start — GPU types, partitions, requesting
- https://hyak.uw.edu/docs/gpus/nvidia_ngc — NVIDIA NGC container catalog usage
"""


@mcp.resource("klone://help/checkpoint")
def help_checkpoint() -> str:
    """Checkpoint (ckpt) partitions — preemptible compute across groups."""
    return """
# Checkpoint (ckpt) Partitions on Klone

The ckpt partitions let any user borrow **idle** compute from any group's
contribution. Free-ish access in exchange for **preemption**: your job
can be stopped and requeued at any time, without warning, when the
owning group needs their resource back.

## The three partitions
- `ckpt` — generation-1 nodes only
- `ckpt-g2` — generation-2 nodes (AMD EPYC 9000-series, L40/L40s GPUs)
- `ckpt-all` — either generation; usually the right default

`ckpt-g2` has faster hardware but a smaller node pool (longer queues).
`ckpt` is the largest pool but slower per-core. `ckpt-all` strikes a balance.

## Hard requeue intervals
Even if no group preempts you, ckpt jobs are stopped and requeued on a
schedule:
- **CPU-only jobs**: every 4-5 hours
- **GPU jobs**: every 8-9 hours

Plus arbitrary preemption from contributors at any time.

## How to use it safely

```bash
#SBATCH --account=YOUR_ACCOUNT       # use any account your NetID has
#SBATCH --partition=ckpt-all
#SBATCH --requeue                    # auto-resubmit when preempted
#SBATCH --time=04:00:00              # what you actually expect
# ... your script ...
```

Your job must be **resumable**: when it restarts after a preemption it
needs to pick up where it stopped. Either save checkpoints to disk
yourself, or use DMTCP (`klone://docs/commands` for the command;
https://hyak.uw.edu/docs/tools/dmtcp for details).

## Best practices
- Always set `--requeue`. Without it, preemption = job lost.
- Save state every 10-30 minutes inside your script; reload on start.
- For builds that take longer than the requeue interval, chain
  `afterany` dependent jobs that read the partial state.
- Avoid ckpt for *interactive* work — wait times under load are long.
  Use a priority partition (your own group's allocation) for interactive.
- Filesystem (gscratch) may throttle ckpt jobs during heavy I/O periods
  to keep the cluster stable. Stage to local SSD (`/tmp/$SLURM_JOB_ID`)
  before doing heavy I/O.

## See also
- `klone://help/monitoring` — diagnose `PREEMPTED` vs `TIMEOUT` vs other
  exit reasons after a ckpt job ends
- `klone://help/jobs` — for non-preemptible alternatives via your account's allocation

*Reference: https://hyak.uw.edu/docs/compute/checkpoint*
"""


@mcp.resource("klone://help/monitoring")
def help_monitoring() -> str:
    """Watching, diagnosing, and post-morteming jobs."""
    return """
# Resource Monitoring & Job Diagnosis on Klone

## What's running right now
```bash
squeue --me                              # your jobs
squeue --me -t R                         # running only
squeue -A YOUR_ACCOUNT                   # everyone in your account
hyakalloc                                # your accounts, current usage, limits
hyakalloc -c                             # idle ckpt resources cluster-wide
```

## Inspecting a running job
```bash
scontrol show job <ID>                   # full job info: node, paths, account, time
sstat -j <ID>.batch --format=AveCPU,MaxRSS,AveRSS    # live CPU/mem use of running step
```
To see what a job is actually doing: SSH the assigned node with
`ssh n3088` (replace with node from `squeue`), then `top`/`htop`/`nvidia-smi`.
This only works while the job has a live allocation.

## Why was my job killed?
```bash
sacct -j <ID> -X -P -n --format=JobID,State,ExitCode,DerivedExitCode,Reason,MaxRSS,Elapsed,ReqMem
```

Common exit signals:
- `OUT_OF_MEMORY` or exit code 137 — your job hit the `--mem` limit.
  Bump `--mem` or use a high-mem partition.
- `TIMEOUT` — you hit `--time`. Either extend or split the work.
- `CANCELLED+` — somebody (you or SLURM via preemption) cancelled it.
- `PREEMPTED` (ckpt) — a contributor reclaimed the resource.
- `NODE_FAIL` — the compute node died; resubmit, the job is not at fault.

## Reading the log
```bash
# Find the log paths SLURM picked:
scontrol show job <ID> | grep -E 'StdOut|StdErr'
# Then:
tail -n 200 /path/to/slurm-<ID>.out
```
For long-running jobs already finished, `scontrol show job` won't have
info (slurmctld forgets). Use `sacct` to find the JobID and look at the
log path you specified in `#SBATCH -o` if you set one.

## Historical accounting
```bash
sacct -S now-1day -X -P -n --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS
sacct -S 2026-05-01 -E 2026-05-19 --format=...                  # explicit range
```
`--format=ReqMem,MaxRSS` is gold for "how close was I to OOM?" — if
MaxRSS is close to ReqMem, increase your request for next time.

## See also
- `klone://help/jobs` — partition catalog + pending reasons (interpret
  squeue's "REASON" column)
- `klone://help/checkpoint` — if you see `State=PREEMPTED`, that's a ckpt
  contributor reclaiming the resource; expected, design for it

*Reference: https://hyak.uw.edu/docs/compute/resource-monitoring*
"""


@mcp.resource("klone://help/ood")
def help_ood() -> str:
    """Open OnDemand web portal."""
    return """
# Open OnDemand (OOD) on Klone

A web portal for klone at **https://ondemand.hyak.uw.edu/**.

## What you can do via OOD
- Submit and monitor SLURM jobs through a web UI
- Launch interactive apps: RStudio, Jupyter, VS Code, MATLAB
- Browse and edit files
- Open a terminal session in the browser

## Access
- UW NetID + Duo login.
- **Off-campus**: connect to UW Husky OnNet VPN first; otherwise some
  resources may not load.

## When to use OOD vs SSH
- **OOD**: GUI apps, file browsing, interactive development without
  manual SSH tunneling.
- **SSH (or this MCP)**: command-line scripting, batch submissions,
  automation, anything you want to be reproducible.

## Gotchas
- OOD interactive apps default to launching in **home** (10 GB quota).
  Symlink something larger first:
  `ln -s /gscratch/scrubbed/YOUR_NETID/work ~/work`
- If the web UI gets stuck, reload via the `</>` icon (server restart).

## See also
- `klone://help/jupyter` — Jupyter via OOD is the easiest of three options
- `klone://help/matlab`, `klone://help/r` — both have OOD apps for GUI use

*Reference: https://hyak.uw.edu/docs/ood/start*
"""


# --- Tools (Actions) ---

def handle_ssh_errors(func):
    """Catch SSH errors and turn them into a string the agent can act on."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DuoExpiredError as e:
            return str(e)
        except SSHCommandError as e:
            return str(e)
        except TimeoutError as e:
            return str(e)
        except Exception as e:
            return f"Unexpected Error: {str(e)}"
    return wrapper


@mcp.tool()
@handle_ssh_errors
def klone_run(cmd: str, timeout: int = 60) -> str:
    """
    Run a shell command on klone and return its stdout.

    `cmd` is run by the remote shell, so pipes, redirects, and `&&` chains
    work. For everything beyond simple commands — SLURM job submission,
    job inspection, log tailing, disk queries, etc. — invoke the
    appropriate shell tool here. See `klone://docs/commands` for a list
    of klone-specific utilities (hyakalloc, hyakstorage, squeue, sacct,
    sbatch, scontrol, scancel, sinfo, apptainer, ...).

    For long-running work (compilation, training), submit a SLURM job
    via `sbatch` rather than running it directly.

    `timeout` (seconds) controls how long to wait for the remote command.
    Default 60. Bump for expensive queries like `du -sh /gscratch/...`.

    **First-time orientation**: if you haven't already, read
    `klone://docs/quickstart` — it covers the storage/quota layout, the
    SSD-staging performance pattern, and indexes all other `klone://help/*`
    topics (SLURM, GPUs, containers, MATLAB, R, Jupyter, etc). Reading it
    once saves repeated trial-and-error.
    """
    return run_ssh(cmd, timeout=timeout)


@mcp.tool()
@handle_ssh_errors
def klone_put_file(path: str, content: str) -> str:
    """
    Create or overwrite a file on klone with the given content.

    Content is piped via SSH stdin, so size is unlimited (no ARG_MAX
    boundary) and shell metacharacters in `content` are not interpreted.

    Use this for writing SLURM scripts, config files, small data files —
    anything where you want exact bytes written verbatim. For very large
    data files, use `rsync` or `scp` from the calling machine instead.

    **If you're writing a SLURM script**, read `klone://help/jobs` first
    for the partition catalog and `klone://help/checkpoint` if you're
    planning to use ckpt-all (preemption handling is required).
    """
    safe_path = shlex.quote(path)
    return run_ssh(f"cat > {safe_path}", stdin=content)


if __name__ == "__main__":
    mcp.run()
