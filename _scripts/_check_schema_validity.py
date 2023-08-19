from pathlib import Path

import _fetch_schema
import yaml

_ROOT = Path(__file__).parent.parent

if __name__ == "__main__":
    _fetch_schema.main(".test.openapi.yaml")
    schema_1 = yaml.safe_load(
        (_ROOT / "openapi" / ".test.openapi.yaml").open("r").read()
    )
    schema_2 = yaml.safe_load((_ROOT / "openapi" / "openapi.yaml").open("r").read())
    # Rm the test schema
    (_ROOT / "openapi" / ".test.openapi.yaml").unlink()
    assert schema_1 == schema_2
