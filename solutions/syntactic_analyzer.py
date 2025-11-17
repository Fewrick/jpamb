import json
import sys
from pathlib import Path

from jpamb import model, jvm


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


def analyze(method_id: str) -> dict:
    suite = model.Suite(Path.cwd())
    abs_id = jvm.AbsMethodID.decode(method_id)
    method = suite.findmethod(abs_id)
    bytecode = method["code"]["bytecode"]
    return {"method": method_id, "has_assertion": has_assertion(bytecode)}


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