SERVER="https://chef.libremesh.org"
SERVER="http://localhost:5000"
curl --request POST -H "Content-Type: application/json" --data @manifest.json "$SERVER/api/upgrade-check"
