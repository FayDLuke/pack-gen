from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Protocol

from endstone_packgen import builder
from endstone_packgen.builder import DATA, PackError, PackSpec


class Log(Protocol):
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


class PackGenerator:
    def __init__(self, server_root: Path, data_folder: Path, logger: Log) -> None:
        self.root = server_root
        self.packs_dir = data_folder / "packs"
        self.state_file = data_folder / "state.json"
        self.logger = logger

    def run(self) -> None:
        self.packs_dir.mkdir(parents=True, exist_ok=True)
        packs = self._load_state()
        seen = set()

        for source in sorted(self.packs_dir.iterdir()):
            if not source.is_dir() or source.name.startswith("."):
                continue
            seen.add(source.name)
            try:
                self._process(source, packs)
            except (PackError, OSError) as exc:
                self.logger.error(f"Skipped '{source.name}': {exc}")

        for name in sorted(set(packs) - seen):
            try:
                self._remove(packs.pop(name))
                self.logger.info(f"Removed pack '{name}' (source folder is gone)")
            except (PackError, OSError) as exc:
                self.logger.error(f"Could not remove '{name}': {exc}")

        self._save_state(packs)

    def _process(self, source: Path, packs: dict) -> None:
        spec = builder.load_spec(source)
        digest = builder.content_hash(source)
        previous = packs.get(source.name)

        if previous and previous["kind"] != spec.kind:
            self._remove(previous)
            previous = None

        if spec.custom_manifest:
            header = spec.custom_manifest["header"]
            pack_id, version, manifest, build = header["uuid"], header["version"], None, 0
        else:
            version, build = builder.next_version(spec.base_version, previous, digest)
            manifest = builder.build_manifest(spec, version)
            pack_id = manifest["header"]["uuid"]

        output = self._output_path(source.name, spec)
        unchanged = previous is not None and previous["hash"] == digest and output.exists()
        label = "behavior" if spec.kind == DATA else "resource"
        shown = output.relative_to(self.root).as_posix()

        if unchanged:
            self.logger.info(f"Up to date: {label} pack '{spec.name}' v{_dotted(version)}")
        else:
            if spec.kind == DATA:
                builder.write_folder(source, manifest, output)
            else:
                builder.write_archive(source, manifest, output)
            self.logger.info(f"Built {label} pack '{spec.name}' v{_dotted(version)} -> {shown}")

        if spec.kind == DATA:
            builder.set_world_pack(self._world_json(), pack_id, version)

        packs[source.name] = {
            "hash": digest,
            "build": build,
            "kind": spec.kind,
            "pack_id": pack_id,
            "version": version,
            "output": shown,
        }

    def _output_path(self, name: str, spec: PackSpec) -> Path:
        if spec.kind == DATA:
            return self.root / "behavior_packs" / name
        return self.root / "resource_packs" / f"{name}.mcpack"

    def _remove(self, entry: dict) -> None:
        output = self.root / entry["output"]
        if entry["kind"] == DATA:
            shutil.rmtree(output, ignore_errors=True)
            builder.set_world_pack(self._world_json(), entry["pack_id"], None)
        else:
            output.unlink(missing_ok=True)

    def _world_json(self) -> Path:
        return self.root / "worlds" / self._level_name() / "world_behavior_packs.json"

    def _level_name(self) -> str:
        properties = self.root / "server.properties"
        if properties.is_file():
            for line in properties.read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition("=")
                if key.strip() == "level-name" and value.strip():
                    return value.strip()
        return "Bedrock level"

    def _load_state(self) -> dict:
        if not self.state_file.is_file():
            return {}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8")).get("packs", {})
        except (json.JSONDecodeError, OSError):
            self.logger.warning("state.json is unreadable; packs will be rebuilt from scratch")
            return {}

    def _save_state(self, packs: dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps({"packs": packs}, indent=2), encoding="utf-8")


def _dotted(version: list[int]) -> str:
    return ".".join(str(v) for v in version)
