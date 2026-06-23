KSM is an assembly-like, scripting language. (NOT EVEN CLOSE TO BEING DONE)

Ensure your script file ends with `.ksm` and has `.ksm` as its **very first line**.

Run the script using the Python interpreter:
```bash
python ksmc.py your_script.ksm

```

---

## Command Reference

| Command | Syntax | How it works |
| --- | --- | --- |
| **`>>`** | <code>... &#124; >><code> | Takes the most recently generated result (`last_val`) and pushes it onto the **stack**. |
| **`push`** | `push <type> <val>` | Converts `<val>` to the requested type (`str`, `int`, `float`, `list`) and places it on top of the **stack**. |
| **`save`** | `save <key>` | Removes the top item from the **stack** and saves it permanently in the **heap** under the name `<key>`. |
| **`store`** | `store <key>=<val>` | Directly saves `<val>` into the **heap** without using the stack. (Auto-detects integers). |
| **`get`** | `get <key>` | Looks up `<key>` in the **heap** and holds its value in `last_val`. |
| **`index`** | `index <key> <idx>` | Finds the item at position `<idx>` inside a list/string in the **heap**, holding the result in `last_val`. |
| **`set`** | `set <key> <idx> <v>` | Overwrites the item at position `<idx>` inside the **heap** list/string with `<v>`. |
| **`rand`** | `rand <min> <max>` | Generates a random integer and holds it in `last_val`. |
| **`add`** | `add [val]` | Pops the top item off the **stack**. Adds it to `<val>` (or pops a second item off the stack if no `<val>` is given). Holds result in `last_val`. |
| **`sub`** | `sub [val]` | Pops the top item off the **stack** and subtracts `<val>` (or a second popped item). Holds result in `last_val`. |
| **`mult`** | `mult [val]` | Pops the top item off the **stack** and multiplies it by `<val>` (or a second popped item). Holds result in `last_val`. |
| **`ifeq`** | `ifeq <key> <val>` | Looks at a value in the **heap**. If it **does not equal** `<val>`, execution skips the rest of the current line. |
| **`ifgt`** | `ifgt <key> <val>` | Looks at a value in the **heap**. If it **is <=** `<val>`, execution skips the rest of the current line. |
| **`jump`** | `jump <label>` | Jumps execution directly to `label <label>`. |
| **`draw`** | `draw <key> <width>` | Clears the screen, takes a string/list from the **heap**, and prints it as a 2D grid wrapped at `<width>`. |
| **`input`** | `input [prompt]` | Pauses for user input. Displays `[prompt]` if provided; otherwise defaults to `input: `. Converts input to lowercase and holds it in `last_val`. |
| **`print`** | `print [val]` | Prints `<val>`. If no `<val>` is provided, it pops and prints the top item of the **stack**. |

---
