import os, subprocess, signal

out = subprocess.check_output(['lsof', '-i', ':8031', '-t']).decode('utf-8').strip()
if out:
    for pid in out.split('\n'):
        print(f"Killing PID {pid}")
        try:
            os.kill(int(pid), signal.SIGKILL)
        except Exception as e:
            print(f"Failed to kill {pid}: {e}")
else:
    print("No process on port 8031")
