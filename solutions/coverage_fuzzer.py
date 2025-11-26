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
        interpreter_result = subprocess.run(cmd, capture_output=True, text=True)

        # Separate the first line (result) from the second line (trace)
        lines = interpreter_result.stdout.strip().splitlines()
        result = lines[0] if len(lines) > 0 else ""
        arr_literal = lines[1] if len(lines) > 1 else "[]"

        # Parse the trace array literal
        trace = list(map(int, arr_literal.split(',')))

        return interpreter_result.returncode, result, trace
    else:
        proc = subprocess.run(cmd)
        return proc.returncode, "", ""

def _analyze_method(analysis: str) -> list[jvm.Value]:
    match analysis:
        case "sign":
            print("⚠️  Sign analysis not implemented; continuing without seeding")
            return [] 
        case "syntactic":
            print("⚠️  Syntactic analysis not implemented; continuing without seeding")
            return []

def _encode_values(values: list[jvm.Value]) -> str:
    return "(" + ", ".join(v.encode() for v in values) + ")"


def _gen_for_type(type: jvm.Type, rng: random.Random, max_str: int, max_arr: int) -> jvm.Value:
    match type:
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


def _mutate_input(value: jvm.Value, rng: random.Random) -> jvm.Value:
    match value:
        case jvm.Value(jvm.Int(), int_type):
            # Mutate integer by adding or subtracting a small random value
            delta = rng.randint(-10, 10)
            return jvm.Value.int(int_type + delta)
        case jvm.Value(jvm.Boolean(), bool_type):
            # Flip the boolean value
            return jvm.Value.boolean(not bool_type)
        case _:
            # For unsupported types, return the original value
            return jvm.Value(jvm.Reference(), None)


def fuzz_method(
    methodid: str,
    iterations: int = 1000,
    seed: int | None = None,
    save_file: str | None = None,
    max_str: int = 16,
    max_arr: int = 8,
    mutation_rate: float = 0.8,
    analysis: str | None = None,
):
    rng = random.Random(seed)

    abs_mid = jvm.AbsMethodID.decode(methodid)
    params = abs_mid.extension.params

    # global coverage and corpus
    global_coverage: set[int] = set()
    corpus: list[jvm.Value] = []

    # get input from analyzer to seed corpus
    if analysis:
        print(f"[+] seeding corpus from analysis: {analysis}")
        corpus = _analyze_method(analysis)  # you can change analysis type as needed

    save_path = Path(save_file) if save_file else None
    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)

    for i in range(iterations):

        # --- choose between random generation and mutation ---
        if corpus and rng.random() < mutation_rate:  # 90% mutations, 10% fresh
            # mutation
            parent_input = rng.choice(corpus)
            try:
                input_value = _mutate_input(parent_input, rng)  # you'll write this small helper
            except Exception:
                input_value = []
            values = [input_value]
        else:
            # full random
            values = []
            for parameter_type in params:
                try:
                    input_value = _gen_for_type(parameter_type, rng, max_str, max_arr)
                except Exception:
                    input_value = jvm.Value(jvm.Reference(), None)
                values.append(input_value)

        in_str = _encode_values(values)
        rc, result, trace = run_interpreter(methodid, in_str, capture_output=True)
        # compute coverage for this run
        run_coverage = set(trace)

        # detect coverage increase
        new_edges = run_coverage - global_coverage
        if new_edges:
            global_coverage |= new_edges
            for value in values:
                if value not in corpus:
                    corpus.append(value)
            print(f"[+] new coverage: +{len(new_edges)} edges  input={in_str}")
            
            if save_path is not None:
                with open(save_path, "a", encoding="utf-8") as f:
                    f.write(f"{methodid} {in_str} -> new edges={new_edges}\n")
        else:
            print(f"[-] no new coverage  input={in_str}")



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
    parser.add_argument("--mut-rate", type=float, default=0.9, help="mutation rate for fuzzing")
    parser.add_argument("--analysis", default=None, help="type of analysis to seed corpus")

    args = parser.parse_args()

    if args.fuzz:
        fuzz_method(
            args.methodid,
            iterations=args.iterations,
            seed=args.seed,
            save_file=args.save_file,
            max_str=args.max_str,
            max_arr=args.max_arr,
            mutation_rate=args.mut_rate,
            analysis=args.analysis,
        )
        return

    if not args.input:
        parser.error("either provide an input or use --fuzz")

    rc, result, trace = run_interpreter(args.methodid, args.input, capture_output=args.capture)

    if args.capture:
        if result:
            print(result, end="")
        if trace:
            print(trace, file=sys.stderr, end="")

    sys.exit(rc)


if __name__ == "__main__":
    main()