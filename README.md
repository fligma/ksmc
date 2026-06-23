KSM is an assembly-like, scripting language.

---

1. Ensure your script file ends with `.ksm` and has `.ksm` as its **very first line**.
2. Run the script using the Python interpreter:

```bash
python ksmc.py your_script.ksm

```

---

## Command Reference

| Command | Syntax | Description |
| --- | --- | --- |
| **`>>`** | `... | >>` | **Feed operator**: Pushes the last evaluated value (`last_val`) onto the stack. |
| **`push`** | `push <type> <val>` | Casts `<val>` to `<type>` (`str`/`int`/`float`/`list`) and pushes it onto the stack. |
| **`save`** | `save <key>` | Pops the top item off the stack and saves it to the heap under `<key>`. |
| **`store`** | `store <key>=<val>` | Directly maps a variable in the heap (auto-detects integers). |
| **`get`** | `get <key>` | Retrieves a value from the heap and holds it in `last_val`. |
| **`index`** | `index <key> <idx>` | Sets `last_val` to the element at `<idx>` in a heap list/string (casts strings to list). |
| **`set`** | `set <key> <idx> <v>` | Overwrites the element at `<idx>` in a heap list/string with `<v>`. |
| **`rand`** | `rand <min> <max>` | Generates a random integer (inclusive) and sets `last_val`. |
| **`add`** | `add [value]` | Pops `a`. Adds `value` (or pops `b` if omitted). Sets `last_val`. Concatenates strings. |
| **`sub`** | `sub [value]` | Pops `a`. Subtracts `value` (or pops `b` if omitted). Sets `last_val`. |
| **`mult`** | `mult [value]` | Pops `a`. Multiplies by `value` (or pops `b`). Sets `last_val`. Replicates strings/lists. |
| **`ifeq`** | `ifeq <key> <val>` | **Guard clause**: If heap value != `<val>`, skips the rest of the current line. |
| **`ifgt`** | `ifgt <key> <val>` | **Guard clause**: If heap value <= `<val>`, skips the rest of the current line. |
| **`jump`** | `jump <label>` | Jumps execution pointer to the line containing `label <label>`. |
| **`draw`** | `draw <key> <w>` | Clears screen and prints a 1D heap list/string as a 2D grid wrapped at width `<w>`. |
| **`input`** | `input` | Prompts `Move (wasd): `, converts input to lowercase, and sets `last_val`. |
| **`print`** | `print [value]` | Prints `value`. If omitted, pops and prints the top item of the stack. |
