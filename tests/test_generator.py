import json
import zipfile

import pytest

from endstone_packgen.builder import PackError, detect_kind, load_spec
from endstone_packgen.generator import PackGenerator


class Recorder:
    def __init__(self):
        self.lines = []

    def info(self, message):
        self.lines.append(("info", message))

    def warning(self, message):
        self.lines.append(("warning", message))

    def error(self, message):
        self.lines.append(("error", message))


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "server"
    data = root / "plugins" / "packgen"
    (root / "plugins").mkdir(parents=True)
    (root / "server.properties").write_text("level-name=Arena\n")
    log = Recorder()
    return root, data, log, PackGenerator(root, data, log)


def make_rp(data, name="Kit", content=b"png"):
    folder = data / "packs" / name / "textures" / "ui"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "a.png").write_bytes(content)
    return data / "packs" / name


def make_bp(data, name="Logic"):
    folder = data / "packs" / name / "scripts"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "main.js").write_text("// x")
    return data / "packs" / name


def test_resource_pack_becomes_mcpack(env):
    root, data, _, gen = env
    make_rp(data)
    gen.run()
    archive = root / "resource_packs" / "Kit.mcpack"
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist()) == {"manifest.json", "textures/ui/a.png"}
        manifest = json.loads(z.read("manifest.json"))
    assert manifest["modules"][0]["type"] == "resources"
    assert manifest["header"]["version"] == [1, 0, 0]


def test_behavior_pack_is_extracted_and_registered(env):
    root, data, _, gen = env
    make_bp(data)
    gen.run()
    assert (root / "behavior_packs" / "Logic" / "scripts" / "main.js").is_file()
    manifest = json.loads((root / "behavior_packs" / "Logic" / "manifest.json").read_text())
    registered = json.loads((root / "worlds" / "Arena" / "world_behavior_packs.json").read_text())
    assert registered == [{"pack_id": manifest["header"]["uuid"], "version": [1, 0, 0]}]


def test_unchanged_pack_keeps_version_and_bytes(env):
    root, data, _, gen = env
    make_rp(data)
    gen.run()
    first = (root / "resource_packs" / "Kit.mcpack").read_bytes()
    gen.run()
    assert (root / "resource_packs" / "Kit.mcpack").read_bytes() == first


def test_changed_content_bumps_patch_and_keeps_uuid(env):
    root, data, _, gen = env

    def read():
        with zipfile.ZipFile(root / "resource_packs" / "Kit.mcpack") as z:
            return json.loads(z.read("manifest.json"))["header"]

    make_rp(data)
    gen.run()
    before = read()
    make_rp(data, content=b"changed")
    gen.run()
    after = read()
    assert after["uuid"] == before["uuid"]
    assert after["version"] == [1, 0, 1]


def test_deleted_source_removes_output_and_registration(env):
    root, data, _, gen = env
    rp, bp = make_rp(data), make_bp(data)
    gen.run()
    import shutil
    shutil.rmtree(rp)
    shutil.rmtree(bp)
    gen.run()
    assert not (root / "resource_packs" / "Kit.mcpack").exists()
    assert not (root / "behavior_packs" / "Logic").exists()
    assert json.loads((root / "worlds" / "Arena" / "world_behavior_packs.json").read_text()) == []


def test_existing_manifest_is_respected(env):
    root, data, _, gen = env
    src = make_rp(data)
    custom = {"format_version": 2, "header": {"name": "Mine", "uuid": "11111111-1111-1111-1111-111111111111",
                                              "version": [2, 3, 4]},
              "modules": [{"type": "resources", "uuid": "22222222-2222-2222-2222-222222222222", "version": [2, 3, 4]}]}
    (src / "manifest.json").write_text(json.dumps(custom))
    gen.run()
    with zipfile.ZipFile(root / "resource_packs" / "Kit.mcpack") as z:
        assert json.loads(z.read("manifest.json")) == custom


def test_pack_toml_overrides(env):
    _, data, _, _ = env
    src = make_rp(data)
    (src / "pack.toml").write_text('name = "Pretty"\nversion = [3, 1, 0]\ndescription = "d"\n')
    spec = load_spec(src)
    assert (spec.name, spec.base_version, spec.description) == ("Pretty", [3, 1, 0], "d")


def test_mixed_content_is_rejected_and_logged(env):
    root, data, log, gen = env
    src = make_rp(data)
    (src / "scripts").mkdir()
    with pytest.raises(PackError):
        detect_kind(src)
    gen.run()
    assert any(level == "error" and "Kit" in msg for level, msg in log.lines)
    assert not (root / "resource_packs").exists()


def test_bad_pack_does_not_block_others(env):
    root, data, _, gen = env
    (data / "packs" / "Empty").mkdir(parents=True)
    make_rp(data)
    gen.run()
    assert (root / "resource_packs" / "Kit.mcpack").is_file()


def test_default_level_name_without_properties(tmp_path):
    root = tmp_path / "s"
    data = root / "plugins" / "packgen"
    gen = PackGenerator(root, data, Recorder())
    make_bp(data)
    gen.run()
    assert (root / "worlds" / "Bedrock level" / "world_behavior_packs.json").is_file()
