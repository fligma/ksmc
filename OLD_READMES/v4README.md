# KSMC - KSM Compiler/Interpreter v4

A strict, stack-based assembly language with Forth-like semantics. Designed for games, scripts, and automation.

## Design Principles

- **One instruction per line** — assembly style, no pipe separators
- **One way to do everything** — no redundant operations
- **Data-safe** — strict types, explicit mutability, bounds checking, no implicit coercion
- **Pure stack machine** — all value-producing ops push to stack
- **Explicit casting** — no automatic type conversion

## Quick Start

```bash
python ksmc.py program.ksm
```

Every `.ksm` file must start with the `.ksm` header:

```ksm
.ksm
push 42
print
```

## Stack Model

KSMC is a **stack machine**. Operations consume values from the stack and push results back.

**Stack convention:** Last pushed = first operand (top of stack).

```ksm
push 10
push 3
add
print        # 13 (10 + 3)
```

### Stack Operations

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `push <val>` | `-> v` | Push literal onto stack |
| `dup` | `a -> a a` | Duplicate top |
| `drop` | `a ->` | Remove top |
| `swap` | `a b -> b a` | Swap top two |
| `over` | `a b -> a b a` | Copy second to top |
| `rot` | `a b c -> b c a` | Rotate top three |
| `pick <n>` | `... a -> ... a a` | Copy nth element |
| `depth` | `-> n` | Push stack depth |
| `clear` | `... ->` | Empty stack |

## Arithmetic

All arithmetic is **strict**: numeric types only (int/float). Int + float auto-widens to float.

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `add` | `a b -> a+b` | Add (numbers) or concat (strings) |
| `sub` | `a b -> a-b` | Subtract |
| `mul` | `a b -> a*b` | Multiply |
| `div` | `a b -> a/b` | Integer division (float div if either is float) |
| `mod` | `a b -> a%b` | Modulo |
| `pow` | `a b -> a^b` | Power |
| `neg` | `a -> -a` | Negate |
| `abs` | `a -> \|a\|` | Absolute value |
| `min` | `a b -> min` | Minimum |
| `max` | `a b -> max` | Maximum |
| `rand` | `lo hi -> r` | Random int in [lo, hi] |

## Bitwise Operations

Strict: **int only**.

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `band` | `a b -> a&b` | Bitwise AND |
| `bor` | `a b -> a\|b` | Bitwise OR |
| `bxor` | `a b -> a^b` | Bitwise XOR |
| `bnot` | `a -> ~a` | Bitwise NOT |
| `shl` | `a b -> a<<b` | Left shift |
| `shr` | `a b -> a>>b` | Right shift |

## Logic

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `and` | `a b -> bool` | Logical AND |
| `or` | `a b -> bool` | Logical OR |
| `not` | `a -> bool` | Logical NOT |

## Comparisons

### Stack Comparisons (push bool)

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `eq` | `a b -> bool` | Equal |
| `neq` | `a b -> bool` | Not equal |
| `gt` | `a b -> bool` | Greater than |
| `lt` | `a b -> bool` | Less than |
| `gte` | `a b -> bool` | Greater or equal |
| `lte` | `a b -> bool` | Less or equal |

### Conditional (`if`)

```ksm
if <a> <op> <b>
<skipped-if-false>
end
```

Skips the **next line** if condition is false. Operators: `==`, `!=`, `>`, `<`, `>=`, `<=`

```ksm
mut x 5
if x > 3
print "x is greater than 3"
end
```

## Memory Model

| Op | Description |
|----|-------------|
| `let <name> [val]` | Declare **immutable** variable. Pops stack if no value given. |
| `mut <name> [val]` | Declare **mutable** variable. Pops stack if no value given. |
| `save <name>` | Pop stack top into variable. Creates mutable if new, errors on immutable. |
| `get <name>` | Push variable value to stack. |
| `del <name>` | Delete a mutable variable. |

**Mutability rules:**
- `let` creates immutable bindings — cannot be reassigned or deleted
- `mut` creates mutable bindings — can be reassigned via `save`
- `save` auto-creates mutable if variable doesn't exist

```ksm
let pi 3.14159
mut counter 0
push 1
save counter        # counter = 1
push 99
save pi             # ERROR: Cannot mutate immutable variable
```

## Control Flow

### Labels and Jumps

