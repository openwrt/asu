edit_packages_bool = false;
packages_flavor = [];

var delay_timer;
function search_delayed() {
	clearTimeout(delay_timer);
	delay_timer = setTimeout(search, 500);
}

function search() {
	var device = document.getElementById("search_device").value;
	if(device.length < 3) { return }

	var distro = document.getElementById("distro").value;
	var release = document.getElementById("release").value;

	request_url = data.update_server + "/api/models?model_search=" + device + "&distro=" + distro + "&release=" + release

	var xmlhttp = new XMLHttpRequest();
	xmlhttp.open("GET", request_url, true);

	xmlhttp.onreadystatechange = function () {
		if (xmlhttp.readyState == 4 && xmlhttp.status == 200) {
			device_results(xmlhttp);
		}
	}
	xmlhttp.send(null);

	function device_results(xmlhttp) {
		devices = JSON.parse(xmlhttp.responseText)
		document.request_form.profile.options.length = 0;
		if(devices.length == 0) {
			document.request_form.profile[0] = new Option("Not found")
		} else {
			for(var i = 0; i < devices.length; i++) {
				document.request_form.profile[i] = new Option(devices[i].model)
				document.request_form.profile[i].value = devices[i].target + "/" + devices[i].subtarget + "/" + devices[i].profile
			}
		}
		if(edit_packages_bool == true) {
			load_packages_image();
		}
		set_device_info();
	}
};

function load_distros() {
	var xmlhttp = new XMLHttpRequest();
	request_url = data.update_server + "/api/distros";

	xmlhttp.open("GET", request_url, true);

	xmlhttp.onreadystatechange = function () {
		if (xmlhttp.readyState == 4 && xmlhttp.status == 200) {
			distros_results(xmlhttp);
		}
	}
	xmlhttp.send(null);

	function distros_results(xmlhttp) {
		distros = JSON.parse(xmlhttp.responseText);
		document.request_form.distro.options.length = 0;

		for(var i = 0; i < distros.length; i++) {
			distros_length = document.request_form.distro.length;
			document.request_form.distro[distros_length] = new Option(distros[i].name)
			document.request_form.distro[distros_length].value = distros[i].name
			document.request_form.distro[distros_length].innerHTML = distros[i].alias
		}
		load_releases();
	}
};

function load_flavors() {
	for(flavor in flavors) {
		flavors_length = document.request_form.flavor.length;
		document.request_form.flavor[flavors_length] = new Option(flavor)
	}
}

function set_packages_flavor() {
	packages_flavor = flavors[document.request_form.flavor.value].split(" ");
	if (typeof packages == 'undefined') {
		load_packages_image();
	} else {
		edit_packages_update();
	}
}

function profile_changed() {
	set_device_info();
	if(edit_packages_bool == true) {
		load_packages_image();
	}
}

function load_network_profiles() {
	var xmlhttp = new XMLHttpRequest();
	request_url = data.update_server + "/api/network_profiles";

	xmlhttp.open("GET", request_url, true);

	xmlhttp.onreadystatechange = function () {
		if (xmlhttp.readyState == 4 && xmlhttp.status == 200) {
			network_profiles_results(xmlhttp);
		}
	}
	xmlhttp.send(null);

	function network_profiles_results(xmlhttp) {
		network_profiles = JSON.parse(xmlhttp.responseText);

		for(var i = 0; i < network_profiles.length; i++) {
			network_profiles_length = document.request_form.network_profile.length;
			document.request_form.network_profile[network_profiles_length] = new Option(network_profiles[i])
		}
	}
};

function load_releases() {
	var xmlhttp = new XMLHttpRequest();
	var device = document.getElementById("search_device").value;
	var distro = document.getElementById("distro").value;
	var release = document.getElementById("release").value;

	request_url = data.update_server + "/api/releases"

	xmlhttp.open("GET", request_url, true);

	xmlhttp.onreadystatechange = function () {
		if (xmlhttp.readyState == 4 && xmlhttp.status == 200) {
			releases_results(xmlhttp);
		}
	}
	xmlhttp.send(null);

	function releases_results(xmlhttp) {
		releases = JSON.parse(xmlhttp.responseText);
		distro_changed();
	}
};

