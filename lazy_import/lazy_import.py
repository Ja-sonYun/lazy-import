import importlib
import sys
from contextlib import contextmanager
from dis import Bytecode, Instruction
from enum import IntEnum
from types import FrameType
from typing import Any, Generator, Optional

LAZY_IMPORT = "lazy_import"


class OpCode(IntEnum):
    POP_TOP = 1
    PUSH_NULL = 2
    WITH_EXCEPT_START = 49
    BEFORE_WITH = 53
    LOAD_CONST = 100
    LOAD_NAME = 101
    IMPORT_NAME = 108
    IMPORT_FROM = 109
    CALL_FUNCTION = 131
    SETUP_WITH = 143
    PRECALL = 166
    CALL = 171


class _LazyImporter:
    __module_name__: str
    __varname__: str
    __loaded__: Optional[Any]

    # Force set all attribute to this self

    def _load(self) -> Any:
        if self.__loaded__ is None:
            imported_module = getattr(
                importlib.import_module(self.__module_name__),
                self.__varname__,
            )
            # Inject __dict__ before replacing self object
            # imported_module.__dict__ is a mappingproxy not a dict
            setattr(self, "__dict__", dict(imported_module.__dict__))

            # Replace self object to the loaded module
            for _method in dir(imported_module):
                if _method in ("__class__", "__weakref__", "__dict__"):
                    continue
                setattr(self, _method, getattr(imported_module, _method))

            self.__loaded__ = imported_module

        return self.__loaded__

    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._load()(*args, **kwargs)


@contextmanager
def lazy_import() -> Generator[None, None, None]:
    """
    Context manager that suppresses the ImportError that is caused by circular import,
    and load the module when it actually called.

    Also work with mypy, due to the fact that mypy doesn't check the exception in the
    contextmanager block.
    """
    backed_up_sys_path = sys.path.copy()

    try:
        # Make sys.path empty to raise import error
        # Remove all path, and cached import
        sys.path = ["__lazy_importing__"]

        yield
        # yield should raise import error

    except ImportError as err:
        if "circular import" in err.msg:
            *_, traceback = sys.exc_info()
            assert traceback is not None
            # Digging into the traceback to find the module that is being imported

            contextmanager_frame = traceback.tb_frame.f_back

            # Ensure that the frame is a contextmanager
            # This block is after the yield, so it should be __exit__
            if not (
                contextmanager_frame
                and contextmanager_frame.f_code.co_name == "__exit__"
            ):
                raise RuntimeError("This should not happen. ") from None

            # Now we need to grab the module that is being imported
            # Go above one more frame
            import_frame = contextmanager_frame.f_back
            assert import_frame is not None

            return _map_lazy_importer(import_frame)
        else:
            sys.path = backed_up_sys_path

            *_, traceback = sys.exc_info()
            assert traceback is not None
            # Digging into the traceback to find the module that is being imported

            contextmanager_frame = traceback.tb_frame.f_back
            assert contextmanager_frame is not None
            import_frame = contextmanager_frame.f_back
            assert import_frame is not None

            return _map_lazy_importer(import_frame)

    sys.path = backed_up_sys_path
    return None


def _map_lazy_importer(import_frame: FrameType) -> None:
    disassembled = Bytecode(import_frame.f_code)
    import_later = _find_what_to_imports(disassembled)

    for module_name, names in import_later:
        for name in names:
            import_frame.f_locals[name] = type(
                name,
                (_LazyImporter,),
                {
                    "__module_name__": module_name,
                    "__varname__": name,
                    "__loaded__": None,
                },
            )()


