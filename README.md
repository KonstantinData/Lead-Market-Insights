# Agentic-Intelligence-Research

A research repository focused on agentic intelligence systems, methodologies, and implementations.

## Development Environment

This project uses [Poetry](https://python-poetry.org/) for dependency management and packaging. Poetry provides reproducible builds, virtual environment management, and simplified dependency resolution.

### Prerequisites

- Python 3.11 or higher
- Poetry (see installation instructions below)

### Poetry Installation

If you don't have Poetry installed, install it using pip:

```bash
pip install poetry
```

Or use the official installer:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

### Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/KonstantinData/Agentic-Intelligence-Research.git
   cd Agentic-Intelligence-Research
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```
   This creates a virtual environment and installs all dependencies defined in `pyproject.toml`.

3. **Activate the Poetry shell:**
   ```bash
   poetry shell
   ```
   Or run commands within the virtual environment:
   ```bash
   poetry run python your_script.py
   ```

### Development Commands

#### Dependency Management

- **Add a new dependency:**
  ```bash
  poetry add package-name
  ```

- **Add a development dependency:**
  ```bash
  poetry add --group dev package-name
  ```

- **Remove a dependency:**
  ```bash
  poetry remove package-name
  ```

- **Update dependencies:**
  ```bash
  poetry update
  ```

- **Show installed packages:**
  ```bash
  poetry show
  ```

#### Code Quality & Testing

- **Run all tests:**
  ```bash
  poetry run pytest
  ```

- **Run tests with coverage:**
  ```bash
  poetry run pytest --cov=src
  ```

- **Format code with Black:**
  ```bash
  poetry run black .
  ```

- **Sort imports with isort:**
  ```bash
  poetry run isort .
  ```

- **Lint code with Ruff:**
  ```bash
  poetry run ruff check .
  ```

- **Fix linting issues automatically:**
  ```bash
  poetry run ruff check --fix .
  ```

- **Type checking with MyPy:**
  ```bash
  poetry run mypy src
  ```

- **Run all quality checks:**
  ```bash
  poetry run black . && poetry run isort . && poetry run ruff check . && poetry run mypy src
  ```

#### Development Tools

- **Launch Jupyter Lab:**
  ```bash
  poetry run jupyter lab
  ```

- **Install pre-commit hooks (recommended):**
  ```bash
  poetry run pre-commit install
  ```

### Project Structure

```
Agentic-Intelligence-Research/
├── src/                    # Source code
├── tests/                  # Test files
├── docs/                   # Documentation
├── notebooks/              # Jupyter notebooks
├── pyproject.toml          # Poetry configuration and dependencies
├── README.md               # This file
└── .gitignore             # Git ignore patterns
```

### Configuration

The project includes comprehensive configuration for development tools:

- **Black**: Code formatting (88 character line length)
- **isort**: Import sorting (compatible with Black)
- **Ruff**: Fast Python linter with extensive rule set
- **MyPy**: Static type checking
- **Pytest**: Testing framework with coverage reporting
- **Pre-commit**: Git hooks for code quality

All configurations are defined in `pyproject.toml` following modern Python best practices.

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes following the code quality standards
4. Run tests and linting: `poetry run pytest && poetry run ruff check .`
5. Commit your changes: `git commit -am 'Add some feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

### CI/CD Integration

The Poetry configuration and development tools are designed to integrate seamlessly with CI/CD pipelines. The `pyproject.toml` file defines all necessary dependencies and tool configurations for automated testing, linting, and deployment.

Example GitHub Actions workflow commands:
```yaml
- name: Install dependencies
  run: poetry install

- name: Run tests
  run: poetry run pytest --cov=src

- name: Lint code
  run: poetry run ruff check .

- name: Check formatting
  run: poetry run black --check .

- name: Type check
  run: poetry run mypy src
```