from concurrent.futures import ThreadPoolExecutor
from threading import Event

from tuba.meshing._gmsh import gmsh_model


class _FakeOption:
    values = {"General.Terminal": 1.0}

    @classmethod
    def getNumber(cls, name):
        return cls.values[name]

    @classmethod
    def setNumber(cls, name, value):
        cls.values[name] = value


class _FakeModel:
    current = "caller"

    @classmethod
    def getCurrent(cls):
        return cls.current

    @classmethod
    def setCurrent(cls, name):
        cls.current = name

    @classmethod
    def add(cls, name):
        cls.current = name

    @classmethod
    def remove(cls):
        cls.current = ""


class _FakeGmsh:
    initialized = True
    model = _FakeModel
    option = _FakeOption

    @classmethod
    def isInitialized(cls):
        return cls.initialized

    @classmethod
    def initialize(cls, _args=None):
        cls.initialized = True

    @classmethod
    def finalize(cls):
        cls.initialized = False


def test_gmsh_model_serializes_process_global_state():
    first_entered = Event()
    release_first = Event()
    second_entered = Event()

    def first():
        with gmsh_model(_FakeGmsh, "first", options={"General.Terminal": 0}):
            first_entered.set()
            assert release_first.wait(2.0)

    def second():
        with gmsh_model(_FakeGmsh, "second"):
            second_entered.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(first)
        assert first_entered.wait(2.0)
        second_future = executor.submit(second)
        try:
            assert not second_entered.wait(0.1)
        finally:
            release_first.set()
        first_future.result()
        second_future.result()

    assert second_entered.is_set()
    assert _FakeGmsh.model.current == "caller"
    assert _FakeGmsh.option.values["General.Terminal"] == 1.0
