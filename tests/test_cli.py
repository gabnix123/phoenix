"""Tests for the WHISPERNET CLI."""
import pytest
from click.testing import CliRunner
from phoenix.whispernet.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_banner_command(runner):
    """Test that the banner command runs and outputs expected text."""
    result = runner.invoke(cli, ['banner'])
    assert result.exit_code == 0
    assert "PHOENIX" in result.output
    assert "unified, privacy-first ecosystem" in result.output

def test_modules_command(runner):
    """Test that the modules command lists all modules."""
    result = runner.invoke(cli, ['modules'])
    assert result.exit_code == 0
    assert "songbird" in result.output
    assert "projector" in result.output
    assert "cipher" in result.output
    assert "vinyl" in result.output

def test_songbird_hello(runner):
    """Test that the songbird hello command works."""
    result = runner.invoke(cli, ['songbird', 'hello'])
    assert result.exit_code == 0
    assert "Welcome to SONGBIRD" in result.output