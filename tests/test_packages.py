def test_api_packages_basic(client):
    """Test basic package selection without diff_packages"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["vim", "tmux"],
        ),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == 200
    assert data["detail"] == "Package selection completed"
    assert data["requested_packages"] == ["vim", "tmux"]
    assert data["packages"] == ["vim", "tmux"]
    assert data["diff_packages"] is False
    assert data["version"] == "1.2.3"
    assert data["target"] == "testtarget/testsubtarget"


def test_api_packages_empty_list(client):
    """Test package selection with empty package list"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=[],
        ),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["packages"] == []
    assert data["requested_packages"] == []


def test_api_packages_invalid_version(client):
    """Test package selection with invalid version"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="99.99.99",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["vim"],
        ),
    )
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported branch" in data["detail"]


def test_api_packages_invalid_target(client):
    """Test package selection with invalid target"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="1.2.3",
            target="invalid/target",
            profile="testprofile",
            packages=["vim"],
        ),
    )
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported target" in data["detail"]


def test_api_packages_invalid_profile(client):
    """Test package selection with invalid profile"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="invalidprofile",
            packages=["vim"],
        ),
    )
    assert response.status_code == 400
    data = response.json()
    assert "Unsupported profile" in data["detail"]


def test_api_packages_with_diff_packages(client):
    """Test package selection with diff_packages enabled"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["vim", "tmux"],
            diff_packages=True,
        ),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["diff_packages"] is True
    # When diff_packages is True, the package list should include removals
    assert isinstance(data["packages"], list)


def test_api_packages_profile_sanitization(client):
    """Test that profile names are sanitized (commas replaced with underscores)"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="test,profile",
            packages=["vim"],
        ),
    )
    # Should fail because sanitized profile "test_profile" doesn't exist
    assert response.status_code == 400
    assert "Unsupported profile" in response.json()["detail"]


def test_api_packages_packages_versions(client):
    """Test package selection with packages_versions"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages_versions={"vim": "1.0", "tmux": "2.0"},
        ),
    )
    assert response.status_code == 200
    data = response.json()
    # packages_versions keys should be used as the package list
    assert set(data["requested_packages"]) == {"vim", "tmux"}


def test_api_packages_defaults_disabled(client):
    """Test that defaults are rejected when not enabled"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["vim"],
            defaults="echo test",
        ),
    )
    assert response.status_code == 400
    data = response.json()
    assert "defaults" in data["detail"].lower()


def test_api_packages_response_includes_profile_info(client):
    """Test that response includes default and profile packages"""
    response = client.post(
        "/api/v1/packages",
        json=dict(
            version="1.2.3",
            target="testtarget/testsubtarget",
            profile="testprofile",
            packages=["vim"],
        ),
    )
    assert response.status_code == 200
    data = response.json()
    assert "default_packages" in data
    assert "profile_packages" in data
    assert isinstance(data["default_packages"], list)
    assert isinstance(data["profile_packages"], list)
