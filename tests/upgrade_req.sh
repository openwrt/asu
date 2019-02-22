SERVER="http://localhost:5000"
SERVER="https://chef.libremesh.org"
curl --request POST -H "Content-Type: application/json" --data @manifest.json "$SERVER/api/upgrade-check"
