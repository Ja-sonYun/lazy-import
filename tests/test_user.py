from lazy_import import lazy_import

with lazy_import():
    from tests.test_company import Company


class User:
    name = "user"

    def get_company(self) -> Company:
        return Company()


def test_get_company() -> None:
    user = User()
    assert user.get_company().name == "company"
