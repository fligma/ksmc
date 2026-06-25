import sys; import os; import shlex; import random
import ast

errmsg = {
    'val': "Value error, invalid type",
    'key': "Key error, cant find objects",
    '.ksm': "No '.ksm' header detected, exiting...",
    'filepath': "Invalid filepath, exiting...",
    'cmd': "Invalid operation, error..."
}

types = {'str': str, 'int': int, 'float': float, 'list': list, 'dict': dict}

def parse_val(val_str):
    try:
        return ast.literal_eval(val_str)
    except (ValueError, SyntaxError):
        return str(val_str)

class kmath:
    @staticmethod
    def add(a, b): 
        try:
            if isinstance(a, float) or isinstance(b, float): return float(a) + float(b)
            return int(a) + int(b)
        except: return str(a) + str(b)
    
    @staticmethod
    def sub(a, b): 
        try:
            if isinstance(a, float) or isinstance(b, float): return float(a) - float(b)
            return int(a) - int(b)
        except:
            raise TypeError(f"Unsupported operand types for sub: '{type(a).__name__}' and '{type(b).__name__}'")
    
    @staticmethod
    def mult(a, b):
        # Try numeric * numeric
        try:
            if isinstance(a, float) or isinstance(b, float): return float(a) * float(b)
            return int(a) * int(b)
        except Exception:
            pass
        try:
            if isinstance(a, str) and str(b).lstrip('-').isdigit():
                repeated = a * int(b)
                return list(repeated)
        except Exception:
            pass
        try:
            if isinstance(b, str) and str(a).lstrip('-').isdigit():
                repeated = b * int(a)
                return list(repeated)
        except Exception:
            pass
        try:
            if isinstance(a, str) and isinstance(b, str) and b.lstrip('-').isdigit():
                return list(a * int(b))
        except Exception:
            pass
        try:
            return list(str(a) + str(b))
        except Exception:
            return str(a) + str(b)

    @staticmethod
    def div(a, b):
        if isinstance(a, float) or isinstance(b, float): return float(a) / float(b)
        return int(a) // int(b)
        
    @staticmethod
    def mod(a, b):
        if isinstance(a, float) or isinstance(b, float): return float(a) % float(b)
        return int(a) % int(b)

class kheap:
    def __init__(self): self.store = {}
    def adkey(self, key, data): self.store[key] = data; return 1
    def getkey(self, key): return self.store.get(key, errmsg['key'])

class kstack:
    def __init__(self): self.store = []
    def push(self, data): self.store.append(data)
    def pop(self): return self.store.pop() if self.store else None

class exestore:
    def __init__(self):
        self.pointer = 0; self.exemem = []; self.labels = {}
        self.heap = kheap(); self.stack = kstack()
        self.call_stack = [] # New call stack for subroutines

