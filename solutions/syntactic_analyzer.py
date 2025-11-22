import json
import sys
from pathlib import Path

from jpamb import model, jvm

def print_info():
    print("Syntactic Assertion Finder\n0.0.1\nGroup 17\nsyntactic,python\nno")

def find_branches(bytecode):
    """Find all branch instructions in bytecode."""
    branches = []
    for op in bytecode:
        opr = op.get("opr")
        if opr in ["ifz", "if"]:
            branches.append({
                "offset": op.get("offset"),
                "type": "conditional_compare" if opr == "if" else "conditional_zero",
                "condition": op.get("condition"),
                "target": op.get("target")
            })
    return branches

def find_comparison_constants(bytecode):
    """Find constants and parameter comparisons in branches."""
    constants, param_comparisons = {}, {}
    
    for i, op in enumerate(bytecode):
        if op.get("opr") not in ["ifz", "if"] or i < 1:
            continue
            
        offset = op.get("offset")
        prev_op = bytecode[i - 1]
        
        # Check for constant push
        if prev_op.get("opr") == "push":
            value = prev_op.get("value", {})
            if value.get("type") == "integer":
                constants[offset] = value.get("value")
        # Check for parameter comparison (two loads)
        elif prev_op.get("opr") == "load" and i >= 2 and bytecode[i - 2].get("opr") == "load":
            param_comparisons[offset] = (bytecode[i - 2].get("index"), prev_op.get("index"))
    
    return constants, param_comparisons

def combine_path_constraints(branches, constants):
    """Combine constraints along execution paths."""
    current_paths = [{"constraints": [], "ranges": []}]
    
    # Mapping of conditions to their constraint pairs (fall_through, branch_taken)
    condition_map = {
        "ge": [("lt", "x < {}"), ("ge", "x >= {}")],
        "lt": [("lt", "x < {}"), ("ge", "x >= {}")],
        "gt": [("gt", "x > {}"), ("le", "x <= {}")],
        "le": [("le", "x <= {}"), ("gt", "x > {}")],
        "eq": [("eq", "x == {}"), ("ne", "x != {}")],
        "ne": [("ne", "x != {}"), ("eq", "x == {}")]
    }
    
    for branch in sorted(branches, key=lambda b: b.get("offset", 0)):
        offset = branch.get("offset")
        condition = branch.get("condition")
        constant = constants.get(offset)
        
        if constant is None or condition not in condition_map:
            continue
            
        new_paths = []
        for path in current_paths:
            for op, constraint_template in condition_map[condition]:
                new_path = path.copy()
                new_path["constraints"] = path["constraints"] + [constraint_template.format(constant)]
                new_path["ranges"] = path["ranges"] + [(op, constant)]
                new_paths.append(new_path)
        
        current_paths = new_paths
    
    return current_paths

def simplify_paths(combined_paths):
    """Remove impossible paths and simplify ranges."""
    feasible_paths = []
    
    for path in combined_paths:
        lower, upper = float('-inf'), float('inf')
        lower_inc, upper_inc = True, False
        equals, not_equals = None, set()
        
        for op, value in path["ranges"]:
            if op == "ge" and value > lower: lower, lower_inc = value, True
            elif op == "gt" and value >= lower: lower, lower_inc = value, False
            elif op == "lt" and value < upper: upper, upper_inc = value, False
            elif op == "le" and value <= upper: upper, upper_inc = value, True
            elif op == "eq": equals = value if equals is None else (None if equals != value else value)
            elif op == "ne": not_equals.add(value)
        
        # Check feasibility
        if equals is not None:
            if equals is None or equals < lower or equals > upper or equals in not_equals:
                continue
            if (equals == lower and not lower_inc) or (equals == upper and not upper_inc):
                continue
            range_str = f"x == {equals}"
            lower = upper = equals
        elif lower >= upper or (lower == upper and not (lower_inc and upper_inc)):
            continue
        else:
            # Format range string
            if lower == float('-inf') and upper == float('inf'):
                range_str = "(-INF, INF)"
            elif lower == float('-inf'):
                range_str = f"(-INF, {upper}{']' if upper_inc else ')'})"
            elif upper == float('inf'):
                range_str = f"{'[' if lower_inc else '('}{lower}, INF)"
            else:
                range_str = f"{'[' if lower_inc else '('}{lower}, {upper}{']' if upper_inc else ')'}"
        
        feasible_paths.append({
            "constraints": path["constraints"],
            "simplified_range": range_str,
            "lower_bound": lower,
            "upper_bound": upper
        })
    
    return feasible_paths

def format_fuzzer_output(feasible_paths):
    """Format output for fuzzer."""
    return [{
        "path_id": i,
        "range": path["simplified_range"],
        "lower_bound": None if path["lower_bound"] == float('-inf') else path["lower_bound"],
        "upper_bound": None if path["upper_bound"] == float('inf') else path["upper_bound"],
        "constraints": path["constraints"]
    } for i, path in enumerate(feasible_paths)]

def analyze(method_id: str) -> dict:
    suite = model.Suite(Path.cwd())
    method = suite.findmethod(jvm.AbsMethodID.decode(method_id))
    bytecode = method["code"]["bytecode"]
    
    branches = find_branches(bytecode)
    constants, param_comparisons = find_comparison_constants(bytecode)
    
    # Handle parameter comparisons
    if param_comparisons:
        return {
            "method": method_id,
            "fuzzer_ranges": [
                {"path_id": i, "description": desc, "example_values": vals}
                for i, (desc, vals) in enumerate([
                    ("param1 < param2", {"param_0": 50, "param_1": 100}),
                    ("param1 == param2", {"param_0": 75, "param_1": 75}),
                    ("param1 > param2", {"param_0": 100, "param_1": 50})
                ])
            ]
        }
    
    # Handle constant comparisons
    combined = combine_path_constraints(branches, constants)
    feasible = simplify_paths(combined)
    
    return {
        "method": method_id,
        "fuzzer_ranges": format_fuzzer_output(feasible)
    }

def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "info":
        print_info()
        return 0
    if len(argv) != 2:
        print("usage: syntactic_analyzer.py <method-id>", file=sys.stderr)
        return 1
    print(json.dumps(analyze(argv[1])))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))