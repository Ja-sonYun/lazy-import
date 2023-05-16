def load() -> int:
    print("Loading heavy lib...")
    from time import sleep
    sleep(2)
    return 0


init = load()

class HeavyLib:
    def __init__(self) -> None:
        self.value = init

print("Heavy lib loaded")