def exe(file):
    store = exestore()
    with open(file) as f:
        for line in f: store.exemem.append(line.strip())
    
    if store.exemem[0] != '.ksm': exit(print(errmsg['.ksm']))

    for idx, line in enumerate(store.exemem):
        if 'label' in line: store.labels[line.split()[-1]] = idx

    last_val = None
    while store.pointer < len(store.exemem):
        i = store.exemem[store.pointer]
        store.pointer += 1
        if not i or i[0] in ['#', '.']: continue
        if i.startswith(';'): i = i[1:].strip()
        
        funcs = [f.strip() for f in i.split('|')]
        skip_line = False
        
        try:
            for func in funcs:
                if skip_line: break
                if func == '>>':
                    if last_val is not None: store.stack.push(last_val); last_val = None
                    continue
                
                l = shlex.split(func)
                cmd = l[0]
                
                if cmd == 'push': 
                    type_name = l[1]
                    val_str = l[2]
                    if type_name in ['list', 'dict']: val = ast.literal_eval(val_str)
                    elif type_name == 'int': val = int(val_str)
                    elif type_name == 'float': val = float(val_str)
                    else: val = str(val_str)
                    store.stack.push(val)
                elif cmd == 'rand': 
                    last_val = random.randint(int(l[1]), int(l[2]))
                
                # --- Logic Comparators ---
                elif cmd == 'ifgt':
                    v1 = store.heap.getkey(l[1])
                    v2 = store.heap.getkey(l[2]) if store.heap.getkey(l[2]) != errmsg['key'] else parse_val(l[2])
                    try: res = float(v1) > float(v2)
                    except: res = str(v1) > str(v2)
                    if not res: skip_line = True
                elif cmd == 'iflt':
                    v1 = store.heap.getkey(l[1])
                    v2 = store.heap.getkey(l[2]) if store.heap.getkey(l[2]) != errmsg['key'] else parse_val(l[2])
                    try: res = float(v1) < float(v2)
                    except: res = str(v1) < str(v2)
                    if not res: skip_line = True
                elif cmd == 'ifeq':
                    v1 = store.heap.getkey(l[1])
                    v2 = store.heap.getkey(l[2]) if store.heap.getkey(l[2]) != errmsg['key'] else parse_val(l[2])
                    if str(v1) != str(v2): skip_line = True
                elif cmd == 'ifneq':
                    v1 = store.heap.getkey(l[1])
                    v2 = store.heap.getkey(l[2]) if store.heap.getkey(l[2]) != errmsg['key'] else parse_val(l[2])
                    if str(v1) == str(v2): skip_line = True

                # --- Data / Memory operations ---
                elif cmd == 'len':
                    val = store.heap.getkey(l[1])
                    if val == errmsg['key']:
                        raise ValueError(f"len error: missing heap key '{l[1]}'")
                    last_val = len(val)
                elif cmd == 'index':
                    container = store.heap.getkey(l[1])
                    if container == errmsg['key']: raise ValueError(f"index error: missing heap key '{l[1]}'")
                    
                    idx_token = l[2]
                    key_val = store.heap.getkey(idx_token)
                    idx_token = key_val if key_val != errmsg['key'] else parse_val(idx_token)
                    
                    if isinstance(container, dict):
                        last_val = container[idx_token]
                    else:
                        idx = int(idx_token)
                        if isinstance(container, str):
                            container = list(container)
                            store.heap.adkey(l[1], container)
                        last_val = container[idx]

                elif cmd == 'set':
                    container = store.heap.getkey(l[1])
                    if container == errmsg['key']: raise ValueError(f"set error: missing heap key '{l[1]}'")
                    
                    idx_token = l[2]
                    key_val = store.heap.getkey(idx_token)
                    idx_token = key_val if key_val != errmsg['key'] else parse_val(idx_token)
                    
                    new_val = parse_val(l[3])
                    
                    if isinstance(container, dict):
                        container[idx_token] = new_val
                    else:
                        idx = int(idx_token)
                        if isinstance(container, str):
                            container = list(container)
                            store.heap.adkey(l[1], container)
                        container[idx] = new_val
                elif cmd == 'save': store.heap.adkey(l[1], store.stack.pop())
                elif cmd == 'store': 
                    key, val_str = l[1].split('=', 1)
                    store.heap.adkey(key, parse_val(val_str))
                elif cmd == 'draw':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    lst, width = store.heap.getkey(l[1]), int(l[2])
                    for r in range(0, len(lst), width):
                        print(" ".join(str(x) for x in lst[r:r+width]))
                elif cmd == 'get': last_val = store.heap.getkey(l[1])
                elif cmd == 'input': 
                    last_val = input(l[1] if len(l) > 1 else "input: ")
                elif cmd == 'print': print(l[1] if len(l) > 1 else store.stack.pop())
                
                # --- Control Flow ---
                elif cmd == 'jump': store.pointer = store.labels[l[1]]
                elif cmd == 'call': 
                    store.call_stack.append(store.pointer) # Save return address
                    store.pointer = store.labels[l[1]]     # Jump to subroutine
                elif cmd == 'ret':
                    if store.call_stack:
                        store.pointer = store.call_stack.pop() # Return to saved address
                    else:
                        raise RuntimeError("ret error: call stack empty")
                
                # --- Math ---
                elif cmd in ['add', 'sub', 'mult', 'div', 'mod']:
                    a = store.stack.pop()
                    b = parse_val(l[1]) if len(l) > 1 else store.stack.pop()
                    if cmd == 'add': last_val = kmath.add(a, b)
                    elif cmd == 'sub': last_val = kmath.sub(a, b)
                    elif cmd == 'mult': last_val = kmath.mult(a, b)
                    elif cmd == 'div': last_val = kmath.div(a, b)
                    elif cmd == 'mod': last_val = kmath.mod(a, b)
        except Exception as e:
            print(f"\n[KSM Error] Execution failed at line {store.pointer}: {i}")
            print(f"Details: {type(e).__name__} - {e}")
            sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) == 2: exe(sys.argv[1])
