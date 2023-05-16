from typing import ClassVar

from tests.test_main import C


class A:
    def __init__(self) -> None:
        self.id = id(self)


class B:
    cls_variable: ClassVar = "OK"

    def __init__(self, c: C, id: int) -> None:
        self.id = id
        self.c = c

    @staticmethod
    def is_ok() -> str:
        return "OK"
