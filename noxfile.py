""" Nox definitations for tests, docs, and linting """
from __future__ import absolute_import
import os

import nox  # pylint: disable=import-error


COVERAGE_FAIL = 95

PYTHON = False if os.getenv("NOX_DOCKER_BUILD") else ['3']

@nox.session(python=PYTHON)
def lint(session):
    """Run linters.
    Returns a failure if the linters find linting errors or sufficiently
    serious code quality issues.
    """
    run_cmd = ['pylint', 'etcd3_model']
    if 'prod' not in session.posargs:
        run_cmd.append('tests')
        run_cmd.append('--disable=import-error')
        run_cmd.append('--enable=fixme')

    if session.python:
        session.install('-r', 'requirements-lint.txt')
    session.run(*run_cmd)


@nox.session(python=PYTHON)
def style(session):
    """Run code style checker.
    Returns a failure if the style checker fails.
    """
    run_cmd = ['pycodestyle',
               '--config=.pycodestyle',
               'etcd3_model']
    if 'prod' not in session.posargs:
        run_cmd.append('--ignore=''')
        run_cmd.append('tests')

    if session.python:
        session.install('-r', 'requirements-style.txt')
    session.run(*run_cmd)


@nox.session(python=PYTHON)
def tests(session):
    """Default unit test session.
    """
    # Install all test dependencies, then install this package in-place.
    path = 'tests'
    if session.python:
        session.install('-r', 'requirements-test.txt')
        session.install('-e', '.')

    # Run py.test against the tests.
    session.run(
        'py.test',
        '--quiet',
        '-W',
        'ignore::DeprecationWarning',
        '--cov=etcd3_model',
        '--cov=tests',
        '--cov-append',
        '--cov-config=.coveragerc',
        '--cov-report=',
        '--cov-fail-under={}'.format(COVERAGE_FAIL),
        os.path.join(path),
        env={
            'ETCD_MOCK_CLIENT': "yes"
        }
    )


@nox.session(python=PYTHON)
def cover(session):
    """Run the final coverage report.
    This outputs the coverage report aggregating coverage from the unit
    test runs, and then erases coverage data.
    """
    if session.python:
        session.install('coverage', 'pytest-cov')
    session.run('coverage', 'report', '--show-missing',
                '--fail-under={}'.format(COVERAGE_FAIL))
    session.run('coverage', 'erase')
