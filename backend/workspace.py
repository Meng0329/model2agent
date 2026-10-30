"""Per-task workspace: isolated dirs, safe path resolution, asset intake, zip export."""
from __future__ import annotations
import json
import shutil
import zipfile
from pathlib import Path

from . import config


class Workspace:
    def __init__(self, task_id: str, root: Path | None = None):
        self.task_id = task_id
        self.root = (Path(root) if root else config.WORKSPACES_DIR) / task_id
        self.inputs = self.root / "inputs"
        self.project = self.root / "project"

    def create(self) -> "Workspace":
        self.root.mkdir(parents=True, exist_ok=True)
        self.inputs.mkdir(exist_ok=True)
        self.project.mkdir(exist_ok=True)
        self._install_skills()
        return self

    def _install_skills(self) -> None:
        """Copy the product's skills into the workspace .claude/skills so the
        main agent (setting_sources=["project"]) discovers them."""
        dst = self.root / ".claude" / "skills"
        src = config.SKILLS_DIR
        if src.exists():
            for skill_dir in src.iterdir():
                if skill_dir.is_dir():
                    target = dst / skill_dir.name
                    target.mkdir(parents=True, exist_ok=True)
                    for f in skill_dir.rglob("*"):
                        if f.is_file():
                            rel = f.relative_to(skill_dir)
                            (target / rel).parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(f, target / rel)

    # ---- safe paths (block path traversal) ----
    def safe_path(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("path traversal blocked")
        return p

    def add_asset(self, src: str | Path) -> Path:
        src = Path(src)
        dst = self.inputs / src.name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
        return dst

    def add_asset_zip(self, zip_path: str | Path, extract: bool = True) -> Path:
        zp = Path(zip_path)
        dst = self.inputs / zp.name
        shutil.copy2(zp, dst)
        if extract:
            dest = self.inputs / zp.stem
            dest.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(dst) as z:
                # safe extraction
                for member in z.namelist():
                    target = (dest / member).resolve()
                    if not str(target).startswith(str(dest.resolve())):
                        raise ValueError(f"unsafe zip entry: {member}")
                z.extractall(dest)
        return dst

    # ---- snapshot for the file panel ----
    def list_files(self) -> list[dict]:
        items = []
        if not self.root.exists():
            return items
        for p in sorted(self.root.rglob("*")):
            rel = p.relative_to(self.root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            items.append({
                "path": str(rel),
                "name": p.name,
                "is_dir": p.is_dir(),
                "size": p.stat().st_size if p.is_file() else 0,
            })
        return items

    def export_zip(self, out_path: str | Path) -> Path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for p in self.root.rglob("*"):
                if p.is_file():
                    z.write(p, p.relative_to(self.root))
        return out

    def export_project_zip(self, out_path: str | Path) -> Path:
        """Export ONLY the generated project (project/), excluding secrets, caches
        and the Builder's private files. Weights are included when the license allows."""
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        skip_names = {".env", ".env.local", "chat.json", "__pycache__", ".git", ".pytest_cache"}
        skip_suffixes = (".pyc",)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            if not self.project.exists():
                return out
            for p in self.project.rglob("*"):
                if not p.is_file():
                    continue
                rel = p.relative_to(self.project)
                if any(part in skip_names for part in rel.parts):
                    continue
                if p.name.endswith(skip_suffixes):
                    continue
                # never ship a real API key file or dot-env anywhere
                if p.name in (".env", ".env.local", ".credentials.json"):
                    continue
                z.write(p, rel)
        return out

    # ---- chat history persistence (survives restart, no DB server) ----
    def save_chat(self, messages: list) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "chat.json").write_text(
            json.dumps(messages, ensure_ascii=False, default=str), encoding="utf-8")

    def load_chat(self) -> list:
        p = self.root / "chat.json"
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
