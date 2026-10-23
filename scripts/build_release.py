# SPDX-FileCopyrightText: 2026 MBS Integrations
# SPDX-License-Identifier: GPL-3.0-only

"""Build a manual-install ZIP containing only the public integration."""

from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parents[1]
source = root / "custom_components/calor_gas"
dist = root / "dist"
dist.mkdir(exist_ok=True)
target = dist / "calor_gas.zip"
files = sorted(p for p in source.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
if any(p.is_symlink() for p in files):
    raise RuntimeError("Release must not contain symlinks")
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in files:
        archive.write(path, "calor_gas/" + path.relative_to(source).as_posix())
digest = hashlib.sha256(target.read_bytes()).hexdigest()
(dist / "SHA256SUMS").write_text(digest + "  calor_gas.zip\n", encoding="utf-8")
print(json.dumps({"zip": str(target), "files": len(files), "sha256": digest}))
