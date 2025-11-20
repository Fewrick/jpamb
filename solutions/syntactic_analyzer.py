import json
import sys
from pathlib import Path

from jpamb import model, jvm

# Example run: uv run solutions/syntactic_analyzer.py "jpamb.cases.Loops.testLessOrEqual:(I)Ljava/lang/String;"

def print_info():
    print("Syntactic Assertion Finder")
    print("0.0.1")
    print("Group 17")
    print("syntactic,python")
    print("no")


def has_assertion(bytecode):
    for op in bytecode:
        opr = op.get("opr")
        if opr == "new":
            cls = op.get("class", {})
            name = cls.get("name") if isinstance(cls, dict) else cls
            if name == "java/lang/AssertionError":
                return True
        if opr == "invoke" and "AssertionError" in op.get("method", {}).get("class", {}).get("name", ""):
            return True
    return False

def find_branches(bytecode):
    """Find all branch instructions in bytecode.
    
    Returns a list of branch operations with their offsets and conditions.
    """
    branches = []
    for op in bytecode:
        opr = op.get("opr")
        
        # Single value comparisons (compare with zero)
        if opr == "ifz":
            branches.append({
                "offset": op.get("offset"),
                "type": "conditional_zero",
                "condition": op.get("condition"),
                "target": op.get("target")
            })
        
        # Two value comparisons
        elif opr == "if":
            branches.append({
                "offset": op.get("offset"),
                "type": "conditional_compare",
                "condition": op.get("condition"),
                "target": op.get("target")
            })
        
        # Unconditional jumps
        elif opr == "goto":
            branches.append({
                "offset": op.get("offset"),
                "type": "unconditional",
                "target": op.get("target")
            })
        
        # Switch statements
        elif opr in ["tableswitch", "lookupswitch"]:
            branches.append({
                "offset": op.get("offset"),
                "type": "switch",
                "targets": op.get("targets", []),
                "default": op.get("default")
            })
    
    return branches

def get_method_params(method):
    """Extract parameter types from method signature.
    
    Returns a list of parameter types.
    """
    params = method.get("params", [])
    param_types = []
    
    for param in params:
        param_type = param.get("type", {})
        if isinstance(param_type, dict):
            base_type = param_type.get("base")
            if base_type:
                param_types.append(base_type)
        else:
            param_types.append(str(param_type))
    
    return param_types

def find_comparison_constants(bytecode):
    """Find constant values used in comparisons.
    
    Returns a dict mapping branch offsets to the constants they compare against.
    """
    constants = {}
    
    for i, op in enumerate(bytecode):
        # Look for conditional branches
        if op.get("opr") in ["ifz", "if"]:
            branch_offset = op.get("offset")
            
            # For "if" (two-value comparison), constant is usually 2 instructions back
            # For "ifz" (compare with zero), constant is 1 instruction back
            if op.get("opr") == "if" and i >= 1:
                # Look back for the push instruction
                prev_op = bytecode[i - 1]
                if prev_op.get("opr") == "push":
                    value = prev_op.get("value", {})
                    if value.get("type") == "integer":
                        constants[branch_offset] = value.get("value")
            
            elif op.get("opr") == "ifz" and i > 0:
                prev_op = bytecode[i - 1]
                if prev_op.get("opr") == "push":
                    value = prev_op.get("value", {})
                    if value.get("type") == "integer":
                        constants[branch_offset] = value.get("value")
    
    return constants

