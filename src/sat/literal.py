class Literal:
    def __init__(self, name: str, id: int, value: bool | None = None):
        self.__name = name

        assert not id == 0, "ID cannot be equal to zero"
        if value is None:
            self.__value = id
        else:
            assert id > 0, "ID must be an absolute value if bool value stated"
            self.__value = id if value else -id

    def __bool__(self) -> bool:
        return self.__value > 0

    def __neg__(self) -> "Literal":
        return Literal(self.__name, -self.__value)

    def __str__(self) -> str:
        return f"{self.__name}: {self.__bool__()} ({self.__value})"

    def value(self) -> int:
        return self.__value

    def name(self) -> str:
        return self.__name

    def __eq__(self, other) -> bool:
        return (self.name(), self.value()) == (other.name(), other.value())

    def __abs__(self) -> "Literal":
        return Literal(self.__name, abs(self.__value))
