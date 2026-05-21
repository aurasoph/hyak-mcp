import os
import subprocess
import threading


# Max bytes we keep per stream before truncating. Above this we silently
# discard further bytes so a runaway `cat /huge` can't blow up the MCP
# response or the agent's context.
MAX_STREAM_BYTES = 1_048_576  # 1 MB


_DUO_EXPIRED_MSG = (
    "klone SSH session has expired or is not configured.\n\n"
    "Diagnostic (does NOT trigger Duo): `ssh -O check klone` —\n"
    "if the ControlMaster is alive it prints 'Master running';\n"
    "anything else means the persistent session needs to be re-seeded.\n\n"
    "Instructions for human:\n"
    "1. If this is your first time, ensure your `~/.ssh/config` is set up exactly like this:\n"
    "   Host klone klone-login\n"
    "       HostName klone.hyak.uw.edu\n"
    "       User YOUR_UWNETID\n"
    "       ControlMaster auto\n"
    "       ControlPath ~/.ssh/cm-%r@%h:%p\n"
    "       ControlPersist 10h\n"
    "       ServerAliveInterval 60\n"
    "2. Open a terminal on your laptop.\n"
    "3. Run: ssh klone\n"
    "4. Complete the Duo push (if prompted).\n"
    "5. Leave that terminal open.\n"
    "6. Ask the agent to retry."
)


class DuoExpiredError(Exception):
    pass


class SSHCommandError(Exception):
    pass


def _control_master_alive(host: str) -> bool:
    """Probe the persistent SSH ControlMaster for `host`.

    Local socket check (`ssh -O check`); fast and never triggers Duo
    even when the master is gone. Returns False on any failure so a
    hanging or misconfigured probe is treated as "not alive" — which
    gives the user the Duo reseed instructions, the right default for
    a stuck SSH layer.
    """
    try:
        result = subprocess.run(
            ["ssh", "-O", "check", host],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def detect_duo_expiry(stderr: str, returncode: int) -> bool:
    """Decide whether an SSH failure is a stale ControlMaster / Duo expiry.

    Only positive signals count. SSH exits 255 for any connection or auth
    failure (permission denied, network timeout, host unreachable, ...); we
    must not route all of those down the Duo re-auth path.
    """
    if returncode != 255:
        return False
    s = stderr.lower().replace(
        "could not open a connection to your authentication agent.", ""
    ).strip()
    if not s:
        return False

    # Positive signals that the persistent SSH session needs reseeding.
    duo_signals = (
        "keyboard-interactive",     # SSH fell back from publickey, no terminal for Duo
        "control socket connect",   # ControlMaster socket missing
        "mux_client",               # multiplexed client gave up
    )
    if any(sig in s for sig in duo_signals):
        return True

    # Definitively NOT Duo: network/config errors that also exit 255.
    not_duo_signals = (
        "connection timed out",
        "connection refused",
        "name or service not known",
        "no route to host",
        "network is unreachable",
        "host key verification failed",
        "permission denied (publickey)",  # pure key failure, no Duo fallback offered
    )
    if any(sig in s for sig in not_duo_signals):
        return False

    # Ambiguous: a bare "broken pipe" on klone usually means the persistent
    # ControlMaster dropped mid-call. Treat as Duo expiry so the user gets
    # the reseed instructions; harmless if they were actually offline.
    if "broken pipe" in s:
        return True

    return False


def _drain(stream, sink, info):
    """Read `stream` into `sink`, capping at MAX_STREAM_BYTES.

    Bytes beyond the cap are silently discarded; `info["total"]` records
    the full byte count so the caller can mark truncation.
    """
    total = 0
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            if total < MAX_STREAM_BYTES:
                keep = MAX_STREAM_BYTES - total
                sink.append(chunk[:keep])
            total += len(chunk)
    finally:
        info["total"] = total


def _mark_truncated(text: str, total: int, label: str) -> str:
    if total <= MAX_STREAM_BYTES:
        return text
    return text + f"\n[{label} truncated: {total} bytes captured, only first {MAX_STREAM_BYTES} returned]\n"


def run_ssh(cmd: str, timeout: int = 60, stdin: str | None = None) -> str:
    """Run `cmd` on the configured klone host and return combined output.

    The remote host is taken from the `KLONE_SSH_HOST` env var (default
    `klone`), so callers using a different SSH alias (klone-login, a test
    cluster, etc.) don't have to patch this file.

    `stdin`: optional string piped to the remote command. Use this for
    large content (files, sbatch scripts) instead of embedding in `cmd`,
    which hits ARG_MAX (~128 KB on Linux).

    On success returns stdout followed by stderr (Lmod and many tools
    write user-visible output to stderr; dropping it would silently lose
    `module avail` / `module list` results). Each stream is capped at
    1 MB; further bytes are dropped with a marker.

    On timeout, probes the SSH ControlMaster — if it's dead, raises
    `DuoExpiredError` (with reseed instructions) rather than a bare
    `TimeoutError`. A hanging `whoami` is almost always a stale Duo
    session, not a slow command.
    """
    host = os.environ.get("KLONE_SSH_HOST", "klone")
    full_cmd = ["ssh", host, cmd]

    process = subprocess.Popen(
        full_cmd,
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=8192,
    )

    out_chunks: list[str] = []
    err_chunks: list[str] = []
    out_info: dict = {}
    err_info: dict = {}

    t_out = threading.Thread(target=_drain, args=(process.stdout, out_chunks, out_info), daemon=True)
    t_err = threading.Thread(target=_drain, args=(process.stderr, err_chunks, err_info), daemon=True)
    t_out.start()
    t_err.start()

    if stdin is not None:
        try:
            process.stdin.write(stdin)
        except BrokenPipeError:
            pass
        finally:
            process.stdin.close()

    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        t_out.join()
        t_err.join()
        # A timeout with a dead ControlMaster is the classic Duo-expired
        # signature: ssh hangs trying to open an interactive auth instead
        # of failing fast. Surface the reseed instructions so the agent
        # doesn't just retry blindly.
        if not _control_master_alive(host):
            raise DuoExpiredError(_DUO_EXPIRED_MSG)
        raise TimeoutError(f"Command timed out after {timeout} seconds.")

    t_out.join()
    t_err.join()

    stdout = _mark_truncated("".join(out_chunks), out_info.get("total", 0), "stdout")
    stderr = _mark_truncated("".join(err_chunks), err_info.get("total", 0), "stderr")

    if process.returncode != 0:
        if detect_duo_expiry(stderr, process.returncode):
            raise DuoExpiredError(_DUO_EXPIRED_MSG)

        raise SSHCommandError(
            f"Error (Exit {process.returncode}):\n{stderr}\nStdout:\n{stdout}"
        )

    if stderr:
        return stdout + stderr
    return stdout