```ksm
label my_label
push "Hello"
print
jump my_label       # infinite loop
```

### Subroutines

```ksm
call do_work
print "Returned"
jump end_prog

label do_work
push "Working..."
print
ret

label end_prog
exit 0
```

### Loops

**Fixed count loop:**
```ksm
loop 5
get _i              # loop counter (0-based)
print
endloop
```

**Conditional loop:**
```ksm
mut x 3
while x > 0
get x
print
get x
push 1
sub
save x
endwhile
```

**Loop control:**
- `break` — exit loop
- `continue` — skip to next iteration

### Exit

```ksm
exit 0              # Exit with code
```

## Error Handling

```ksm
try
push 10
push 0
div                 # throws ZeroDivisionError
catch err
print "Caught:"
get err
print
endtry
```

**Throw user errors:**
```ksm
try
push "Something went wrong"
throw
catch err
get err
print
endtry
```

## Imports

Load another `.ksm` file and import its `def` blocks:

```ksm
use "stdlib.ksm"
push 7
double              # imported from stdlib
print               # 14
```

Import with prefix:
```ksm
use "math_lib.ksm" as math
push 5
math.square         # prefixed import
```

**Cycle protection:** Files are tracked by absolute path — importing the same file twice is a no-op.

## String Operations

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `upper` | `s -> S` | Uppercase |
| `lower` | `s -> S` | Lowercase |
| `split` | `s delim -> list` | Split string |
| `join` | `list delim -> s` | Join list |
| `find` | `s target -> int` | Find substring index |
| `replace` | `s old new -> s` | Replace substring |
| `substr` | `s start end -> s` | Extract substring |
| `char` | `int -> char` or `char -> int` | chr/ord |
| `repeat` | `s n -> list` | Repeat string as char list |

## Collections

### Lists

```ksm
push [1, 2, 3]
mut mylist

len mylist          # 3
idx mylist 1        # 2
setidx mylist 1 99
append mylist 4
pop mylist          # removes and returns last
slice mylist 0 2    # [1, 99]
```

### Dicts

```ksm
push {"name": "KSM", "ver": 4}
mut info

idx info "name"     # "KSM"
setidx info "ver" 5
has info "name"     # true
has info "missing"  # false
```

**Bounds checking:** All `idx`/`setidx` operations check bounds and raise errors on out-of-range access.

## Casting

**Explicit only** — no implicit type coercion.

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `cast int` | `val -> int` | Convert to int |
| `cast float` | `val -> float` | Convert to float |
| `cast str` | `val -> str` | Convert to string |
| `cast list` | `val -> list` | Convert to list |
| `cast bool` | `val -> bool` | Convert to bool |
| `typeof` | `val -> str` | Push type name |

```ksm
push "42"
cast int
push 1
add                 # 43 (not "421")
```

## I/O

| Op | Description |
|----|-------------|
| `print [val]` | Print with newline. No arg = pop stack. |
| `emit [val]` | Print without newline. No arg = pop stack. |
| `input [prompt]` | Read line, push to stack. |

## File I/O

| Op | Description |
|----|-------------|
| `fopen <name> [mode]` | Open file (default: read) |
| `fread <name>` | Read file contents, push to stack |
| `fwrite <name> [data]` | Write to file. No data = pop stack. |
| `fclose <name>` | Close file |

## Game/System

| Op | Description |
|----|-------------|
| `cls` | Clear screen |
| `sleep <ms>` | Pause execution |
| `time` | Push current timestamp (ms) |
| `color <ansi>` | Set terminal color |
| `cursor <row> <col>` | Move cursor |
| `key` | Non-blocking key read, push char or empty string |
| `draw <name> <width>` | Clear screen and draw grid |

## Syscall Bridge

The `sys.*` namespace exposes Python stdlib for building KSMC libraries.

### sys.json

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `sys.json encode` | `val -> str` | Serialize to JSON |
| `sys.json decode` | `str -> val` | Parse JSON |

### sys.re (Regex)

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `sys.re find` | `s pattern -> match` | First match |
| `sys.re findall` | `s pattern -> list` | All matches |
| `sys.re split` | `s pattern -> list` | Split by pattern |
| `sys.re replace` | `s pattern repl -> s` | Replace matches |
| `sys.re match` | `s pattern -> bool` | Full match from start |

