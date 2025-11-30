import json
import sys
from pathlib import Path
from jpamb import model, jvm

def print_info():
    print("Syntactic Assertion Finder\n0.0.1\nGroup 17\nsyntactic,python\nno")

def parse_method_signature(method_id: str) -> tuple[int, list[str]]:
    """Extract parameter count and types from method signature."""
    if ":" not in method_id:
        return 0, []
    
    params_part = method_id.split(":")[1].split(")")[0][1:]
    if not params_part:
        return 0, []
    
    param_types = []
    i = 0
    while i < len(params_part):
        if params_part[i] in 'IZFDJSBC':
            param_types.append(params_part[i])
            i += 1
        elif params_part[i] == 'L':
            end = params_part.index(';', i) + 1
            param_types.append(params_part[i:end])
            i = end
        elif params_part[i] == '[':
            start = i
            i += 1
            if i < len(params_part) and params_part[i] == 'L':
                i = params_part.index(';', i) + 1
            else:
                i += 1
            param_types.append(params_part[start:i])
        else:
            i += 1
    
    return len(param_types), param_types

def extract_constants(bytecode, param_count):
    """Extract constants, strings, and detection flags from bytecode."""
    constants = []
    string_constants = []
    all_strings = []
    has_param_comparison = False
    has_null_check = False
    string_transform = None
    
    # Collect all pushed strings
    for op in bytecode:
        if op.get("opr") == "push":
            val = op.get("value")
            if val and val.get("type") == "string":
                s = val["value"]
                if not any(kw in s.lower() for kw in ["must not", "does not match", "invalid", "error", "expected", "unexpected"]):
                    all_strings.append(s)
    
    # Analyze operations
    for i, op in enumerate(bytecode):
        opr = op.get("opr")
        
        # Find comparison constants
        if opr in ("ifz", "if"):
            # Look back for pushed constants
            for k in (1, 2):
                if i >= k:
                    prev = bytecode[i - k]
                    if prev.get("opr") == "push":
                        val_info = prev.get("value", {})
                        if val_info.get("type") in ("integer", "float"):
                            val = val_info["value"]
                            constants.append(val)
                            if val_info["type"] == "integer" and 32 <= val <= 126:
                                constants.append(chr(val))
                        break
            
            # ifz implies comparison with 0
            if opr == "ifz":
                constants.append(0)
                # Detect null checks
                if i >= 1 and op.get("condition") in ("is", "isnot"):
                    if bytecode[i - 1].get("opr") == "load" and bytecode[i - 1].get("type") == "ref":
                        has_null_check = True
            
            # Detect parameter comparisons
            elif i >= 2:
                prev1, prev2 = bytecode[i - 1], bytecode[i - 2]
                if prev1.get("opr") == "load" and prev2.get("opr") == "load":
                    idx1, idx2 = prev1.get("index", -1), prev2.get("index", -1)
                    if idx1 != idx2 and 0 <= idx1 < param_count and 0 <= idx2 < param_count:
                        has_param_comparison = True
        
        # Detect string transformations and equals() calls
        elif opr == "invoke" and op.get("access") == "virtual":
            method_name = op.get("method", {}).get("name", "")
            
            if method_name == "toUpperCase":
                string_transform = "uppercase"
            elif method_name == "toLowerCase":
                string_transform = "lowercase"
            elif method_name == "equals":
                for j in range(max(0, i - 10), i):
                    val = bytecode[j].get("value", {})
                    if bytecode[j].get("opr") == "push" and val.get("type") == "string":
                        s = val["value"]
                        if s not in string_constants and not any(kw in s.lower() for kw in ["must not", "does not match", "invalid", "error", "expected", "unexpected"]):
                            string_constants.append(s)
    
    if string_transform and all_strings:
        string_constants = all_strings
    
    return constants, string_constants, has_param_comparison, has_null_check, string_transform

def extract_array_info(bytecode):
    """Extract array access patterns."""
    max_index = -1
    element_values = {}
    length_req = None
    
    for i, op in enumerate(bytecode):
        # Array element access
        if op.get("opr") == "array_load" and i >= 1:
            prev = bytecode[i - 1]
            if prev.get("opr") == "push" and prev.get("value", {}).get("type") == "integer":
                idx = prev["value"]["value"]
                max_index = max(max_index, idx)
                
                # Check for element value comparison
                if i + 2 < len(bytecode):
                    next_op, cmp_op = bytecode[i + 1], bytecode[i + 2]
                    if next_op.get("opr") == "push" and cmp_op.get("opr") == "if":
                        val = next_op["value"]["value"]
                        element_values[idx] = chr(val) if 32 <= val <= 126 else val
        
        # Array length checks
        if op.get("opr") == "arraylength" and i + 1 < len(bytecode):
            next_op = bytecode[i + 1]
            if next_op.get("opr") == "ifz":
                length_req = (0, next_op.get("condition", ""))
            elif next_op.get("opr") == "push" and i + 2 < len(bytecode):
                cmp = bytecode[i + 2]
                if cmp.get("opr") == "if":
                    length_req = (next_op["value"]["value"], cmp.get("condition", ""))
    
    return max_index, element_values, length_req

def has_parameter_usage(bytecode, param_count):
    """Check if any parameters are actually used in the bytecode."""
    if param_count == 0:
        return False
    
    for op in bytecode:
        if op.get("opr") == "load" and 0 <= op.get("index", -1) < param_count:
            return True
    
    return False

