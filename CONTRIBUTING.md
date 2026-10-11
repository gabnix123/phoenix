# Contributing to PHOENIX

Thank you for considering contributing to PHOENIX! We welcome contributions from the community to help build this privacy-first ecosystem.

## How to Contribute

There are many ways to contribute to PHOENIX:

1. **Report bugs** - Use the issue tracker to report bugs
2. **Suggest features** - Share your ideas for new features or improvements
3. **Improve documentation** - Help us make our docs clearer and more complete
4. **Fix bugs** - Look through the issue tracker for bugs to fix
5. **Implement features** - Work on feature requests from the community
6. **Review code** - Help review pull requests from other contributors

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/phoenix.git
   cd phoenix
   ```
3. Create a new branch for your work:
   ```bash
   git checkout -b feature-or-fix-name
   ```
4. Set up your development environment:
   ```bash
   pip install -e .[dev]
   ```
5. Make your changes
6. Ensure your code follows our style guidelines
7. Add or update tests as needed
8. Run the test suite to ensure nothing is broken:
   ```bash
   pytest
   ```
9. Commit your changes and push to your fork
10. Open a pull request against the main repository

## Development Setup

### Prerequisites
- Python 3.8 or higher
- Git
- Depending on which modules you want to work on: FFmpeg (for audio/video), libssl, etc.

### Installing Dependencies
```bash
# For development with all tools
pip install -e .[dev]

# For working on specific modules:
pip install -e .[songbird]   # Music player
pip install -e .[projector]  # Film/TV tracker
pip install -e .[cipher]     # Network security toolkit
pip install -e .[vinyl]      # Media cataloging
```

### Running Tests
```bash
# Run all tests
pytest

# Run tests for a specific module
pytest tests/test_songbird.py
pytest tests/test_projector.py
pytest tests/test_cipher.py
pytest tests/test_vinyl.py

# Run tests with coverage
pytest --cov=phoenix
```

## Code Style

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for Python code style. Additionally:

- Use type hints where possible
- Write clear, descriptive docstrings for all public functions and classes
- Keep functions small and focused (aim for < 50 lines when possible)
- Use meaningful variable and function names
- Comment complex logic, but aim for self-documenting code
- Use the Rich library for consistent terminal output styling

### Linting
We use several tools to maintain code quality:
- `black` for code formatting
- `flake8` for style guide enforcement
- `mypy` for type checking
- `pre-commit` for automated checks

To install and run these tools:
```bash
pip install -e .[dev]
pre-commit install
pre-commit run --all-files
```

## Module Structure

PHOENIX follows a modular structure where each module lives in its own directory under `src/phoenix/`:

```
src/phoenix/
├── songbird/       # Music player and library manager
├── projector/      # Film/TV tracking system
├── cipher/         # Network privacy and security toolkit
├── vinyl/          # Physical media cataloging
└── whispernet/     # Unified CLI and hub
```

Each module typically contains:
- `__init__.py` - Module initialization
- `models.py` - Data models and database logic
- `cli.py` - Command-line interface using Click
- `tests/` - Unit tests (in the top-level tests directory)

## Making Changes

When making changes to PHOENIX:

1. **Consider privacy implications** - Ensure your changes maintain our privacy-first approach
2. **Keep it terminal-friendly** - PHOENIX is designed for terminal use
3. **Maintain modularity** - Keep module boundaries clear
4. **Add appropriate tests** - Ensure new functionality is tested
5. **Update documentation** - Keep README and docstrings current
6. **Follow existing patterns** - See how similar functionality is implemented

## Pull Request Process

1. Ensure your code passes all tests and linting checks
2. Update documentation as needed
3. Add yourself to the contributors list if this is your first contribution
4. Describe your changes clearly in the pull request
5. Reference any related issues
6. Be responsive to feedback from maintainers
7. Keep your pull request focused on a single concern

## Reporting Security Issues

Please see our [SECURITY.md](SECURITY.md) file for details on how to report security vulnerabilities.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and collaborative environment. Harassment of any kind will not be tolerated.

## License

By contributing to PHOENIX, you agree that your contributions will be licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Questions?

If you have questions about contributing, please open an issue or reach out to the maintainers.