def combine_path_constraints(branches, constants):
    """Combine constraints along execution paths.
    
    Returns a list of complete paths through the code with their combined constraints.
    """
    paths = []
    
    # Sort branches by offset to process them in order
    sorted_branches = sorted(branches, key=lambda b: b.get("offset", 0))
    
    # Start with an initial path with no constraints
    current_paths = [{"constraints": [], "ranges": []}]
    
    for branch in sorted_branches:
        offset = branch.get("offset")
        condition = branch.get("condition")
        constant = constants.get(offset)
        
        if constant is not None and condition and branch.get("type") in ["conditional_compare", "conditional_zero"]:
            new_paths = []
            
            for path in current_paths:
                # Handle different conditions
                if condition == "ge":
                    # Branch NOT taken (fall through): x < constant
                    fall_through = path.copy()
                    fall_through["constraints"] = path["constraints"] + [f"x < {constant}"]
                    fall_through["ranges"] = path["ranges"] + [("lt", constant)]
                    new_paths.append(fall_through)
                    
                    # Branch taken: x >= constant
                    branch_taken = path.copy()
                    branch_taken["constraints"] = path["constraints"] + [f"x >= {constant}"]
                    branch_taken["ranges"] = path["ranges"] + [("ge", constant)]
                    new_paths.append(branch_taken)
                
                elif condition == "lt":
                    # Branch taken: x < constant
                    branch_taken = path.copy()
                    branch_taken["constraints"] = path["constraints"] + [f"x < {constant}"]
                    branch_taken["ranges"] = path["ranges"] + [("lt", constant)]
                    new_paths.append(branch_taken)
                    
                    # Branch NOT taken (fall through): x >= constant
                    fall_through = path.copy()
                    fall_through["constraints"] = path["constraints"] + [f"x >= {constant}"]
                    fall_through["ranges"] = path["ranges"] + [("ge", constant)]
                    new_paths.append(fall_through)
                
                elif condition == "eq":
                    # Branch taken: x == constant
                    branch_taken = path.copy()
                    branch_taken["constraints"] = path["constraints"] + [f"x == {constant}"]
                    branch_taken["ranges"] = path["ranges"] + [("eq", constant)]
                    new_paths.append(branch_taken)
                    
                    # Branch NOT taken (fall through): x != constant
                    fall_through = path.copy()
                    fall_through["constraints"] = path["constraints"] + [f"x != {constant}"]
                    fall_through["ranges"] = path["ranges"] + [("ne", constant)]
                    new_paths.append(fall_through)
                
                elif condition == "ne":
                    # Branch taken: x != constant
                    branch_taken = path.copy()
                    branch_taken["constraints"] = path["constraints"] + [f"x != {constant}"]
                    branch_taken["ranges"] = path["ranges"] + [("ne", constant)]
                    new_paths.append(branch_taken)
                    
                    # Branch NOT taken (fall through): x == constant
                    fall_through = path.copy()
                    fall_through["constraints"] = path["constraints"] + [f"x == {constant}"]
                    fall_through["ranges"] = path["ranges"] + [("eq", constant)]
                    new_paths.append(fall_through)
                
                elif condition == "le":
                    # Branch taken: x <= constant
                    branch_taken = path.copy()
                    branch_taken["constraints"] = path["constraints"] + [f"x <= {constant}"]
                    branch_taken["ranges"] = path["ranges"] + [("le", constant)]
                    new_paths.append(branch_taken)
                    
                    # Branch NOT taken: x > constant
                    fall_through = path.copy()
                    fall_through["constraints"] = path["constraints"] + [f"x > {constant}"]
                    fall_through["ranges"] = path["ranges"] + [("gt", constant)]
                    new_paths.append(fall_through)
                
                elif condition == "gt":
                    # Branch taken: x > constant
                    branch_taken = path.copy()
                    branch_taken["constraints"] = path["constraints"] + [f"x > {constant}"]
                    branch_taken["ranges"] = path["ranges"] + [("gt", constant)]
                    new_paths.append(branch_taken)
                    
                    # Branch NOT taken: x <= constant
                    fall_through = path.copy()
                    fall_through["constraints"] = path["constraints"] + [f"x <= {constant}"]
                    fall_through["ranges"] = path["ranges"] + [("le", constant)]
                    new_paths.append(fall_through)
            
            current_paths = new_paths
    
    return current_paths

