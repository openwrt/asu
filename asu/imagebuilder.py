import base64
import hashlib
import json
import re
import struct
from datetime import datetime
from pathlib import Path
from shutil import copyfile, rmtree
from subprocess import run

import nacl.signing
import requests
from urlpath import URL
import logging

logging.getLogger().setLevel(logging.DEBUG)


def verify_usign(signature: str, message: str, public_key: str) -> bool:
    """Verify a signify/usign signature

    This implementation uses pynacl

    Args:
        sig (str): signature content in bytes
        msg (str): message content in bytes
        pub_key (str): public key to use for verification

    Returns:
        bool: Sucessfull verification

    Todo:
         Currently ignores keynum and pkalg

    """
    _pkalg, _keynum, pubkey = struct.unpack("!2s8s32s", base64.b64decode(public_key))
    sig = base64.b64decode(signature.splitlines()[-1])

    _pkalg, _keynum, sig = struct.unpack("!2s8s64s", sig)

    verify_key = nacl.signing.VerifyKey(pubkey, encoder=nacl.encoding.RawEncoder)
    try:
        verify_key.verify(bytes(message, "utf-8"), sig)
        return True
    except nacl.exceptions.CryptoError:
        return False


def fingerprint_pubkey_usign(pubkey: str) -> str:
    """Return fingerprint of signify/usign public key

    Args:
        pubkey (str): signify/usign public key

    Returns:
        str: string containing the fingerprint
    """
    keynum = base64.b64decode(pubkey.splitlines()[-1])[2:10]
    return "".join(format(x, "02x") for x in keynum)


def get_file_hash(path: Path) -> str:
    """Return sha256sum of given path

    Args:
        path (str): path to file

    Returns:
        str: hash of file
    """
    BLOCK_SIZE = 65536

    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        fb = f.read(BLOCK_SIZE)
        while len(fb) > 0:
            h.update(fb)
            fb = f.read(BLOCK_SIZE)

    return h.hexdigest()


