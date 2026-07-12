# PalWorld Save Parser (sav_cli.py)

Replaces the closed-source `sav_cli` binary with a Python script.

## Setup

```bash
# Option A: Install the fork with PalWorld 1.0 support (recommended)
git clone https://github.com/deafdudecomputers/PalworldSaveTools.git
cd PalworldSaveTools/src/palsav
pip install -e .
# Then copy the palsav package:
#   cp -r PalworldSaveTools/src/palsav/palsav module/
#   (overwrite the vendored files in module/palsav/palsav/)

# Option B: Use pip package (may not support PalWorld 1.0)
pip install palworld-save-tools
```

The vendored files in `module/palsav/palsav/` are from the pip package as fallback.
Replace with the `deafdudecomputers` fork for PalWorld 1.0 support.
