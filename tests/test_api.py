def test_api_version(client):
    response = client.get("/api/versions")
    assert response.json == {
        "SNAPSHOT": {
            "branch": "master",
            "path": "snapshots",
            "pubkey": "RWS1BD5w+adc3j2Hqg9+b66CvLR7NlHbsj7wjNVj0XGt/othDgIAOJS+",
        }
    }
