# sends a request to the demo update server
UPDATESERVER="localhost:5000"
UPDATESERVER="https://betaupdate.libremesh.org"

curl -w "\nStatuscode: %{http_code}\n" -X POST "$UPDATESERVER"/image-request -d @libremesh.json --header "Content-Type: application/json"
