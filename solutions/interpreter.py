import jpamb
from jpamb import jvm
from dataclasses import dataclass, field
import sys

import sys
from loguru import logger

from jpamb.jvm.base import Value

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}")

methodid, input = jpamb.getcase()

trace = set()

# ┌ Case jpamb.cases.Simple.checkBeforeDivideByN2:(0) -> ok ------------------- This one is nor working anymore
# uv run solutions/interpreter.py "jpamb.cases.Simple.checkBeforeDivideByN2:(I)I" "(0)"


@dataclass
class PC:
    method: jvm.AbsMethodID
    offset: int

    def __iadd__(self, delta):
        self.offset += delta
        return self

    def __add__(self, delta):
        return PC(self.method, self.offset + delta)

    def __str__(self):
        return f"{self.method}:{self.offset}"


@dataclass
class Bytecode:
    suite: jpamb.Suite
    methods: dict[jvm.AbsMethodID, list[jvm.Opcode]]

    def __getitem__(self, pc: PC) -> jvm.Opcode:
        try:
            opcodes = self.methods[pc.method]
        except KeyError:
            opcodes = list(self.suite.method_opcodes(pc.method))
            self.methods[pc.method] = opcodes

        return opcodes[pc.offset]


@dataclass
class Stack[T]:
    items: list[T]

    def __bool__(self) -> bool:
        return len(self.items) > 0

    @classmethod
    def empty(cls):
        return cls([])

    def peek(self) -> T:
        return self.items[-1]

    def pop(self) -> T:
        return self.items.pop(-1)

    def push(self, value):
        self.items.append(value)
        return self

    def __str__(self):
        if not self:
            return "ϵ"
        return "".join(f"{v}" for v in self.items)


suite = jpamb.Suite()
bc = Bytecode(suite, dict())


@dataclass
class Frame:
    locals: dict[int, jvm.Value]
    stack: Stack[jvm.Value]
    pc: PC

    def __str__(self):
        locals = ", ".join(f"{k}:{v}" for k, v in sorted(self.locals.items()))
        return f"<{{{locals}}}, {self.stack}, {self.pc}>"

    def from_method(method: jvm.AbsMethodID) -> "Frame":
        return Frame({}, Stack.empty(), PC(method, 0))


@dataclass
class State:
    heap: dict[int, jvm.Value]
    frames: Stack[Frame]

    def __str__(self):
        return f"{self.heap} {self.frames}"


