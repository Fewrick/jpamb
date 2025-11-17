import argparse
import subprocess
import sys
from pathlib import Path


def run_interpreter(methodid: str, input_str: str, capture_output: bool = True) -> tuple[int, str, str]:
    """Run `solutions/interpreter.py` with the given method id and input string.

    Returns a tuple of (returncode, stdout, stderr).
    """
    interp_path = Path(__file__).resolve().parent / "interpreter.py"
    if not interp_path.exists():
        raise FileNotFoundError(f"interpreter.py not found at {interp_path}")

    cmd = [sys.executable, str(interp_path), methodid, input_str]

    if capture_output:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr
    else:
        proc = subprocess.run(cmd)
        return proc.returncode, "", ""


def main():
    parser = argparse.ArgumentParser(description="Run the interpreter with a given method id and input.")
    parser.add_argument("methodid", help="method id to pass to interpreter (e.g. 'jpamb.cases.Simple.assertInteger:(I)V')")
    parser.add_argument("input", help="input string to pass to interpreter (e.g. '(1)')")
    parser.add_argument("--no-capture", dest="capture", action="store_false", help="don't capture interpreter output; stream to console")
    args = parser.parse_args()

    rc, out, err = run_interpreter(args.methodid, args.input, capture_output=args.capture)

    if args.capture:
        if out:
            print(out, end="")
        if err:
            print(err, file=sys.stderr, end="")

    sys.exit(rc)


if __name__ == "__main__":
    main()