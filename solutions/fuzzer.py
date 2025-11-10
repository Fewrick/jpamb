import random
import jpamb
from jpamb import jvm

def random_input(types: list[str]):
    values = []
    for t in types:
        if t == "int":
            values.append(jvm.Value.int(random.randint(-10, 10)))
        elif t == "boolean":
            values.append(jvm.Value.int(random.randint(0, 1)))
        else:
            raise NotImplementedError(t)
    return values

def run_case(methodid, input_values):
    frame = Frame.from_method(methodid)
    for i, v in enumerate(input_values):
        frame.locals[i] = v
    state = State({}, Stack.empty().push(frame))
    
    covered = set()
    
    for _ in range(1000):
        if isinstance(state, str):
            return covered, state
        # track branch coverage
        frame = state.frames.peek()
        covered.add((frame.pc.method, frame.pc.offset))
        state = step(state)
    
    return covered, "ok"

# Example fuzzing loop
method_types = ["int", "int"]  # adjust per method
coverage_map = set()
for i in range(1000):
    inp = random_input(method_types)
    covered, result = run_case(methodid, inp)
    coverage_map |= covered
    print(f"Run {i}: {result}, total branches hit: {len(coverage_map)}")
