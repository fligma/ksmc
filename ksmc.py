#!/usr/bin/env python3
"""
KSMC - KSM Compiler/Interpreter v4
A strict, stack-based assembly language with Forth-like semantics.

Design principles:
  - ONE way to do everything (no redundant operations)
  - Data-safe (strict types, no implicit coercion, bounds checking, mutability)
  - Pure stack machine (all value-producing ops push to stack, no hidden state)
  - One instruction per line (assembly style)
  - Explicit casting required for type conversion
  - Imports: 'use "file.ksm"' loads another .ksm as a module
  - Error handling: try/catch/throw for recoverable errors
  - Syscall bridge: sys.* exposes OS/network/regex/json primitives

Type system:
  int, float, str, list, dict, bool
  - No implicit coercion between types
  - Arithmetic only on numeric types (int/float auto-widens to float)
  - Must cast explicitly: cast int, cast str, etc.

Memory model:
  - let name [val]  -> immutable (protected from reassignment)
  - mut name [val]  -> mutable
  - save name       -> store stack top (auto-creates as mut, errors on immutable)
  - get name        -> push value to stack

Control flow:
  - if a op b      -> skip next line if condition is false
  - while a op b   -> loop while condition holds ... endwhile
  - loop N         -> repeat body N times ... endloop
  - jump label
  - call label / ret
  - break / continue / exit
  - try ... catch var ... endtry
"""

import sys, os, shlex, random, ast, re, json
import time as _time
import urllib.request, urllib.parse, urllib.error

# ─── Type Names ───────────────────────────────────────────────────────────────

T_INT = 'int'
T_FLOAT = 'float'
T_STR = 'str'
T_LIST = 'list'
T_DICT = 'dict'
T_BOOL = 'bool'

NUMERIC = (int, float)

def type_name(val):
    if isinstance(val, bool): return T_BOOL
    if isinstance(val, int): return T_INT
    if isinstance(val, float): return T_FLOAT
    if isinstance(val, str): return T_STR
    if isinstance(val, list): return T_LIST
    if isinstance(val, dict): return T_DICT
    return type(val).__name__

def parse_literal(s):
    """Parse a literal string into a typed Python value."""
    if isinstance(s, (int, float, bool, list, dict)):
        return s
    if s == 'true': return True
    if s == 'false': return False
    if s.startswith('"') or s.startswith("'"):
        try: return ast.literal_eval(s)
        except: return s.strip('"').strip("'")
    if s.startswith('[') or s.startswith('{'):
        return ast.literal_eval(s)
    try:
        if '.' in s: return float(s)
        return int(s)
    except ValueError:
        return s  # bare word -> str

def expect_numeric(val, op):
    if not isinstance(val, NUMERIC):
        raise TypeError(f"'{op}' requires numeric, got {type_name(val)}: {repr(val)}")
    return val

def expect_type(val, expected, op):
    if not isinstance(val, expected):
        raise TypeError(f"'{op}' requires {expected.__name__}, got {type_name(val)}: {repr(val)}")
    return val

def expect_same_type(a, b, op):
    if isinstance(a, NUMERIC) and isinstance(b, NUMERIC):
        return
    if type(a) != type(b):
        raise TypeError(f"'{op}' cannot compare {type_name(a)} with {type_name(b)} (cast explicitly)")

# ─── KSM Error Type ──────────────────────────────────────────────────────────

class KSMError(Exception):
    """User-thrown error from KSM code."""
    def __init__(self, value):
        self.value = value
        super().__init__(str(value))

# ─── Stack ────────────────────────────────────────────────────────────────────

class Stack:
    def __init__(self):
        self._data = []

    def push(self, val): self._data.append(val)
    def pop(self):
        if not self._data: raise RuntimeError("Stack underflow: tried to pop empty stack")
        return self._data.pop()
    def peek(self):
        if not self._data: raise RuntimeError("Stack underflow: tried to peek empty stack")
        return self._data[-1]
    def depth(self): return len(self._data)
    def dup(self): self.push(self.peek())
    def swap(self):
        if len(self._data) < 2: raise RuntimeError("Stack underflow: swap needs 2")
        self._data[-1], self._data[-2] = self._data[-2], self._data[-1]
    def over(self):
        if len(self._data) < 2: raise RuntimeError("Stack underflow: over needs 2")
        self.push(self._data[-2])
    def rot(self):
        if len(self._data) < 3: raise RuntimeError("Stack underflow: rot needs 3")
        a = self._data[-3]
        self._data[-3] = self._data[-2]
        self._data[-2] = self._data[-1]
        self._data[-1] = a
    def drop(self): self.pop()
    def pick(self, n):
        if n >= len(self._data): raise RuntimeError(f"Stack underflow: pick({n}) but depth is {len(self._data)}")
        self.push(self._data[-(n + 1)])
    def clear(self): self._data.clear()
    def __repr__(self): return f"Stack({self._data})"

# ─── Heap (Typed Variable Store) ──────────────────────────────────────────────

