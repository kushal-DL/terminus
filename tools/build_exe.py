"""Build Terminus as a single-file executable using PyInstaller."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    spec_file = root / "terminus.spec"

    if not spec_file.exists():
        print(f"ERROR: Spec file not found: {spec_file}")
        sys.exit(1)

    print("Building Terminus executable...")
    print(f"  Spec: {spec_file}")
    print(f"  Output: {root / 'dist'}")
    print()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_file),
        "--clean",
        "--noconfirm",
    ]

    result = subprocess.run(cmd, cwd=str(root))

    if result.returncode != 0:
        print("\nBuild FAILED.")
        sys.exit(result.returncode)

    # Find output
    dist = root / "dist"
    exe_name = "terminus.exe" if sys.platform == "win32" else "terminus"
    exe_path = dist / exe_name

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nBuild SUCCESS!")
        print(f"  Executable: {exe_path}")
        print(f"  Size: {size_mb:.1f} MB")
    else:
        print(f"\nWARNING: Expected output not found at {exe_path}")
        print(f"  Check {dist} for output files.")


if __name__ == "__main__":
    main()
