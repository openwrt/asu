# sends a request to the running update server
UPDATESERVER="localhost:5000"

curl -vX POST "$UPDATESERVER"/image-request -d @test_image.json --header "Content-Type: application/json"
curl -vX POST "$UPDATESERVER"/image-request -d @test_image2.json --header "Content-Type: application/json"
