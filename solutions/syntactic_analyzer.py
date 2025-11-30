import json
import sys
from pathlib import Path

from jpamb import model, jvm

def print_info():
    print("Syntactic Assertion Finder\n0.0.1\nGroup 17\nsyntactic,python\nno")

def get_parameter_count(method_id: str) -> int:
    """Extract parameter count from method signature."""
    # Method ID format: "class.method:(params)return"
    # Example: "jpamb.cases.Loops.averageCategory:(III)Ljava/lang/String;"
    
    if ":" not in method_id:
        return 0
    
    params_part = method_id.split(":")[1].split(")")[0]
    if params_part == "(":
        return 0
    
    # Count parameter types
    count = 0
    i = 1  # Skip opening '('
    while i < len(params_part):
        char = params_part[i]
        if char in ['I', 'Z', 'F', 'D', 'J', 'S', 'B', 'C']:  # Primitive types
            count += 1
            i += 1
        elif char == 'L':  # Object type
            count += 1
            # Skip until ';'
            while i < len(params_part) and params_part[i] != ';':
                i += 1
            i += 1
        elif char == '[':  # Array type
            i += 1
        else:
            i += 1
    
    return count

def get_parameter_types(method_id: str) -> list[str]:
    """Extract parameter types from method signature."""
    
    if ":" not in method_id:
        return []
    
    params_part = method_id.split(":")[1].split(")")[0]
    if params_part == "(":
        return []
    
    param_types = []
    i = 1  # Skip opening '('
    while i < len(params_part):
        char = params_part[i]
        if char in ['I', 'Z', 'F', 'D', 'J', 'S', 'B', 'C']:
            param_types.append(char)
            i += 1
        elif char == 'L':  # Object type
            start = i
            while i < len(params_part) and params_part[i] != ';':
                i += 1
            param_types.append(params_part[start:i+1]) 
            i += 1
        elif char == '[':  # Array type
            start = i
            i += 1
            if i < len(params_part) and params_part[i] == 'L':
                while i < len(params_part) and params_part[i] != ';':
                    i += 1
                i += 1
            else:
                i += 1
            param_types.append(params_part[start:i])
        else:
            i += 1
    
    return param_types

def find_comparison_constants(bytecode):
    constants = []
    for i, op in enumerate(bytecode):
        opr = op.get("opr")
        if opr not in ["ifz", "if"] or i < 1:
            continue

        # check prev, and prev2 if needed
        for k in (1, 2):
            if i - k < 0: 
                continue
            prev_op = bytecode[i - k]
            if prev_op.get("opr") == "push":
                value = prev_op.get("value", {})
                t = value.get("type")
                if t in ("integer", "float"):
                    val = value.get("value")
                    if t == "integer" and 32 <= val <= 126:
                        constants.append(chr(val))
                    constants.append(val)
                break  

        if opr == "ifz":
            constants.append(0)

    return constants

def find_parameter_comparisons(bytecode):
    """Detect if parameters are compared to each other."""
    for i, op in enumerate(bytecode):
        if op.get("opr") == "if" and i >= 2:
            prev1 = bytecode[i - 1]
            prev2 = bytecode[i - 2]
            if prev1.get("opr") == "load" and prev2.get("opr") == "load":
                return True
    return False

def detect_null_checks(bytecode):
    """Detect if the method checks for null references."""
    for i, op in enumerate(bytecode):
        if op.get("opr") == "ifz" and i >= 1:
            condition = op.get("condition")
            if condition in ("is", "isnot"):
                # Check if previous operation was loading a reference
                prev_op = bytecode[i - 1]
                if prev_op.get("opr") == "load" and prev_op.get("type") == "ref":
                    return True
    return False

