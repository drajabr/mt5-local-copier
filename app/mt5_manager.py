from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable


class Mt5Manager:
    def __init__(self, mt5_root: Path, installer_script: Path, log_path: Path):
        self.mt5_root = mt5_root
        self.installer_script = installer_script
        self.log_path = log_path
        self.shared_install = self.mt5_root / "shared" / "terminal64.exe"
        self.instances_dir = self.mt5_root / "instances"

    def ensure_installation(self) -> None:
        self.mt5_root.mkdir(parents=True, exist_ok=True)
        self.instances_dir.mkdir(parents=True, exist_ok=True)

        if self.shared_install.exists():
            return

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write("MT5 shared binary missing; running installer script.\n")
            subprocess.run(
                ["/bin/bash", str(self.installer_script)],
                check=True,
                stdout=log_file,
                stderr=log_file,
            )

    def ensure_instances(self, instance_ids: Iterable[str]) -> None:
        for instance_id in instance_ids:
            instance_dir = self.instances_dir / instance_id
            terminal_link = instance_dir / "terminal64.exe"
            data_dir = instance_dir / "data"

            instance_dir.mkdir(parents=True, exist_ok=True)
            data_dir.mkdir(parents=True, exist_ok=True)

            if terminal_link.exists() or terminal_link.is_symlink():
                continue

            os.symlink(self.shared_install, terminal_link)
