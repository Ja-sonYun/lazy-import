from lazy_import import lazy_import

with lazy_import():
    from tests.test_user import User


class Company:
    name = "company"

    def get_user(self) -> User:
        return User()


def test_get_user() -> None:
    company = Company()
    assert company.name == "company"
    assert company.get_user().name == "user"


print("Imported!!")
