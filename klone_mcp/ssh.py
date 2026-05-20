import subprocess
import shlex

class DuoExpiredError(Exception):
    pass

class SSHCommandError(Exception):
    pass

def detect_duo_expiry(stderr: str, returncode: int) -> bool:
    """Check if the error message indicates a Duo/SSH expiry securely."""
    stderr = stderr.lower()
    # 255 is the standard SSH exit code for auth failure/connection drop
    if returncode == 255:
        return True
    if "(keyboard-interactive)" in stderr:
        return True
    if "broken pipe" in stderr:
        return True
    return False

def run_ssh(cmd: str, timeout: int = 60, stdin: str = None) -> str:
    """
    Helper to run SSH commands on klone.
    Expects a single string command to prevent accidental argument splitting.

    `stdin`: optional string piped to the remote command's standard input.
    Use this for large content (files, sbatch scripts) instead of embedding
    in the command string, which would hit ARG_MAX (~128KB on Linux).
    """
    # Pass the entire command as a single argument to SSH so it gets parsed
    # properly by the remote shell.
    full_cmd = ["ssh", "klone", cmd]
    try:
        process = subprocess.run(
            full_cmd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if process.returncode != 0:
            if detect_duo_expiry(process.stderr, process.returncode):
                raise DuoExpiredError(
                    "⚠️ klone SSH session has expired or is not configured.\n\n"
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
            
            raise SSHCommandError(f"Error (Exit {process.returncode}):\n{process.stderr}\nStdout:\n{process.stdout}")

        return process.stdout

    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout} seconds.")
