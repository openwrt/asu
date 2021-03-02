curl --header "Content-Type: application/json" \
	--request POST \
	--data @request.json \
	http://localhost:5000/api/build
curl --header "Content-Type: application/json" \
	--request POST \
	--data @request.json \
	https://chef.libremesh.org/api/build
