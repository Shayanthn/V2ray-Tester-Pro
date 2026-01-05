# 🤝 Contributing to V2Ray Tester Pro

First off, thank you for considering contributing! This document provides guidelines and steps for contributing.

## 🌟 How Can I Contribute?

### Reporting Bugs
- Use the GitHub issue tracker
- Include Python version, OS, and steps to reproduce
- Attach logs if possible (`tester.log`)

### Suggesting Features
- Open an issue with the `enhancement` label
- Describe the feature and why it's needed
- Provide examples if possible

### Code Contributions

#### Setup Development Environment
```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/V2ray-Tester-Pro.git
cd V2ray-Tester-Pro

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install black isort pylint mypy
```

#### Code Style
- Follow PEP 8
- Use type hints where possible
- Add docstrings to functions and classes
- Keep functions small and focused

#### Before Submitting
```bash
# Format code
black .
isort .

# Run tests (if available)
pytest tests/

# Check types
mypy "v2raytesterpro source.py"
```

#### Pull Request Process
1. Create a feature branch: `git checkout -b feature/amazing-feature`
2. Make your changes
3. Commit with clear messages: `git commit -m 'feat: add amazing feature'`
4. Push to your fork: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Commit Message Format
We follow Conventional Commits:

```
feat: add new protocol support
fix: resolve crash on invalid URI
docs: update README with examples
refactor: improve config parser
test: add unit tests for validator
chore: update dependencies
```

## 📋 Development Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features and priorities.

Current focus areas:
- Smart caching system
- GeoIP integration
- Web dashboard
- Machine learning optimization

## 🧪 Testing

When adding new features:
1. Test manually in both GUI and CLI modes
2. Test with various config formats
3. Check for memory leaks in long-running tests
4. Verify error handling

## 📝 Documentation

- Update README.md for user-facing changes
- Update ROADMAP.md for architectural changes
- Add inline comments for complex logic
- Update type hints

## 🐛 Found a Security Issue?

Please DO NOT open a public issue. Email the maintainer directly at your-email@example.com.

## 📄 License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 License.

## 💬 Questions?

- Open a discussion on GitHub
- Join our Telegram channel: @YourChannel

---

**Thank you for making V2Ray Tester Pro better!** 🎉