def generate_values(param_types, constants, string_constants, has_param_comparison, 
                    string_transform=None, max_index=-1, element_values=None, 
                    length_req=None, bytecode=None):
    """Generate test values based on analysis."""
    param_count = len(param_types)

    # Handle booleans
    if param_types and 'Z' in param_types[0]:
        return [False, True]
    
    # Handle arrays
    if param_types and '[' in param_types[0]:
        results = []
        if '[C' in param_types[0] and element_values:
            chars = [f"'{element_values.get(i, '?')}'" for i in range(max(element_values.keys()) + 1)]
            results.append(f"[C: {', '.join(chars)}]")
        elif '[I' in param_types[0]:
            if element_values:
                ints = [element_values.get(i, 0) for i in range(max(element_values.keys()) + 1)]
                results.append(f"[I: {', '.join(map(str, ints))}]")
            elif max_index >= 0:
                results.append(f"[I: {', '.join(map(str, range(max_index + 1)))}]")
            elif length_req and length_req[1] in ("gt", "ne"):
                results.append("[I: 0]")
            elif constants:
                int_constants = [c for c in constants if isinstance(c, int) and c > 10]
                if int_constants:
                    val = max(int_constants) // 2 + 1
                    results.append(f"[I: {val}, {val}, {val}]")
        results.append(f"[{param_types[0][1]}: ]")
        return results
    
    # Handle strings
    if any('String' in str(pt) for pt in param_types):
        chars = [c for c in constants if isinstance(c, str) and len(c) == 1]
        
        # Handle uppercase/lowercase transformations
        if string_transform and string_constants:
            test_values = []
            for s in string_constants:
                if string_transform == "uppercase":
                    test_values.append(s.upper())
                    test_values.append(s.lower())
                elif string_transform == "lowercase":
                    test_values.append(s.lower())
                    test_values.append(s.upper())
            return test_values
        
        # Check for alternating letter-digit pattern
        if '0' in chars and '9' in chars:
            int_constants = [c for c in constants if isinstance(c, int) and 0 < c < 30]
            if int_constants:
                target_sum = max(int_constants)
                result = ""
                
                if target_sum >= 3:
                    digits_needed = [1, 2, target_sum - 3]
                else:
                    digits_needed = [target_sum]
                
                for i, digit in enumerate(digits_needed):
                    result += chr(ord('a') + i)
                    result += str(digit)
                
                return [result]
        
        # Build string by interleaving characters with strings
        if chars and string_constants:
            result = ""
            char_idx = 0
            strings_to_match = [s for s in string_constants if s and s[0] in chars]
            strings_no_match = [s for s in string_constants if not s or s[0] not in chars]
            
            for s in sorted(strings_to_match, key=lambda x: chars.index(x[0])):
                while char_idx < len(chars) and chars[char_idx] != s[0]:
                    result += chars[char_idx]
                    char_idx += 1
                result += s
                char_idx += 1
            
            while char_idx < len(chars):
                result += chars[char_idx]
                char_idx += 1
            
            for s in strings_no_match:
                result += s
            
            return [result] if result else string_constants
        
        if chars:
            result = string_constants.copy() if string_constants else []
            combined = ''.join(chars)
            if combined and combined not in result:
                result.append(combined)
            return result
        
        if string_constants:
            return string_constants
        
        return ["", "test"]
    
    # Handle floats
    if any(pt in ("F", "D") for pt in param_types):
        if constants:
            nums = sorted(set(float(c) for c in constants))
            return sorted(set(v for n in nums for v in [n - 0.5, n, n + 0.5]))
    
    # Handle parameter comparisons
    if has_param_comparison and constants:
        max_c = max(constants)
        return [[max_c + d1, max_c + d2] for d1, d2 in [(-1, -1), (0, 0), (1, 1), (1, 10), (5, 5), (10, 1)]]
    
    # Check param_count FIRST
    if param_count == 0:
        return []
    
    # Handle integers with constants
    if constants:
        unique = sorted(set(constants))
        
        if param_count >= 3:
            return [[c + d] * param_count for c in unique for d in [-2, 0, 2]]
        
        if len(unique) == 1:
            return [unique[0] + d for d in [-1, 0, 1]]
        
        return sorted(set(v for c in unique for v in [c - 1, c, c + 1]))
    
    # Fallback for methods with parameters but no constants
    if param_count == 1:
        return [0, 1]
    else:
        if bytecode and has_parameter_usage(bytecode, param_count):
            return [[0, 0], [0, 1], [1, 0], [1, 1]]
        else:
            return [[1, 2]]

def analyze(method_id: str):
    """Analyze a method and generate test values."""
    suite = model.Suite(Path.cwd())
    
    # Load method
    try:
        method = suite.findmethod(jvm.AbsMethodID.decode(method_id))
    except AssertionError:
        if '[C' in method_id:
            class_name = method_id.split(':')[0].rsplit('.', 1)[0].replace('.', '/')
            method_name = method_id.split(':')[0].rsplit('.', 1)[1]
            with open(Path.cwd() / "target" / "decompiled" / f"{class_name}.json") as f:
                for m in json.load(f)['methods']:
                    if m['name'] == method_name:
                        method = m
                        break
        else:
            raise
    
    bytecode = method["code"]["bytecode"]
    param_count, param_types = parse_method_signature(method_id)
    constants, string_constants, has_param_comparison, has_null_check, string_transform = extract_constants(bytecode, param_count)
    
    if any('[' in pt for pt in param_types):
        max_idx, elem_vals, len_req = extract_array_info(bytecode)
        test_values = generate_values(param_types, constants, string_constants, 
                                      has_param_comparison, string_transform, 
                                      max_idx, elem_vals, len_req, bytecode)
    else:
        test_values = generate_values(param_types, constants, string_constants, 
                                      has_param_comparison, string_transform, 
                                      bytecode=bytecode)
    
    return {"method": method_id, "values": test_values}

def main(argv):
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