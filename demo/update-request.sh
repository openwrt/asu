# sends a request to the demo update server
UPDATESERVER="https://betaupdate.libremesh.org"
UPDATESERVER="localhost:5000"

curl -w "\nStatuscode: %{http_code}\n" -X POST "$UPDATESERVER"/update-request -d @$1 --header "Content-Type: application/json"
