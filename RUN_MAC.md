# Run on macOS

Open Terminal in this project directory.

```bash
# Use the system Python 3 installation
python3 --version

# Create a fresh project-local environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install the Flask dependency
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Start the web application
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

Demo login: `admin` / `home1234`.

If `python3 -m venv .venv` fails with an `ensurepip` error, verify the Python installation first:

```bash
which python3
python3 --version
python3 -m ensurepip --version
```

If your Python distribution does not include `ensurepip`, install/repair Python 3 using the official Python macOS installer or your package manager, then recreate `.venv`. Do not run `sudo pip install` and do not delete your project folder.

For test execution:

```bash
python -m unittest discover -s tests -v
```

For actual screenshots of the updated app, see `SCREENSHOTS_GUIDE.md`. The screenshot script requires the optional Playwright package and Chromium.
