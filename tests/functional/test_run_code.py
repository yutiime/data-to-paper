import os

from scientistgpt.run_gpt_code.dynamic_code import run_code_using_module_reload, CODE_MODULE
from scientistgpt.run_gpt_code.exceptions import FailedRunningCode, CodeUsesForbiddenFunctions, CodeWriteForbiddenFile
from scientistgpt.utils import dedent_triple_quote_str


def test_run_code_on_legit_code():
    code = dedent_triple_quote_str("""
        def f():
            return 'hello'
        """)
    run_code_using_module_reload(code)
    assert CODE_MODULE.f() == 'hello'


def test_run_code_correctly_reports_exception():
    code = dedent_triple_quote_str("""
        # line 1
        # line 2
        raise Exception('error')
        # line 4
        """)
    try:
        run_code_using_module_reload(code)
    except FailedRunningCode as e:
        pass
        assert e.exception.args[0] == 'error'
        assert e.code == code
        assert e.tb[-1].lineno == 3
    else:
        assert False, 'Expected to fail'


def test_run_code_catches_warning():
    code = dedent_triple_quote_str("""
        import warnings
        warnings.warn('be careful', UserWarning)
        """)
    try:
        run_code_using_module_reload(code, warnings_to_raise=[UserWarning])
    except FailedRunningCode as e:
        assert e.exception.args[0] == 'be careful'
        assert e.code == code
        assert e.tb[-1].lineno == 2
    else:
        assert False, 'Expected to fail'


def test_run_code_timeout():
    code = dedent_triple_quote_str("""
        import time
        # line 2
        time.sleep(2)
        # line 4
        """)
    try:
        run_code_using_module_reload(code, timeout_sec=1)
    except FailedRunningCode as e:
        assert isinstance(e.exception, TimeoutError)
        assert e.code == code
        assert e.tb is None  # we currently do not get a traceback for timeout
    else:
        assert False, 'Expected to fail'


def test_run_code_forbidden_function():
    code = dedent_triple_quote_str("""
        a = 1
        input('')
        """)
    try:
        run_code_using_module_reload(code)
    except FailedRunningCode as e:
        assert isinstance(e.exception, CodeUsesForbiddenFunctions)
        assert e.code == code
        assert e.tb[-1].lineno == 2
    else:
        assert False, 'Expected to fail'


code = dedent_triple_quote_str("""
    with open('test.txt', 'w') as f:
        f.write('hello')
    """)


def test_run_code_raises_on_unallowed_files(tmpdir):
    try:
        os.chdir(tmpdir)
        run_code_using_module_reload(code, allowed_write_files=[])
    except FailedRunningCode as e:
        assert isinstance(e.exception, CodeWriteForbiddenFile)
        assert e.code == code
        assert e.tb[-1].lineno == 1
    else:
        assert False, 'Expected to fail'


def test_run_code_allows_allowed_files(tmpdir):
    os.chdir(tmpdir)
    run_code_using_module_reload(code, allowed_write_files=['test.txt'])