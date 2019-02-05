SERVER="https://as-test.stephen304.com"
SERVER="http://localhost:5000"

curl  --request POST -H "Content-Type: application/json" --data @image.json "$SERVER"/api/build-request
echo
curl  --request POST -H "Content-Type: application/json" --data @image2.json "$SERVER"/api/build-request
echo