def find_string_constants(bytecode):
    """Find string constants used in equals() comparisons."""
    string_constants = []
    
    for i, op in enumerate(bytecode):
        if op.get("opr") == "invoke" and op.get("access") == "virtual":
            method = op.get("method", {})
            method_name = method.get("name", "")
            
            if method_name == "equals":
                for j in range(max(0, i - 3), i):
                    prev_op = bytecode[j]
                    if prev_op.get("opr") == "push":
                        value = prev_op.get("value", {})
                        if value.get("type") == "string":
                            string_val = value.get("value")
                            if "must not be null" not in string_val and "does not match" not in string_val:
                                if string_val not in string_constants:
                                    string_constants.append(string_val)
    
    return string_constants
def detect_array_info(bytecode):
    """Detect array patterns: max index, element values, and length requirements."""
    max_index = -1
    element_values = {}
    length_req = None
    
    for i, op in enumerate(bytecode):
        # Detect array[index] access
        if op.get("opr") == "array_load" and i >= 1:
            prev = bytecode[i - 1]
            if prev.get("opr") == "push" and prev.get("value", {}).get("type") == "integer":
                idx = prev["value"]["value"]
                max_index = max(max_index, idx)
                
                # Check if followed by comparison (array[i] == value)
                if i + 2 < len(bytecode):
                    next_op = bytecode[i + 1]
                    cmp_op = bytecode[i + 2]
                    if next_op.get("opr") == "push" and cmp_op.get("opr") == "if":
                        val = next_op["value"]["value"]
                        element_values[idx] = chr(val) if 32 <= val <= 126 else val
        
        # Detect array.length checks
        if op.get("opr") == "arraylength" and i + 1 < len(bytecode):
            next_op = bytecode[i + 1]
            if next_op.get("opr") == "ifz":
                length_req = (0, next_op.get("condition", ""))
            elif next_op.get("opr") == "push" and i + 2 < len(bytecode):
                cmp_op = bytecode[i + 2]
                if cmp_op.get("opr") == "if":
                    length_req = (next_op["value"]["value"], cmp_op.get("condition", ""))
    
    return max_index, element_values, length_req