function set_device_info() {
	profile_split = document.request_form.profile.value.split("/");
    target = profile_split[0]
    subtarget = profile_split[1]
    profile = profile_split[2]
	document.getElementById("info_device").innerHTML = "<b>Target:</b> " + target + " - <b>Subtarget</b>: " + subtarget + " - <b>Profile</b>: " + profile
}

function load_packages_image() {
	var xmlhttp = new XMLHttpRequest();
	var device = document.getElementById("search_device").value;
	var distro = document.getElementById("distro").value;
	var release = document.getElementById("release").value;
	set_device_info()
	if(typeof target != 'undefined' && typeof subtarget != 'undefined' && typeof profile != 'undefined') {

		request_url = data.update_server + "/api/packages_image?distro=" + distro + "&release=" + release + "&target=" + target + "&subtarget=" + subtarget+ "&profile=" + profile

		xmlhttp.open("GET", request_url, true);

		xmlhttp.onreadystatechange = function () {
			if (xmlhttp.readyState == 4 && xmlhttp.status == 200) {
				packages_image_results(xmlhttp);
			}
		}
		xmlhttp.send(null);
	} else {
		packages_image = [];
		edit_packages_update();
	}

	function packages_image_results(xmlhttp) {
		packages_image = diff_packages(JSON.parse(xmlhttp.responseText).packages);
		edit_packages_update();
	}
};

function edit_packages_update() {
	if (packages_flavor != "") {
		packages = diff_packages(packages_image.concat(packages_flavor))
	} else {
		packages = packages_image.slice()
	}
	document.request_form.edit_packages.value = packages.join("\n");
}

function edit_packages() {
	edit_packages_bool = true;
	load_packages_image();
	document.getElementById("edit_packages_div").style.display = "block";
}

function diff_packages(packages_diff) {
	packages_remove = [];
	packages_install = [];
	for (var i = 0; i < packages_diff.length; i++) {
		if (packages_diff[i].startsWith("-")) {
			packages_remove.push(packages_diff[i]);
		} else {
			packages_install.push(packages_diff[i]);
		}
	}
	for (var j = 0; j < packages_remove.length; j++) {
		package_index = packages_install.indexOf(packages_remove[j].substring(1))
		if(package_index != -1) {
			packages_install.splice(package_index, 1);
		}
	}
	return(packages_install)

	packages = packages_image.slice()
	for (var j = packages.length -1; j > 0; j--) {
		if (packages[j].startsWith("-")) {
			packages.splice(j, 1);
		}
	}

	for (var i in packages_flavor) {
		if(packages_flavor[i].startsWith("-")) {
			package_index = packages.indexOf(packages_flavor[i].substring(1))
			if(package_index != -1) {
				packages.splice(package_index, 1);
			}
		} else if(!packages.includes(packages_flavor[i])) {
			packages.push(packages_flavor[i])
		}
	}
	document.request_form.edit_packages.value = packages.join("\n");
}

function distro_changed() {
	document.request_form.release.options.length = 0;

	for(var i = 0; i < releases.length; i++) {
		if(releases[i].distro === document.request_form.distro[document.request_form.distro.selectedIndex].value) {
			if (releases[i].release == "snapshot") {

			}
			release_length = document.request_form.release.length
			document.request_form.release[release_length] = new Option(releases[i].release)
		}
	}
	if(document.request_form.distro[document.request_form.distro.selectedIndex].value === "lime") {
		document.getElementById("lime_config").style.display = "block";
	}  else {
		document.getElementById("lime_config").style.display = "none";
		packages_flavor = ""
	}
	search();
}

function create() {
	packages = [];
	edit_packages_split = document.request_form.edit_packages.value.split("\n")
	for(var i = 0; i < edit_packages_split.length; i++) {
		package_trimmed = edit_packages_split[i].trim()
		if (package_trimmed != "") {
			packages.push(package_trimmed)
		}
	}
	image_request()
}

