""" Verify cargo dependency licenses are present.

    mostly copied from:
    https://github.com/conda-forge/pysyntect-feedstock/blob/master/recipe/check_licenses.py

    If this fails, you'll probably need to:
    - ensure the magic-named file(s) exist in library_licenses
    - ensure the magic-named file is included in meta.yaml#/license_file
"""
import json
import os
import sys
from pathlib import Path

import ruamel_yaml
import pytest
from argparse import ArgumentParser

PARSER = ArgumentParser()

PARSER.add_argument("--ignore", default="")
ARGS = PARSER.parse_args()

# paths unlikely to change per package
LICENSE_DIR = "library_licenses"
RECIPE_DIR = Path(os.environ["RECIPE_DIR"])
SRC_DIR = Path(os.environ["SRC_DIR"])

# semi-surpisingly, this is the post-rendered recipe
META = ruamel_yaml.safe_load((RECIPE_DIR / "meta.yaml").read_text("utf-8"))
META_LICENSE_NAMES = [
    lf.split(f"{LICENSE_DIR}/")[1]
    for lf in META["about"]["license_file"]
    if LICENSE_DIR in lf
]

# vendored crates are covered by packaged LICENSE-* file
IGNORE_DEPS = ARGS.ignore.strip().split(",")

LIBRARY_LICENSES = RECIPE_DIR / "parent" / LICENSE_DIR
LICENSE_FILE_NAMES = sorted([f.name for f in LIBRARY_LICENSES.glob("*")])

# as generated by cargo-license
RAW_DEPENDENCIES = json.loads(
    (
        SRC_DIR
        / f"""{os.environ["PKG_NAME"]}-{os.environ["PKG_VERSION"]}-cargo-dependencies.json"""
    ).read_text("utf-8")
)
DEPENDENCIES = {
    crate["name"]: crate
    for crate in RAW_DEPENDENCIES
    if crate["name"] not in IGNORE_DEPS
}


@pytest.fixture(params=DEPENDENCIES.keys())
def crate(request):
    return request.param


def test_missing_license(crate):
    """looks for magic-named files
    handles at least:

    library_licenses/<crate-name>-LICEN(S|C)E-(|-MIT|-APACHE|-ZLIB)

    COPYING is not a license, but some of the manually-built files need it
    for clarification
    """
    assert LIBRARY_LICENSES.exists()
    matches = list(LIBRARY_LICENSES.glob(f"{crate}-LICEN*"))

    errors = []

    if not matches:
        errors += ["no license files"]

    for match in matches:
        if match.name not in META_LICENSE_NAMES:
            errors += ["not in meta.yaml"]

    assert not errors, ruamel_yaml.safe_dump(
        DEPENDENCIES[crate], default_flow_style=False
    )


@pytest.mark.parametrize("license_in_yaml", META_LICENSE_NAMES)
def test_over_licensed(license_in_yaml):
    if "-LICENSE" in license_in_yaml:
        crate = license_in_yaml.split("-LICENSE")[0]
    elif "-COPYING" in license_in_yaml:
        crate = license_in_yaml.split("-COPYING")[0]
    else:
        return

    assert crate in DEPENDENCIES, f"{crate} not a dependency"


@pytest.mark.parametrize("license_in_yaml", META_LICENSE_NAMES)
def test_yaml_license_missing(license_in_yaml):
    assert license_in_yaml in LICENSE_FILE_NAMES


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-svv"]))