def _find_what_to_imports(bytecode: Bytecode) -> list[tuple[str, list[str]]]:
    """
    Find the block that lazy_import is called
    Example disassembled code:
    0        0 LOAD_NAME                0 (lazy_import)
             2 CALL_FUNCTION            0
             4 SETUP_WITH              16 (to 22)
             6 POP_TOP

    ...

    XX       XX LOAD_CONST               0 (None)
    XX       XX LOAD_CONST               0 (None)
    XX       XX IMPORT_NAME              0 (sys)
    XX       XX STORE_NAME               0 (sys)
    XX       XX POP_TOP
    XX       XX POP_BLOCK             # This is the block we want, but not documented.
    XX       XX ...
    XX    >> XX WITH_EXCEPT_START     # This instruction is documented, so use this
                                      # as mark.
    XX       XX POP_JUMP_IF_TRUE
    ...

    WITH_EXCEPT_START is the mark we want, and it's new in Python 3.9
    Used when the except occured in the with block
    See:
    https://docs.python.org/3/library/dis.html#opcode-WITH_EXCEPT_START
    """

    instruction_blocks: list[tuple[Instruction, ...]] = []
    inst_buffer: list[Instruction] = []

    # Sepereate the instructions into blocks
    for instruction in bytecode:
        if instruction.starts_line:
            instruction_blocks.append(tuple(inst_buffer))
            # Start a new block
            inst_buffer = [instruction]
        else:
            inst_buffer.append(instruction)

    all_lazy_imports: list[list[tuple[Instruction, ...]]] = []
    collecting_buffer: Optional[list[tuple[Instruction, ...]]] = None

    for instruction_block in instruction_blocks:
        if _is_being_lazy(instruction_block):
            collecting_buffer = []
            continue

        if collecting_buffer is not None:
            if _is_existing_block(instruction_block):
                all_lazy_imports.append(collecting_buffer + [instruction_block])
                collecting_buffer = None
                continue

            collecting_buffer.append(instruction_block)

    will_be_imported: list[tuple[str, list[str]]] = []

    for lazy_import_block in all_lazy_imports:
        for import_statement in lazy_import_block:
            will_be_imported.extend(_extract_imports(import_statement))

    return will_be_imported


def _is_being_lazy(instrction_block: tuple[Instruction, ...]) -> bool:
    """
    Find below instrction block:

    # python 3.9, 3.10

    0        0 LOAD_NAME                0 (lazy_import)
             2 CALL_FUNCTION            0
             4 SETUP_WITH              16 (to 22)
             6 POP_TOP

    # python 3.11

    0        40 PUSH_NULL
             42 LOAD_NAME                7 (lazy_import)
             44 PRECALL                  0
             48 CALL                     0
             58 BEFORE_WITH
             60 POP_TOP

    """
    if sys.version_info <= (3, 11):
        if len(instrction_block) != 4:
            return False

        load_name, call_function, setup_with, pop_top = instrction_block

        return (
            load_name.opcode == OpCode.LOAD_NAME
            and load_name.argval == LAZY_IMPORT
            and call_function.opcode == OpCode.CALL_FUNCTION
            and setup_with.opcode == OpCode.SETUP_WITH
            and pop_top.opcode == OpCode.POP_TOP
        )
    elif sys.version_info >= (3, 11) and sys.version_info < (3, 12):
        if len(instrction_block) != 6:
            return False

        push_null, load_name, precall, call, before_with, pop_top = instrction_block

        return (
            load_name.opcode == OpCode.LOAD_NAME
            and load_name.argval == LAZY_IMPORT
            and push_null.opcode == OpCode.PUSH_NULL
            and precall.opcode == OpCode.PRECALL
            and call.opcode == OpCode.CALL
            and before_with.opcode == OpCode.BEFORE_WITH
            and pop_top.opcode == OpCode.POP_TOP
        )

    raise RuntimeError(f"Python version {sys.version_info} is not supported.")


def _is_existing_block(instruction_block: tuple[Instruction, ...]) -> bool:
    """
    Check that this instruction block include WITH_EXCEPT_START,
    with include import statement:

    XX       XX LOAD_CONST               0 (None)
    XX       XX LOAD_CONST               0 (None)
        # NOTE: In python 3.9, IMPORT_NAME is exists, but in python 3.10 or above,
        #       it's gone.
    XX       XX IMPORT_NAME              0 (sys)
    XX       XX STORE_NAME               0 (sys)
    XX       XX POP_TOP
    XX       XX POP_BLOCK             # This is the block we want, but not documented.
    XX       XX ...
    XX    >> XX WITH_EXCEPT_START     # This instruction is documented, so use this
                                      # as mark.
    XX       XX POP_JUMP_IF_TRUE
    """
    all_opcodes = [instruction.opcode for instruction in instruction_block]

    return OpCode.WITH_EXCEPT_START in all_opcodes


def _extract_imports(
    instruction_block: tuple[Instruction, ...]
) -> list[tuple[str, list[str]]]:
    """
    Extract the imports from the instruction block

    return (module_name, [imported_names, ...])
    """

    # list [ tuple [ module_name, [imported_names, ...] ] ]
    lazy_import_modules: list[tuple[str, list[str]]] = []

    # Get list of sequence of LOAD_CONST -> IMPORT_NAME
    for i1, i2 in zip(instruction_block, instruction_block[1:]):
        if i1.opcode == OpCode.LOAD_CONST and i2.opcode == OpCode.IMPORT_NAME:
            names = list(i1.argval) if i1.argval is not None else []
            lazy_import_modules.append((i2.argval, names))

    return lazy_import_modules
