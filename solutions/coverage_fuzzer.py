import argparse
import json
import subprocess
import sys
import random
import string
import time 
from pathlib import Path

import jpamb
from jpamb import jvm, model
from syntactic_analyzer import analyze

# Examples of how to run the interpreter from this script:
# uv run solutions/coverage_fuzzer.py "jpamb.cases.Floats.floatGreaterThanThree:(F)V" --fuzz --iterations 10 --seed 1
# uv run solutions/coverage_fuzzer.py "jpamb.cases.Loops.testEqual:(I)Ljava/lang/String;" --fuzz --iterations 5000 --seed 1 --no-seeds

def get_all_offsets(methodid: str) -> set[int]:
    suite = model.Suite(Path.cwd())
    m = suite.findmethod(jvm.AbsMethodID.decode(methodid))
    return set(range(len(m["code"]["bytecode"])))


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
        arr_literal = arr_literal.strip()
        if arr_literal in ("[]", ""):
            trace = []
        else:
            trace = list(map(int, arr_literal.split(',')))

        return interpreter_result.returncode, result, trace
    else:
        proc = subprocess.run(cmd)
        return proc.returncode, "", ""


def _encode_values(values):
    parts = []
    for v in values:
        try:
            parts.append(v.encode())
        except NotImplementedError:
            parts.append("null")
    return "(" + ", ".join(parts) + ")"


def _gen_for_type(tt: jvm.Type, rng: random.Random, max_str: int, max_arr: int) -> jvm.Value:
    match tt:
        case jvm.Int():
            return jvm.Value.int(rng.randint(-1000, 1000))
        case jvm.Float(): 
            return jvm.Value.float(rng.uniform(-100.0, 100.0))
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
            if "String" in str(obj):
                length = rng.randint(0, max_str)
                s = "".join(rng.choice(string.ascii_letters + string.digits + " _-") for _ in range(length))
                return jvm.Value.string(s)
            return jvm.Value(jvm.Reference(), None)
        case _:
            # Unknown/unsupported type: produce a null reference
            return jvm.Value(jvm.Reference(), None)


def mutate_input(val: jvm.Value, rng: random.Random) -> jvm.Value:
    match val:
        case jvm.Value(jvm.Int(), x):
            return jvm.Value.int(x + rng.randint(-10, 10))
        case jvm.Value(jvm.Float(), f):
            return jvm.Value.float(f + rng.uniform(-50.0, 50.0))
        case jvm.Value(jvm.Boolean(), b):
            return jvm.Value.boolean(not b)
        case jvm.Value(jvm.Char(), c):
            new_c = chr((ord(c) + rng.randint(-5, 5) - ord('a')) % 26 + ord('a'))
            return jvm.Value.char(new_c)
        case jvm.Value(jvm.String(), str_val):
            # Mutate string by adding/removing/replacing a character
            mutation_type = rng.choice(["add", "remove", "replace"])
            if mutation_type == "add" and len(str_val) < 100:
                idx = rng.randint(0, len(str_val))
                char = rng.choice(string.ascii_letters + string.digits)
                new_str = str_val[:idx] + char + str_val[idx:]
                return jvm.Value.string(new_str)
            elif mutation_type == "remove" and len(str_val) > 0:
                idx = rng.randint(0, len(str_val) - 1)
                new_str = str_val[:idx] + str_val[idx+1:]
                return jvm.Value.string(new_str)
            elif mutation_type == "replace" and len(str_val) > 0:
                idx = rng.randint(0, len(str_val) - 1)
                char = rng.choice(string.ascii_letters + string.digits)
                new_str = str_val[:idx] + char + str_val[idx+1:]
                return jvm.Value.string(new_str)
            else:
                return val
        case jvm.Value(jvm.Array(contains), arr_val):
            # Mutate array by modifying an element or changing length
            if arr_val and len(arr_val) > 0:
                idx = rng.randint(0, len(arr_val) - 1)
                mutated_elem = mutate_input(arr_val[idx], rng)
                new_arr = arr_val[:idx] + [mutated_elem] + arr_val[idx+1:]
                return jvm.Value.array(contains, new_arr)
            else:
                return val
        case _:
            return val   


