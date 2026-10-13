"""Exercise the VS Code diff adapter without opening real GUI windows."""

import os
from pathlib import Path
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / 'home/dot_local/bin/executable_chezmoi-code-diff'


@pytest.fixture
def code_stub(tmp_path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    code = bin_dir / 'code'
    code.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CODE_ARGS"\n'
                    'test -f "$3" && test -f "$4"\n')
    code.chmod(0o755)
    return {**os.environ, 'PATH': str(bin_dir) + os.pathsep + os.environ['PATH'],
            'CODE_ARGS': str(tmp_path / 'arguments')}


def test_added_file_uses_regular_empty_document(tmp_path, code_stub):
    target = tmp_path / 'new-file'
    target.write_text('managed\n')
    subprocess.run(['/bin/bash', str(SCRIPT), '/dev/null', str(target)],
                   env=code_stub, check=True)
    args = Path(code_stub['CODE_ARGS']).read_text().splitlines()
    assert args[:2] == ['--wait', '--diff']
    assert args[3] == str(target)
    assert args[2] != '/dev/null'
    assert not Path(args[2]).exists()  # temporary file removed after VS Code exits


def test_existing_file_stays_unchanged(tmp_path, code_stub):
    source = tmp_path / 'before'
    target = tmp_path / 'after'
    source.write_text('old\n')
    target.write_text('new\n')
    subprocess.run(['/bin/bash', str(SCRIPT), str(source), str(target)],
                   env=code_stub, check=True)
    assert Path(code_stub['CODE_ARGS']).read_text().splitlines() == [
        '--wait', '--diff', str(source), str(target),
    ]


def test_directory_difference_is_not_opened_in_file_editor(tmp_path, code_stub):
    directory = tmp_path / 'generated'
    directory.mkdir()
    (directory / 'child').write_text('content')
    result = subprocess.run(['/bin/bash', str(SCRIPT), '/dev/null', str(directory)],
                            env=code_stub, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not Path(code_stub['CODE_ARGS']).exists()
