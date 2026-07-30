from backend.database.db import PackageDB
from backend.services import debian_packages


SAMPLE_INDEX = """Package: htop
Version: 3.2.2-2
Installed-Size: 378
Size: 12345
Section: utils
Description: interactive processes viewer

Package: chromium
Version: 120.0
Installed-Size: 250000
Size: 90000000
Section: web
Description: web browser
 extended description line

Package: docker.io
Version: 20.10
Installed-Size: 200000
Size: 50000000
Section: admin
Description: Linux container runtime
"""


def seed_index():
    rows = list(debian_packages._parse_packages_file(SAMPLE_INDEX))
    PackageDB.replace_all(rows)


def test_parse_packages_file():
    rows = list(debian_packages._parse_packages_file(SAMPLE_INDEX))
    assert len(rows) == 3
    names = [r[0] for r in rows]
    assert names == ["htop", "chromium", "docker.io"]
    htop = rows[0]
    assert htop[2] == 378  # installed size kb


def test_validate_against_index():
    seed_index()
    result = debian_packages.validate_packages(["htop", "chrome", "not-a-pkg"])
    by_name = {r["name"]: r for r in result["results"]}
    assert by_name["htop"]["exists"]
    assert by_name["htop"]["installed_size_kb"] == 378
    assert not by_name["chrome"]["exists"]
    assert "chromium" in by_name["chrome"]["suggestions"]  # known alias
    assert not result["all_valid"]


def test_invalid_package_names_rejected():
    seed_index()
    result = debian_packages.validate_packages(["Bad;Name", "UPPER"])
    assert not result["all_valid"]
    assert all(not r["exists"] for r in result["results"])


def test_size_estimate_uses_real_sizes():
    seed_index()
    small = debian_packages.estimate_iso_size_mb([])
    large = debian_packages.estimate_iso_size_mb(["chromium"])
    assert large > small
    assert small >= debian_packages.BASE_SYSTEM_MB


def test_fuzzy_suggestions():
    seed_index()
    assert "chromium" in debian_packages.suggest_alternatives("chromum")


def test_expand_companions():
    from backend.services.debian_packages import expand_companions

    expanded, added = expand_companions(["calamares", "htop"])
    assert "squashfs-tools" in expanded
    assert "calamares-settings-debian" in expanded
    assert "calamares" in added

    # already-present companions are not duplicated
    expanded2, added2 = expand_companions(["calamares", "squashfs-tools"])
    assert expanded2.count("squashfs-tools") == 1
    assert "squashfs-tools" not in added2.get("calamares", [])

    # no triggers, no changes
    expanded3, added3 = expand_companions(["htop", "git"])
    assert expanded3 == ["htop", "git"] and added3 == {}
