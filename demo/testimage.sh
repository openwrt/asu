# sends a request to the demo update server
UPDATESERVER="35.189.253.152"
#UPDATESERVER="localhost:5000"

curl -w "\nStatuscode: %{http_code}\n" -X POST "$UPDATESERVER"/image-request -d @testimage.json --header "Content-Type: application/json"
