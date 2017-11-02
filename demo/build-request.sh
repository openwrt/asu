# sends a request to the demo upgrade server
UPDATESERVER="localhost:5000"
UPDATESERVER="https://betaupdate.libremesh.org"
JSON_FILE=$1

function image_request () {
	response=$(curl -s -w "\n%{http_code}" -X POST "$UPDATESERVER"/api/build-request -d @$JSON_FILE --header "Content-Type: application/json")
	export statuscode=$(echo "$response" | tail -n 1)
	export content=$(echo "$response" | head -n 1)
}

image_request

while [ "$statuscode" -ne 200 ];  do
	if [ $statuscode -eq 500 ]; then
		echo "internal server error"
		echo "$content"
		exit 1
	elif [ $statuscode -eq 400 ]; then
		echo "bad request"
		echo "$content"
		exit 1
	elif [ $statuscode -eq 201 ]; then
			echo "setting up imagebuilder - please wait"
	elif [ $statuscode -eq 206 ]; then
			echo "currently building - please wait"
	fi
	image_request
	sleep 5
done

echo "build successfull"
echo $content
