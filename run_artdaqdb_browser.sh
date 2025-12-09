#!/bin/bash


set -e

PATH=${HOME}/.mongodb/mongosh/bin:${HOME}/.mongodb/mongodb-database-tools/bin:${PATH}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"

CLEANUP=false
PYTHON_ARGS=()

for arg in "$@"; do
    case "$arg" in
        -c|--cleanup)
            CLEANUP=true
            ;;
        *)
            PYTHON_ARGS+=("$arg")
            ;;
    esac
done

DATA_DIR="${PYTHON_ARGS[0]:-$SCRIPT_DIR/sampledata/teststand_db}"

echo "======================================"
echo "OTSDAQ Configuration Browser"
echo "======================================"
echo ""

if [ "$CLEANUP" = true ]; then
    echo "Cleaning up Python cache files..."
    find "$SCRIPT_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
    find "$SCRIPT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo "✓ Cache cleanup complete"

    echo "Resetting trace.log..."
    rm -f "$SCRIPT_DIR/trace.log" 2>/dev/null || true
    touch "$SCRIPT_DIR/trace.log"
    echo "✓ trace.log reset"
    echo ""
fi

PYTHON_CMD=""
for cmd in python3.11 python3.10 python3.9 python3; do
    if command -v $cmd &> /dev/null; then
        VERSION=$($cmd --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo $VERSION | cut -d. -f1)
        MINOR=$(echo $VERSION | cut -d. -f2)
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 9 ]; then
            PYTHON_CMD=$cmd
            echo "✓ Found Python $VERSION"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "✗ Error: Python 3.9 or higher is required"
    echo "  Please install Python 3.9+ and try again"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo "✓ Virtual environment created at: $VENV_DIR"
else
    echo "✓ Virtual environment already exists"
fi

echo ""
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

if python -c "import artdaqdb_browser" 2>/dev/null; then
    echo "✓ otsdaq-artdaqdb-browser already installed"
else
    echo ""
    echo "Upgrading pip..."
    pip install --quiet --upgrade pip

    echo ""
    echo "Installing dependencies..."
    if [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
        pip install --quiet -e "$SCRIPT_DIR[dev]"
        echo "✓ Installed otsdaq-artdaqdb-browser with dev dependencies"
    else
        echo "✗ Error: pyproject.toml not found"
        exit 1
    fi
fi

echo ""
if [ ! -d "$DATA_DIR" ]; then
    echo "✗ Warning: Data directory not found: $DATA_DIR"
    echo "  Creating sample data directory..."
    mkdir -p "$DATA_DIR"
fi

echo ""
echo "Starting OTSDAQ Configuration Browser..."
echo "Data directory: $DATA_DIR"
echo ""

export PATH="$SCRIPT_DIR/.mongodb/mongodb-database-tools/bin:$SCRIPT_DIR/.mongodb/mongosh/bin:$PATH"
export TERM=xterm-256color

python -m artdaqdb_browser "${PYTHON_ARGS[@]}"

deactivate
