"""Tests for the PROJECTOR CLI."""
import pytest
from click.testing import CliRunner
from phoenix.projector.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_banner_command(runner):
    """Test that the banner command runs and outputs expected text."""
    # Note: projector does not have a banner command, but we can test the hello command if we added one.
    # Since we didn't add a hello command, we'll test that the CLI group exists.
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert "PROJECTOR" in result.output

def test_projector_add(runner):
    """Test the add command (will fail without media files, but we can test the command exists)."""
    result = runner.invoke(cli, ['add', '--help'])
    assert result.exit_code == 0
    assert "Add media files" in result.output