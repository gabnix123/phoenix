"""Tests for the VINYL CLI."""
import pytest
from click.testing import CliRunner
from phoenix.vinyl.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_vinyl_help(runner):
    """Test that the CLI help works."""
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert "VINYL" in result.output

def test_add_help(runner):
    """Test the add command help."""
    result = runner.invoke(cli, ['add', '--help'])
    assert result.exit_code == 0
    assert "Add a vinyl record" in result.output

def test_list_help(runner):
    """Test the list command help."""
    result = runner.invoke(cli, ['list', '--help'])
    assert result.exit_code == 0
    assert "List all vinyl records" in result.output

def test_search_help(runner):
    """Test the search command help."""
    result = runner.invoke(cli, ['search', '--help'])
    assert result.exit_code == 0
    assert "Search vinyl records" in result.output

def test_show_help(runner):
    """Test the show command help."""
    result = runner.invoke(cli, ['show', '--help'])
    assert result.exit_code == 0
    assert "Show details of a vinyl record" in result.output

def test_play_help(runner):
    """Test the play command help."""
    result = runner.invoke(cli, ['play', '--help'])
    assert result.exit_code == 0
    assert "Mark a vinyl record as played" in result.output