class ImageBuilder(object):
    def __init__(
        self,
        distro="openwrt",
        version="21.02.3",
        target="x86/64",
        cache=Path.cwd() / "cache",
        bin_dir=Path.cwd() / "bin",
        upstream_url="https://downloads.openwrt.org",
        keys=Path.cwd(),
        files=None,
        custom_public_key=None,
        use_podman=True,
    ):
        self.distro = distro
        self.version = version
        self.target = target.lower()
        if cache:
            self.cache = Path(cache)
        else:
            self.cache = Path.cwd() / "cache"
        self.upstream_url = URL(upstream_url)
        self.keys = Path(keys)
        self.workdir = self.cache / self.version / self.target
        self.sha256sums = None
        self.sha256sums_sig = None
        self.version_code = ""
        self.default_packages = set()
        self.profile_packages = set()
        self.bin_dir = bin_dir
        self.files = files or self.bin_dir
        self.custom_public_key = custom_public_key
        self.stdout = ""
        self.stderr = ""
        self.build_cmd = []
        self.profiles_json = None

        if use_podman:
            from podman import PodmanClient

            self.podman = PodmanClient(
                # base_url="unix:///Users/user/.colima/default/podman.sock"
                # base_url="unix:///Users/user/podman.sock"
                base_url="unix:///run/user/1000/podman/podman.sock"
            )
        else:
            self.podman = None

    @property
    def public_key(self):
        if self.custom_public_key:
            return self.custom_public_key

        if self.version == "SNAPSHOT":
            return "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+"
        elif self.version.startswith("21.02"):
            return "RWQviwuY4IMGvwLfs6842A0m4EZU1IjczTxKMSk3BQP8DAQLHBwdQiaU"
        else:
            return None

    @property
    def version_folder(self):
        if self.version != "SNAPSHOT":
            return f"releases/{self.version}"
        else:
            return "snapshots"

    # create function that returns root of number
    def root(self, x, n):
        return x ** (1 / n)

    def get_sha256sums(self):
        if not self.sha256sums:
            self.sha256sums = self._download_file("sha256sums").text

        return self.sha256sums

    def get_sha256sums_sig(self):
        """Return sha256sums.sig file
        
        :return: sha256sums.sig file"""
        if not self.sha256sums_sig:
            self.sha256sums_sig = self._download_file("sha256sums.sig").content

        return self.sha256sums_sig

    def _download_header(self, filename):
        """Return header of file
        
        :param filename: filename to download
        :return: header of file
        """
        print(self.imagebuilder_url )
        return requests.head(self.imagebuilder_url / filename).headers

    def _download_file(self, filename, path: Path = None):
        file_request = requests.get(self.imagebuilder_url / filename)
        file_request.raise_for_status()

        if path:
            path.write_bytes(file_request.content)
            return True
        else:
            return file_request

    @property
    def imagebuilder_url(self):
        return self.upstream_url / self.version_folder / "targets" / self.target

    def is_outdated(self):
        makefile = self.workdir / "Makefile"
        if not makefile.exists():
            return True

        remote_stamp = datetime.strptime(
            self._download_header("sha256sums.sig").get("last-modified"),
            "%a, %d %b %Y %H:%M:%S %Z",
        )

        local_stamp = datetime.fromtimestamp(makefile.stat().st_mtime)

        logging.debug(f"{local_stamp} vs {remote_stamp}")

        if remote_stamp > local_stamp:
            return True

        return False

    def _get_archive_sum_name(self):
        return re.search(
            r"^(.{64}) \*(openwrt-imagebuilder-.+?\.Linux-x86_64\.tar\.xz)$",
            self.get_sha256sums(),
            re.MULTILINE,
        ).groups()

    @property
    def config(self):
        config_path = self.workdir / ".config"
        if config_path.exists():
            return config_path
        else:
            return None

    @property
    def archive_name(self):
        return self._get_archive_sum_name()[1]

    @property
    def archive_sum(self):
        return self._get_archive_sum_name()[0]

    def valid_signature(self):
        return verify_usign(
            self.get_sha256sums_sig(), self.get_sha256sums(), self.public_key
        )

    def valid_checksum(self):
        return self.archive_sum == get_file_hash(self.cache / self.archive_name)

    def download(self):
        logging.info(f"Download { self.version}/{self.target}")
        self.cache.mkdir(exist_ok=True, parents=True)

        return self._download_file(
            self.archive_name,
            self.cache / self.archive_name,
        )

    def unpack(self):
        self.workdir.mkdir(parents=True, exist_ok=True)
        run(
            [
                "tar",
                "--modification-time",
                "--strip-components=1",
                "-xf",
                self.cache / self.archive_name,
            ],
            cwd=self.workdir,
        )

        (self.cache / self.archive_name).unlink()

        copyfile(
            self.workdir / ".config",
            self.workdir / ".config.orig",
        )

        return True

    def copy_keys(self):
        for suffix in ["", ".pub", ".ucert"]:
            file = (self.keys / "key-build").with_suffix(suffix)
            if file.exists():
                (self.workdir / file.name).symlink_to(file)

    def setup(self, check_online=False):
        # if self.podman:
        #     return None

        if not self.is_outdated():
            return None

        if not self.valid_signature():
            return "Invalid signature"

        if not self.download():
            return "Failed to download"

        if not self.valid_checksum():
            return "Bad checksum of archive"

        if not self.unpack():
            return "Failed to unpack"

        self.parse_info()

    def info(self):
        return run(["make", "info"], text=True, capture_output=True, cwd=self.workdir)

    def parse_info(self):
        info_run = self.info()

        self.version_code = re.search(
            'Current Revision: "(r.+)"', info_run.stdout
        ).group(1)

        self.default_packages = set(
            re.search(r"Default Packages: (.*)\n", info_run.stdout).group(1).split()
        )

        self.profile_packages = set(
            re.search(
                r"(.*?):\n    .+\n    Packages: (.*?)\n",
                info_run.stdout,
                re.MULTILINE,
            )
            .group(1)
            .split()
        )

    def _packages(self, packages):
        return sorted(list(set(packages)))

    def _make(self, cmd: list):
        make_run = run(cmd, text=True, cwd=self.workdir, capture_output=True)
        self.stdout = make_run.stdout
        self.stderr = make_run.stderr
        return make_run.returncode

    def _podman(self, cmd: list):
        # self.podman.containers.pull(f"openwrt/imagebuilder")

        self.podman.images.pull("openwrt/imagebuilder", tag=f"{ self.target.replace('/', '-') }-{ self.version.lower() }")
        print(str(self.workdir))
        print(str(self.bin_dir))
        container = self.podman.containers.run(
            # image=f"openwrt/imagebuilder",
            image=f"openwrt/imagebuilder:{ self.target.replace('/', '-') }-{ self.version.lower() }",
            command=cmd,
            detach=True,
            # overlay_volumes=[
            #     { "destination": str(self.workdir), "soruce": str(self.workdir)}
            # ],
            mounts=[
                     {
                        "type": "bind",
                        "source": str(self.bin_dir),
                        "target": str(self.bin_dir),
                        "read_only": False,
                    },
            ],
            # volumes={
            #     str(self.bin_dir): {"bind": str(self.bin_dir), "mode": "rw"},
            # },
                # f"{self.workdir}/.config": {"bind": f"{self.workdir}/.config" },
                # f"{self.workdir}/files/": {
                #     "bind": f"{self.workdir}/files/",
                #     "mode": "ro",
                # },
                # str(self.bin_dir): {"bind": f"/home/build/openwrt/bin/targets/{self.target}/", "mode": "rw"},
                # "./": {"bind": str(self.bin_dir), "mode": "rw"},
            # },
            # working_dir=str(self.workdir),
        )

        returncode = container.wait()
        print(returncode)
        self.stdout = b"\n".join(container.logs(stdout=True, stderr=False)).decode("utf-8")
        self.stderr = b"\n".join(container.logs(stdout=False, stderr=True)).decode("utf-8")
        container.remove()
        return returncode

    def cleanup(self):
        kernel_build_dir_run = self._make(["make", "val.KERNEL_BUILD_DIR"])

        kernel_build_dir_tmp = Path(kernel_build_dir_run.stdout.strip()) / "tmp"

        if kernel_build_dir_tmp.exists():
            # log.info("Removing KDIR_TMP at %s", kernel_build_dir_tmp)
            rmtree(kernel_build_dir_tmp)
        else:
            pass
            # log.warning("KDIR_TMP missing at %s", kernel_build_dir_tmp)

    def manifest(self, profile: str, packages: list) -> dict:
        manifest_cmd = [
            "make",
            "manifest",
            f"PROFILE={profile}",
            f"PACKAGES={' '.join(self._packages(packages))}",
            "STRIP_ABI=1",
        ]

        if self.podman:
            returncode = self._podman(manifest_cmd)

        else:
            returncode = self._make(manifest_cmd)

        logging.debug(self.stderr)
        logging.debug(self.stdout)
        logging.debug(returncode)

        if returncode:
            raise ValueError("Package selection caused error")

        return dict(map(lambda pv: pv.split(" - "), self.stdout.splitlines()))

    def set_filesystem(self, filesystem):
        config = self.config.read_text()

        for available_filesystem in ["squashfs", "ext4fs", "ubifs", "jffs2"]:
            # this implementation uses `startswith` since a running device thinks
            # it's running `ext4` while really there is `ext4fs` running
            if not available_filesystem.startswith(filesystem):
                # log.debug(f"Disable {available_filesystem}")
                config = config.replace(
                    f"CONFIG_TARGET_ROOTFS_{available_filesystem.upper()}=y",
                    f"# CONFIG_TARGET_ROOTFS_{available_filesystem.upper()} is not set",
                )
            else:
                # log.debug(f"Enable {available_filesystem}")
                config = config.replace(
                    f"# CONFIG_TARGET_ROOTFS_{available_filesystem.upper()} is not set",
                    f"CONFIG_TARGET_ROOTFS_{available_filesystem.upper()}=y",
                )

        self.config.write_text(config)

    def build(
        self, profile, packages, extra_image_name="", defaults="", filesystem=None
    ):
        if filesystem:
            self.set_filesystem(filesystem)
        else:
            copyfile(
                self.workdir / ".config.orig",
                self.workdir / ".config",
            )

        self.build_cmd = [
            "make",
            "image",
            f"PROFILE={profile}",
            f"PACKAGES={' '.join(self._packages(packages))}",
            f"EXTRA_IMAGE_NAME={extra_image_name}",
        ]

        defaults_file = self.files / "files/etc/uci-defaults/99-asu-defaults"
        defaults_file.parent.mkdir(parents=True, exist_ok=True)

        if defaults:
            defaults_file.write_text(defaults)
            self.build_cmd.append(f"FILES={self.files / 'files'}")
        else:
            defaults_file.unlink(missing_ok=True)

        if self.podman:
            returncode = self._podman(self.build_cmd)
        else:
            returncode = self._make(self.build_cmd)

        if returncode:
            raise ValueError("Error while building firmware. See stdout/stderr")

        if "is too big" in self.stderr:
            raise ValueError("Selected packages exceed device storage")

        profiles_json_path = self.bin_dir / "profiles.json"
        if profiles_json_path.exists():
            self.profiles_json = json.loads(profiles_json_path.read_text())

        if not self.podman:
            self.cleanup()
