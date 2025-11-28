import argparse
import subprocess
import sys
import random
import string
import time
from pathlib import Path

from jpamb import jvm, model
import signInterpreter
import syntactic_analyzer

global min_value, max_value
max_value = 1000
min_value = -1000

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
        arr_literal = lines[1] if len(lines) > 1 else ""

        print(f"Debug: interpreter returned arr_literal: {arr_literal}")

        if result == "*":
            global max_value, min_value
            max_value = int(max_value / 2)
            min_value = int(min_value / 2)

        # Parse the trace line into a list of integers
        if not arr_literal:
            print(f"Debug: trace line from interpreter: {arr_literal}")
            trace = []
        else:
            print("Debug: no trace line from interpreter")
            trace = list(map(int, arr_literal.split(',')))

        return interpreter_result.returncode, result, trace
    else:
        proc = subprocess.run(cmd)
        return proc.returncode, "", ""

def _analyze_method(analyser: list[str], method_id: str, type: jvm.Type) -> list[jvm.Value]:
    inputs: list[jvm.Value] = []
    analyses = []
    # perform analysis
    if not analyser:
        return inputs
    
    # perform sign analysis
    if "sign" in analyser:
        try:
            for n in (range(-1,2)):  # -1, 0, 1
                result = signInterpreter.run(method_id, f"({n})")
                if result == {'ok'}:
                    if n == -1:
                        global min_value
                        min_value = 0
                    
                    elif n == 1:
                        global max_value
                        max_value = 0

                    analyses.append(n)
            analyses.append(0)
        except Exception:
            max_value = 1000
            min_value = 1000
            
            print(f"\033[91m⚠️   Sign analysis failed for method {method_id}; continuing without seeding\033[0m")
            pass

        print(f"    \033[94msign analysis reduced range: [{min_value}, {max_value}]\033[0m")

    # perform syntactic analysis
    if "syntactic" in analyser:
        analyses = syntactic_analyzer.analyze(method_id).get("values", [])

    print(f"    \033[94minputs from analyses: {analyses}\033[0m")
    # convert analysis results to jvm.Value based on type
    match type:
        case jvm.Int():
            inputs = [jvm.Value.int(v) for v in analyses]
        case jvm.Float():
            inputs = [jvm.Value.float(v) for v in analyses]
        case jvm.Boolean():
            inputs = [jvm.Value.boolean(v) for v in analyses]
        case jvm.Char():
            inputs = [jvm.Value.char(v) for v in analyses]
        case jvm.String():
            inputs = [jvm.Value.string(v) for v in analyses]
        case _:
            print(f"\033[91m⚠️   Analysis for type {type} not implemented; continuing without seeding\033[0m")
    return inputs
    

def _encode_values(values: list[jvm.Value]) -> str:
    return "(" + ", ".join(v.encode() for v in values) + ")"


def _gen_for_type(type: jvm.Type, rng: random.Random, max_str: int, max_arr: int) -> jvm.Value:
    match type:
        case jvm.Int():
            return jvm.Value.int(rng.randint(min_value, max_value))
        case jvm.Float():
            return jvm.Value.float(rng.uniform(float(min_value), float(max_value)))
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
        case jvm.Value(jvm.Int(), int_val):
            # Mutate integer by adding or subtracting a small random value
            delta = rng.randint(-10, 10)
            return jvm.Value.int(int_val + delta)
        case jvm.Value(jvm.Float(), float_val):
            # Mutate float by adding a small random delta
            delta = rng.uniform(-1.0, 1.0)
            return jvm.Value.float(float_val + delta)
        case jvm.Value(jvm.Boolean(), bool_val):
            # Flip the boolean value
            return jvm.Value.boolean(not bool_val)
        case jvm.Value(jvm.Char(), char_val):
            # Mutate char by replacing with a random character
            return jvm.Value.char(rng.choice(string.ascii_letters))
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
                return value
        case jvm.Value(jvm.Array(contains), arr_val):
            # Mutate array by modifying an element or changing length
            if arr_val and len(arr_val) > 0:
                idx = rng.randint(0, len(arr_val) - 1)
                mutated_elem = _mutate_input(arr_val[idx], rng)
                new_arr = arr_val[:idx] + [mutated_elem] + arr_val[idx+1:]
                return jvm.Value.array(contains, new_arr)
            else:
                return value
        case _:
            # For unsupported types, return the original value
            return value


