"""Tests for the CIPHER CLI."""
import pytest
from click.testing import CliRunner
from phoenix.cipher.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_cipher_help(runner):
    """Test that the CLI help works."""
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert "CIPHER" in result.output

def test_vault_help(runner):
    """Test the vault subcommand help."""
    result = runner.invoke(cli, ['vault', '--help'])
    assert result.exit_code == 0
    assert "Manage the encrypted password vault" in result.output

def test_wireguard_help(runner):
    """Test the wireguard subcommand help."""
    result = runner.invoke(cli, ['wireguard', '--help'])
    assert result.exit_code == 0
    assert "Manage WireGuard VPN configurations" in result.output

def test_firewall_help(runner):
    """Test the firewall subcommand help."""
    result = runner.invoke(cli, ['firewall', '--help'])
    assert result.exit_code == 0
    assert "Manage firewall rules" in result.output