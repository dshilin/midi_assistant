import paramiko, os, sys, stat, time
from pathlib import Path

HOST = "31.56.204.156"
REMOTE_DIR = "/root/midi_assistant"
LOCAL_DIR = os.path.dirname(os.path.abspath(__file__))

EXCLUDE = {
    ".venv", ".git", ".pytest_cache", "__pycache__",
    ".env", ".env.example", ".gitattributes", ".gitignore",
    ".python-version", "uv.lock", "pyproject.toml",
    "products.db", "logs",
    "deploy.py",
}

def sync_file(sftp, local_path, rel_path):
    remote_path = f"{REMOTE_DIR}/{rel_path}"
    try:
        sftp.stat(remote_path)
        needs_upload = os.path.getmtime(local_path) > sftp.stat(remote_path).st_mtime
    except FileNotFoundError:
        needs_upload = True
    if needs_upload:
        sftp.put(local_path, remote_path)
        print(f"  ↑ {rel_path}", flush=True)

def sync_dir(sftp, local_dir, rel_dir=""):
    for entry in sorted(os.listdir(local_dir)):
        if entry in EXCLUDE or entry.startswith(".") or entry.endswith(".pyc"):
            continue
        local_path = os.path.join(local_dir, entry)
        rel_path = f"{rel_dir}/{entry}" if rel_dir else entry
        if os.path.isdir(local_path):
            if entry in ("__pycache__",): continue
            try:
                sftp.stat(f"{REMOTE_DIR}/{rel_path}")
            except FileNotFoundError:
                sftp.mkdir(f"{REMOTE_DIR}/{rel_path}")
                print(f"  + {rel_path}/", flush=True)
            sync_dir(sftp, local_path, rel_path)
        elif os.path.isfile(local_path):
            sync_file(sftp, local_path, rel_path)

def deploy():
    if len(sys.argv) > 1:
        if sys.argv[1] in ("-h", "--help"):
            print("Usage: python deploy.py [password]")
            print("  password defaults to env MIDI_SSH_PASSWORD")
            sys.exit(0)

    password = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MIDI_SSH_PASSWORD")
    if not password:
        import getpass
        password = getpass.getpass("SSH password for root@{HOST}: ")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...", flush=True)
    client.connect(HOST, username="root", password=password, timeout=15)

    sftp = client.open_sftp()
    print("Syncing code...", flush=True)
    sync_dir(sftp, LOCAL_DIR)
    print("Syncing DB...", flush=True)
    local_db = os.path.join(LOCAL_DIR, "products.db")
    if os.path.exists(local_db):
        sftp.put(local_db, f"{REMOTE_DIR}/products.db")
        print(f"  ↑ products.db ({os.path.getsize(local_db)} bytes)", flush=True)
    sftp.close()

    print("Restarting services...", flush=True)
    for cmd in ["systemctl daemon-reload", "systemctl restart midi-bot", "systemctl restart midi-web"]:
        client.exec_command(cmd)
    time.sleep(1)
    for name in ["midi-bot", "midi-web"]:
        _, stdout, _ = client.exec_command(f"systemctl is-active {name}")
        status = stdout.read().decode().strip()
        print(f"  {name}: {status}", flush=True)
        if status != "active":
            _, out, _ = client.exec_command(f"journalctl -u {name} -n 10 --no-pager")
            print(f"  journal: {out.read().decode().strip()[-500:]}", flush=True)

    client.close()
    print("Done.", flush=True)

if __name__ == "__main__":
    deploy()
