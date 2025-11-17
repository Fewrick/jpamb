import os
import sys
import subprocess
import argparse

#!/usr/bin/env python3
# run_coverage_fuzzer.py
# Small runner to execute the coverage_fuzzer.py script and stream its output.


DEFAULT_PATH = r"C:\Users\kaspe\Programming\GitHub\Mining_jpamb\solutions\coverage_fuzzer.py"

def main():
    parser = argparse.ArgumentParser(description="Run coverage_fuzzer.py and stream output.")
    parser.add_argument("path", nargs="?", default=DEFAULT_PATH, help="Path to coverage_fuzzer.py")
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    if not os.path.isfile(path):
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(2)

    cmd = [sys.executable, path]
    print("Running:", " ".join(cmd), file=sys.stderr)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for line in proc.stdout:
            print(line, end="")
    except KeyboardInterrupt:
        proc.kill()
        proc.wait()
        print("\nExecution interrupted by user.", file=sys.stderr)
        sys.exit(130)

    proc.wait()
    sys.exit(proc.returncode)

if __name__ == "__main__":
    main()