
# KSM is an assembly-like, scripting language. (NOT EVEN CLOSE TO BEING DONE)

Ensure your script file ends with `.ksm` and has `.ksm` as its **very first line**.

Run the script using the Python interpreter: (or compile and run like ./ksmc your_script.ksm)
```bash
python ksmc.py your_script.ksm
```

---

## Command Reference

| Command | Syntax | How it works |
| --- | --- | --- |
| **`>>`** | ... | >> | Takes the most recently generated result (`last_val`) and pushes it onto the **stack**. |
| **`push`** | `push <type> <val>` | Converts `<val>` to the requested type (`str`, `int`, `float`, `list`, `dict`) and places it on top of the **stack**. |
| **`save`** | `save <key>` | Removes the top item from the **stack** and saves it permanently in the **heap** under the name `<key>`. |
| **`store`** | `store <key>=<val>` | Directly saves `<val>` into the **heap** without using the stack. (Auto-detects integers, floats, lists, and dicts). |
| **`get`** | `get <key>` | Looks up `<key>` in the **heap** and holds its value in `last_val`. |
| **`index`** | `index <key> <idx>` | Finds the item at position `<idx>` (or key name) inside a list/string/dictionary in the **heap**, holding the result in `last_val`. |
| **`set`** | `set <key> <idx> <v>` | Overwrites the item at position `<idx>` (or key name) inside the **heap** list/string/dictionary with `<v>`. |
| **`rand`** | `rand <min> <max>` | Generates a random integer and holds it in `last_val`. |
| **`add`** | `add [val]` | Pops the top item off the **stack**. Adds it to `<val>` (or pops a second item off the stack if no `<val>` is given). Holds result in `last_val`. |
| **`sub`** | `sub [val]` | Pops the top item off the **stack** and subtracts `<val>` (or a second popped item). Holds result in `last_val`. |
| **`mult`** | `mult [val]` | Pops the top item off the **stack** and multiplies it by `<val>` (or a second popped item). Holds result in `last_val`. |
| **`div`** | `div [val]` | Pops the top item off the **stack** and divides it by `<val>` (or a second popped item). Holds result in `last_val`. |
| **`mod`** | `mod [val]` | Pops the top item off the **stack** and performs a modulo operation with `<val>` (or a second popped item). Holds result in `last_val`. |
| **`ifeq`** | `ifeq <key> <val>` | Looks at a value in the **heap**. If it **does not equal** `<val>`, execution skips the rest of the current line. |
| **`ifneq`** | `ifneq <key> <val>` | Looks at a value in the **heap**. If it **equals** `<val>`, execution skips the rest of the current line. |
| **`ifgt`** | `ifgt <key> <val>` | Looks at a value in the **heap**. If it **is <=** `<val>`, execution skips the rest of the current line. |
| **`iflt`** | `iflt <key> <val>` | Looks at a value in the **heap**. If it **is >=** `<val>`, execution skips the rest of the current line. |
| **`len`** | `len <key>` | Calculates the length of a string, list, or dictionary in the **heap** and holds it in `last_val`. |
| **`jump`** | `jump <label>` | Jumps execution directly to `label <label>`. |
| **`call`** | `call <label>` | Pushes the current line number onto an internal call stack and jumps execution directly to `label <label>`. |
| **`ret`** | `ret` | Pops the last saved line position from the call stack and returns execution to the statement immediately following the original `call`. |
| **`draw`** | `draw <key> <width>` | Clears the screen, takes a string/list from the **heap**, and prints it as a 2D grid wrapped at `<width>`. |
| **`input`** | `input [prompt]` | Pauses for user input. Displays `[prompt]` if provided; otherwise defaults to `input: `. Converts input to lowercase and holds it in `last_val`. |
| **`print`** | `print [val]` | Prints `<val>`. If no `<val>` is provided, it pops and prints the top item of the **stack**. |

---

### Execution Flow & Pipelining (`|`)

Commands can be chained on a single line using the pipe (`|`) delimiter. Execution runs sequentially from left to right. If a conditional check command (`ifeq`, `ifneq`, `ifgt`, `iflt`) evaluates to **false**, the interpreter immediately stops processing the remainder of that line and drops to the next line in the script.

### Comments & Whitespace

* Any line starting with `#` is classified as a comment and skipped entirely.
* Empty lines are completely ignored.

```

```
