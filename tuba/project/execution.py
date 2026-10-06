"""Fresh project-local imports without changing CWD, paths or foreign modules."""

from __future__ import annotations

import builtins
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from uuid import uuid4
import weakref


_ACTIVE_LOADER = ContextVar("tuba_project_loader", default=None)


def _remove_private_module(name, proxy):
    if sys.modules.get(name) is proxy:
        del sys.modules[name]


class _ProjectImports:
    def __init__(self, root: Path):
        self.root = root
        self.modules = {}
        self.dependencies = set()
        self.fingerprints = {}
        self.builtins = {**vars(builtins), "__import__": self.import_module, "__build_class__": self.build_class}
        self.prefix = "_tuba_project_" + uuid4().hex
        self.package = ModuleType(self.prefix)
        self.package.__path__ = [str(root)]
        self._register(self.package)

    @staticmethod
    def _register(module, name=None):
        # Dataclasses and type-hint resolution need a defining module. Private
        # weak entries retain that identity while its project globals live,
        # without keeping discarded reloads alive or replacing foreign imports.
        proxy = weakref.proxy(module)
        name = name or module.__name__
        sys.modules[name] = proxy
        weakref.finalize(module, _remove_private_module, name, proxy)

    def entry_namespace(self, run_name, script):
        self.entry_name = self.prefix + "_entry"
        self.entry = ModuleType(self.entry_name)
        namespace = self.entry.__dict__
        namespace.update(__name__=run_name, __file__=str(script), __package__=None,
                         __spec__=None, __cached__=None, __builtins__=self.builtins)
        self._register(self.entry, self.entry_name)
        return namespace

    def build_class(self, function, name, *bases, **options):
        cls = builtins.__build_class__(function, name, *bases, **options)
        if function.__globals__ is self.entry.__dict__ and cls.__module__ == self.entry.__name__:
            # Keep __main__ guards and source frames intact, while decorators
            # resolve entry-defined annotations from this private module.
            cls.__module__ = self.entry_name
        return cls

    def _local_name(self, name):
        if name == self.prefix:
            return ""
        return name.removeprefix(self.prefix + ".")

    def source(self, name):
        name = self._local_name(name)
        if not name:
            return self.root
        # Framework imports retain the installed Tuba identity.
        if name.split(".")[0] == "tuba" or not all(part.isidentifier() for part in name.split(".")):
            return None
        base = self.root.joinpath(*name.split("."))
        for path in (base.with_suffix(".py"), base / "__init__.py"):
            if path.is_file() and path.resolve().is_relative_to(self.root):
                return path
        if base.is_dir() and base.resolve().is_relative_to(self.root):
            return base
        return None

    def load(self, name):
        name = self._local_name(name)
        if not name:
            return self.package
        if name in self.modules:
            return self.modules[name]
        path = self.source(name)
        if path is None:
            return importlib.import_module(name)
        parent_name, _, leaf = name.rpartition(".")
        parent = self.load(parent_name) if parent_name else self.package
        module = ModuleType(self.prefix + "." + name)
        is_package = path.is_dir() or path.name == "__init__.py"
        module.__package__ = module.__name__ if is_package else parent.__name__
        module.__builtins__ = self.builtins
        if is_package:
            module.__path__ = [str(path if path.is_dir() else path.parent)]
        self.modules[name] = module  # circular imports see their in-progress module
        self._register(module)
        setattr(parent, leaf or name, module)
        if path.is_file():
            self.dependencies.add(path.resolve())
            module.__file__ = str(path)
            payload = path.read_bytes()
            self.fingerprints[path.resolve()] = hashlib.sha256(payload).digest()
            exec(compile(payload, str(path), "exec", dont_inherit=True), module.__dict__)
        return module

    def import_module(self, name, globals=None, locals=None, fromlist=(), level=0):
        if level:
            package = (globals or {}).get("__package__")
            if not package:
                raise ImportError("Project relative imports require a package.")
            name = importlib.util.resolve_name("." * level + name, package)
        name = self._local_name(name)
        if self.source(name) is None:
            return builtins.__import__(name, globals, locals, fromlist, 0)
        module = self.load(name)
        if fromlist:
            for item in fromlist:
                child = f"{name}.{item}" if name else item
                if item != "*" and not hasattr(module, item) and self.source(child) is not None:
                    setattr(module, item, self.load(child))
            return module
        return self.load(name.split(".")[0])


def import_project_module(name: str):
    """Resolve a construction unit in the current project, or import normally."""
    loader = _ACTIVE_LOADER.get()
    return loader.load(name) if loader is not None else importlib.import_module(name)


@contextmanager
def project_namespace(path, *, run_name="__main__"):
    """Run project code and construction units with one fresh, isolated import context."""
    script = Path(path).resolve()
    loader = _ProjectImports(script.parent)
    namespace = loader.entry_namespace(run_name, script)
    token = _ACTIVE_LOADER.set(loader)
    try:
        yield namespace
    except BaseException as exc:
        exc.__tuba_project_dependencies__ = tuple(loader.dependencies)
        raise
    finally:
        _ACTIVE_LOADER.reset(token)
    namespace["__tuba_project_dependencies__"] = tuple(sorted(loader.dependencies))
    namespace["__tuba_project_fingerprints__"] = tuple(sorted(loader.fingerprints.items()))


def execute_project_script(path, *, run_name="__main__"):
    """Execute fresh source and local helpers; report the files actually read."""
    script = Path(path).resolve()
    with project_namespace(script, run_name=run_name) as namespace:
        loader = _ACTIVE_LOADER.get()
        loader.dependencies.add(script)
        payload = script.read_bytes()
        loader.fingerprints[script] = hashlib.sha256(payload).digest()
        exec(compile(payload, str(script), "exec", dont_inherit=True), namespace)
        if run_name == "__main__" and namespace.get("model") is None and callable(namespace.get("build_model")):
            namespace["model"] = namespace["build_model"]()
    return namespace
