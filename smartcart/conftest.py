import sys
from pathlib import Path

# Ensure the smartcart/ package root is on sys.path so tests can import modules
# without a package prefix (matches how the app itself is run).
sys.path.insert(0, str(Path(__file__).parent))
