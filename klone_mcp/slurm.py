import shlex
from klone_mcp.ssh import run_ssh

def get_squeue(user: str = None, state: str = None, partition: str = None) -> list[dict]:
    """Returns structured current jobs for a specific user.

    Defaults to the current SSH user (--me). Pass `user="netid"` to query
    someone else's queue. Cluster-wide queue is intentionally not exposed:
    it's typically thousands of rows that blow up agent context, and the
    answer to "what's on klone overall" is rarely a job list — it's stats
    like 'sinfo' that the agent can get via `klone_run`.
    """
    cmd_parts = ["squeue", "-h", "-o", "'%i|%j|%T|%M|%L|%R|%N|%P|%u'"]
    if user is None:
        cmd_parts.append("--me")
    else:
        cmd_parts.extend(["-u", shlex.quote(user)])
    if state:
        cmd_parts.extend(["-t", shlex.quote(state)])
    if partition:
        cmd_parts.extend(["-p", shlex.quote(partition)])

    stdout = run_ssh(" ".join(cmd_parts))
    jobs = []
    for line in stdout.strip().splitlines():
        parts = line.split('|')
        if len(parts) >= 9:
            jobs.append({
                "id": parts[0].strip(),
                "name": parts[1].strip(),
                "state": parts[2].strip(),
                "time": parts[3].strip(),
                "time_left": parts[4].strip(),
                "reason": parts[5].strip(),
                "nodes": parts[6].strip(),
                "partition": parts[7].strip(),
                "user": parts[8].strip(),
            })
    return jobs

def get_sacct(job_id: str = None, days: int = 1, limit: int = 10) -> list[dict]:
    """Returns structured job history."""
    fmt = "JobID,JobName,State,ExitCode,MaxRSS,Elapsed"
    if job_id:
        # Use -X to only show the main job allocation, not every sub-step, unless looking for specific details
        cmd = f"sacct -j {job_id} -X -P -n --format={fmt}"
    else:
        cmd = f"sacct -S now-{days}days -X -P -n --format={fmt}"
        
    stdout = run_ssh(cmd)
    jobs = []
    for line in stdout.strip().splitlines():
        parts = line.split('|')
        if len(parts) >= 6:
            jobs.append({
                "id": parts[0].strip(),
                "name": parts[1].strip(),
                "state": parts[2].strip(),
                "exit_code": parts[3].strip(),
                "max_rss": parts[4].strip(),
                "elapsed": parts[5].strip()
            })
    
    # Return the most recent jobs up to the limit
    # (sacct output is typically chronologically ordered, so we take from the end)
    if not job_id and limit and len(jobs) > limit:
        return jobs[-limit:]
    
    return jobs

