# endstone-packgen

Drop a pack folder into `plugins/packgen/packs/` and restart the server. PackGen builds it and installs it.

```
plugins/packgen/packs/
  MyUI/                  -> resource pack  (has textures/, ui/, texts/ ...)
    textures/ui/a.png
  MyLogic/               -> behavior pack  (has scripts/, entities/, items/ ...)
    scripts/main.js
```

| Pack type | Output | Activation |
|---|---|---|
| Resource | `resource_packs/<folder>.mcpack` | Endstone auto-activates archives in `resource_packs/` |
| Behavior | `behavior_packs/<folder>/` | Entry added to `worlds/<level-name>/world_behavior_packs.json` |

- No `manifest.json` needed. UUIDs are derived from the pack name, so they stay stable across restarts.
- When the content changes, the patch version goes up so clients re-download the pack.
- A `manifest.json` in the folder is used as is.
- Removing the folder removes the generated pack on the next start.

## Optional `pack.toml`

```toml
name = "My UI"                # default: folder name
description = "Wardrobe UI"
version = [1, 0, 0]           # base version, patch is bumped automatically
min_engine_version = [1, 21, 0]
type = "resources"            # "resources" or "data"; only needed if auto-detect fails
```
