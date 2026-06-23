import sys; import os; import shlex; import random

errmsg = {
    'val': "Value error, invalid type",
    'key': "Key error, cant find objects",
    '.ksm': "No '.ksm' header detected, exiting...",
    'filepath': "Invalid filepath, exiting...",
    'cmd': "Invalid operation, error..."
}

types = {'str': str, 'int': int, 'float': float, 'list': list}

class kmath:
    @staticmethod
    def add(a, b, typeid): 
        try: return int(a) + int(b)
        except: return str(a) + str(b)
    
    @staticmethod
    def sub(a, b, typeid): 
        return int(a) - int(b)
    
    @staticmethod
    def mult(a, b, typeid):
        # Try numeric * numeric
        try:
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
        for func in funcs:
            if skip_line: break
            if func == '>>':
                if last_val is not None: store.stack.push(last_val); last_val = None
                continue
            
            l = shlex.split(func)
            cmd = l[0]
            
            if cmd == 'push': store.stack.push(types[l[1]](l[2]))
            elif cmd == 'rand': 
                last_val = random.randint(int(l[1]), int(l[2]))
            elif cmd == 'ifgt':
                if int(store.heap.getkey(l[1])) <= int(l[2]): skip_line = True
            elif cmd == 'index':
                lst = store.heap.getkey(l[1])
                idx_token = l[2]

                try:
                    idx = int(idx_token)
                except Exception:

                    idx_val = store.heap.getkey(idx_token)
                    if idx_val == errmsg['key']:
                        raise ValueError(f"index error: missing heap key '{idx_token}'")
                    try:
                        idx = int(idx_val)
                    except Exception:
                        raise ValueError(f"index error: heap key '{idx_token}' is not integer-like: {idx_val!r}")

                if isinstance(lst, str):
                    lst = list(lst)
                    store.heap.adkey(l[1], lst)
                if not (0 <= idx < len(lst) or -len(lst) <= idx < 0):
                    raise IndexError(f"index error: index {idx} out of range for '{l[1]}' (len {len(lst)})")
                last_val = lst[idx]

            elif cmd == 'set':
                lst = store.heap.getkey(l[1])
                idx_token = l[2]
                try:
                    idx = int(idx_token)
                except Exception:
                    idx_val = store.heap.getkey(idx_token)
                    if idx_val == errmsg['key']:
                        raise ValueError(f"set error: missing heap key '{idx_token}'")
                    try:
                        idx = int(idx_val)
                    except Exception:
                        raise ValueError(f"set error: heap key '{idx_token}' is not integer-like: {idx_val!r}")
                if isinstance(lst, str):
                    lst = list(lst)
                    store.heap.adkey(l[1], lst)
                if not (0 <= idx < len(lst) or -len(lst) <= idx < 0):
                    raise IndexError(f"set error: index {idx} out of range for '{l[1]}' (len {len(lst)})")
                lst[idx] = l[3]
            elif cmd == 'save': store.heap.adkey(l[1], store.stack.pop())
            elif cmd == 'store': 
                key, val = l[1].split('=')
                try: store.heap.adkey(key, int(val))
                except: store.heap.adkey(key, val)
            elif cmd == 'draw':
                os.system('cls' if os.name == 'nt' else 'clear')
                lst, width = store.heap.getkey(l[1]), int(l[2])
                for i in range(0, len(lst), width):
                    print(" ".join(lst[i:i+width]))
            elif cmd == 'get': last_val = store.heap.getkey(l[1])
            elif cmd == 'input': 
                last_val = input(l[1] if len(l) > 1 else "input: ").lower()
            elif cmd == 'print': print(l[1] if len(l) > 1 else store.stack.pop())
            elif cmd == 'jump': store.pointer = store.labels[l[1]]
            elif cmd == 'ifeq':
                v = store.heap.getkey(l[1])
                if str(v) != str(l[2]): skip_line = True
            elif cmd in ['add', 'sub', 'mult']:
                a = store.stack.pop()
                b = l[1] if len(l) > 1 else store.stack.pop()
                t = 'str' if isinstance(a, str) else type(a).__name__
                if cmd == 'add': last_val = kmath.add(a, b, t)
                elif cmd == 'sub': last_val = kmath.sub(a, b, t)
                elif cmd == 'mult': last_val = kmath.mult(a, b, t)

if __name__ == "__main__":
    if len(sys.argv) == 2: exe(sys.argv[1])
