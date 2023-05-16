# Lazy Import
[![Supported Python Versions](https://img.shields.io/pypi/pyversions/lz-import/0.1.1)](https://pypi.org/project/lz-import/) [![PyPI version](https://badge.fury.io/py/lz-import.svg)](https://badge.fury.io/py/lz-import)


### Installation
```
pip install lz-import
# Or
poetry add lz-import
```

### Usage
```python
# File: company.py
from user import User

class Company:
    name = "company"

    def get_user(self) -> User:
        return User()

```

```python
# File: user.py
from company import Company

class User:
    name = "user"

    def get_company(self) -> Company:
        return Company()

if __name__ == "__main__":
    company = User.get_company()
```

This file layout will throw a circular import error, but if we can do a lazy import, it's perfectly fine. Just wrap the block of code like follow snippets.
```python
from lazy_import import lazy_import

with lazy_import():
    from user import User

...
```
User will be imported when the `__call__` or `__getattr__` methods are called.  
This example codes are implemented in the tests folder. See `tests/test_user.py` and `tests/test_company.py`.

#### NOTE
- Keep in mind that the class of lazy imported is not the same class with your original `User` class. It is wrapped by another class inside of `lazy_imported()`.
- Only work for module or class.
- This library works with mypy.

#### TODO
This library currently doesn't support follow syntax:
```python
with lazy_import():
    # these are actually possible but currently not implmented...
    import user  
    from user import User as user
```


### How it works?
We can find out which files to import by parsing bytecodes inside the `with` syntax. After that, just wrap the value to be imported.
