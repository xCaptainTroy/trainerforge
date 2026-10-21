# Table format

TrainerForge tables use UTF-8 JSON and the schema identifier
`trainerforge.table/1`. The format is deliberately boring: no scripts, URLs,
binary blobs, or executable content.

File extension: `.tforge.json` (the editor also accepts any `.json` file).

## Top-level object

```json
{
  "schema": "trainerforge.table/1",
  "name": "My game table",
  "process_name": "MyGame.exe",
  "created_at": "2026-10-21T12:00:00+00:00",
  "updated_at": "2026-10-21T12:30:00+00:00",
  "entries": []
}
```

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `schema` | string | yes | Must be exactly `trainerforge.table/1`. |
| `name` | string | no | Display name; defaults to `Untitled`. |
| `process_name` | string | no | Informational target image name. |
| `created_at` | ISO-8601 string | no | Creation timestamp. |
| `updated_at` | ISO-8601 string | no | Last modification timestamp. |
| `entries` | array | yes | Table entries. |

Unknown top-level fields are ignored. An unknown `schema` is rejected rather
than guessed.

## Entry object

```json
{
  "id": "a1b2c3d4e5f6",
  "description": "Player health",
  "kind": "pointer",
  "base": "MyGame.exe+0x1A2B0",
  "offsets": ["0x10", "0x20"],
  "value_type": "float",
  "value": "100.0",
  "frozen": true,
  "hotkey": "F1",
  "notes": "Offline save only"
}
```

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `id` | string | no | Unique entry identifier; generated if missing. |
| `description` | string | yes | Human-readable label, must be non-empty. |
| `kind` | `"absolute"` or `"pointer"` | yes | Address strategy. |
| `base` | string | yes | Numeric address or base expression. |
| `offsets` | array of strings | pointer only | Multi-level pointer offsets, applied in order. |
| `value_type` | `"int32"`, `"int64"`, `"float"`, `"double"` | yes | Memory layout. |
| `value` | string | yes | Value that is written/frozen; parsed according to `value_type`. |
| `frozen` | boolean | no | Whether the freezer should write it continuously. |
| `hotkey` | string | no | Global hotkey to toggle freeze; empty means none. |
| `notes` | string | no | Free-form note. |

### Address kinds

**Absolute**

```json
{
  "kind": "absolute",
  "base": "0x7FF6A1B2C3D4",
  "offsets": [],
  "description": "Gold",
  "value_type": "int32",
  "value": "9999"
}
```

`base` must resolve to a positive numeric address. `offsets` must be empty.

**Pointer**

```json
{
  "kind": "pointer",
  "base": "MyGame.exe+0x1A2B0",
  "offsets": ["0x10", "0x20"],
  "description": "Stamina",
  "value_type": "float",
  "value": "100.0"
}
```

Resolution:

```text
address = base
for offset in offsets:
    address = read_pointer(address) + offset
read/write value at address
```

`base` accepts:

- `0x7FF6A1B2C3D4`
- `MyGame.exe+0x1A2B0`
- `MyGame.exe` (offset 0)
- `0x1000+0x20` (numeric arithmetic)

The final address is not dereferenced again. At least one offset is required for
a pointer entry.

### Values

- Integers accept decimal and `0x` notation in the table value.
- Floats accept normal Python float syntax, including exponent notation.
- `int32` is range-checked to `[-2^31, 2^31)`.
- `int64` is range-checked to `[-2^63, 2^63)`.
- `float` is a 32-bit IEEE-754 value; `double` is 64-bit.

Values are stored as strings so the JSON remains human-editable and platform
independent.

### Hotkeys

Format: modifiers followed by a key, separated by `+`.

Examples: `F1`, `Ctrl+F2`, `Alt+Shift+3`, `Win+Space`.

Supported keys include F1–F24, A–Z, 0–9, Space, Enter, Esc, Tab, Insert,
Delete, Home, End, PageUp, PageDown, arrow keys, Backspace, and common
punctuation. The UI rejects invalid combinations before saving.

## Loading rules

- The file must contain a JSON object.
- The `schema` must match exactly.
- `entries` must be a list.
- Entries with duplicate IDs are assigned new IDs when loaded.
- Invalid value types are rejected.
- Every entry is validated while loading (addresses, offsets, value encoding,
  and hotkey syntax). A malformed entry rejects the table with an error naming
  the entry, so a corrupt file cannot trigger an unintended write.
- Unknown top-level fields are ignored.

## Saving rules

- Files are written as UTF-8 with LF newlines.
- Saves use a temporary file plus `os.replace` to avoid a half-written table.
- A missing extension is expanded to `.tforge.json`.
- No network access is performed while saving or loading.

## Sharing tables

Tables are text, so they can be committed to git, attached to an issue, or
reviewed in a pull request. Before sharing:

1. Remove personal notes and paths.
2. Verify every entry against a single-player game you own.
3. Do not include copied commercial trainer content or executable payloads.
4. Mention the game build/version, because offsets change between patches.
