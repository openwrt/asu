from asu.config import settings

# store_path = settings.public_path / "store"


def test_store_content_type_img(client):
    (settings.public_path / "store").mkdir(parents=True, exist_ok=True)
    (settings.public_path / "store" / "test_store_content_type.img").touch()

    response = client.head("/store/test_store_content_type.img")

    assert response.status_code == 200

    headers = response.headers
    assert headers["Content-Type"] == "application/octet-stream"


def test_store_content_type_imggz(client):
    (settings.public_path / "store").mkdir(parents=True, exist_ok=True)
    (settings.public_path / "store" / "test_store_content_type.img.gz").touch()

    response = client.head("/store/test_store_content_type.img.gz")

    assert response.status_code == 200

    headers = response.headers
    assert headers["Content-Type"] == "application/octet-stream"


def test_store_file_missing(client):
    response = client.head("/store/test_store_file_missing.bin")

    assert response.status_code == 404

    headers = response.headers
    assert headers["Content-Type"] != "application/octet-stream"
