from asu.config import settings
from asu.fastapi.staticfiles import FileResponse

store_path = settings.public_path / "store"

def test_store_content_type_img(client):
    store_path.mkdir(parents=True, exist_ok=True)
    with open(store_path / "test_store_content_type.img", "w+b"):
        pass
    response = client.head("/store/test_store_content_type.img")

    assert response.status_code == 200

    headers = response.headers
    assert headers["Content-Type"] == "application/octet-stream"


def test_store_content_type_imggz(client):
    store_path.mkdir(parents=True, exist_ok=True)
    with open(store_path / "test_store_content_type.img.gz", "w+b"):
        pass
    response = client.head("/store/test_store_content_type.img.gz")

    assert response.status_code == 200

    headers = response.headers
    assert headers["Content-Type"] == "application/octet-stream"


def test_store_file_missing(client):
    response = client.head("/store/test_store_file_missing.bin")

    assert response.status_code == 404

    headers = response.headers
    assert headers["Content-Type"] != "application/octet-stream"
