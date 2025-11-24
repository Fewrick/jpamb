import argparse
import subprocess
import sys
import random
import string
from pathlib import Path

import jpamb
from jpamb import jvm
import re


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

        lines = proc.stdout.strip().splitlines()
        msg = lines[0] if len(lines) > 0 else ""
        arr_literal = lines[1] if len(lines) > 1 else "[]"

        # parse arr_literal like "[1, 2, 3]" or "1,2,3" or "1 2 3" into a list of ints
        s = arr_literal.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        parts = [p for p in re.split(r"[,\s]+", s) if p]
        arr = []
        for p in parts:
            try:
                arr.append(int(p))
            except ValueError:
                # ignore non-integer tokens
                pass

        return proc.returncode, proc.stdout, proc.stderr
    else:
        proc = subprocess.run(cmd)
        return proc.returncode, "", ""



def _encode_values(values: list[jvm.Value]) -> str:
    return "(" + ", ".join(v.encode() for v in values) + ")"


def _gen_for_type(tt: jvm.Type, rng: random.Random, max_str: int, max_arr: int) -> jvm.Value:
    match tt:
        case jvm.Int():
            return jvm.Value.int(rng.randint(-1000, 1000))
        case jvm.Boolean():
            return jvm.Value.boolean(rng.choice([True, False]))
        case jvm.Char():
            return jvm.Value.char(rng.choice(string.ascii_letters))
        case jvm.String():
            length = rng.randint(0, max_str)
            s = "".join(rng.choice(string.ascii_letters + string.digits + " _-") for _ in range(length))
            return jvm.Value.string(s)
        case jvm.Array(contains):
            length = rng.randint(0, max_arr)
            if isinstance(contains, jvm.Int):
                content = [rng.randint(-100, 100) for _ in range(length)]
                return jvm.Value.array(jvm.Int(), content)
            if isinstance(contains, jvm.Char):
                content = [rng.choice(string.ascii_letters) for _ in range(length)]
                return jvm.Value.array(jvm.Char(), content)
            # fallback to null reference for unsupported arrays
            return jvm.Value(jvm.Reference(), None)
        case jvm.Reference():
            return jvm.Value(jvm.Reference(), None)
        case jvm.Object() as obj:
            # For object types other than String, produce a null reference
            return jvm.Value(jvm.Reference(), None)
        case _:
            # Unknown/unsupported type: produce a null reference
            return jvm.Value(jvm.Reference(), None)


def fuzz_method(
    methodid: str,
    iterations: int = 1000,
    seed: int | None = None,
    save_file: str | None = None,
    max_str: int = 16,
    max_arr: int = 8,
):
    rng = random.Random(seed)

    abs_mid = jvm.AbsMethodID.decode(methodid)
    params = abs_mid.extension.params

    seen = set()
    saved = 0
    save_path = Path(save_file) if save_file else None

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)

    for i in range(iterations):
        values: list[jvm.Value] = []
        for tt in params:
            try:
                v = _gen_for_type(tt, rng, max_str, max_arr)
            except Exception:
                v = jvm.Value(jvm.Reference(), None)
            values.append(v)

        in_str = _encode_values(values)
        rc, out, err = run_interpreter(methodid, in_str, capture_output=True)
        key = (out.strip(), err.strip())
        if key not in seen:
            seen.add(key)
            saved += 1
            summary = out.strip() or err.strip() or f"rc={rc}"
            print(f"[+] new outcome #{len(seen)}: {summary}  input={in_str}")
            if save_path is not None:
                with open(save_path, "a", encoding="utf-8") as f:
                    f.write(f"{methodid} {in_str} -> {summary}\n")

    print(f"Fuzzing completed: {iterations} iterations, {len(seen)} unique outcomes, {saved} saved")


def main():
    parser = argparse.ArgumentParser(description="Run the interpreter with a given method id and input, or fuzz it.")
    parser.add_argument("methodid", help="method id to pass to interpreter (e.g. 'jpamb.cases.Simple.assertInteger:(I)V')")
    parser.add_argument("input", nargs="?", help="input string to pass to interpreter (e.g. '(1)')")
    parser.add_argument("--no-capture", dest="capture", action="store_false", help="don't capture interpreter output; stream to console")
    parser.add_argument("--fuzz", dest="fuzz", action="store_true", help="run fuzzing mode (generate random inputs)")
    parser.add_argument("--iterations", type=int, default=1000, help="number of fuzz iterations (default: 1000)")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument("--save-file", default=None, help="file to append interesting cases to")
    parser.add_argument("--max-str", type=int, default=16, help="max string length for generated strings")
    parser.add_argument("--max-arr", type=int, default=8, help="max array length for generated arrays")

    args = parser.parse_args()

    if args.fuzz:
        fuzz_method(
            args.methodid,
            iterations=args.iterations,
            seed=args.seed,
            save_file=args.save_file,
            max_str=args.max_str,
            max_arr=args.max_arr,
        )
        return

    if not args.input:
        parser.error("either provide an input or use --fuzz")

    rc, out, err = run_interpreter(args.methodid, args.input, capture_output=args.capture)

    if args.capture:
        if out:
            print(out, end="")
        if err:
            print(err, file=sys.stderr, end="")

    sys.exit(rc)


if __name__ == "__main__":
    main()