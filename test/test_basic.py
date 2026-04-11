import sys
import os
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import (
    parse_github_repo_url,
    check_readme_quality,
    has_tests,
    infer_test_command,
    find_file_in_root
)

# URL PARSING TESTS

def test_parse_valid_url():
    owner, repo = parse_github_repo_url("https://github.com/user/repo")
    assert owner == "user"
    assert repo == "repo"

def test_parse_url_without_https():
    owner, repo = parse_github_repo_url("github.com/user/repo")
    assert owner == "user"
    assert repo == "repo"

def test_parse_url_with_git_suffix():
    owner, repo = parse_github_repo_url("https://github.com/user/repo.git")
    assert repo == "repo"

def test_parse_invalid_url():
    with pytest.raises(ValueError):
        parse_github_repo_url("invalid-url")

# README QUALITY TESTS

def test_readme_full_score():
    text = "This project shows how to install and run the application."
    score, status, _ = check_readme_quality(text)
    assert score == 20
    assert status == "pass"

def test_readme_partial_score():
    text = "This project explains installation only."
    score, status, _ = check_readme_quality(text)
    assert score == 10
    assert status == "partial"

def test_readme_missing_content():
    text = "Just a description."
    score, status, _ = check_readme_quality(text)
    assert score == 5


# FILE DETECTION TESTS

def test_find_license_file():
    contents = [{"name": "LICENSE"}]
    found, _ = find_file_in_root(contents, ["LICENSE"])
    assert found is True

def test_no_license_file():
    contents = [{"name": "README.md"}]
    found, _ = find_file_in_root(contents, ["LICENSE"])
    assert found is False

# TEST DETECTION

def test_has_tests_folder():
    contents = [{"name": "tests"}]
    assert has_tests(contents) is True

def test_has_test_file():
    contents = [{"name": "test_app.py"}]
    assert has_tests(contents) is True

def test_no_tests():
    contents = [{"name": "app.py"}]
    assert has_tests(contents) is False

# TEST COMMAND INFERENCE

def test_infer_pytest():
    contents = [{"name": "pytest.ini"}]
    assert infer_test_command(contents) == "pytest"

def test_infer_npm():
    contents = [{"name": "package.json"}]
    assert infer_test_command(contents) == "npm test"

def test_infer_unittest():
    contents = [{"name": "test"}]
    assert infer_test_command(contents) == "python -m unittest"