def simplify_paths(combined_paths):
    """Remove impossible paths and simplify constraint ranges.
    
    Returns only feasible paths with simplified range notation.
    """
    feasible_paths = []
    
    for path in combined_paths:
        ranges = path["ranges"]
        
        # Extract bounds and equality constraints
        lower_bound = float('-inf')
        upper_bound = float('inf')
        lower_inclusive = True
        upper_inclusive = False
        equals = None
        not_equals = set()
        is_feasible = True
        
        for op, value in ranges:
            if op == "ge":
                if value > lower_bound:
                    lower_bound = value
                    lower_inclusive = True
            elif op == "gt":
                if value >= lower_bound:
                    lower_bound = value
                    lower_inclusive = False
            elif op == "lt":
                if value < upper_bound:
                    upper_bound = value
                    upper_inclusive = False
            elif op == "le":
                if value <= upper_bound:
                    upper_bound = value
                    upper_inclusive = True
            elif op == "eq":
                if equals is not None and equals != value:
                    is_feasible = False  # Can't equal two different values
                equals = value
            elif op == "ne":
                not_equals.add(value)
        
        # Check if equality constraint conflicts with range
        if equals is not None:
            if equals < lower_bound or equals > upper_bound:
                is_feasible = False
            elif equals == lower_bound and not lower_inclusive:
                is_feasible = False
            elif equals == upper_bound and not upper_inclusive:
                is_feasible = False
            if equals in not_equals:
                is_feasible = False
        
        # Check if path is feasible
        if lower_bound > upper_bound:
            is_feasible = False
        elif lower_bound == upper_bound and not (lower_inclusive and upper_inclusive):
            is_feasible = False
        
        if is_feasible:
            # Format the range nicely
            if equals is not None:
                range_str = f"x == {equals}"
                lower_bound = equals
                upper_bound = equals
            elif lower_bound == float('-inf') and upper_bound == float('inf'):
                range_str = "(-INF, INF)"
            elif lower_bound == float('-inf'):
                bracket = "]" if upper_inclusive else ")"
                range_str = f"(-INF, {upper_bound}{bracket}"
            elif upper_bound == float('inf'):
                bracket = "[" if lower_inclusive else "("
                range_str = f"{bracket}{lower_bound}, INF)"
            else:
                left_bracket = "[" if lower_inclusive else "("
                right_bracket = "]" if upper_inclusive else ")"
                range_str = f"{left_bracket}{lower_bound}, {upper_bound}{right_bracket}"
            
            feasible_paths.append({
                "constraints": path["constraints"],
                "simplified_range": range_str,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound
            })
    
    return feasible_paths

def format_fuzzer_output(feasible_paths):
    """Format the output in a fuzzer-friendly way.
    
    Returns ranges that the fuzzer should explore.
    """
    fuzzer_ranges = []
    
    for i, path in enumerate(feasible_paths):
        lower = path["lower_bound"]
        upper = path["upper_bound"]
        
        range_info = {
            "path_id": i,
            "range": path["simplified_range"],
            "lower_bound": None if lower == float('-inf') else lower,
            "upper_bound": None if upper == float('inf') else upper,
            "constraints": path["constraints"]
        }
        
        fuzzer_ranges.append(range_info)
    
    return fuzzer_ranges

def analyze(method_id: str) -> dict:
    suite = model.Suite(Path.cwd())
    abs_id = jvm.AbsMethodID.decode(method_id)
    method = suite.findmethod(abs_id)
    bytecode = method["code"]["bytecode"]
    branches = find_branches(bytecode)
    params = get_method_params(method)
    constants = find_comparison_constants(bytecode)
    combined_paths = combine_path_constraints(branches, constants)
    feasible_paths = simplify_paths(combined_paths)
    fuzzer_ranges = format_fuzzer_output(feasible_paths)
    return {
        "method": method_id,
        #"has_assertion": has_assertion(bytecode),
        #"branches": branches,
        #"params": params,
        #"feasible_paths": feasible_paths,
        "fuzzer_ranges": fuzzer_ranges
    }


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "info":
        print_info()
        return 0
    if len(argv) != 2:
        print("usage: syntactic_analyzer.py <method-id>", file=sys.stderr)
        return 1
    result = analyze(argv[1])
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))