### sys.http

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `sys.http get` | `url -> dict` | GET request `{status, body}` |
| `sys.http post` | `url data -> dict` | POST request `{status, body}` |

### sys.os

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `sys.os env` | `key -> str` | Get environment variable |
| `sys.os exec` | `cmd -> dict` | Run shell command `{stdout, stderr, code}` |
| `sys.os args` | `-> list` | Get CLI arguments |
| `sys.os cwd` | `-> str` | Get current working directory |
| `sys.os exists` | `path -> bool` | Check if path exists |

### sys.math

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `sys.math pi` | `-> float` | Push π |
| `sys.math e` | `-> float` | Push e |
| `sys.math sqrt` | `n -> float` | Square root |
| `sys.math sin/cos/tan` | `n -> float` | Trig functions |
| `sys.math floor` | `n -> int` | Floor |
| `sys.math ceil` | `n -> int` | Ceiling |
| `sys.math log` | `n -> float` | Natural log |

### sys.time

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `sys.time now` | `-> int` | Unix timestamp (seconds) |
| `sys.time ms` | `-> int` | Unix timestamp (milliseconds) |
| `sys.time sleep` | `ms ->` | Sleep |
| `sys.time format` | `[fmt] -> str` | Format current time |

### sys.str

| Op | Stack Effect | Description |
|----|-------------|-------------|
| `sys.str format` | `template -> str` | Format with `{}` placeholders |
| `sys.str startswith` | `s prefix -> bool` | Check prefix |
| `sys.str endswith` | `s suffix -> bool` | Check suffix |
| `sys.str trim` | `s -> str` | Strip whitespace |
| `sys.str contains` | `s sub -> bool` | Check substring |
| `sys.str repeat` | `s n -> str` | Repeat string |

## Word Definitions (Custom Functions)

Define reusable blocks:

```ksm
def double
dup
add
end

push 7
double
print               # 14
```

Words operate on the **shared stack** — they cannot take parameters or return values directly. Use the stack for input/output.

**Nested blocks in defs:**
```ksm
def is_positive
push 0
gt
end

push 5
is_positive
print               # true
```

## Types

| Type | Literals | Notes |
|------|----------|-------|
| `int` | `42`, `-7`, `0` | Arbitrary precision |
| `float` | `3.14`, `-0.5`, `2.` | IEEE 754 double |
| `str` | `"hello"`, `'world'` | Immutable (Python) |
| `list` | `[1, 2, 3]` | Mutable, heterogeneous |
| `dict` | `{"key": "val"}` | Mutable, any key type |
| `bool` | `true`, `false` | From comparisons/logic |

**No implicit coercion:**
```ksm
push 5
push "hello"
add                 # ERROR: type mismatch
```

Must cast explicitly:
```ksm
push 5
cast str
push "hello"
add                 # "5hello"
```

## Debug

```ksm
debug [name1 name2 ...]    # Print stack and variable states
```

## Examples

### Calculator
```ksm
.ksm
input "First: "
save a
get a
cast int
save a

input "Second: "
save b
get b
cast int
save b

get a
get b
add
save result
print "Sum:"
get result
print
```

### Loop with Accumulator
```ksm
.ksm
mut sum 0
loop 10
get sum
get _i
add
save sum
endloop
print "Sum 0..9:"
get sum
print               # 45
```

### Error Recovery
```ksm
.ksm
try
push "data.json"
fread
sys.json decode
save config
catch err
print "Failed to load config:"
get err
print
push {}
save config
endtry
```

## Building Libraries

Create a `.ksm` file with `def` blocks:

```ksm
.ksm
# math_utils.ksm

def square
dup
mul
end

def cube
dup
dup
mul
mul
end

def factorial
save n
push 1
save result
mut i 1
while i <= n
get result
get i
mul
save result
get i
push 1
add
save i
endwhile
get result
end
```

Use it:
```ksm
.ksm
use "math_utils.ksm"
push 5
square
print               # 25

push 4
cube
print               # 64
```

## Running

```bash
# Run a program
python ksmc.py program.ksm

# Check version/help
python ksmc.py
```

## Limitations

- No first-class functions or closures
- No modules/packages (single file imports only)
- No concurrency/async
- Word definitions share global state (stack + heap)
- No struct/object types (use dicts)

## License

MIT