def generate_array_values(param_type, max_index, element_values, length_req, constants=None):
    """Generate array test values."""
    results = []
    
    # Char array with specific elements
    if '[C' in param_type and element_values:
        chars = [f"'{element_values.get(i, '?')}'" for i in range(max(element_values.keys()) + 1)]
        results.append(f"[C: {', '.join(chars)}]")
        results.append("[C: ]")
        return results
    
    # Int array with specific elements
    if '[I' in param_type:
        if element_values:
            ints = [element_values.get(i, 0) for i in range(max(element_values.keys()) + 1)]
            results.append(f"[I: {', '.join(map(str, ints))}]")
        elif max_index >= 0:
            results.append(f"[I: {', '.join(map(str, range(max_index + 1)))}]")
        elif length_req and length_req[1] in ("gt", "ne"):
            results.append(f"[I: 0]")  # Non-empty
        elif constants:
            int_constants = [c for c in constants if isinstance(c, int) and c > 10]
            if int_constants:
                target = max(int_constants)
                val = (target // 2) + 1
                results.append(f"[I: {val}, {val}, {val}]")
        results.append("[I: ]")
        return results
    
    return results

def generate_test_values(constants, string_constants, has_param_comparison, param_count, param_types):
    """Generate concrete test values for the fuzzer."""
    
    has_null_check = any(pt in ('Ljava/lang/String;', 'L') or '[' in pt for pt in param_types)
    
    if param_types and 'String' in str(param_types):
        chars = [c for c in constants if isinstance(c, str) and len(c) == 1]
        strings = string_constants if string_constants else []
        
        if chars and strings:
            result = []
            char_prefix = ''.join(chars)
            for s in strings:
                result.append(char_prefix + s)
            if has_null_check:
                result.append("null")
            return result
        elif chars:
            result = string_constants.copy() if string_constants else []
            combined = ''.join(chars)
            if combined:
                result.append(combined)
            return result
    
    if string_constants:
        return string_constants
    
    if param_types and all('String' in pt for pt in param_types) and not string_constants:
        if not constants:
            return []
        small_cs = sorted({c for c in constants if isinstance(c, int) and 0 <= c <= 20})
        if not small_cs:
            return []
        vals = []
        for c in small_cs:
            for L in [max(0, c-1), c, c+1]:
                vals.append("a" * L)
        return sorted(set(vals), key=len)
    
    # params are float/double, do float boundaries no matter how constants are typed
    if any(pt in ("F", "D") for pt in param_types):
        if not constants:
            return []
        nums = sorted(set(float(c) for c in constants))
        out = []
        for c in nums:
            out.extend([c - 0.5, c, c + 0.5])
        return sorted(set(out))
    
    # Handle parameter comparisons (2 parameters)
    if has_param_comparison:
        if constants:
            unique_constants = sorted(set(constants))
            max_c = max(unique_constants)
            return [[max_c - 1, max_c - 1], [max_c, max_c], [max_c + 1, max_c + 1],
                    [max_c + 1, max_c + 10], [max_c + 5, max_c + 5], [max_c + 10, max_c + 1]]
        else:
            return [[50, 100], [75, 75], [100, 50]]
    
    # Handle integer ranges
    if constants:
        unique_constants = sorted(set(constants))
        
        if any(isinstance(c, float) for c in unique_constants):
            result = []
            for c in unique_constants:
                if isinstance(c, float):
                    result.extend([c - 0.5, c, c + 0.5])
            return sorted(set(result))

        # For methods with 3+ parameters, generate complete test cases
        if param_count >= 3:
            test_cases = []
            for c in unique_constants:
                below_val = c - 2
                test_cases.append([below_val] * param_count)
                test_cases.append([c] * param_count)
                above_val = c + 2
                test_cases.append([above_val] * param_count)
            return test_cases
        
        # For single parameter methods
        if len(unique_constants) == 1:
            c = unique_constants[0]
            return [c - 1, c, c + 1]
        else:
            result = []
            for c in unique_constants:
                result.extend([c - 1, c, c + 1])
            return sorted(set(result))
    
    return []

def analyze(method_id: str) -> dict:
    suite = model.Suite(Path.cwd())
    
    # NEW: Workaround for char array parsing bug
    try:
        method = suite.findmethod(jvm.AbsMethodID.decode(method_id))
    except AssertionError:
        if '[C' in method_id:
            import json
            class_name = method_id.split(':')[0].rsplit('.', 1)[0].replace('.', '/')
            method_name = method_id.split(':')[0].rsplit('.', 1)[1]
            class_file = Path.cwd() / "target" / "decompiled" / f"{class_name}.json" 
            with open(class_file) as f:
                class_data = json.load(f)
            for m in class_data['methods']:
                if m['name'] == method_name:
                    method = m
                    break
        else:
            raise
    
    bytecode = method["code"]["bytecode"]
    param_count = get_parameter_count(method_id)
    param_types = get_parameter_types(method_id)
    
    max_index, element_values, length_req = detect_array_info(bytecode)
    if any('[' in pt for pt in param_types):
        constants = find_comparison_constants(bytecode)  # NEW: get constants for arrays too
        test_values = generate_array_values(param_types[0], max_index, element_values, length_req, constants)  # NEW: pass constants
    else:
        constants = find_comparison_constants(bytecode)
        string_constants = find_string_constants(bytecode)
        has_param_comparison = find_parameter_comparisons(bytecode)
        test_values = generate_test_values(constants, string_constants, has_param_comparison, 
                                          param_count, param_types)
    
    return {"method": method_id, "values": test_values}

def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "info":
        print_info()
        return 0
    if len(argv) != 2:
        print("usage: syntactic_analyzer.py <method-id>", file=sys.stderr)
        return 1
    print(json.dumps(analyze(argv[1]), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))