def fuzz_method(
    methodid: str,
    iterations: int = 1000,
    seed: int | None = None,
    save_file: str | None = None,
    max_str: int = 16,
    max_arr: int = 8,
    mutation_rate: float = 0.8,
    analysis: list[str] | None = None,
):
    
    all_offsets = get_all_offsets(methodid)

    rng = random.Random(seed)

    abs_mid = jvm.AbsMethodID.decode(methodid)
    params_type = abs_mid.extension.params
    params = getattr(params_type, "_elements", []) if params_type else []

    # global coverage and corpus
    global_coverage: set[int] = set()
    corpus: list[jvm.Value] = []

    analysis_values: list[jvm.Value] = []

    start_time = time.time()

    # get input from analyzer to seed corpus
    if analysis:
        print(f"    \033[94mrunning analyses {analysis}\033[0m")
        analysis_values = _analyze_method(analysis, methodid, params[0])  # only analyze for first parameter type

    save_path = Path(save_file) if save_file else None
    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)

    for i in range(iterations):
        global max_value, min_value
        max_value = 1000
        min_value = -1000
        # --- choose input generation strategy ---
        if analysis_values:
            # use analysis values first
            input_value = analysis_values.pop(0)
            values = [input_value]

        # --- choose between random generation and mutation ---
        elif corpus and rng.random() < mutation_rate:  # 90% mutations, 10% fresh
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
            print(f"\033[92m[+]\033[0m new coverage: +{len(new_edges)} edges  input={in_str}\tresult={result}")
            print(f"    coverage precentage: {len(global_coverage)/len(all_offsets)*100:.2f}%")
    
            if len(global_coverage) >= len(all_offsets):
                print("\033[94mAll edges covered! Ending fuzzing early.\033[0m")
                break
            
            if save_path is not None:
                with open(save_path, "a", encoding="utf-8") as f:
                    f.write(f"{methodid} {in_str} -> new edges={new_edges}\n")
        else:
            print(f"\033[93m[-]\033[0m no new coverage  input={in_str}\t\tresult={result}")
    end_time = time.time()
    elapsed = end_time - start_time
    coverage_pct = (len(global_coverage)/len(all_offsets)*100) if all_offsets else 0.0
    print(f"\033[94mFuzzing complete. Total coverage: {len(global_coverage)}/{len(all_offsets)} edges ({coverage_pct:.2f}%)\033[0m")
    print(f"\033[94mElapsed time: {elapsed:.2f} seconds\033[0m")

    return {
        "method": methodid,
        "coverage": len(global_coverage),
        "total": len(all_offsets),
        "percent": coverage_pct,
        "time": elapsed
    }

def get_all_cases_from_file() -> list[str]:
    case_file = Path("target/stats/cases.txt")
    if not case_file.exists():
        # Fallback: try to find it relative to the script location if run from elsewhere
        case_file = Path(__file__).parent.parent / "target/stats/cases.txt"

    if not case_file.exists():
        print(f"\033[93mWarning: Could not find cases file at {case_file}\033[0m")
        return []
    
    method_ids = set()
    try:
        with open(case_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if parts:
                    method_ids.add(parts[0])
    except Exception as e:
        print(f"\033[91mError reading cases file: {e}\033[0m")
        return []
        
    return sorted(list(method_ids))

def main():
    parser = argparse.ArgumentParser(description="Run the interpreter with a given method id and input, or fuzz it.")
    parser.add_argument("methodid", nargs="?", help="method id to pass to interpreter (e.g. 'jpamb.cases.Simple.assertInteger:(I)V')")
    parser.add_argument("input", nargs="?", help="input string to pass to interpreter (e.g. '(1)')")
    parser.add_argument("--no-capture", dest="capture", action="store_false", help="don't capture interpreter output; stream to console")
    parser.add_argument("--fuzz", dest="fuzz", action="store_true", help="run fuzzing mode (generate random inputs)")
    parser.add_argument("--iterations", type=int, default=1000, help="number of fuzz iterations (default: 1000)")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument("--save-file", default=None, help="file to append interesting cases to")
    parser.add_argument("--max-str", type=int, default=16, help="max string length for generated strings")
    parser.add_argument("--max-arr", type=int, default=8, help="max array length for generated arrays")
    parser.add_argument("--mut-rate", type=float, default=0.9, help="mutation rate for fuzzing")
    parser.add_argument("--analysis", nargs="+", default=None, help="type of analysis to seed corpus (e.g. 'syntactic', 'sign')")

    args = parser.parse_args()

    if args.methodid is None:
        print("No method ID provided. Fuzzing all cases found in target/stats/cases.txt...")
        method_ids = get_all_cases_from_file()
        
        if not method_ids:
            print("No cases found to fuzz.")
            sys.exit(1)

        results = []
        total_start_time = time.time()

        for mid in method_ids:
            print(f"\n\033[1m{'='*80}\nFuzzing {mid}\n{'='*80}\033[0m")
            try:
                stats = fuzz_method(
                    methodid=mid,
                    iterations=args.iterations,
                    seed=args.seed,
                    save_file=args.save_file,
                    max_str=args.max_str,
                    max_arr=args.max_arr,
                    mutation_rate=args.mut_rate,
                    analysis=args.analysis,
                )
                results.append(stats)
            except Exception as e:
                print(f"\033[91mError fuzzing {mid}: {e}\033[0m")
                results.append({"method": mid, "error": str(e)})
        
        total_elapsed = time.time() - total_start_time
        
        print("\n" + "="*100)
        print(f"{'Method ID':<60} | {'Cov %':<8} | {'Time (s)':<8}")
        print("-" * 100)
        
        total_pct = 0
        valid_count = 0
        
        # Variables for aggregate total coverage
        total_covered_edges = 0
        total_available_edges = 0
        
        for res in results:
            mid_display = res['method']
            if len(mid_display) > 58:
                mid_display = mid_display[:55] + "..."
            
            if "error" in res:
                print(f"{mid_display:<60} | {'ERR':<8} | {'-':<8}")
            else:
                print(f"{mid_display:<60} | {res['percent']:6.2f}% | {res['time']:6.2f}")
                total_pct += res['percent']
                valid_count += 1
                
                # Accumulate totals for global calculation
                total_covered_edges += res['coverage']
                total_available_edges += res['total']
                
        print("-" * 100)
        avg_cov = total_pct / valid_count if valid_count > 0 else 0
        
        # Calculate total coverage across all valid cases
        total_cov_pct = (total_covered_edges / total_available_edges * 100) if total_available_edges > 0 else 0.0
        
        print(f"Total Elapsed Time: {total_elapsed:.2f}s")
        print(f"Average Coverage:   {avg_cov:.2f}%")
        print(f"Total Coverage:     {total_cov_pct:.2f}% ({total_covered_edges}/{total_available_edges} edges)")
        
        return

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