class Heap:
    def __init__(self):
        self._store = {}

    def declare(self, name, value, mutable):
        if name in self._store:
            raise RuntimeError(f"Variable '{name}' already declared (use save to update)")
        self._store[name] = [value, mutable]

    def get(self, name):
        if name not in self._store:
            raise RuntimeError(f"Undefined variable: '{name}'")
        return self._store[name][0]

    def save(self, name, value):
        if name in self._store:
            if not self._store[name][1]:
                raise RuntimeError(f"Cannot mutate immutable variable: '{name}' (declared with let)")
            self._store[name][0] = value
        else:
            self._store[name] = [value, True]

    def has(self, name): return name in self._store
    def is_mutable(self, name):
        if name not in self._store: return False
        return self._store[name][1]

    def delete(self, name):
        if name not in self._store: raise RuntimeError(f"Cannot delete undefined variable: '{name}'")
        if not self._store[name][1]: raise RuntimeError(f"Cannot delete immutable variable: '{name}'")
        del self._store[name]

# ─── Virtual Machine ──────────────────────────────────────────────────────────

class VM:
    def __init__(self, base_dir=None):
        self.stack = Stack()
        self.heap = Heap()
        self.program = []
        self.pointer = 0
        self.labels = {}
        self.words = {}
        self.call_stack = []
        self.loop_stack = []
        self.files = {}
        self.running = True
        self.imported = set()
        self.base_dir = base_dir or os.getcwd()
        self.try_stack = []
        self.skip_next = False  # for 'if' conditional skip

    def load(self, filepath):
        if not os.path.isfile(filepath):
            self._fatal(f"File not found: '{filepath}'")
        self.base_dir = os.path.dirname(os.path.abspath(filepath))
        with open(filepath, 'r') as f:
            for line in f:
                self.program.append(line.strip())
        if not self.program or self.program[0] != '.ksm':
            self._fatal("Missing '.ksm' header on line 1")
        self.imported.add(os.path.abspath(filepath))
        self._prescan()

    def _prescan(self):
        idx = 0
        while idx < len(self.program):
            line = self.program[idx]
            if line.startswith('label '):
                self.labels[line.split(None, 1)[1].strip()] = idx
            elif line.startswith('def '):
                word_name = line.split(None, 1)[1].strip()
                body = []
                idx += 1
                depth = 1  # track nested blocks
                while idx < len(self.program):
                    inner = self.program[idx].strip()
                    if inner in ('if', 'while', 'loop', 'try'):
                        depth += 1
                    elif inner in ('end', 'endif', 'endwhile', 'endloop', 'endtry', 'catch'):
                        depth -= 1
                        if depth == 0:
                            break
                    body.append(self.program[idx])
                    idx += 1
                self.words[word_name] = body
            idx += 1

    def run(self):
        while self.pointer < len(self.program) and self.running:
            line = self.program[self.pointer]
            self.pointer += 1
            if self.skip_next:
                self.skip_next = False
                continue
            try:
                self._exec_line(line)
            except KSMError as e:
                if not self._handle_error(e): raise
            except SystemExit:
                raise
            except Exception as e:
                if not self._handle_error(e): raise

    def _handle_error(self, e):
        if not self.try_stack: return False
        ctx = self.try_stack.pop()
        err_val = e.value if isinstance(e, KSMError) else f"{type(e).__name__}: {e}"
        self.heap.save(ctx['var'], err_val)
        self.pointer = ctx['catch_ptr']
        return True

    def _exec_line(self, line):
        if not line or line[0] in ('#', '.'): return
        if line.startswith('label '): return
        if line.startswith('def '):
            while self.pointer < len(self.program) and self.program[self.pointer].strip() != 'end':
                self.pointer += 1
            self.pointer += 1
            return
        if line in ('end', 'endif'): return

        # push needs special handling for complex literals (dicts, lists, quoted strings)
        if line.startswith('push '):
            raw = line[5:].strip()
            self.stack.push(parse_literal(raw))
            return

        try:
            tokens = shlex.split(line)
        except ValueError:
            tokens = line.split()
        if not tokens: return

        cmd = tokens[0]
        args = tokens[1:]

        if cmd in self.words:
            for wline in self.words[cmd]:
                self._exec_line(wline)
            return

        if '.' in cmd:
            parts = cmd.split('.', 1)
            if parts[0] == 'sys':
                return self._syscall(parts[1], args)
            if cmd in self.words:
                for wline in self.words[cmd]:
                    self._exec_line(wline)
                return

        handler = getattr(self, f'_op_{cmd}', None)
        if handler:
            return handler(args)
        raise RuntimeError(f"Unknown command: '{cmd}'")

    def _resolve(self, token):
        if self.heap.has(token):
            return self.heap.get(token)
        return parse_literal(token)

    # ─── Import System ────────────────────────────────────────────────────

    def _op_use(self, args):
        """use "file.ksm" [as prefix] - import defs from another .ksm file."""
        filepath = args[0]
        prefix = None
        if len(args) >= 3 and args[1] == 'as':
            prefix = args[2]

        abs_path = os.path.abspath(os.path.join(self.base_dir, filepath))
        if not os.path.isfile(abs_path):
            raise RuntimeError(f"Cannot import: file not found '{filepath}'")
        if abs_path in self.imported: return
        self.imported.add(abs_path)

        with open(abs_path, 'r') as f:
            lines = [l.strip() for l in f]
        if not lines or lines[0] != '.ksm':
            raise RuntimeError(f"Import error: '{filepath}' missing .ksm header")

        idx = 0
        while idx < len(lines):
            line = lines[idx]
            if line.startswith('def '):
                word_name = line.split(None, 1)[1].strip()
                body = []
                idx += 1
                depth = 1
                while idx < len(lines):
                    inner = lines[idx].strip()
                    if inner in ('if', 'while', 'loop', 'try'):
                        depth += 1
                    elif inner in ('end', 'endif', 'endwhile', 'endloop', 'endtry', 'catch'):
                        depth -= 1
                        if depth == 0:
                            break
                    body.append(lines[idx])
                    idx += 1
                key = f"{prefix}.{word_name}" if prefix else word_name
                self.words[key] = body
            idx += 1

    # ─── Error Handling ───────────────────────────────────────────────────

    def _op_try(self, args):
        """try - begin error-handling block."""
        catch_ptr = None
        end_ptr = None
        depth = 1
        ptr = self.pointer
        while ptr < len(self.program):
            parts = self.program[ptr].strip().split()
            word = parts[0] if parts else ''
            if word == 'try': depth += 1
            elif word == 'catch' and depth == 1:
                catch_ptr = ptr
            elif word == 'endtry':
                depth -= 1
                if depth == 0:
                    end_ptr = ptr
                    break
            ptr += 1
        if catch_ptr is None or end_ptr is None:
            raise RuntimeError("'try' without matching 'catch'/'endtry'")

        catch_line = self.program[catch_ptr].strip().split()
        var_name = catch_line[1] if len(catch_line) > 1 else '_err'

        self.try_stack.append({
            'catch_ptr': catch_ptr + 1,
            'end_ptr': end_ptr,
            'var': var_name
        })

    def _op_catch(self, args):
        """catch var - marks error handler start. Skip to endtry if no error."""
        if self.try_stack:
            self.try_stack.pop()
        depth = 1
        ptr = self.pointer
        while ptr < len(self.program):
            parts = self.program[ptr].strip().split()
            word = parts[0] if parts else ''
            if word == 'try': depth += 1
            elif word == 'endtry':
                depth -= 1
                if depth == 0:
                    self.pointer = ptr + 1
                    return
            ptr += 1
        raise RuntimeError("'catch' without matching 'endtry'")

    def _op_endtry(self, args):
        """endtry - end of try/catch block."""
        if self.try_stack and self.try_stack[-1]['end_ptr'] == self.pointer - 1:
            self.try_stack.pop()

    def _op_throw(self, args):
        """throw [value] - throw an error. No args = pop stack."""
        if args:
            val = self._resolve(args[0])
        else:
            val = self.stack.pop()
        raise KSMError(val)

    # ─── Syscall Bridge ───────────────────────────────────────────────────

    def _syscall(self, module, args):
        fn = args[0] if args else ''
        fargs = args[1:]

        if module == 'json': return self._sys_json(fn, fargs)
        elif module == 're': return self._sys_re(fn, fargs)
        elif module == 'http': return self._sys_http(fn, fargs)
        elif module == 'os': return self._sys_os(fn, fargs)
        elif module == 'math': return self._sys_math(fn, fargs)
        elif module == 'time': return self._sys_time(fn, fargs)
        elif module == 'str': return self._sys_str(fn, fargs)
        else: raise RuntimeError(f"Unknown syscall module: 'sys.{module}'")

    def _sys_json(self, fn, args):
        if fn == 'encode':
            val = self.stack.pop()
            self.stack.push(json.dumps(val))
        elif fn == 'decode':
            s = expect_type(self.stack.pop(), str, 'sys.json decode')
            self.stack.push(json.loads(s))
        else: raise RuntimeError(f"sys.json: unknown function '{fn}' (use encode/decode)")

    def _sys_re(self, fn, args):
        if fn == 'match':
            pattern = args[0] if args else expect_type(self.stack.pop(), str, 'sys.re match')
            s = expect_type(self.stack.pop(), str, 'sys.re match')
            self.stack.push(bool(re.match(pattern, s)))
        elif fn == 'find':
            pattern = args[0] if args else expect_type(self.stack.pop(), str, 'sys.re find')
            s = expect_type(self.stack.pop(), str, 'sys.re find')
            m = re.search(pattern, s)
            self.stack.push(m.group(0) if m else "")
        elif fn == 'findall':
            pattern = args[0] if args else expect_type(self.stack.pop(), str, 'sys.re findall')
            s = expect_type(self.stack.pop(), str, 'sys.re findall')
            self.stack.push(re.findall(pattern, s))
        elif fn == 'replace':
            repl = args[1] if len(args) > 1 else expect_type(self.stack.pop(), str, 'sys.re replace')
            pattern = args[0] if args else expect_type(self.stack.pop(), str, 'sys.re replace')
            s = expect_type(self.stack.pop(), str, 'sys.re replace')
            self.stack.push(re.sub(pattern, repl, s))
        elif fn == 'split':
            pattern = args[0] if args else expect_type(self.stack.pop(), str, 'sys.re split')
            s = expect_type(self.stack.pop(), str, 'sys.re split')
            self.stack.push(re.split(pattern, s))
        else: raise RuntimeError(f"sys.re: unknown function '{fn}' (use match/find/findall/replace/split)")

    def _sys_http(self, fn, args):
        if fn == 'get':
            url = args[0] if args else expect_type(self.stack.pop(), str, 'sys.http get')
            try:
                with urllib.request.urlopen(url) as resp:
                    self.stack.push({"status": resp.status, "body": resp.read().decode('utf-8')})
            except Exception as e:
                self.stack.push({"status": 0, "body": "", "error": str(e)})
        elif fn == 'post':
            url = args[0] if args else expect_type(self.stack.pop(), str, 'sys.http post')
            data = self.stack.pop()
            body_bytes = json.dumps(data).encode('utf-8') if isinstance(data, dict) else str(data).encode('utf-8')
            content_type = 'application/json' if isinstance(data, dict) else 'text/plain'
            try:
                req = urllib.request.Request(url, data=body_bytes, headers={'Content-Type': content_type})
                with urllib.request.urlopen(req) as resp:
                    self.stack.push({"status": resp.status, "body": resp.read().decode('utf-8')})
            except Exception as e:
                self.stack.push({"status": 0, "body": "", "error": str(e)})
        else: raise RuntimeError(f"sys.http: unknown function '{fn}' (use get/post)")

    def _sys_os(self, fn, args):
        if fn == 'env':
            key = args[0] if args else expect_type(self.stack.pop(), str, 'sys.os env')
            self.stack.push(os.environ.get(key, ""))
        elif fn == 'exec':
            cmd = args[0] if args else expect_type(self.stack.pop(), str, 'sys.os exec')
            import subprocess
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            self.stack.push({"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode})
        elif fn == 'args':
            self.stack.push(sys.argv[2:])
        elif fn == 'cwd':
            self.stack.push(os.getcwd())
        elif fn == 'exists':
            path = args[0] if args else expect_type(self.stack.pop(), str, 'sys.os exists')
            self.stack.push(os.path.exists(path))
        else: raise RuntimeError(f"sys.os: unknown function '{fn}' (use env/exec/args/cwd/exists)")

    def _sys_math(self, fn, args):
        import math
        if fn == 'sqrt': self.stack.push(math.sqrt(expect_numeric(self.stack.pop(), 'sys.math sqrt')))
        elif fn == 'sin': self.stack.push(math.sin(expect_numeric(self.stack.pop(), 'sys.math sin')))
        elif fn == 'cos': self.stack.push(math.cos(expect_numeric(self.stack.pop(), 'sys.math cos')))
        elif fn == 'tan': self.stack.push(math.tan(expect_numeric(self.stack.pop(), 'sys.math tan')))
        elif fn == 'floor': self.stack.push(int(math.floor(expect_numeric(self.stack.pop(), 'sys.math floor'))))
        elif fn == 'ceil': self.stack.push(int(math.ceil(expect_numeric(self.stack.pop(), 'sys.math ceil'))))
        elif fn == 'log': self.stack.push(math.log(expect_numeric(self.stack.pop(), 'sys.math log')))
        elif fn == 'pi': self.stack.push(math.pi)
        elif fn == 'e': self.stack.push(math.e)
        else: raise RuntimeError(f"sys.math: unknown function '{fn}'")

    def _sys_time(self, fn, args):
        if fn == 'now': self.stack.push(int(_time.time()))
        elif fn == 'ms': self.stack.push(int(_time.time() * 1000))
        elif fn == 'sleep':
            ms = int(args[0]) if args else expect_type(self.stack.pop(), int, 'sys.time sleep')
            _time.sleep(ms / 1000.0)
        elif fn == 'format':
            fmt = args[0] if args else "%Y-%m-%d %H:%M:%S"
            self.stack.push(_time.strftime(fmt))
        else: raise RuntimeError(f"sys.time: unknown function '{fn}'")

    def _sys_str(self, fn, args):
        if fn == 'format':
            template = expect_type(self.stack.pop(), str, 'sys.str format')
            parts = template.split('{}')
            result = parts[0]
            for i in range(1, len(parts)):
                result += str(self.stack.pop()) + parts[i]
            self.stack.push(result)
        elif fn == 'startswith':
            prefix = args[0] if args else expect_type(self.stack.pop(), str, 'sys.str startswith')
            s = expect_type(self.stack.pop(), str, 'sys.str startswith')
            self.stack.push(s.startswith(prefix))
        elif fn == 'endswith':
            suffix = args[0] if args else expect_type(self.stack.pop(), str, 'sys.str endswith')
            s = expect_type(self.stack.pop(), str, 'sys.str endswith')
            self.stack.push(s.endswith(suffix))
        elif fn == 'trim':
            self.stack.push(expect_type(self.stack.pop(), str, 'sys.str trim').strip())
        elif fn == 'contains':
            sub = args[0] if args else expect_type(self.stack.pop(), str, 'sys.str contains')
            s = expect_type(self.stack.pop(), str, 'sys.str contains')
            self.stack.push(sub in s)
        elif fn == 'repeat':
            n = expect_type(self.stack.pop(), int, 'sys.str repeat')
            s = expect_type(self.stack.pop(), str, 'sys.str repeat')
            self.stack.push(s * n)
        else: raise RuntimeError(f"sys.str: unknown function '{fn}'")

    # ─── Stack ────────────────────────────────────────────────────────────

    def _op_dup(self, a): self.stack.dup()
    def _op_drop(self, a): self.stack.drop()
    def _op_swap(self, a): self.stack.swap()
    def _op_over(self, a): self.stack.over()
    def _op_rot(self, a): self.stack.rot()
    def _op_pick(self, args): self.stack.pick(int(args[0]))
    def _op_depth(self, a): self.stack.push(self.stack.depth())
    def _op_clear(self, a): self.stack.clear()

    # ─── Memory ───────────────────────────────────────────────────────────

    def _op_let(self, args):
        name = args[0]
        val = parse_literal(' '.join(args[1:])) if len(args) > 1 else self.stack.pop()
        self.heap.declare(name, val, mutable=False)

    def _op_mut(self, args):
        name = args[0]
        val = parse_literal(' '.join(args[1:])) if len(args) > 1 else self.stack.pop()
        self.heap.declare(name, val, mutable=True)

    def _op_save(self, args):
        self.heap.save(args[0], self.stack.pop())

    def _op_get(self, args):
        self.stack.push(self.heap.get(args[0]))

    def _op_del(self, args):
        self.heap.delete(args[0])

    # ─── Arithmetic ───────────────────────────────────────────────────────

    def _op_add(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        if isinstance(a, str) and isinstance(b, str):
            self.stack.push(a + b)
        elif isinstance(a, NUMERIC) and isinstance(b, NUMERIC):
            if isinstance(a, float) or isinstance(b, float):
                self.stack.push(float(a) + float(b))
            else:
                self.stack.push(a + b)
        else:
            raise TypeError(f"'add' requires matching types: got {type_name(a)} + {type_name(b)} (use 'cast')")

    def _op_sub(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        expect_numeric(a, 'sub'); expect_numeric(b, 'sub')
        self.stack.push(float(a) - float(b) if isinstance(a, float) or isinstance(b, float) else a - b)

    def _op_mul(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        expect_numeric(a, 'mul'); expect_numeric(b, 'mul')
        self.stack.push(float(a) * float(b) if isinstance(a, float) or isinstance(b, float) else a * b)

    def _op_div(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        expect_numeric(a, 'div'); expect_numeric(b, 'div')
        if b == 0: raise ZeroDivisionError("Division by zero")
        self.stack.push(float(a) / float(b) if isinstance(a, float) or isinstance(b, float) else a // b)

    def _op_mod(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        expect_numeric(a, 'mod'); expect_numeric(b, 'mod')
        if b == 0: raise ZeroDivisionError("Modulo by zero")
        self.stack.push(float(a) % float(b) if isinstance(a, float) or isinstance(b, float) else a % b)

    def _op_pow(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        expect_numeric(a, 'pow'); expect_numeric(b, 'pow')
        self.stack.push(a ** b)

    def _op_neg(self, args):
        a = expect_numeric(self.stack.pop(), 'neg')
        self.stack.push(-a)

    def _op_abs(self, args):
        a = expect_numeric(self.stack.pop(), 'abs')
        self.stack.push(abs(a))

    def _op_min(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        expect_numeric(a, 'min'); expect_numeric(b, 'min')
        self.stack.push(min(a, b))

    def _op_max(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        expect_numeric(a, 'max'); expect_numeric(b, 'max')
        self.stack.push(max(a, b))

    def _op_rand(self, args):
        if len(args) >= 2:
            lo, hi = int(self._resolve(args[0])), int(self._resolve(args[1]))
        else:
            hi = self.stack.pop()
            lo = self.stack.pop()
        self.stack.push(random.randint(int(lo), int(hi)))

    # ─── Bitwise ──────────────────────────────────────────────────────────

    def _op_band(self, args):
        b = int(expect_type(self._resolve(args[0]) if args else self.stack.pop(), int, 'band'))
        a = int(expect_type(self.stack.pop(), int, 'band'))
        self.stack.push(a & b)

    def _op_bor(self, args):
        b = int(expect_type(self._resolve(args[0]) if args else self.stack.pop(), int, 'bor'))
        a = int(expect_type(self.stack.pop(), int, 'bor'))
        self.stack.push(a | b)

    def _op_bnot(self, args):
        self.stack.push(~expect_type(self.stack.pop(), int, 'bnot'))

    def _op_bxor(self, args):
        b = int(expect_type(self._resolve(args[0]) if args else self.stack.pop(), int, 'bxor'))
        a = int(expect_type(self.stack.pop(), int, 'bxor'))
        self.stack.push(a ^ b)

    def _op_shl(self, args):
        b = int(expect_type(self._resolve(args[0]) if args else self.stack.pop(), int, 'shl'))
        a = int(expect_type(self.stack.pop(), int, 'shl'))
        self.stack.push(a << b)

    def _op_shr(self, args):
        b = int(expect_type(self._resolve(args[0]) if args else self.stack.pop(), int, 'shr'))
        a = int(expect_type(self.stack.pop(), int, 'shr'))
        self.stack.push(a >> b)

    # ─── Logic ────────────────────────────────────────────────────────────

    def _op_eq(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        if isinstance(a, NUMERIC) and isinstance(b, NUMERIC):
            self.stack.push(float(a) == float(b))
        else:
            self.stack.push(str(a) == str(b))

    def _op_neq(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        if isinstance(a, NUMERIC) and isinstance(b, NUMERIC):
            self.stack.push(float(a) != float(b))
        else:
            self.stack.push(str(a) != str(b))

    def _op_gt(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        self.stack.push(a > b)

    def _op_lt(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        self.stack.push(a < b)

    def _op_gte(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        self.stack.push(a >= b)

    def _op_lte(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        self.stack.push(a <= b)

    def _op_and(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        self.stack.push(bool(a) and bool(b))

    def _op_or(self, args):
        b = self._resolve(args[0]) if args else self.stack.pop()
        a = self.stack.pop()
        self.stack.push(bool(a) or bool(b))

    def _op_not(self, args):
        self.stack.push(not bool(self.stack.pop()))

    # ─── Conditional ──────────────────────────────────────────────────────

    def _op_if(self, args):
        """if a op b - skip next line if condition is false."""
        if len(args) < 3:
            raise RuntimeError("'if' requires: if <a> <op> <b>")
        a = self._resolve(args[0])
        op = args[1]
        b = self._resolve(args[2])
        if op in ('>', '<', '>=', '<='):
            expect_same_type(a, b, f'if {op}')
        if not self._compare(a, op, b):
            self.skip_next = True

    def _compare(self, a, op, b):
        if isinstance(a, NUMERIC) and isinstance(b, NUMERIC):
            a, b = float(a), float(b)
        if op == '==': return a == b
        if op == '!=': return a != b
        if op == '>': return a > b
        if op == '<': return a < b
        if op == '>=': return a >= b
        if op == '<=': return a <= b
        raise RuntimeError(f"Unknown operator: '{op}' (use == != > < >= <=)")

    # ─── Strings ──────────────────────────────────────────────────────────

    def _op_upper(self, args):
        self.stack.push(expect_type(self.stack.pop(), str, 'upper').upper())

    def _op_lower(self, args):
        self.stack.push(expect_type(self.stack.pop(), str, 'lower').lower())

    def _op_split(self, args):
        s = expect_type(self.stack.pop(), str, 'split')
        delim = args[0] if args else expect_type(self.stack.pop(), str, 'split')
        self.stack.push(s.split(delim))

    def _op_join(self, args):
        lst = expect_type(self.stack.pop(), list, 'join')
        delim = args[0] if args else expect_type(self.stack.pop(), str, 'join')
        self.stack.push(delim.join(str(x) for x in lst))

    def _op_find(self, args):
        s = expect_type(self.stack.pop(), str, 'find')
        target = args[0] if args else expect_type(self.stack.pop(), str, 'find')
        self.stack.push(s.find(target))

    def _op_replace(self, args):
        s = expect_type(self.stack.pop(), str, 'replace')
        if len(args) >= 2:
            old, new = args[0], args[1]
        else:
            new = expect_type(self.stack.pop(), str, 'replace')
            old = expect_type(self.stack.pop(), str, 'replace')
        self.stack.push(s.replace(old, new))

    def _op_substr(self, args):
        s = expect_type(self.stack.pop(), str, 'substr')
        start = int(args[0]) if args else 0
        end = int(args[1]) if len(args) > 1 else len(s)
        self.stack.push(s[start:end])

    def _op_char(self, args):
        val = self.stack.pop()
        if isinstance(val, int):
            self.stack.push(chr(val))
        elif isinstance(val, str) and len(val) == 1:
            self.stack.push(ord(val))
        else:
            raise TypeError(f"'char' requires int or single char str, got {type_name(val)}")

    def _op_repeat(self, args):
        count = expect_type(self.stack.pop(), int, 'repeat')
        s = expect_type(self.stack.pop(), str, 'repeat')
        self.stack.push(list(s * count))

    # ─── Collections ──────────────────────────────────────────────────────

    def _op_len(self, args):
        if args and self.heap.has(args[0]):
            val = self.heap.get(args[0])
        else:
            val = self.stack.pop()
        if not isinstance(val, (str, list, dict)):
            raise TypeError(f"'len' requires str/list/dict, got {type_name(val)}")
        self.stack.push(len(val))

    def _op_idx(self, args):
        container = self.heap.get(args[0])
        key = self._resolve(args[1])
        if isinstance(container, list):
            i = expect_type(key, int, 'idx')
            if i < 0 or i >= len(container):
                raise IndexError(f"Index {i} out of bounds (list length {len(container)})")
            self.stack.push(container[i])
        elif isinstance(container, dict):
            if key not in container:
                raise KeyError(f"Key {repr(key)} not found in dict")
            self.stack.push(container[key])
        elif isinstance(container, str):
            i = expect_type(key, int, 'idx')
            if i < 0 or i >= len(container):
                raise IndexError(f"Index {i} out of bounds (str length {len(container)})")
            self.stack.push(container[i])
        else:
            raise TypeError(f"'idx' requires list/dict/str, got {type_name(container)}")

    def _op_setidx(self, args):
        name = args[0]
        if not self.heap.is_mutable(name):
            raise RuntimeError(f"Cannot mutate immutable variable: '{name}'")
        container = self.heap.get(name)
        key = self._resolve(args[1])
        val = self._resolve(args[2]) if len(args) > 2 else self.stack.pop()
        if isinstance(container, list):
            i = expect_type(key, int, 'setidx')
            if i < 0 or i >= len(container):
                raise IndexError(f"Index {i} out of bounds (list length {len(container)})")
            container[i] = val
        elif isinstance(container, dict):
            container[key] = val
        elif isinstance(container, str):
            lst = list(container)
            i = expect_type(key, int, 'setidx')
            if i < 0 or i >= len(lst):
                raise IndexError(f"Index {i} out of bounds (str length {len(lst)})")
            lst[i] = val
            self.heap.save(name, lst)
        else:
            raise TypeError(f"'setidx' requires list/dict/str, got {type_name(container)}")

    def _op_append(self, args):
        name = args[0]
        if not self.heap.is_mutable(name):
            raise RuntimeError(f"Cannot mutate immutable variable: '{name}'")
        container = self.heap.get(name)
        expect_type(container, list, 'append')
        val = self._resolve(args[1]) if len(args) > 1 else self.stack.pop()
        container.append(val)

    def _op_pop(self, args):
        name = args[0]
        if not self.heap.is_mutable(name):
            raise RuntimeError(f"Cannot mutate immutable variable: '{name}'")
        container = self.heap.get(name)
        expect_type(container, list, 'pop')
        if not container:
            raise RuntimeError(f"Cannot pop from empty list '{name}'")
        self.stack.push(container.pop())

    def _op_slice(self, args):
        container = self.heap.get(args[0])
        start = int(self._resolve(args[1]))
        end = int(self._resolve(args[2])) if len(args) > 2 else len(container)
        self.stack.push(container[start:end])

    def _op_has(self, args):
        container = self.heap.get(args[0])
        key = self._resolve(args[1])
        if isinstance(container, dict):
            self.stack.push(key in container)
        elif isinstance(container, list):
            self.stack.push(0 <= int(key) < len(container))
        else:
            raise TypeError(f"'has' requires list/dict, got {type_name(container)}")

    # ─── Casting ──────────────────────────────────────────────────────────

    def _op_cast(self, args):
        target = args[0]
        val = self.stack.pop()
        try:
            if target == T_INT:
                if isinstance(val, bool): r = int(val)
                elif isinstance(val, float): r = int(val)
                elif isinstance(val, int): r = val
                elif isinstance(val, str): r = int(float(val)) if '.' in val else int(val)
                else: raise ValueError()
            elif target == T_FLOAT: r = float(val)
            elif target == T_STR: r = str(val)
            elif target == T_LIST:
                if isinstance(val, str): r = list(val)
                elif isinstance(val, list): r = val
                else: r = [val]
            elif target == T_BOOL: r = bool(val)
            else: raise RuntimeError(f"Unknown cast target: '{target}'")
        except (ValueError, TypeError):
            raise TypeError(f"Cannot cast {type_name(val)} ({repr(val)}) to {target}")
        self.stack.push(r)

    def _op_typeof(self, args):
        self.stack.push(type_name(self.stack.pop()))

    # ─── Control Flow ─────────────────────────────────────────────────────

    def _op_jump(self, args):
        if args[0] not in self.labels:
            raise RuntimeError(f"Undefined label: '{args[0]}'")
        self.pointer = self.labels[args[0]]

    def _op_call(self, args):
        if args[0] not in self.labels:
            raise RuntimeError(f"Undefined label: '{args[0]}'")
        self.call_stack.append(self.pointer)
        self.pointer = self.labels[args[0]]

    def _op_ret(self, args):
        if not self.call_stack:
            raise RuntimeError("'ret' with empty call stack")
        self.pointer = self.call_stack.pop()

    def _op_exit(self, args):
        sys.exit(int(args[0]) if args else 0)

    # ─── Loops ────────────────────────────────────────────────────────────

    def _op_loop(self, args):
        count = int(self._resolve(args[0]))
        end_ptr = self._find_block_end('loop', 'endloop', self.pointer)
        if count <= 0:
            self.pointer = end_ptr + 1
        else:
            self.loop_stack.append({'type': 'loop', 'start': self.pointer, 'end': end_ptr, 'current': 0, 'limit': count})
            self.heap.save('_i', 0)

    def _op_endloop(self, args):
        if not self.loop_stack or self.loop_stack[-1]['type'] != 'loop':
            raise RuntimeError("'endloop' without matching 'loop'")
        ctx = self.loop_stack[-1]
        ctx['current'] += 1
        if ctx['current'] < ctx['limit']:
            self.pointer = ctx['start']
            self.heap.save('_i', ctx['current'])
        else:
            self.loop_stack.pop()

    def _op_while(self, args):
        if len(args) < 3:
            raise RuntimeError("'while' requires: while <a> <op> <b>")
        end_ptr = self._find_block_end('while', 'endwhile', self.pointer)
        a = self._resolve(args[0])
        b = self._resolve(args[2])
        if not self._compare(a, args[1], b):
            self.pointer = end_ptr + 1
        else:
            self.loop_stack.append({'type': 'while', 'start': self.pointer - 1, 'end': end_ptr, 'args': args})

    def _op_endwhile(self, args):
        if not self.loop_stack or self.loop_stack[-1]['type'] != 'while':
            raise RuntimeError("'endwhile' without matching 'while'")
        ctx = self.loop_stack[-1]
        wargs = ctx['args']
        if self._compare(self._resolve(wargs[0]), wargs[1], self._resolve(wargs[2])):
            self.pointer = ctx['start'] + 1
        else:
            self.loop_stack.pop()

    def _op_break(self, args):
        if not self.loop_stack: raise RuntimeError("'break' outside of loop")
        ctx = self.loop_stack.pop()
        self.pointer = ctx['end'] + 1

    def _op_continue(self, args):
        if not self.loop_stack: raise RuntimeError("'continue' outside of loop")
        ctx = self.loop_stack[-1]
        if ctx['type'] == 'loop':
            ctx['current'] += 1
            if ctx['current'] < ctx['limit']:
                self.pointer = ctx['start']
                self.heap.save('_i', ctx['current'])
            else:
                self.loop_stack.pop()
                self.pointer = ctx['end'] + 1
        else:
            self.pointer = ctx['end']

    def _find_block_end(self, open_kw, close_kw, start):
        depth = 1
        ptr = start
        while ptr < len(self.program):
            parts = self.program[ptr].strip().split()
            word = parts[0] if parts else ''
            if word == open_kw: depth += 1
            elif word == close_kw:
                depth -= 1
                if depth == 0: return ptr
            ptr += 1
        raise RuntimeError(f"No matching '{close_kw}' for '{open_kw}'")

    # ─── I/O ──────────────────────────────────────────────────────────────

    def _op_print(self, args):
        if args: print(' '.join(args))
        else: print(self.stack.pop())

    def _op_emit(self, args):
        val = self._resolve(args[0]) if args else self.stack.pop()
        print(str(val), end='', flush=True)

    def _op_input(self, args):
        self.stack.push(input(args[0] if args else ""))

    def _op_draw(self, args):
        os.system('cls' if os.name == 'nt' else 'clear')
        lst = self.heap.get(args[0])
        width = int(args[1])
        for r in range(0, len(lst), width):
            print(" ".join(str(x) for x in lst[r:r + width]))

    # ─── Game / System ────────────────────────────────────────────────────

    def _op_cls(self, args):
        os.system('cls' if os.name == 'nt' else 'clear')

    def _op_sleep(self, args):
        ms = int(args[0]) if args else expect_type(self.stack.pop(), int, 'sleep')
        _time.sleep(ms / 1000.0)

    def _op_time(self, args):
        self.stack.push(int(_time.time() * 1000))

    def _op_color(self, args):
        code = int(args[0]) if args else int(self.stack.pop())
        print(f"\033[{code}m", end='')

    def _op_cursor(self, args):
        row = int(self._resolve(args[0]))
        col = int(self._resolve(args[1]))
        print(f"\033[{row};{col}H", end='')

    def _op_key(self, args):
        if os.name == 'nt':
            import msvcrt
            self.stack.push(msvcrt.getch().decode('utf-8', errors='ignore') if msvcrt.kbhit() else '')
        else:
            import select, tty, termios
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                r, _, _ = select.select([sys.stdin], [], [], 0)
                self.stack.push(sys.stdin.read(1) if r else '')
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)

    # ─── File I/O ─────────────────────────────────────────────────────────

    def _op_fopen(self, args):
        fname = args[0]
        mode = args[1] if len(args) > 1 else 'r'
        self.files[fname] = open(fname, mode)

    def _op_fread(self, args):
        fname = args[0]
        if fname in self.files: self.stack.push(self.files[fname].read())
        else:
            with open(fname, 'r') as f: self.stack.push(f.read())

    def _op_fwrite(self, args):
        fname = args[0]
        data = args[1] if len(args) > 1 else str(self.stack.pop())
        if fname in self.files: self.files[fname].write(data)
        else:
            with open(fname, 'w') as f: f.write(data)

    def _op_fclose(self, args):
        fname = args[0]
        if fname not in self.files: raise RuntimeError(f"File not open: '{fname}'")
        self.files[fname].close()
        del self.files[fname]

    # ─── Debug ────────────────────────────────────────────────────────────

    def _op_debug(self, args):
        print(f"  [DBG] ptr={self.pointer} stack={self.stack}")
        for name in args:
            if self.heap.has(name):
                v = self.heap.get(name)
                m = "mut" if self.heap.is_mutable(name) else "let"
                print(f"  [DBG] {m} {name} = {repr(v)} ({type_name(v)})")

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _fatal(self, msg):
        print(f"[KSM Fatal] {msg}")
        sys.exit(1)

# ─── Entry Point ──────────────────────────────────────────────────────────────

def run_file(filepath):
    vm = VM()
    try:
        vm.load(filepath)
        vm.run()
    except SystemExit:
        raise
    except Exception as e:
        ptr = vm.pointer
        line_info = vm.program[ptr - 1] if 0 < ptr <= len(vm.program) else '???'
        print(f"\n[KSM Error] Line {ptr}: {line_info}")
        print(f"  {type(e).__name__}: {e}")
        sys.exit(1)
    finally:
        for f in vm.files.values():
            try: f.close()
            except: pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("KSMC v4 - Strict stack-based assembly (one instruction per line)")
        print("Usage: python ksmc.py <file.ksm>")
        sys.exit(0)
    run_file(sys.argv[1])