def fuzz_method(
    methodid: str,
    iterations: int = 1000,
    seed: int | None = None,
    save_file: str | None = None,
    max_str: int = 16,
    max_arr: int = 8,
    mutation_rate: float = 0.8,
    no_seeds: bool = False,
):
    rng = random.Random(seed)
    start = time.time()
    abs_mid = jvm.AbsMethodID.decode(methodid)
    all_offsets = get_all_offsets(methodid)
    params = abs_mid.extension.params
    param_count = len(params)

    global_coverage: set[int] = set()
    corpus: list[jvm.Value] = []

    stuck = 0
    last_new_time = start
    last_new_iter = 0

    save_path = Path(save_file) if save_file else None
    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)

    # --- syntactic seeds ---
    raw_seeds = analyze(methodid)["values"]
    
    seeds = [
        s for s in raw_seeds
        if (isinstance(s, list) and len(s) == param_count)
        or (param_count == 1 and not isinstance(s, list))
    ]

    def seed_to_str(s):
        if isinstance(s, list):
            return "(" + ", ".join(map(str, s)) + ")"
        return "(" + (json.dumps(s) if isinstance(s, str) else str(s)) + ")"

    seed_strs = [] if no_seeds else [seed_to_str(s) for s in seeds]

    for i in range(iterations):

        # --- run syntactic seeds first ---
        if i < len(seed_strs):
            in_str = seed_strs[i]
            rc, result, trace = run_interpreter(methodid, in_str, capture_output=True)
            run_coverage = set(trace)

        else:
            # --- choose between random generation and mutation ---
            if corpus and param_count == 1 and rng.random() < mutation_rate:
                parent_input = rng.choice(corpus)
                try:
                    input_value = mutate_input(parent_input, rng)
                except Exception:
                    input_value = jvm.Value(jvm.Reference(), None)
                values = [input_value]
            else:
                values = []
                for parameter_type in params:
                    try:
                        input_value = _gen_for_type(parameter_type, rng, max_str, max_arr)
                    except Exception:
                        input_value = jvm.Value(jvm.Reference(), None)
                    values.append(input_value)

            in_str = _encode_values(values)
            rc, result, trace = run_interpreter(methodid, in_str, capture_output=True)
            run_coverage = set(trace)

        # --- coverage bookkeeping ---
        print("result =", result, " trace =", trace)
        new_edges = run_coverage - global_coverage
        if new_edges:
            global_coverage |= new_edges  

            stuck = 0
            last_new_time = time.time()
            last_new_iter = i + 1
            if i < len(seed_strs):
                print(f"[+] new coverage: +{len(new_edges)} edges  seed={in_str}")
                if save_path is not None:
                    with open(save_path, "a", encoding="utf-8") as f:
                        f.write(f"{methodid} {in_str} -> new edges={new_edges}\n")
            else:
                for value in values:
                    if value not in corpus:
                        corpus.append(value)
                print(f"[+] new coverage: +{len(new_edges)} edges  input={in_str}")
                if save_path is not None:
                    with open(save_path, "a", encoding="utf-8") as f:
                        f.write(f"{methodid} {in_str} -> new edges={new_edges}\n")

            if global_coverage >= all_offsets:
                full_time = time.time() - start
                print(f"[FULL] {full_time:.3f}s  iters={i+1} coverage={len(global_coverage)}/{len(all_offsets)}")
                iterations = i + 1
                stuck = 0
                last_new_time = time.time()
                last_new_iter = i + 1  
                break    

        else:
            tag = "seed" if i < len(seed_strs) else "input"
            print(f"[-] no new coverage  {tag}={in_str}")

            stuck += 1  
            if stuck >= 40:  
                iterations = i + 1  
                break

    print(f"[FULL] {last_new_time - start:.3f}s  iters={last_new_iter} coverage={len(global_coverage)}/{len(all_offsets)}")
    print(f"[TIME] {time.time() - start:.3f}s  total_iters={iterations}")



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
    parser.add_argument("--no-seeds", action="store_true", help="disable syntactic seeds")

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
            no_seeds = args.no_seeds,
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