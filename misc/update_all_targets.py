from requests import Session

session = Session()

asu_url = "http://localhost:5001"


def reload_all():
    versions = session.get("https://downloads.openwrt.org/.versions.json").json()[
        "versions_list"
    ]
    for version in versions:
        print(f"Reloading {version}")
        targets = session.get(
            f"https://downloads.openwrt.org/releases/{version}/.targets.json"
        )
        if targets.status_code == 404:
            print(f"Targets not found for {version}")
            continue
        targets = targets.json()
        for target in targets:
            print(f"Reloading {version}/{target}")
            res = session.get(
                f"{asu_url}/api/v1/update/{version}/{target}",
                headers={"X-Update-Token": "<TOKEN>"},
            )
            print(res)

    targets = session.get(
        "https://downloads.openwrt.org/snapshots/.targets.json"
    ).json()
    for target in targets:
        print(f"Reloading SNAPSHOT/{target}")
        session.get(
            f"{asu_url}/api/v1/update/SNAPSHOT/{target}",
            headers={"X-Update-Token": "<TOKEN>"},
        )


reload_all()