def step(state: State) -> State | str:
    assert isinstance(state, State), f"expected frame but got {state}"
    frame = state.frames.peek()
    opr = bc[frame.pc]
    
    trace.add(str(frame.pc))

    logger.debug(f"STEP {opr}\n{state}")
    match opr:
        case jvm.Push(value=v):
            frame.stack.push(v)
            frame.pc += 1
            return state
        
        case jvm.Load(type=jvm.Int(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        
        case jvm.Load(type=jvm.Float(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Div): # Binary Division
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            # assert v2.value > 0, "Helooooo we need to do something here!!!"
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"
            if v2.value == 0:
                return "divide by zero"

            frame.stack.push(jvm.Value.int(v1.value // v2.value))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Sub): # Binary subtraction
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"
            frame.stack.push(jvm.Value.int(v1.value - v2.value))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Add): # Binary addition
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            logger.debug(f"{v1} + {v2}")


            try:
                result = v1.value + v2.value
            except Exception as e:
                return "assertion error"

            frame.stack.push(jvm.Value.int(result))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Mul): # Binary multiplication
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"
            frame.stack.push(jvm.Value.int(v1.value * v2.value))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Rem): # Binary remainder
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"
            if v2.value == 0:
                return "divide by zero"
            frame.stack.push(jvm.Value.int(v1.value % v2.value))
            frame.pc += 1
            return state
        
        case jvm.Binary(type=jvm.Float(), operant=jvm.BinaryOpr.Add):  # Float addition
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            frame.stack.push(jvm.Value.float(v1.value + v2.value))
            frame.pc += 1
            return state

        case jvm.Binary(type=jvm.Float(), operant=jvm.BinaryOpr.Sub):  # Float subtraction
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            frame.stack.push(jvm.Value.float(v1.value - v2.value))
            frame.pc += 1
            return state

        case jvm.Binary(type=jvm.Float(), operant=jvm.BinaryOpr.Mul):  # Float multiplication
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            frame.stack.push(jvm.Value.float(v1.value * v2.value))
            frame.pc += 1
            return state

        case jvm.Binary(type=jvm.Float(), operant=jvm.BinaryOpr.Div):  # Float division
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            if v2.value == 0.0:
                return "divide by zero"
            frame.stack.push(jvm.Value.float(v1.value / v2.value))
            frame.pc += 1
            return state
        
        case jvm.CompareFloating(type=typ, nan_value=nan_val):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            
            # Compare the two float values
            if v1.value > v2.value:
                result = 1
            elif v1.value < v2.value:
                result = -1
            elif v1.value == v2.value:
                result = 0
            else:
                # One or both are NaN
                result = nan_val
            
            frame.stack.push(jvm.Value.int(result))
            frame.pc += 1
            return state

        case jvm.Return(type=jvm.Int()):
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.stack.push(v1)
                frame.pc += 1
                return state
            else:
                return "ok"
            
        case jvm.Return(type=jvm.Reference()):
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.stack.push(v1)
                frame.pc += 1
                return state
            else:
                if isinstance(v1.type, jvm.String):
                    return v1.value
                elif v1.value in state.heap:
                    obj = state.heap[v1.value]
                    if isinstance(obj, dict) and "java" in obj.get("class", "").lower() and "string" in obj.get("class", "").lower():
                        return obj.get("value", "ok")
                return "ok"
            
        case jvm.Return(type=None):
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.pc += 1
                return state
            else:
                return "ok"
            
        case jvm.Get(static=is_static, field=field):
            logger.debug(f"Get field: {field}, static: {is_static}")
            
            # Handle $assertionsDisabled field
            if "$assertionsDisabled" in str(field):
                frame.stack.push(Value.int(0))  # assertions are enabled
                frame.pc += 1
                return state
            
            if frame.locals and (0 in frame.locals or 1 in frame.locals):
                if frame.locals[0] == Value.int(0):
                    frame.stack.push(Value.int(0))
                    frame.pc += 1
                if frame.locals[0] == Value.int(1):
                    frame.stack.push(Value.int(1))
                    frame.pc += 1
                    return state
                else:
                    return "assertion error"
            else:
                return "assertion error"
            # assert val is True, f"expected boolean, but got {val}"
            # assert val >= 0
            # logger.debug(f"Get static field value: {val}")
            #if val is True:
            #    frame.stack.push(1)
            #else: 
            #    frame.stack.push(0)
            #frame.pc += 1
            #return state
            
            # return f"{val}"
            
        case jvm.Ifz(condition=cond, target=val):
            v = frame.stack.pop()
            if cond == 'eq': # equal to zero
                if v == Value.int(0):
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            elif cond == 'ne': # not equal to zero
                if v != Value.int(0):
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            elif cond == 'gt': # greater than zero
                if v.value > 0:
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            elif cond == 'ge': # greater than or equal to zero
                if v.value >= 0:
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            elif cond == 'is': # if null (reference == null)
                if v.value is None:
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            elif cond == 'isnot': # if not null (reference != null)
                if v.value is not None:
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            return state      
        
        case jvm.New(classname=name):
            obj_ref = len(state.heap)
            state.heap[obj_ref] = {"class": name}
            frame.stack.push(obj_ref)
            frame.pc += 1
            return state
        
        case jvm.Dup():
            v = frame.stack.peek()
            frame.stack.push(v)
            frame.pc += 1
            return state
        
        case jvm.InvokeStatic(method=mid):
            logger.debug(f"InvokeStatic: classname={mid.classname.dotted()}, method={mid.extension.name}")

            params = getattr(mid.extension, "params", None)
            param_elems = getattr(params, "_elements", ()) if params is not None else ()
            param_count = len(param_elems)

            args = [frame.stack.pop() for _ in range(param_count)][::-1]

            callee = Frame.from_method(mid)
            for i, a in enumerate(args):
                callee.locals[i] = a

            state.frames.push(callee)
            return state
        
        case jvm.InvokeSpecial(method=mid):
            method_name = mid.extension.name
            if method_name == "<init>":
                # Simulate object creation (same as jvm.New)
                obj_ref = len(state.heap)
                state.heap[obj_ref] = {"class": mid.classname._as_string}
                frame.stack.push(obj_ref)
                frame.pc += 1
                return state
            else:
                # Handle other special methods
                frame.pc += 1
                return state
            
        case jvm.InvokeVirtual(method=mid):
            logger.debug(f"InvokeVirtual: classname={mid.classname.dotted()}, method={mid.extension.name}")
            if str(mid.classname) == "java/lang/String" or str(mid.classname) == "java.lang.String":
                
                if mid.extension.name == "length":
                    string_ref = frame.stack.pop()  
                    if string_ref.value is None:
                        return "null pointer"
                    string_obj = state.heap[string_ref.value]
                    string_value = string_obj.get("value", "")
                    length = len(string_value)
                    frame.stack.push(jvm.Value.int(length))
                    frame.pc += 1
                    return state
                    
                elif mid.extension.name == "toUpperCase":
                    string_ref = frame.stack.pop() 
                    if string_ref.value is None:
                        return "null pointer"
                    string_obj = state.heap[string_ref.value]
                    string_value = string_obj.get("value", "")
                    upper = string_value.upper()
                    new_string_ref = len(state.heap)
                    state.heap[new_string_ref] = {"class": "java.lang.String", "value": upper}
                    frame.stack.push(jvm.Value(jvm.Reference(), new_string_ref))
                    frame.pc += 1
                    return state
                
                elif mid.extension.name == "charAt":
                    index = frame.stack.pop()  
                    string_ref = frame.stack.pop()  
                    if string_ref.value is None:
                        return "null pointer"
                    string_obj = state.heap[string_ref.value]
                    string_value = string_obj.get("value", "")
                    if 0 <= index.value < len(string_value):
                        char = string_value[index.value]
                        frame.stack.push(jvm.Value.int(ord(char)))
                    else:
                        return "out of bounds"
                    frame.pc += 1
                    return state
                    
                elif mid.extension.name == "equals":
                    other_ref = frame.stack.pop()  
                    string_ref = frame.stack.pop() 
                    if string_ref.value is None:
                        return "null pointer"
                    string_obj = state.heap[string_ref.value]
                    string_value = string_obj.get("value", "")
                    
                    if isinstance(other_ref.type, jvm.String) and not isinstance(other_ref.value, int):
                        # It's a direct string value
                        other_value = other_ref.value
                        result = 1 if string_value == other_value else 0
                    elif other_ref.value in state.heap:
                        # It's a heap reference
                        other_obj = state.heap[other_ref.value]
                        other_value = other_obj.get("value", "")
                        result = 1 if string_value == other_value else 0
                    else:
                        result = 0
                    
                    frame.stack.push(jvm.Value.int(result))
                    frame.pc += 1
                    return state
                
                elif mid.extension.name == "substring":
                    param_count = len(mid.extension.params._elements) if hasattr(mid.extension, 'params') and mid.extension.params else 0
                    
                    if param_count == 2:
                        # substring(int beginIndex, int endIndex)
                        end_idx = frame.stack.pop()    
                        start_idx = frame.stack.pop()  
                        string_ref = frame.stack.pop() 
                        
                        if string_ref.value is None:
                            return "null pointer"
                        string_obj = state.heap[string_ref.value]
                        string_value = string_obj.get("value", "")
                        
                        result = string_value[start_idx.value:end_idx.value]
                    elif param_count == 1:
                        # substring(int beginIndex) - goes to end
                        start_idx = frame.stack.pop()  
                        string_ref = frame.stack.pop()  
                        
                        if string_ref.value is None:
                            return "null pointer"
                        string_obj = state.heap[string_ref.value]
                        string_value = string_obj.get("value", "")
                        
                        result = string_value[start_idx.value:]  
                    else:
                        raise NotImplementedError(f"substring with {param_count} params not supported")
                    
                    new_ref = max(state.heap.keys()) + 1 if state.heap else 1
                    state.heap[new_ref] = {'class': 'java.lang.String', 'value': result}
                    frame.stack.push(jvm.Value(jvm.Reference(), new_ref))
                    frame.pc += 1
                    return state

                raise NotImplementedError(f"String method {mid.extension.name} not implemented")
            raise NotImplementedError(f"InvokeVirtual not implemented for {mid}")
        
        case jvm.InvokeDynamic(name=name, descriptor=descriptor):
            if "makeConcat" in name:
                args = []
                num_args = descriptor.count('L') + descriptor.count('I') + descriptor.count('Z')
                if num_args == 0:
                    num_args = 1 
                    
                for _ in range(min(num_args, len(frame.stack.items))):
                    if frame.stack.items:
                        args.append(frame.stack.pop())
                
                args.reverse()
                
                result = "".join(str(arg.value) if hasattr(arg, 'value') else str(arg) for arg in args)
                frame.stack.push(jvm.Value.string(result))
                frame.pc += 1  
                return state   
            else:
                raise NotImplementedError(f"Unhandled invokedynamic: {name}")

            
        case jvm.Throw():            
            exception_ref = frame.stack.pop()
    
            # Handle both raw int and Value(int) cases
            if isinstance(exception_ref, jvm.Value):
                ref_value = exception_ref.value
            else:
                ref_value = exception_ref
            
            # Check if it's an AssertionError
            if ref_value in state.heap:
                exception_obj = state.heap[ref_value]
                if isinstance(exception_obj, dict):
                    class_name = str(exception_obj.get("class", ""))
                    if "AssertionError" in class_name:
                        return "assertion error"
            
            # For other exceptions or if we can't determine the type
            return "assertion error"
            # return f"Stack items: , {frame.stack.items}"
            # assertionsDisabled = frame.locals[0]
            # logger.debug(f"Stack items: , {frame.stack.items}")
            # logger.debug(f"assertionsDisabled: {assertionsDisabled}")
            #if assertionsDisabled == Value.int(0):

            #    return "assertion error"
            #else:
            #    frame.pc += 1
            #    return state
            
            # classname = "java/lang/RuntimeException"
            # obj_ref = len(state.heap)
            # state.heap[obj_ref] = {"class": classname}
            # frame.stack.items.clear()
            # frame.stack.push(obj_ref)
            # frame.pc += 1
            # return state
            
        case jvm.If(condition=cond, target=val):
            if cond == 'gt': # greater than
                v2, v1 = frame.stack.pop(), frame.stack.pop()
                if v1.value > v2.value:
                    # logger.debug(f"Jumping to {val}")
                    frame.pc = PC(frame.pc.method, val)
                else:
                    # logger.debug(f"Not jumping")
                    frame.pc += 1
            if cond == 'ge': # greater than or equal
                v2, v1 = frame.stack.pop(), frame.stack.pop()
                if v1.value >= v2.value:
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            if cond == 'ne': # not equal
                v2, v1 = frame.stack.pop(), frame.stack.pop()
                if v1.value != v2.value:
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            if cond == 'eq': # equal
                v2, v1 = frame.stack.pop(), frame.stack.pop()
                if v1.value == v2.value:
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            if cond == 'lt': # Less than
                v2, v1 = frame.stack.pop(), frame.stack.pop()
                if v1.value < v2.value:
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
            if cond == 'le': # Less than or equal
                v2, v1 = frame.stack.pop(), frame.stack.pop()
                if v1.value <= v2.value:
                    frame.pc = PC(frame.pc.method, val)
                else:
                    frame.pc += 1
                
            return state
        
        case jvm.Store(type=jvm.Int(), index=i):
            v = frame.stack.pop()
            frame.locals[i] = v
            frame.pc += 1
            return state

        case jvm.Goto(target=val):
            frame.pc = PC(frame.pc.method, val)
            return state
        
        case jvm.NewArray(type=jvm.Int(), dim=dim):
            size = frame.stack.pop()
            array_ref = len(state.heap)
            state.heap[array_ref] = [0] * size.value
            frame.stack.push(Value.int(array_ref))
            frame.pc += 1
            return state
        
        case jvm.ArrayStore(type=jvm.Int()):
            value, index, array_ref = frame.stack.pop(), frame.stack.pop(), frame.stack.pop()
            logger.debug(f"Storing value {value} at index {index} of array {array_ref}")


            # check for null
            if getattr(array_ref, "value", array_ref) is None:
                return "null pointer"
            if not hasattr(array_ref, "value"):
                array_ref = Value.int(array_ref)

            
            try:
                state.heap[array_ref.value][index.value] = value.value
            except Exception as e:
                return "out of bounds"
            frame.pc += 1
            return state
        
        case jvm.Cast(from_=jvm.Int(), to_=jvm.Short()): # This case is not complete but for now it works... :/
            v = frame.stack.pop()
            assert v.type is jvm.Int(), f"expected int, but got {v}"
            short_value = ((v.value + 32768) % 65536) - 32768
            frame.stack.push(jvm.Value.int(short_value))
            frame.pc += 1
            return state
        
        case jvm.Store(type=jvm.Reference(), index=i): # Handle reference store
            v = frame.stack.pop()
            frame.locals.update({i: v})
            frame.pc += 1
            return state
        
        case jvm.Load(type=jvm.Reference(), index=i): # Handle reference load
            v = frame.locals[i]
            frame.stack.push(v)
            frame.pc += 1
            return state
        
        case jvm.ArrayLength():
    
            array_ref = frame.stack.pop()
            logger.debug(f"ArrayLength: array_ref = {array_ref}, heap = {state.heap}")
            
            # Check if it's in the heap
            if array_ref.value not in state.heap:
                logger.debug(f"Reference {array_ref.value} not found in heap!")
                return "null pointer"
            
            heap_obj = state.heap[array_ref.value]
            
            # Check if it's a String object
            if isinstance(heap_obj, dict) and heap_obj.get("class") == "java.lang.String":
                # Get the length of the string value
                string_value = heap_obj.get("value", "")
                length = len(string_value)
            elif isinstance(heap_obj, dict) and heap_obj.get("class") == "Array":
                # Use the 'elements' key for arrays stored as dicts
                length = len(heap_obj.get("elements", []))
            else:
                # It's an array
                length = len(heap_obj)
            
            logger.debug(f"Array/String length is {length}")
            frame.stack.push(jvm.Value.int(length))
            frame.pc += 1
            return state
        
        case jvm.ArrayLoad(type=jvm.Int()):
            index, array_ref = frame.stack.pop(), frame.stack.pop()
            logger.debug(f"Loading value at index {index} from array {array_ref}")
            
            if array_ref.value is None:
                return "null pointer"
            
            heap_obj = state.heap[array_ref.value]
            
            # Handle both dict format and list format
            if isinstance(heap_obj, dict) and heap_obj.get("class") == "Array":
                elements = heap_obj.get("elements", [])
            else:
                elements = heap_obj
            
            if index.value < 0 or index.value >= len(elements):
                return "out of bounds"
            
            try:
                value = elements[index.value]
            except Exception as e:
                return "assertion error"
            
            frame.stack.push(jvm.Value.int(value))
            frame.pc += 1
            return state
        
        case jvm.ArrayLoad(type=jvm.Char()):
            index, array_ref = frame.stack.pop(), frame.stack.pop()
            logger.debug(f"Loading char at index {index} from array {array_ref}")
            
            if array_ref.value is None:
                return "null pointer"
            heap_obj = state.heap[array_ref.value]
            
            # Handle both dict format and list format
            if isinstance(heap_obj, dict):
                elements = heap_obj.get("elements", [])
            else:
                elements = heap_obj
            
            if index.value < 0 or index.value >= len(elements):
                return "out of bounds"
            
            char_value = elements[index.value]
            # Convert char to int (ASCII value)
            frame.stack.push(jvm.Value.int(ord(char_value)))
            frame.pc += 1
            return state
        
        # case jvm.Value(type=jvm.Array(contains=jvm.Int()), value=vals):
        #     # vals may be a tuple of ints or jvm.Value(int, ...)
        #     array_ref = len(state.heap)
        #     elements = []
        #     for item in vals:
        #         if isinstance(item, jvm.Value):
        #             if item.type is jvm.Int():
        #                 elements.append(item.value)
        #             else:
        #                 raise NotImplementedError(f"array contains unsupported value: {item}")
        #         else:
        #             # assume a plain python int
        #             elements.append(item)
        #     state.heap[array_ref] = elements
        #     frame.stack.push(jvm.Value(jvm.Reference(), array_ref))
        #     frame.pc += 1
        #     return state

        case jvm.Incr(index=i, amount=c):
            v = frame.locals[i]
            assert v.type is jvm.Int(), f"expected int, but got {v}"
            frame.locals[i] = jvm.Value.int(v.value + c)
            frame.pc += 1
            return state
        
        case a:
            # a.help()
            raise NotImplementedError(f"Don't know how to handle: {a!r}")

state = State({}, Stack.empty())

frame = Frame.from_method(methodid)
logger.debug(f"input.values = {input.values}")

params = getattr(methodid.extension, "params", None)
param_elems = getattr(params, "_elements", ()) if params is not None else ()
param_count = len(param_elems)

for i in range(param_count):
    if i < len(input.values):
        v = input.values[i]
        match v: 
            case jvm.Value(type=jvm.Int(), value = value):
                v = v
            case jvm.Value(type=jvm.Float(), value = value):
                v = v
            case jvm.Value(type=jvm.Boolean(), value = value):
                logger.debug(f"converting boolean {value} to int")
                v = jvm.Value.int(1 if value else 0)
            case jvm.Value(type=jvm.String(), value = value):
                string_ref = len(state.heap)
                state.heap[string_ref] = {"class": "java.lang.String", "value": value}
                v = jvm.Value(jvm.Reference(), string_ref)
            case jvm.Value(type=jvm.Reference(), value=None):
                v = jvm.Value(jvm.Reference(), None)
            case jvm.Value(type=jvm.Array(contains=contains), value=value):
                if v.value is None:
                    frame.locals[i] = jvm.Value(jvm.Reference(), None)
                else:
                        # Allocate array in heap
                        arr_ref = len(state.heap)  # CHANGE: use len(state.heap) instead of state.allocate()
                        arr_contents = list(value)  # Convert tuple to list
                        state.heap[arr_ref] = {
                            "class": "Array",
                            "type": contains,
                            "length": len(arr_contents),
                            "elements": arr_contents
                        }
                        v = jvm.Value(jvm.Reference(), arr_ref)
            case _:
                raise NotImplementedError(f"Don't know how to handle input value: {v!r}")
    else:
        # No input provided for this parameter, default to null
        v = jvm.Value(jvm.Reference(), None)
    
    frame.locals[i] = v

def main():
    try:
        # This will cache the method in bc.methods
        _ = bc[frame.pc]
    except AssertionError:
        if any(isinstance(p, jvm.Array) and isinstance(p.contains, jvm.Char) 
               for p in getattr(methodid.extension.params, "_elements", [])):
            # Load method directly from JSON
            import json
            from pathlib import Path
            
            class_name = str(methodid.classname).replace('.', '/')
            method_name = methodid.extension.name
            class_file = Path.cwd() / "target" / "decompiled" / f"{class_name}.json"
            
            with open(class_file) as f:
                class_data = json.load(f)
            
            for m in class_data['methods']:
                if m['name'] == method_name:
                    # Convert JSON bytecode to opcodes
                    opcodes = []
                    for bc_json in m["code"]["bytecode"]:
                        opcodes.append(jvm.Opcode.from_json(bc_json))
                    bc.methods[methodid] = opcodes
                    break
        else:
            raise
    state.frames.push(frame)
    for _ in range(1000):
        res = step(state)
        if isinstance(res, str):
            print(res)
            # Print trace in a readable format
            # COMMENT THE BELOW LINE OUT IF YOU WANT TO USE ONLY INTERPRETER WITHOUT COVERAGE FUZZER
            print(*trace, sep=",")
            break
    else:
        print("*")

if __name__ == "__main__":
    main()