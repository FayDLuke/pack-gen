from endstone.plugin import Plugin

from endstone_packgen.generator import PackGenerator


class PackGenPlugin(Plugin):
    prefix = "PackGen"
    api_version = "0.11"

    def on_load(self) -> None:
        server_root = self.data_folder.parent.parent
        try:
            PackGenerator(server_root, self.data_folder, self.logger).run()
        except Exception as exc:
            self.logger.error(f"Pack generation failed: {exc!r}")
