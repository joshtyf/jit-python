# jit-python

> **Note:** This project is a proof of concept and is not intended for production use.

Dynamically generate and improve Python methods at runtime using an AI agent powered by [Google ADK](https://google.github.io/adk-docs/).

## Inspiration

This project is inspired by [luai.nvim](https://github.com/tjdevries/luai.nvim) by [@tjdevries](https://github.com/tjdevries), which applies the same concept to Lua in Neovim. Watch the original video [here](https://www.youtube.com/watch?v=HOO_yaidVWk).

## How it works

`JitPython` intercepts calls to methods that don't exist yet and asks a Gemini-backed agent to write them. The generated code is compiled on the fly, bound to the instance, and called — all transparently. Describe what you want once, and the method is yours. Not happy with the result? Pass feedback to `improve_method` and the agent will revise it.

If the generated method requires a third-party package, the agent will emit code to install it via `pip` at runtime.

> **Security warning:** `JitPython` executes AI-generated code and can install arbitrary pip packages at runtime. Run at your own risk.

## Installation

```bash
pip install git+https://github.com/joshtyf/jit-python.git
```

Or clone and install locally:

```bash
git clone https://github.com/joshtyf/jit-python.git
cd jit-python
pip install -e .
```

## Requirements

A `GEMINI_MODEL` environment variable can be set to control which Gemini model is used (defaults to `gemini-3-flash-preview`). A valid Google API key must be configured in your environment.

## Usage

```python
from jit_python import JitPython

jit = JitPython()

# --- Example 1: No external libraries required ---
# The agent generates pure Python code with no imports needed.
result = jit.fizzbuzz(
    15,
    __description="Return 'FizzBuzz' if divisible by 3 and 5, 'Fizz' if by 3, 'Buzz' if by 5, else the number as a string."
)
print(result)  # 'FizzBuzz'
print(jit.fizzbuzz(7))  # '7'

# --- Example 2: Builtin standard library required ---
# The agent imports from Python's stdlib (e.g. 're') inside the function body.
emails = jit.extract_emails(
    "Contact us at hello@example.com or support@foo.io",
    __description="Extract all email addresses from a string and return them as a list."
)
print(emails)  # ['hello@example.com', 'support@foo.io']

# Refine with feedback
jit.improve_method("extract_emails", "Also validate that each address has a valid TLD before returning it.")
print(jit.extract_emails("reach me at jane@bar.com"))  # ['jane@bar.com']

# --- Example 3: External library required ---
# WARNING: The agent will install the externals package (e.g. 'requests') via pip at runtime.
# Only run this if you trust the generated code and accept the security implications.
html = jit.fetch_webpage(
    "https://example.com",
    __description="Fetch the HTML content of a URL using the requests library and return it as a string."
)
print(html[:200])

# Inspect the generated source for any example
print(jit.get_method_code("fetch_webpage"))
```

## API

| Method | Description |
|---|---|
| `JitPython()` | Instantiates the agent. Emits a `UserWarning` about runtime code execution. |
| `jit.<method_name>(*args, __description=..., **kwargs)` | Calls a dynamically generated method. On first call, `__description` is required. Subsequent calls use the cached compiled method. |
| `jit.improve_method(method_name, feedback)` | Re-generates a method using the original session context plus the provided feedback. |
| `jit.get_method_code(method_name)` | Returns the raw source code of a previously generated method. |
