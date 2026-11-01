"""Tests for static test guard and multi-branch execution classifier."""

from reprolens.classify import (
    classify_multi_execution,
    classify_single_execution,
)
from reprolens.models import ExpectedSymptom, InvestigationStatus
from reprolens.sandbox.base import ExecutionResult
from reprolens.test_guard import validate_repair_attempt, validate_test_code


def test_guard_valid_test():
    code = """
import pytest

EXPECTED_SYMPTOM = {
    "exception_type": "ValueError",
    "message_regex": "bad argument",
    "target_symbols": ["my_pkg.core.run_task"]
}

def test_reproduce_issue(tmp_path):
    from my_pkg.core import run_task
    run_task(None)
"""
    res = validate_test_code(code)
    assert res.passed is True
    assert res.expected_symptom.exception_type == "ValueError"


def test_guard_rejects_missing_expected_symptom():
    code = """
def test_foo():
    assert True
"""
    res = validate_test_code(code)
    assert res.passed is False
    assert "EXPECTED_SYMPTOM" in res.reason


def test_guard_rejects_unconditional_assert_false():
    code = """
EXPECTED_SYMPTOM = {"exception_type": "AssertionError"}
def test_bad():
    assert False
"""
    res = validate_test_code(code)
    assert res.passed is False
    assert "assert False" in res.reason


def test_guard_rejects_forbidden_imports():
    for mod in ["subprocess", "socket", "ctypes", "requests"]:
        code = f"""
import {mod}
EXPECTED_SYMPTOM = {{"exception_type": "ValueError"}}
def test_hack():
    pass
"""
        res = validate_test_code(code)
        assert res.passed is False, f"Did not reject import {mod}"
        assert "forbidden module" in res.reason


def test_guard_rejects_forbidden_calls():
    for call in ["eval", "exec", "skip", "xfail"]:
        code = f"""
EXPECTED_SYMPTOM = {{"exception_type": "ValueError"}}
def test_bad():
    {call}("1 + 1")
"""
        res = validate_test_code(code)
        assert res.passed is False
        assert f"forbidden call '{call}()'" in res.reason


def test_guard_rejects_excessive_sleep():
    code = """
import time
EXPECTED_SYMPTOM = {"exception_type": "ValueError"}
def test_sleep():
    time.sleep(10)
"""
    res = validate_test_code(code)
    assert res.passed is False
    assert "excessive sleep" in res.reason


def test_guard_target_symbol_enforcement():
    code = """
EXPECTED_SYMPTOM = {
    "exception_type": "ValueError",
    "target_symbols": ["my_pkg.special_routine"]
}
def test_repro():
    from other_pkg import irrelevant
    irrelevant()
"""
    res = validate_test_code(code)
    assert res.passed is False
    assert "does not call any specified target symbols" in res.reason


def test_repair_validation_assertion_weakening():
    orig = """
EXPECTED_SYMPTOM = {"exception_type": "ValueError"}
def test_one():
    assert 1 == 1
    assert 2 == 2
"""
    weakened = """
EXPECTED_SYMPTOM = {"exception_type": "ValueError"}
def test_one():
    assert 1 == 1
"""
    valid, reason = validate_repair_attempt(orig, weakened)
    assert valid is False
    assert "weakened" in reason


def test_classifier_reproduced_clean():
    symptom = ExpectedSymptom(
        exception_type="TypeError",
        message_regex="unexpected NoneType",
    )
    stdout = """
============================= test session starts =============================
collected 1 item

test_repro.py F                                                          [100%]

================================== FAILURES ===================================
____________________________ test_reproduce_issue _____________________________

    def test_reproduce_issue():
>       cli_runner.invoke(None)

Traceback (most recent call last):
  File "click/testing.py", line 45, in invoke
    return self.command.main(args)
TypeError: unexpected NoneType
=========================== short test summary info ===========================
FAILED test_repro.py::test_reproduce_issue - TypeError: unexpected NoneType
============================== 1 failed in 0.12s ==============================
"""
    result = ExecutionResult(exit_code=1, stdout=stdout, stderr="", duration_sec=0.2)
    cls_res = classify_single_execution(result, symptom)

    assert cls_res.status == InvestigationStatus.REPRODUCED
    assert cls_res.extracted_exception_type == "TypeError"
    assert cls_res.has_target_repo_frame is True


def test_classifier_not_reproduced_on_pass():
    symptom = ExpectedSymptom(exception_type="ValueError")
    stdout = "=== 1 passed in 0.05s ==="
    result = ExecutionResult(exit_code=0, stdout=stdout, stderr="", duration_sec=0.1)
    cls_res = classify_single_execution(result, symptom)
    assert cls_res.status == InvestigationStatus.NOT_REPRODUCED


def test_classifier_environment_error_missing_dependency():
    symptom = ExpectedSymptom(exception_type="ValueError")
    stderr = "ModuleNotFoundError: No module named 'numpy'"
    result = ExecutionResult(exit_code=1, stdout="", stderr=stderr, duration_sec=0.1)
    cls_res = classify_single_execution(result, symptom, known_repo_files={"calc.py"})
    assert cls_res.status == InvestigationStatus.ENVIRONMENT_ERROR
    assert "numpy" in cls_res.reason


def test_classifier_mismatched_exception_type():
    symptom = ExpectedSymptom(exception_type="TypeError")
    stdout = """
Traceback (most recent call last):
  File "pkg/core.py", line 10, in run
    val = d["missing_key"]
KeyError: 'missing_key'
"""
    result = ExecutionResult(exit_code=1, stdout=stdout, stderr="", duration_sec=0.1)
    cls_res = classify_single_execution(result, symptom)
    assert cls_res.status == InvestigationStatus.INVALID_TEST
    assert "Observed exception 'KeyError' does not match" in cls_res.reason


def test_classifier_no_repo_frame():
    symptom = ExpectedSymptom(exception_type="AssertionError")
    stdout = """
Traceback (most recent call last):
  File "test_repro.py", line 10, in test_repro
    assert 1 == 2
AssertionError
"""
    result = ExecutionResult(exit_code=1, stdout=stdout, stderr="", duration_sec=0.1)
    cls_res = classify_single_execution(result, symptom)
    assert cls_res.status == InvestigationStatus.INVALID_TEST
    assert "Failure occurred exclusively inside test harness" in cls_res.reason


def test_classifier_multi_run_flaky():
    symptom = ExpectedSymptom(exception_type="ValueError")
    r_pass = ExecutionResult(exit_code=0, stdout="1 passed", stderr="", duration_sec=0.1)
    r_fail = ExecutionResult(
        exit_code=1,
        stdout='File "pkg/core.py", line 2\nValueError: test',
        stderr="",
        duration_sec=0.1,
    )

    cls_res = classify_multi_execution([r_fail, r_pass, r_fail], symptom)
    assert cls_res.status == InvestigationStatus.INVALID_TEST
    assert cls_res.is_flaky is True
    assert "flaky" in cls_res.reason
