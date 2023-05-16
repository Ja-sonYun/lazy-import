from lazy_import import lazy_import

with lazy_import():
    from tests import test_user


class Company:
    name = "company"

    def get_user(self) -> test_user.User:
        return test_user.User()


def test_get_user() -> None:
    company = Company()
    assert company.name == "company"
    assert company.get_user().name == "user"
