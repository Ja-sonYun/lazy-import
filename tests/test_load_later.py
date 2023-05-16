from lazy_import import lazy_import

with lazy_import():
    from tests.heavy_lib import HeavyLib


def test_heavy_lib_init() -> None:
    print("loaded")
    from time import sleep

    sleep(2)
    print("Use heavy lib")
    assert HeavyLib().value == 0


if __name__ == "__main__":
    test_heavy_lib_init()
