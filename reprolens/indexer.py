"""Python AST Indexer for code structure, signatures, and symbol discovery."""

import ast
from dataclasses import dataclass, field
from pathlib import Path

from reprolens.config import Config

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "vendor",
    "vendored",
    "third_party",
    "node_modules",
    ".eggs",
    "benchmark_private",
    "benchmark",
}


@dataclass
class ASTFunction:
    """Represents a top-level function or method."""

    name: str
    qualified_name: str
    signature: str
    docstring: str
    start_line: int
    end_line: int
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False


@dataclass
class ASTClass:
    """Represents a class definition and its methods."""

    name: str
    qualified_name: str
    bases: list[str]
    docstring: str
    start_line: int
    end_line: int
    methods: list[ASTFunction] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)


@dataclass
class ASTModule:
    """Summary of a Python module's AST structure."""

    rel_path: str
    module_name: str
    docstring: str
    classes: list[ASTClass] = field(default_factory=list)
    functions: list[ASTFunction] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    syntax_error: str | None = None


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Construct readable parameter signature string from AST arguments."""
    args_parts = []
    # Position-only args (Python 3.8+)
    for a in getattr(node.args, "posonlyargs", []):
        args_parts.append(a.arg)
    if getattr(node.args, "posonlyargs", []):
        args_parts.append("/")

    for a in node.args.args:
        args_parts.append(a.arg)

    if node.args.vararg:
        args_parts.append(f"*{node.args.vararg.arg}")
    elif node.args.kwonlyargs:
        args_parts.append("*")

    for a in node.args.kwonlyargs:
        args_parts.append(a.arg)

    if node.args.kwarg:
        args_parts.append(f"**{node.args.kwarg.arg}")

    return f"({', '.join(args_parts)})"


def _get_docstring_first_line(node: ast.AST) -> str:
    """Extract clean first line of docstring."""
    raw = ast.get_docstring(node)
    if not raw:
        return ""
    lines = raw.strip().splitlines()
    return lines[0].strip() if lines else ""


def _decorator_name(dec: ast.expr) -> str:
    """Extract string representation of decorator."""
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        return f"{_decorator_name(dec.value)}.{dec.attr}"
    if isinstance(dec, ast.Call):
        return _decorator_name(dec.func)
    return "decorator"


def parse_module_ast(rel_path: str, source_text: str) -> ASTModule:
    """Parse single Python file AST into structured ASTModule."""
    mod_name = rel_path.replace("\\", "/").removesuffix(".py").replace("/", ".")

    try:
        tree = ast.parse(source_text, filename=rel_path)
    except SyntaxError as e:
        return ASTModule(
            rel_path=rel_path,
            module_name=mod_name,
            docstring="",
            syntax_error=f"SyntaxError at line {e.lineno}: {e.msg}",
        )

    module_doc = _get_docstring_first_line(tree)
    classes: list[ASTClass] = []
    functions: list[ASTFunction] = []
    imports: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            else:
                mod = node.module or ""
                for alias in node.names:
                    imports.append(f"{mod}.{alias.name}")

        elif isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
                elif isinstance(b, ast.Attribute):
                    bases.append(f"{_decorator_name(b.value)}.{b.attr}")

            cls_methods: list[ASTFunction] = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    fn = ASTFunction(
                        name=item.name,
                        qualified_name=f"{node.name}.{item.name}",
                        signature=_format_signature(item),
                        docstring=_get_docstring_first_line(item),
                        start_line=item.lineno,
                        end_line=getattr(item, "end_lineno", item.lineno),
                        decorators=[_decorator_name(d) for d in item.decorator_list],
                        is_async=isinstance(item, ast.AsyncFunctionDef),
                    )
                    cls_methods.append(fn)

            cls_def = ASTClass(
                name=node.name,
                qualified_name=node.name,
                bases=bases,
                docstring=_get_docstring_first_line(node),
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                methods=cls_methods,
                decorators=[_decorator_name(d) for d in node.decorator_list],
            )
            classes.append(cls_def)

        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            fn = ASTFunction(
                name=node.name,
                qualified_name=node.name,
                signature=_format_signature(node),
                docstring=_get_docstring_first_line(node),
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                decorators=[_decorator_name(d) for d in node.decorator_list],
                is_async=isinstance(node, ast.AsyncFunctionDef),
            )
            functions.append(fn)

    return ASTModule(
        rel_path=rel_path,
        module_name=mod_name,
        docstring=module_doc,
        classes=classes,
        functions=functions,
        imports=imports,
    )


class RepoIndexer:
    """Scans and indexes an entire Python codebase."""

    def __init__(self, repo_dir: Path) -> None:
        self.repo_dir = Path(repo_dir)
        self.modules: dict[str, ASTModule] = {}

    def build_index(self) -> dict[str, ASTModule]:
        """Index all valid Python files in the repository."""
        self.modules.clear()

        for py_file in self.repo_dir.rglob("*.py"):
            # Check exclusions
            parts = py_file.relative_to(self.repo_dir).parts
            if any(part in EXCLUDED_DIRS or part.startswith(".") for part in parts[:-1]):
                continue

            # Check file size limit
            try:
                if py_file.stat().st_size > Config.MAX_FILE_SIZE_BYTES:
                    continue
            except Exception:
                continue

            rel_path = str(py_file.relative_to(self.repo_dir)).replace("\\", "/")
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                mod = parse_module_ast(rel_path, source)
                self.modules[rel_path] = mod
            except Exception as e:
                self.modules[rel_path] = ASTModule(
                    rel_path=rel_path,
                    module_name=rel_path.removesuffix(".py").replace("/", "."),
                    docstring="",
                    syntax_error=f"Read error: {e}",
                )

        return self.modules

    def find_symbol(self, symbol_name: str) -> list[tuple[ASTModule, ASTFunction | ASTClass]]:
        """Look up function or class definitions matching a symbol name."""
        matches = []
        clean_name = symbol_name.split(".")[-1]
        for mod in self.modules.values():
            for fn in mod.functions:
                if fn.name == clean_name or fn.qualified_name.endswith(symbol_name):
                    matches.append((mod, fn))
            for cls in mod.classes:
                if cls.name == clean_name:
                    matches.append((mod, cls))
                for m in cls.methods:
                    if m.name == clean_name or m.qualified_name.endswith(symbol_name):
                        matches.append((mod, m))
        return matches
