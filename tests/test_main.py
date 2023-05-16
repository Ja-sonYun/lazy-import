from lazy_import import lazy_import

with lazy_import():
    from tests.circular import A, B


class C:
    def __init__(self, a: A) -> None:
        self.state = "OK"
        self.a = a


def test_circular_import() -> None:
    a = A()
    assert a.id == id(a)

    b = B(C(a), id(a))
    assert b.id == id(a)
    assert b.c.state == "OK"
    assert b.c.a.id == id(a)

    # __getattr__ should work
    assert B.is_ok() == "OK"

    # classvar
    assert B.cls_variable == "OK"
