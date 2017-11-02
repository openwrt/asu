# sends a request to the demo update server
UPDATESERVER="localhost:5000"
UPDATESERVER="https://betaupdate.libremesh.org"

curl -w "\nStatuscode: %{http_code}\n" -X POST "$UPDATESERVER"/api/upgrade-check -d @$1 --header "Content-Type: application/json"
