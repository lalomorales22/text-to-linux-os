import pytest

from backend.database.db import BuildDB, ProjectDB, VersionDB


def test_project_crud():
    pid = ProjectDB.create("My System")
    project = ProjectDB.get(pid)
    assert project["name"] == "My System"
    assert project["status"] == "draft"

    ProjectDB.update(pid, name="Renamed", status="configuring",
                     draft_config={"packages": ["htop"]})
    project = ProjectDB.get(pid)
    assert project["name"] == "Renamed"
    assert project["draft_config"] == {"packages": ["htop"]}

    ProjectDB.delete(pid)
    assert ProjectDB.get(pid) is None


def test_update_rejects_unknown_columns():
    pid = ProjectDB.create("x")
    with pytest.raises(ValueError):
        ProjectDB.update(pid, **{"name = 'x' WHERE 1=1; --": "inject"})


def test_version_numbers_increment():
    pid = ProjectDB.create("versioned")
    v1 = VersionDB.create(pid, {"packages": []})
    v2 = VersionDB.create(pid, {"packages": ["vim"]})
    assert VersionDB.get(v1)["version_number"] == 1
    assert VersionDB.get(v2)["version_number"] == 2
    assert VersionDB.latest_for_project(pid)["id"] == v2


def test_build_lifecycle_and_stale_recovery():
    pid = ProjectDB.create("buildable", status="building")
    vid = VersionDB.create(pid, {"packages": []})
    BuildDB.create("build-1", pid, vid, "/tmp/log")
    BuildDB.update("build-1", status="running", progress=42, step="Installing")

    build = BuildDB.get("build-1")
    assert build["progress"] == 42
    assert BuildDB.active_for_project(pid)["id"] == "build-1"

    # simulate a server restart with the build still marked running
    assert BuildDB.mark_stale_builds_failed() == 1
    assert BuildDB.get("build-1")["status"] == "failed"
    assert BuildDB.active_for_project(pid) is None
