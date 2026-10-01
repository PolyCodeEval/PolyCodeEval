# Website data exporter

Generate the canonical static snapshots:

```bash
python3 website/tools/export_data.py
```

Validate existing snapshots without rewriting them:

```bash
python3 website/tools/validate_data.py
```

The exporter uses an explicit allowlist of canonical configurations. It validates task-set equality across configurations and against the dataset task registry. Generated JSON is compact, English-only, and contains repository-relative audit links.

Export responsibilities are divided by website feature under `exporters/`.
`export_data.py` orchestrates those modules and remains the only supported
snapshot-generation command. `validate_data.py` validates both the benchmark
explorer snapshots and the public leaderboard/submission contracts.

Export responsibilities are organized by website data domain under `exporters/`.
`export_data.py` is the only command that writes the complete snapshot, and
`validate_data.py` is the read-only validation entry point.

Run the Python tests with:

```bash
cd website
python3 -m unittest discover -s tools/tests -t . -v
```