function toggle_advanced_view() {
	if (document.request_form.advanced_view.checked) {
		action = "block"
	} else {
		action = "none"
	}
	var advanced_elements = document.querySelectorAll(".advanced_view");
	for(var i = 0; i < advanced_elements.length; i++) {
		advanced_elements[i].style.display = action;
	}

}

function bootstrap() {
	packages_flavor = ""
	load_distros();
	load_network_profiles();
	load_flavors();
	toggle_advanced_view();
}


// shows notification if update is available
function info_box(info_output) {
	document.getElementById("info_box").style.display = "block";
	document.getElementById("info_box").innerHTML = info_output;
}

function error_box(error_output) {
	document.getElementById("error_box").style.display = "block";
	document.getElementById("error_box").innerHTML = error_output;
	document.getElementById("info_box").style.display = "none";
}

// requests to the update server
function server_request(request_dict, path, callback) {
	url = data.update_server + "/" + path
	var xmlhttp = new XMLHttpRequest();
	xmlhttp.open("POST", url, true);
	xmlhttp.setRequestHeader("Content-type", "application/json");
	xmlhttp.send(JSON.stringify(request_dict));
	xmlhttp.onerror = function(e) {
		console.log("update server down")
	}
	xmlhttp.addEventListener('load', function(event) {
		callback(xmlhttp)
	});
}

function image_request() {
	request_dict = {}
	request_dict.distro = document.request_form.distro.value;
	request_dict.version = document.request_form.release.value;
	profile_split = document.request_form.profile.value.split("/");
	request_dict.target = profile_split[0]
	request_dict.subtarget = profile_split[1]
	request_dict.board = profile_split[2]
	request_dict.network_profile = document.request_form.network_profile.value
	if (packages != "") {
		request_dict.packages = packages
	}
	server_request(request_dict, "image-request", image_request_handler)
}

function image_request_handler(response) {
	if (response.status === 400) {
		response_content = JSON.parse(response.responseText)
		error_box_content = response_content.error
		if('log' in response_content) {
			error_box_content += ' <a href="' + response_content.log + '">Build log</a>'
		}
		error_box(error_box_content)

	} else if (response.status === 500) {
		error_box("internal server error. please try again later")
	} else if (response.status === 503) {
		error_box("please wait. server overloaded")
		// handle overload
		setTimeout(image_request, 30000)
	} else if (response.status === 201) {
		response_content = JSON.parse(response.responseText)
		if(response_content.queue != undefined) {
			// in queue
			info_box("please wait. you are in queue position " + response_content.queue)
			console.log("queued")
		} else {
			info_box("imagebuilder not ready, please wait")
			console.log("setting up imagebuilder")
		}
		setTimeout(image_request, 5000)
	} else if (response.status === 206) {
		// building
		console.log("building")
		info_box("building image")
		setTimeout(image_request, 5000)
	} else if (response.status === 200) {
		// ready to download
		response_content = JSON.parse(response.responseText)
		files_url = response_content.files
		load_files();
		info_box("image created. Download: <a href='" + response_content.sysupgrade + "'>Firmware</a>, <a href='" + response_content.sysupgrade + ".log'>Build log</a>, <a href='" + response_content.sysupgrade + ".sig'>Signature</a>")
	}
}

function load_files() {
	var xmlhttp = new XMLHttpRequest();

	xmlhttp.open("GET", files_url, true);

	xmlhttp.onreadystatechange = function () {
		if (xmlhttp.readyState == 4 && xmlhttp.status == 200) {
			releases_results(xmlhttp);
		}
	}
	xmlhttp.send(null);

	function releases_results(xmlhttp) {
		response_content = JSON.parse(xmlhttp.responseText);
		files_box = document.getElementById("files_box")
		files_box.innerHTML = ""
		var list = document.createElement('ul');

		for(var i = 0; i < response_content.length; i++) {
			var item = document.createElement('li');
			var link = document.createElement('a');
			link.href = files_url + response_content[i].name
			link.innerHTML = response_content[i].name
			item.appendChild(link)
			list.appendChild(item);
		}
		files_box.appendChild(list);
	}
}
