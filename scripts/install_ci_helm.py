#!/usr/bin/env python3
"""Install checksum-pinned Helm into a workspace directory, without system changes."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
VERSION = "4.3.1"
# Published archive checksums: https://github.com/helm/helm/releases/tag/v4.3.1
CHECKSUMS = {
    "linux-amd64": "0403a88ae20913d11b10a2467b50087721fea7581736da6b9d3992f5357fe54b",
    "darwin-arm64": "6b4e61c8cd27d99e5a801e63ff25dd5c70b36875c2cd659d3e9ce6b76fc23198",
}


def install_archive(archive, platform_name, output_dir):
    """Verify the complete archive before reading its single executable member."""
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != CHECKSUMS[platform_name]:
        raise ValueError(f"Helm archive checksum mismatch: {digest}")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as bundle:
        member = bundle.getmember(f"{platform_name}/helm")
        if not member.isfile():
            raise ValueError("Helm archive executable is not a regular file")
        # Read only this member; never extract archive paths into the filesystem.
        with bundle.extractfile(member) as source:
            with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as staged:
                staged_path = Path(staged.name)
                try:
                    shutil.copyfileobj(source, staged)
                    staged.flush()
                    os.fchmod(staged.fileno(), 0o755)
                    os.replace(staged_path, output_dir / "helm")
                finally:
                    staged_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".data/ci/bin")
    args = parser.parse_args()
    architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())
    platform_name = f"{platform.system().lower()}-{architecture}"
    if platform_name not in CHECKSUMS:
        parser.error(f"Unsupported validation platform: {platform_name}; use a separately verified Helm {VERSION}")
    archive_name = f"helm-v{VERSION}-{platform_name}.tar.gz"
    with tempfile.TemporaryDirectory(prefix="unum-helm-install-") as temporary:
        archive = Path(temporary) / archive_name
        with urllib.request.urlopen(f"https://get.helm.sh/{archive_name}", timeout=60) as response:
            with archive.open("wb") as destination:
                shutil.copyfileobj(response, destination)
        install_archive(archive, platform_name, args.output_dir)
    print(f"Installed Helm {VERSION} at {args.output_dir / 'helm'} (SHA256 verified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
