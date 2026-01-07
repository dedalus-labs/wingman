# Python Style Reference

[Overview](README.md) | [Guide](guide.md) | [Best Practices](best-practices.md) | [Reference](reference.md)

> Complete style reference adapted from [Google's Python style guide](https://google.github.io/styleguide/pyguide.html). For quick project conventions, see the [Guide](guide.md).

> **Tooling Note:** This reference mentions `pylint`, `Black`, and `Pyink`. At Wingman, we use modern equivalents:
>
> - **Linting/Formatting:** [ruff](https://docs.astral.sh/ruff/) (replaces pylint, Black, isort, Flake8)
> - **Type Checking:** [mypy](https://mypy.readthedocs.io/) now, [ty](https://github.com/astral-sh/ty) at beta
> - **Project Management:** [uv](https://docs.astral.sh/uv/) (replaces pip, poetry, virtualenv)
>
> The style principles in this document still apply; only the tools have changed.

---

<details>
<summary>Table of Contents</summary>

- [1 Background](#s1-background)
- [2 Python Language Rules](#s2-python-language-rules)
  - [2.1 Lint](#s2.1-lint)
  - [2.2 Imports](#s2.2-imports)
  - [2.3 Packages](#s2.3-packages)
  - [2.4 Exceptions](#s2.4-exceptions)
  - [2.5 Mutable Global State](#s2.5-global-variables)
  - [2.6 Nested/Local/Inner Classes and Functions](#s2.6-nested)
  - [2.7 Comprehensions & Generator Expressions](#s2.7-comprehensions)
  - [2.8 Default Iterators and Operators](#s2.8-default-iterators-and-operators)
  - [2.9 Generators](#s2.9-generators)
  - [2.10 Lambda Functions](#s2.10-lambda-functions)
  - [2.11 Conditional Expressions](#s2.11-conditional-expressions)
  - [2.12 Default Argument Values](#s2.12-default-argument-values)
  - [2.13 Properties](#s2.13-properties)
  - [2.14 True/False Evaluations](#s2.14-truefalse-evaluations)
  - [2.16 Lexical Scoping](#s2.16-lexical-scoping)
  - [2.17 Function and Method Decorators](#s2.17-function-and-method-decorators)
  - [2.18 Threading](#s2.18-threading)
  - [2.19 Power Features](#s2.19-power-features)
  - [2.20 Modern Python: from \_\_future\_\_ imports](#s2.20-modern-python)
  - [2.21 Type Annotated Code](#s2.21-type-annotated-code)
- [3 Python Style Rules](#s3-python-style-rules)
  - [3.1 Semicolons](#s3.1-semicolons)
  - [3.2 Line length](#s3.2-line-length)
  - [3.3 Parentheses](#s3.3-parentheses)
  - [3.4 Indentation](#s3.4-indentation)
  - [3.5 Blank Lines](#s3.5-blank-lines)
  - [3.6 Whitespace](#s3.6-whitespace)
  - [3.7 Shebang Line](#s3.7-shebang-line)
  - [3.8 Comments and Docstrings](#s3.8-comments-and-docstrings)
  - [3.10 Strings](#s3.10-strings)
  - [3.11 Files, Sockets, and similar Stateful Resources](#s3.11-files-sockets-closeables)
  - [3.12 TODO Comments](#s3.12-todo-comments)
  - [3.13 Imports formatting](#s3.13-imports-formatting)
  - [3.14 Statements](#s3.14-statements)
  - [3.15 Accessors](#s3.15-accessors)
  - [3.16 Naming](#s3.16-naming)
  - [3.17 Main](#s3.17-main)
  - [3.18 Function length](#s3.18-function-length)
  - [3.19 Type Annotations](#s3.19-type-annotations)
- [4 Parting Words](#4-parting-words)

</details>

## 1 Background

Python is the main dynamic language used at Google. This style guide is a list of _dos and don'ts_ for Python programs.

Many teams use the [Black](https://github.com/psf/black) or [Pyink](https://github.com/google/pyink) auto-formatter to avoid arguing over formatting.

## 2 Python Language Rules

### 2.1 Lint

Run `ruff` over your code.

#### 2.1.1 Definition

`ruff` is a tool for finding bugs and style problems in Python source code. It finds problems that are typically caught by a compiler for less dynamic languages like C and C++.

#### 2.1.2 Pros

Catches easy-to-miss errors like typos, using-vars-before-assignment, etc.

#### 2.1.3 Cons

`ruff` isn't perfect. To take advantage of it, sometimes we'll need to write around it, suppress its warnings or fix it.

#### 2.1.4 Decision

Make sure you run `ruff` on your code.

Suppress warnings if they are inappropriate so that other issues are not hidden. To suppress warnings, you can set a line-level comment:

```python
def do_PUT(self):  # noqa: N802 - WSGI name
  ...
```

If the reason for the suppression is not clear from the comment, add an explanation.

### 2.2 Imports

Use `import` statements for packages and modules only, not for individual types, classes, or functions.

#### 2.2.1 Definition

Reusability mechanism for sharing code from one module to another.

#### 2.2.2 Pros

The namespace management convention is simple. The source of each identifier is indicated in a consistent way; `x.Obj` says that object `Obj` is defined in module `x`.

#### 2.2.3 Cons

Module names can still collide. Some module names are inconveniently long.

#### 2.2.4 Decision

- Use `import x` for importing packages and modules.
- Use `from x import y` where `x` is the package prefix and `y` is the module name with no prefix.
- Use `from x import y as z` in any of the following circumstances:
  - Two modules named `y` are to be imported.
  - `y` conflicts with a top-level name defined in the current module.
  - `y` is an inconveniently long name.
- Use `import y as z` only when `z` is a standard abbreviation (e.g., `import numpy as np`).

For example the module `sound.effects.echo` may be imported as follows:

```python
from sound.effects import echo
...
echo.EchoFilter(input, output, delay=0.7, atten=4)
```

Do not use relative names in imports. Even if the module is in the same package, use the full package name.

##### 2.2.4.1 Exemptions

Exemptions from this rule:

Symbols from the following modules are used to support static analysis and type checking:

- `typing` module
- `collections.abc` module
- `typing_extensions` module

### 2.3 Packages

Import each module using the full pathname location of the module.

#### 2.3.1 Pros

Avoids conflicts in module names or incorrect imports due to the module search path not being what the author expected.

#### 2.3.2 Cons

Makes it harder to deploy code because you have to replicate the package hierarchy. Not really a problem with modern deployment mechanisms.

#### 2.3.3 Decision

All new code should import each module by its full package name.

```python
# Yes:
from wingman import sessions
from wingman.ui import widgets

# No:
import sessions  # Unclear which sessions module
```

### 2.4 Exceptions

Exceptions are allowed but must be used carefully.

#### 2.4.1 Definition

Exceptions are a means of breaking out of normal control flow to handle errors or other exceptional conditions.

#### 2.4.2 Pros

The control flow of normal operation code is not cluttered by error-handling code. It also allows the control flow to skip multiple frames when a certain condition occurs.

#### 2.4.3 Cons

May cause the control flow to be confusing. Easy to miss error cases when making library calls.

#### 2.4.4 Decision

Exceptions must follow certain conditions:

- Make use of built-in exception classes when it makes sense. For example, raise a `ValueError` to indicate a programming mistake like a violated precondition.

- Do not use `assert` statements in place of conditionals or validating preconditions. They must not be critical to the application logic.

```python
# Yes:
  def connect_to_next_port(self, minimum: int) -> int:
    """Connects to the next available port."""
    if minimum < 1024:
      raise ValueError(f'Min. port must be at least 1024, not {minimum}.')
    port = self._find_next_open_port(minimum)
    if port is None:
      raise ConnectionError(
          f'Could not connect to service on port {minimum} or higher.')
    return port
```

```python
# No:
  def connect_to_next_port(self, minimum: int) -> int:
    assert minimum >= 1024, 'Minimum port must be at least 1024.'
    port = self._find_next_open_port(minimum)
    assert port is not None
    return port
```

- Libraries or packages may define their own exceptions. When doing so they must inherit from an existing exception class. Exception names should end in `Error`.

- Never use catch-all `except:` statements, or catch `Exception` or `StandardError`, unless you are re-raising the exception or creating an isolation point.

- Minimize the amount of code in a `try`/`except` block.

- Use the `finally` clause to execute code whether or not an exception is raised.

### 2.5 Mutable Global State

Avoid mutable global state.

#### 2.5.1 Definition

Module-level values or class attributes that can get mutated during program execution.

#### 2.5.2 Pros

Occasionally useful.

#### 2.5.3 Cons

Breaks encapsulation: Such design can make it hard to achieve valid objectives.

Has the potential to change module behavior during the import, because assignments to global variables are done when the module is first imported.

#### 2.5.4 Decision

Avoid mutable global state.

In those rare cases where using global state is warranted, mutable global entities should be declared at the module level and made internal by prepending an `_` to the name.

Module-level constants are permitted and encouraged. For example:
`_MAX_RETRIES = 3` for an internal use constant or
`DEFAULT_TIMEOUT = 30` for a public API constant.

### 2.6 Nested/Local/Inner Classes and Functions

Nested local functions or classes are fine when used to close over a local variable. Inner classes are fine.

#### 2.6.1 Definition

A class can be defined inside of a method, function, or class. A function can be defined inside a method or function.

#### 2.6.2 Pros

Allows definition of utility classes and functions that are only used inside of a very limited scope. Commonly used for implementing decorators.

#### 2.6.3 Cons

Nested functions and classes cannot be directly tested. Nesting can make the outer function longer and less readable.

#### 2.6.4 Decision

They are fine with some caveats. Avoid nested functions or classes except when closing over a local value other than `self` or `cls`. Do not nest a function just to hide it from users of a module. Instead, prefix its name with an `_` at the module level.

### 2.7 Comprehensions & Generator Expressions

Okay to use for simple cases.

#### 2.7.1 Definition

List, Dict, and Set comprehensions as well as generator expressions provide a concise and efficient way to create container types and iterators.

#### 2.7.2 Pros

Simple comprehensions can be clearer and simpler than other dict, list, or set creation techniques.

#### 2.7.3 Cons

Complicated comprehensions or generator expressions can be hard to read.

#### 2.7.4 Decision

Comprehensions are allowed, however multiple `for` clauses or filter expressions are not permitted. Optimize for readability, not conciseness.

```python
# Yes:
  result = [mapping_expr for value in iterable if filter_expr]

  result = [
      is_valid(metric={'key': value})
      for value in interesting_iterable
      if a_longer_filter_expression(value)
  ]
```

```python
# No:
  result = [(x, y) for x in range(10) for y in range(5) if x * y > 10]
```

### 2.8 Default Iterators and Operators

Use default iterators and operators for types that support them, like lists, dictionaries, and files.

#### 2.8.1 Definition

Container types, like dictionaries and lists, define default iterators and membership test operators ("in" and "not in").

#### 2.8.2 Pros

The default iterators and operators are simple and efficient. They express the operation directly, without extra method calls.

#### 2.8.3 Cons

You can't tell the type of objects by reading the method names (unless the variable has type annotations).

#### 2.8.4 Decision

Use default iterators and operators for types that support them.

```python
# Yes:
for key in adict: ...
      if obj in alist: ...
      for line in afile: ...
      for k, v in adict.items(): ...
```

```python
# No:
for key in adict.keys(): ...
      for line in afile.readlines(): ...
```

### 2.9 Generators

Use generators as needed.

#### 2.9.1 Definition

A generator function returns an iterator that yields a value each time it executes a yield statement.

#### 2.9.2 Pros

Simpler code, because the state of local variables and control flow are preserved for each call. A generator uses less memory than a function that creates an entire list of values at once.

#### 2.9.3 Cons

Local variables in the generator will not be garbage collected until the generator is either consumed to exhaustion or itself garbage collected.

#### 2.9.4 Decision

Fine. Use "Yields:" rather than "Returns:" in the docstring for generator functions.

### 2.10 Lambda Functions

Okay for one-liners. Prefer generator expressions over `map()` or `filter()` with a `lambda`.

#### 2.10.1 Definition

Lambdas define anonymous functions in an expression, as opposed to a statement.

#### 2.10.2 Pros

Convenient.

#### 2.10.3 Cons

Harder to read and debug than local functions. The lack of names means stack traces are more difficult to understand.

#### 2.10.4 Decision

Lambdas are allowed. If the code inside the lambda function spans multiple lines or is longer than 60-80 chars, it might be better to define it as a regular nested function.

For common operations like multiplication, use the functions from the `operator` module instead of lambda functions.

### 2.11 Conditional Expressions

Okay for simple cases.

#### 2.11.1 Definition

Conditional expressions (sometimes called a "ternary operator") are mechanisms that provide a shorter syntax for if statements. For example: `x = 1 if cond else 2`.

#### 2.11.2 Pros

Shorter and more convenient than an if statement.

#### 2.11.3 Cons

May be harder to read than an if statement.

#### 2.11.4 Decision

Okay to use for simple cases. Each portion must fit on one line.

```python
# Yes:
    one_line = 'yes' if predicate(value) else 'no'
```

```python
# No:
    bad_line_breaking = ('yes' if predicate(value) else
                         'no')
```

### 2.12 Default Argument Values

Okay in most cases.

#### 2.12.1 Definition

You can specify values for variables at the end of a function's parameter list, e.g., `def foo(a, b=0):`.

#### 2.12.2 Pros

Often you have a function that uses lots of default values, but on rare occasions you want to override the defaults.

#### 2.12.3 Cons

Default arguments are evaluated once at module load time. This may cause problems if the argument is a mutable object such as a list or a dictionary.

#### 2.12.4 Decision

Okay to use with the following caveat:

Do not use mutable objects as default values in the function or method definition.

```python
# Yes:
def foo(a, b=None):
         if b is None:
             b = []

def foo(a, b: Sequence | None = None):
         if b is None:
             b = []

def foo(a, b: Sequence = ()):  # Empty tuple OK since tuples are immutable.
         ...
```

```python
# No:
def foo(a, b=[]):
    ...

def foo(a, b=time.time()):
    ...

def foo(a, b: Mapping = {}):
         ...
```

### 2.13 Properties

Properties may be used to control getting or setting attributes that require trivial computations or logic.

#### 2.13.1 Definition

A way to wrap method calls for getting and setting an attribute as a standard attribute access.

#### 2.13.2 Pros

Allows for an attribute access and assignment API rather than getter and setter method calls.

#### 2.13.3 Cons

Can hide side-effects much like operator overloading. Can be confusing for subclasses.

#### 2.13.4 Decision

Properties are allowed, but should only be used when necessary and match the expectations of typical attribute access.

Properties should be created with the `@property` decorator. Manually implementing a property descriptor is considered a power feature.

### 2.14 True/False Evaluations

Use the "implicit" false if at all possible (with a few caveats).

#### 2.14.1 Definition

Python evaluates certain values as `False` when in a boolean context. A quick "rule of thumb" is that all "empty" values are considered false, so `0, None, [], {}, ''` all evaluate as false.

#### 2.14.2 Pros

Conditions using Python booleans are easier to read and less error-prone.

#### 2.14.3 Cons

May look strange to C/C++ developers.

#### 2.14.4 Decision

Use the "implicit" false if possible, e.g., `if foo:` rather than `if foo != []:`.

- Always use `if foo is None:` (or `is not None`) to check for a `None` value.
- Never compare a boolean variable to `False` using `==`. Use `if not x:` instead.
- For sequences (strings, lists, tuples), use the fact that empty sequences are false.

```python
# Yes:
if not users:
         print('no users')

     if i % 10 == 0:
         self.handle_multiple_of_ten()

     def f(x=None):
         if x is None:
             x = []
```

```python
# No:
if len(users) == 0:
         print('no users')

     if not i % 10:
         self.handle_multiple_of_ten()

     def f(x=None):
         x = x or []
```

### 2.16 Lexical Scoping

Okay to use.

A nested Python function can refer to variables defined in enclosing functions, but cannot assign to them.

```python
def get_adder(summand1: float) -> Callable[[float], float]:
    """Returns a function that adds numbers to a given number."""
    def adder(summand2: float) -> float:
        return summand1 + summand2

    return adder
```

### 2.17 Function and Method Decorators

Use decorators judiciously when there is a clear advantage. Avoid `staticmethod` and limit use of `classmethod`.

#### 2.17.1 Definition

Decorators for Functions and Methods (a.k.a "the `@` notation").

#### 2.17.2 Pros

Elegantly specifies some transformation on a method; the transformation might eliminate some repetitive code, enforce invariants, etc.

#### 2.17.3 Cons

Decorators can perform arbitrary operations on a function's arguments or return values, resulting in surprising implicit behavior.

#### 2.17.4 Decision

Use decorators judiciously when there is a clear advantage. Decorators should follow the same import and naming guidelines as functions.

Never use `staticmethod` unless forced to in order to integrate with an API defined in an existing library. Write a module-level function instead.

Use `classmethod` only when writing a named constructor, or a class-specific routine that modifies necessary global state.

### 2.18 Threading

Do not rely on the atomicity of built-in types.

Use the `queue` module's `Queue` data type as the preferred way to communicate data between threads. Otherwise, use the `threading` module and its locking primitives.

### 2.19 Power Features

Avoid these features.

#### 2.19.1 Definition

Python is an extremely flexible language and gives you many fancy features such as custom metaclasses, access to bytecode, on-the-fly compilation, dynamic inheritance, object reparenting, import hacks, reflection, modification of system internals, etc.

#### 2.19.2 Pros

These are powerful language features. They can make your code more compact.

#### 2.19.3 Cons

It's very tempting to use these "cool" features when they're not absolutely necessary. It's harder to read, understand, and debug code that's using unusual features.

#### 2.19.4 Decision

Avoid these features in your code.

Standard library modules and classes that internally use these features are okay to use (for example, `abc.ABCMeta`, `dataclasses`, and `enum`).

### 2.20 Modern Python: from \_\_future\_\_ imports

Use of `from __future__ import` statements is encouraged. It allows a given source file to start using more modern Python syntax features today.

```python
from __future__ import annotations
```

### 2.21 Type Annotated Code

You can annotate Python code with type hints. Type-check the code at build time with a type checking tool like mypy.

#### 2.21.1 Definition

Type annotations (or "type hints") are for function or method arguments and return values:

```python
def func(a: int) -> list[int]:
    ...
```

#### 2.21.2 Pros

Type annotations improve the readability and maintainability of your code.

#### 2.21.3 Cons

You will have to keep the type declarations up to date.

#### 2.21.4 Decision

You are strongly encouraged to enable Python type analysis when updating code. When adding or modifying public APIs, include type annotations.

## 3 Python Style Rules

### 3.1 Semicolons

Do not terminate your lines with semicolons, and do not use semicolons to put two statements on the same line.

### 3.2 Line length

Maximum line length is _120 characters_ (configured in `pyproject.toml`).

Explicit exceptions:

- Long import statements.
- URLs, pathnames, or long flags in comments.
- Long string module-level constants.

Do not use a backslash for explicit line continuation. Instead, make use of Python's implicit line joining inside parentheses, brackets and braces.

```python
# Yes:
if (width == 0 and height == 0 and
         color == 'red' and emphasis == 'strong'):
    ...

# No:
if width == 0 and height == 0 and \
         color == 'red' and emphasis == 'strong':
    ...
```

### 3.3 Parentheses

Use parentheses sparingly.

It is fine, though not required, to use parentheses around tuples. Do not use them in return statements or conditional statements unless using parentheses for implied line continuation.

```python
# Yes:
if foo:
         bar()
     return foo
     return spam, beans

# No:
if (x):
         bar()
     return (foo)
```

### 3.4 Indentation

Indent your code blocks with _4 spaces_.

Never use tabs. Implied line continuation should align wrapped elements vertically, or use a hanging 4-space indent.

```python
# Yes: Aligned with opening delimiter.
       foo = long_function_name(var_one, var_two,
                                var_three, var_four)

# Yes: 4-space hanging indent; nothing on first line.
       foo = long_function_name(
           var_one, var_two, var_three,
           var_four)
```

#### 3.4.1 Trailing commas in sequences of items?

Trailing commas in sequences of items are recommended only when the closing container token `]`, `)`, or `}` does not appear on the same line as the final element.

```python
# Yes:
golomb3 = [0, 1, 3]
       golomb4 = [
           0,
           1,
           4,
           6,
       ]
```

### 3.5 Blank Lines

Two blank lines between top-level definitions. One blank line between method definitions and between the docstring of a `class` and the first method.

### 3.6 Whitespace

Follow standard typographic rules for the use of spaces around punctuation.

- No whitespace inside parentheses, brackets or braces.
- No whitespace before a comma, semicolon, or colon.
- Surround binary operators with a single space on either side.
- Never use spaces around `=` when passing keyword arguments, except when a type annotation is present.

```python
# Yes:
spam(ham[1], {'eggs': 2}, [])
def complex(real, imag=0.0): return Magic(r=real, i=imag)
def complex(real, imag: float = 0.0): return Magic(r=real, i=imag)

# No:
spam( ham[ 1 ], { 'eggs': 2 }, [ ] )
def complex(real, imag = 0.0): return Magic(r = real, i = imag)
```

### 3.7 Shebang Line

Most `.py` files do not need to start with a `#!` line. Start the main file of a program with `#!/usr/bin/env python3`.

### 3.8 Comments and Docstrings

Be sure to use the right style for module, function, method docstrings and inline comments.

#### 3.8.1 Docstrings

Python uses _docstrings_ to document code. A docstring is a string that is the first statement in a package, module, class or function. Always use the three-double-quote `"""` format for docstrings.

#### 3.8.2 Modules

Files should start with a docstring describing the contents and usage of the module.

```python
"""A one-line summary of the module or program, terminated by a period.

Leave one blank line. The rest of this docstring should contain an
overall description of the module or program.

Typical usage example:

  foo = ClassFoo()
  bar = foo.function_bar()
"""
```

#### 3.8.3 Functions and Methods

A docstring is mandatory for every function that has one or more of the following properties:

- being part of the public API
- nontrivial size
- non-obvious logic

```python
def fetch_smalltable_rows(
    table_handle: smalltable.Table,
    keys: Sequence[bytes | str],
    require_all_keys: bool = False,
) -> Mapping[bytes, tuple[str, ...]]:
    """Fetches rows from a Smalltable.

    Retrieves rows pertaining to the given keys from the Table instance
    represented by table_handle.

    Args:
        table_handle: An open smalltable.Table instance.
        keys: A sequence of strings representing the key of each table
          row to fetch.
        require_all_keys: If True only rows with values set for all keys
          will be returned.

    Returns:
        A dict mapping keys to the corresponding table row data fetched.

    Raises:
        IOError: An error occurred accessing the smalltable.
    """
```

#### 3.8.4 Classes

Classes should have a docstring below the class definition describing the class. Public attributes should be documented in an `Attributes` section.

```python
class SampleClass:
    """Summary of class here.

    Longer class information...

    Attributes:
        likes_spam: A boolean indicating if we like SPAM or not.
        eggs: An integer count of the eggs we have laid.
    """

    def __init__(self, likes_spam: bool = False):
        """Initializes the instance based on spam preference."""
        self.likes_spam = likes_spam
        self.eggs = 0
```

#### 3.8.5 Block and Inline Comments

The final place to have comments is in tricky parts of the code. Complicated operations get a few lines of comments before the operations commence.

```python
# We use a weighted dictionary search to find out where i is in
# the array. We extrapolate position based on the largest num
# in the array and the array size.

if i & (i-1) == 0:  # True if i is 0 or a power of 2.
```

### 3.10 Strings

Use an f-string, the `%` operator, or the `format` method for formatting strings. A single join with `+` is okay but do not format with `+`.

```python
# Yes:
x = f'name: {name}; score: {n}'
     x = '%s, %s!' % (imperative, expletive)
     x = a + b

# No:
    x = 'name: ' + name + '; score: ' + str(n)
```

#### 3.10.1 Logging

For logging functions that expect a pattern-string as their first argument: Always call them with a string literal (not an f-string!) as their first argument.

```python
# Yes:
  logging.info('Current $PAGER is: %s', os.getenv('PAGER', default=''))

# No:
    logging.error(f'Cannot write to home directory, $HOME={homedir!r}')
```

### 3.11 Files, Sockets, and similar Stateful Resources

Explicitly close files and sockets when done with them.

The preferred way to manage files and similar resources is using the `with` statement:

```python
with open("hello.txt") as hello_file:
    for line in hello_file:
        print(line)
```

### 3.12 TODO Comments

Use `TODO` comments for code that is temporary, a short-term solution, or good-enough but not perfect.

A `TODO` comment begins with the word `TODO` in all caps, a following colon, and a link to a resource that contains the context, ideally a bug reference.

```python
# TODO: crbug.com/192795 - Investigate cpufreq optimizations.
```

### 3.13 Imports formatting

Imports should be on separate lines (except for `typing` and `collections.abc` imports).

```python
# Yes:
from collections.abc import Mapping, Sequence
     import os
     import sys
     from typing import Any, NewType

# No:
import os, sys
```

Imports should be grouped from most generic to least generic:

1. Python future import statements
2. Python standard library imports
3. Third-party module imports
4. Local imports

### 3.14 Statements

Generally only one statement per line.

### 3.15 Getters and Setters

Getter and setter functions should be used when they provide a meaningful role or behavior. If a pair of getters/setters simply read and write an internal attribute, the internal attribute should be made public instead.

### 3.16 Naming

`module_name`, `package_name`, `ClassName`, `method_name`, `ExceptionName`, `function_name`, `GLOBAL_CONSTANT_NAME`, `global_var_name`, `instance_var_name`, `function_parameter_name`, `local_var_name`.

#### 3.16.1 Names to Avoid

- single character names, except for counters/iterators, exception identifiers, file handles
- dashes (`-`) in any package/module name
- `__double_leading_and_trailing_underscore__` names
- offensive terms

#### 3.16.2 Naming Conventions

- Prepending a single underscore (`_`) has some support for protecting module variables and functions.
- Prepending a double underscore (`__`) is discouraged as it impacts readability and testability.

| Type       | Public               | Internal              |
| ---------- | -------------------- | --------------------- |
| Packages   | `lower_with_under`   |                       |
| Modules    | `lower_with_under`   | `_lower_with_under`   |
| Classes    | `CapWords`           | `_CapWords`           |
| Exceptions | `CapWords`           |                       |
| Functions  | `lower_with_under()` | `_lower_with_under()` |
| Constants  | `CAPS_WITH_UNDER`    | `_CAPS_WITH_UNDER`    |
| Variables  | `lower_with_under`   | `_lower_with_under`   |

### 3.17 Main

In Python, `pydoc` as well as unit tests require modules to be importable. If a file is meant to be used as an executable, its main functionality should be in a `main()` function.

```python
def main():
    ...

if __name__ == '__main__':
    main()
```

### 3.18 Function length

Prefer small and focused functions.

We recognize that long functions are sometimes appropriate, so no hard limit is placed on function length. If a function exceeds about 40 lines, think about whether it can be broken up without harming the structure of the program.

### 3.19 Type Annotations

#### 3.19.1 General Rules

- Annotating `self` or `cls` is generally not necessary.
- Don't feel compelled to annotate the return value of `__init__`.
- If any other variable or a returned type should not be expressed, use `Any`.
- At least annotate your public APIs.

#### 3.19.2 Line Breaking

After annotating, many function signatures will become "one parameter per line".

```python
def my_method(
    self,
    first_var: int,
    second_var: Foo,
    third_var: Bar | None,
) -> int:
  ...
```

#### 3.19.3 Forward Declarations

If you need to use a class name that is not yet defined, either use `from __future__ import annotations` or use a string for the class name.

```python
from __future__ import annotations

class MyClass:
  def __init__(self, stack: Sequence[MyClass], item: OtherClass) -> None:
  ...

class OtherClass:
  ...
```

#### 3.19.4 Default Values

Use spaces around the `=` _only_ for arguments that have both a type annotation and a default value.

```python
# Yes:
def func(a: int = 0) -> int:
  ...

# No:
def func(a:int=0) -> int:
  ...
```

#### 3.19.5 NoneType

If an argument can be `None`, it has to be declared! Use `X | None` (recommended in Python 3.10+).

```python
# Yes:
def modern_or_union(a: str | int | None, b: str | None = None) -> str:
  ...

# No:
def implicit_optional(a: str = None) -> str:
  ...
```

#### 3.19.6 Type Aliases

You can declare aliases of complex types. The name of an alias should be CapWorded.

```python
from typing import TypeAlias

_LossAndGradient: TypeAlias = tuple[tf.Tensor, tf.Tensor]
ComplexTFMap: TypeAlias = Mapping[str, _LossAndGradient]
```

#### 3.19.7 Ignoring Types

You can disable type checking on a line with the special comment `# type: ignore`.

#### 3.19.8 Typing Variables

If an internal variable has a type that is hard or impossible to infer, specify its type with an annotated assignment:

```python
a: Foo = SomeUndecoratedFunction()
```

#### 3.19.9 Tuples vs Lists

Typed lists can only contain objects of a single type. Typed tuples can either have a single repeated type or a set number of elements with different types.

```python
a: list[int] = [1, 2, 3]
b: tuple[int, ...] = (1, 2, 3)
c: tuple[int, str, float] = (1, "2", 3.5)
```

#### 3.19.10 Type Variables

A type variable, such as `TypeVar` and `ParamSpec`, is a common way to use generics.

```python
from collections.abc import Callable
from typing import ParamSpec, TypeVar

_P = ParamSpec("_P")
_T = TypeVar("_T")

def next(l: list[_T]) -> _T:
  return l.pop()
```

#### 3.19.11 String types

Use `str` for string/text data. For code that deals with binary data, use `bytes`.

#### 3.19.12 Imports For Typing

For symbols from the `typing` or `collections.abc` modules, always import the symbol itself.

```python
from collections.abc import Mapping, Sequence
from typing import Any, Generic, cast, TYPE_CHECKING
```

#### 3.19.13 Conditional Imports

Use conditional imports only in exceptional cases. Imports that are needed only for type annotations can be placed within an `if TYPE_CHECKING:` block.

```python
import typing
if typing.TYPE_CHECKING:
  import sketch

def f(x: "sketch.Sketch"): ...
```

#### 3.19.14 Circular Dependencies

Circular dependencies that are caused by typing are code smells. Such code is a good candidate for refactoring.

#### 3.19.15 Generics

When annotating, prefer to specify type parameters for generic types; otherwise, the generics' parameters will be assumed to be `Any`.

```python
# Yes:
def get_names(employee_ids: Sequence[int]) -> Mapping[int, str]:
  ...

# No:
def get_names(employee_ids: Sequence) -> Mapping:
  ...
```

## 4 Parting Words

_BE CONSISTENT_.

If you're editing code, take a few minutes to look at the code around you and determine its style. If their comments have little boxes of hash marks around them, make your comments have little boxes of hash marks around them too.

The point of having style guidelines is to have a common vocabulary of coding so people can concentrate on what you're saying rather than on how you're saying it. We present global style rules here so people know the vocabulary, but local style is also important.

However, there are limits to consistency. It applies more heavily locally and on choices unspecified by the global style. Consistency should not generally be used as a justification to do things in an old style without considering the benefits of the new style.
