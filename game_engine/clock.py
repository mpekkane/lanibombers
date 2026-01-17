import time


class Singleton(object):
    _instance = None

    def __new__(class_, *args, **kwargs):
        if not isinstance(class_._instance, class_):
            class_._instance = object.__new__(class_, *args, **kwargs)
        return class_._instance


class Clock(Singleton):
    def __init__(self) -> None:
        super().__init__()

    @staticmethod
    def now() -> float:
        return time.time()

    @staticmethod
    def now_ns() -> int:
        return time.time_ns()

    @staticmethod
    def sleep(seconds: float) -> None:
        time.sleep(seconds)
