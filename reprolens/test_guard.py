"""Static AST-based security and sanity guard for generated reproduction tests."""

import ast
from dataclasses import dataclass

from reprolens.models import ExpectedSymptom

FORBIDDEN_MODULES = {
    "socket",
    "subprocess",
    "ctypes",
    "pty",
    "multiprocessing",
    "urllib.request",
    "urllib3",
    "requests",
    "httpx",
    "aiohttp",
}

FORBIDDEN_CALLS = {
    "system",
    "popen",
    "spawn",
    "exec",
    "eval",
    "skip",
    "xfail",
    "importorskip",
}


@dataclass
class GuardResult:
    """Outcome of static analysis check on test code."""

    passed: bool
    reason: str
    expected_symptom: ExpectedSymptom | None = None


def extract_expected_symptom_from_ast(tree: ast.Module) -> ExpectedSymptom | None:
    """Locate and extract module-level EXPECTED_SYMPTOM dictionary."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "EXPECTED_SYMPTOM"
                    and isinstance(node.value, ast.Dict)
                ):
                    data = {}
                    for k, v in zip(node.value.keys, node.value.values, strict=False):
                        if isinstance(k, ast.Constant) and isinstance(k.value, str):
                            if isinstance(v, ast.Constant):
                                data[k.value] = v.value
                            elif isinstance(v, ast.List):
                                items = []
                                for elem in v.elts:
                                    if isinstance(elem, ast.Constant) and isinstance(
                                        elem.value, str
                                    ):
                                        items.append(elem.value)
                                data[k.value] = items
                    if "exception_type" in data:
                        return ExpectedSymptom(
                            exception_type=str(data.get("exception_type", "")),
                            message_regex=str(data.get("message_regex", "")),
                            description=str(data.get("description", "")),
                            target_symbols=data.get("target_symbols", []),
                        )
    return None


def count_assertions_and_raises(tree: ast.Module) -> int:
    """Count assert statements and pytest.raises contexts in AST."""
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            count += 1
        elif isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if (
                    isinstance(ctx, ast.Call)
                    and isinstance(ctx.func, ast.Attribute)
                    and ctx.func.attr == "raises"
                ):
                    count += 1
    return count


def extract_called_names(tree: ast.Module) -> set[str]:
    """Collect all function/method names called within the AST."""
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
    return called


def validate_test_code(
    test_source: str, expected_target_symbols: list[str] | None = None
) -> GuardResult:
    """Perform static AST security audit and integrity check before execution."""
    if not test_source or not test_source.strip():
        return GuardResult(passed=False, reason="Test source code is empty.")

    try:
        tree = ast.parse(test_source)
    except SyntaxError as e:
        return GuardResult(
            passed=False, reason=f"Syntax error in test code at line {e.lineno}: {e.msg}"
        )

    # 1. Verify EXPECTED_SYMPTOM declaration
    symptom = extract_expected_symptom_from_ast(tree)
    if not symptom or not symptom.exception_type.strip():
        return GuardResult(
            passed=False,
            reason="Missing or invalid module-level EXPECTED_SYMPTOM dict with 'exception_type'.",
        )

    # 2. Check for test function
    has_test_func = any(
        isinstance(node, ast.FunctionDef) and node.name.startswith("test_") for node in tree.body
    )
    if not has_test_func:
        return GuardResult(passed=False, reason="No pytest function (test_*) found in test code.")

    # 3. Walk AST and reject forbidden constructs
    called_names = set()
    for node in ast.walk(tree):
        # Forbidden imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                for forbidden in FORBIDDEN_MODULES:
                    if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                        return GuardResult(
                            passed=False,
                            reason=f"Security violation: forbidden module '{alias.name}' imported.",
                        )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for forbidden in FORBIDDEN_MODULES:
                if mod == forbidden or mod.startswith(forbidden + "."):
                    return GuardResult(
                        passed=False,
                        reason=f"Security violation: forbidden module '{mod}' imported.",
                    )

        # Unconditional failures: assert False / assert 0
        elif isinstance(node, ast.Assert):
            if isinstance(node.test, ast.Constant) and (
                node.test.value is False or node.test.value == 0
            ):
                return GuardResult(
                    passed=False,
                    reason="Security violation: unconditional 'assert False' or 'assert 0' detected.",
                )

        # Forbidden calls
        elif isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name:
                called_names.add(func_name)

            if func_name in FORBIDDEN_CALLS:
                return GuardResult(
                    passed=False,
                    reason=f"Security violation: forbidden call '{func_name}()' detected.",
                )

            # Check time.sleep duration
            if func_name == "sleep" and node.args and isinstance(node.args[0], ast.Constant):
                val = node.args[0].value
                if isinstance(val, int | float) and val > 2.0:
                    return GuardResult(
                        passed=False,
                        reason=f"Security violation: excessive sleep({val}s) detected.",
                    )

    # 4. Verify target symbol calls if specified
    targets_to_check = expected_target_symbols or symptom.target_symbols
    if targets_to_check:
        clean_targets = {t.split(".")[-1] for t in targets_to_check if t.strip()}
        if clean_targets and not clean_targets.intersection(called_names):
            return GuardResult(
                passed=False,
                reason=f"Sanity check failed: test does not call any specified target symbols: {sorted(clean_targets)}.",
                expected_symptom=symptom,
            )

    return GuardResult(passed=True, reason="Static guard passed.", expected_symptom=symptom)


def validate_repair_attempt(original_source: str, repaired_source: str) -> tuple[bool, str]:
    """Programmatically enforce that test repairs do not weaken assertions or change symptom."""
    orig_res = validate_test_code(original_source)
    rep_res = validate_test_code(repaired_source)

    if not rep_res.passed:
        return False, f"Repaired test failed static guard: {rep_res.reason}"

    # EXPECTED_SYMPTOM must be identical
    if (
        orig_res.expected_symptom
        and rep_res.expected_symptom
        and (
            orig_res.expected_symptom.exception_type != rep_res.expected_symptom.exception_type
            or orig_res.expected_symptom.message_regex != rep_res.expected_symptom.message_regex
        )
    ):
        return False, "Repaired test modified EXPECTED_SYMPTOM (forbidden)."

    # Assertion count must not decrease
    orig_tree = ast.parse(original_source)
    rep_tree = ast.parse(repaired_source)
    orig_asserts = count_assertions_and_raises(orig_tree)
    rep_asserts = count_assertions_and_raises(rep_tree)

    if rep_asserts < orig_asserts:
        return False, (
            f"Assertion count weakened in repaired test: "
            f"original had {orig_asserts}, repaired has {rep_asserts}."
        )

    return True, "Repair satisfies integrity rules."
