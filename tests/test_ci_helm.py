"""Fail-closed checks for the workspace-only CI tool installer."""
import hashlib
import io
import tarfile

import pytest

from scripts import install_ci_helm


def test_corrupt_archive_does_not_replace_existing_binary(tmp_path):
    destination = tmp_path / "bin"
    destination.mkdir()
    executable = destination / "helm"
    executable.write_bytes(b"existing verified executable")
    archive = tmp_path / "corrupt.tar.gz"
    archive.write_bytes(b"corrupt or substituted download")

    with pytest.raises(ValueError, match="checksum mismatch"):
        install_ci_helm.install_archive(archive, "linux-amd64", destination)

    assert executable.read_bytes() == b"existing verified executable"
    assert list(destination.iterdir()) == [executable]


def test_only_expected_executable_is_written(tmp_path, monkeypatch):
    archive = tmp_path / "helm.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        for name, content in (("linux-amd64/helm", b"verified executable"),
                              ("../../unexpected", b"must not be extracted")):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            bundle.addfile(member, io.BytesIO(content))
    monkeypatch.setitem(install_ci_helm.CHECKSUMS, "linux-amd64", hashlib.sha256(archive.read_bytes()).hexdigest())
    destination = tmp_path / "bin"

    install_ci_helm.install_archive(archive, "linux-amd64", destination)

    assert (destination / "helm").read_bytes() == b"verified executable"
    assert (destination / "helm").stat().st_mode & 0o777 == 0o755
    assert sorted(path.name for path in tmp_path.iterdir()) == ["bin", "helm.tar.gz"]
    assert list(destination.iterdir()) == [destination / "helm"]


def test_symlink_executable_is_rejected(tmp_path, monkeypatch):
    archive = tmp_path / "helm.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        member = tarfile.TarInfo("linux-amd64/helm")
        member.type = tarfile.SYMTYPE
        member.linkname = "../../unexpected"
        bundle.addfile(member)
    monkeypatch.setitem(install_ci_helm.CHECKSUMS, "linux-amd64", hashlib.sha256(archive.read_bytes()).hexdigest())
    destination = tmp_path / "bin"

    with pytest.raises(ValueError, match="not a regular file"):
        install_ci_helm.install_archive(archive, "linux-amd64", destination)

    assert list(destination.iterdir()) == []
