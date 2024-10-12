# Setting up a local server

Assumptions:
  - You're using a recent Ubuntu for install, below examples developed on a qemu VM using 24.04.
    - Examples below use `apt`
    - `git` is already installed
    - Has Python 3.12 (3.11 is ok)
  - You are going to use the server on your LAN for local installs, and not expose it to the internet, hence no discussion of proxies or whatnot.

## First check IPv6 connectivity from your VM

Run curl against an external server forcing IPv6, if this works, then skip forward.

```bash
curl -6 https://sysupgrade.openwrt.org/json/v1/overview.json
```

If that fails to connect, then you will have all sorts of issues unless you resolve them.  The easiest thing to do is just disable IPv6 on your VM:
```bash
sudo vi /etc/sysctl.d/10-ipv6-privacy.conf
```
Add one line:
```
net.ipv6.conf.all.disable_ipv6 = 1
```
and reload:
```bash
sudo sysctl -f /etc/sysctl.d/10-ipv6-privacy.conf
```

If you can figure out how to get qemu to punch through the IPv6 blocking, @efahl would really (really) like to know.

## Podman installation

Make sure you have `podman`, Ubuntu 24.04 did not:

```bash
cd ~
sudo apt -y install podman
systemctl --user enable podman.socket
systemctl --user start podman.socket
systemctl --user status podman.socket
```

## Python configuration

Create a new Python virtual environment using `venv`:

```bash
sudo apt -y install python3-venv
python3 -m venv asu-venv
. asu-venv/bin/activate
```

Test your new virtual environment.  Verify that the executables are in your venv, and that the Python version is 3.11 or newer.

```bash
$ which python
/home/efahlgren/asu-venv/bin/python
$ which pip
/home/efahlgren/asu-venv/bin/pip
$ python --version
Python 3.12.3
```

Install the basic tools (`poetry` will be used to easily install all the rest of the requirements):

```bash
pip install poetry podman-compose
```

## Attended Sysupgrade installation and configuration

Get ASU and install all of its requirements:

```bash
git clone https://github.com/openwrt/asu.git
cd asu/
poetry install
```

Edit `podman-compose.yml` and make the server listen on the VM's WAN port at `0.0.0.0`:
```bash
server:
  ...
  ports:
    - "0.0.0.0:8000:8000"
```

Set up your initial podman environment:

```bash
echo "# where to store images and json files
PUBLIC_PATH=$(pwd)/public
HOST_PATH=$(pwd)/public
# absolute path to podman socket mounted into worker containers
CONTAINER_SOCK=/run/user/$(id -u)/podman/podman.sock
# allow host cli tools access to redis database
REDIS_URL=redis://localhost:6379
# turn on the 'defaults' option on the server
ALLOW_DEFAULTS=True
" > .env
```

## Running the server

Start up the server:
```bash
$ podman-compose up -d
...

$ podman logs asu_server_1
INFO:     Started server process [2]
INFO:     Waiting for application startup.
INFO:root:ASU server starting up
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Check that the server is accessible.  `ssh` into your router and fetch the front page, this should spew a pile of html:
```bash
asu_server=<your server's IPv4, or its name if you have it in DNS>
uclient-fetch -O - "http://$asu_server:8000/"
```

On a host with "real" curl (we need `--headers`), pick a version, target and subtarget and compose an update query as follows.  This is the mechanism by which your ASU server will learn about new releases, so for each version/target/subtarget combination, you need to run a similar query.  (To update almost everything, you can run `python misc/update_all_targets.py`, but that's fairly wasteful of time and bandwidth.)

```bash
curl -v --header "x-update-token: foobar" "http://$asu_server:8000/api/v1/update/SNAPSHOT/x86/64"
```
Note that the value of "x-update-token" is "foobar" by default, but can be changed in `asu/config.py` or by adding `UPDATE_TOKEN=whatever` in the `.env` file.

Selectively add more versions to the server from your router (if you have curl installed), or from your workstation using the data from the router.  Here's how you'd go about it on the router:

```bash
$ eval $(ubus call system board | jsonfilter -e 'version=$.release.version' -e 'target=$.release.target')
$ echo "$version $target"
23.05.5 mediatek/mt7622
$ curl -v --header "x-update-token: foobar" "http://$asu_server:8000/api/v1/update/$version/$target"
```
(Note that you can run these `curl` queries on the ASU server itself, it has `curl` and you just use `localhost` as the value for `$asu_server`.)

Back on your ASU server, look at the worker log and see what happened:

```bash
$ podman logs asu_worker_1
...
01:18:20 default: asu.update.update(target_subtarget='x86/64', version='SNAPSHOT') (2376baed-c4bf-4d37-ba9c-4021feec54b6)
01:18:20 SNAPSHOT: Found 86 targets
01:18:20 SNAPSHOT/x86/64: Found 1 profiles
01:18:20 SNAPSHOT/x86/64: Found revision r27707-084665698b
01:18:20 default: Job OK (2376baed-c4bf-4d37-ba9c-4021feec54b6)
01:18:20 Result is kept for 500 seconds
```

You can now try to do a download using LuCI ASU, `auc` or `owut`.  First point the `attendedsysupgrade` config at your server.

```bash
uci set attendedsysupgrade.server.url="http://$asu_server:8000"
uci commit
```
(To revert, simply substitute `https://sysupgrade.openwrt.org` as the `url`.)

On snapshot, run an `owut` check with `--verbose` to see where it's getting data:
```
$ owut check -v
owut - OpenWrt Upgrade Tool
Downloaded http://$asu_server:8000/json/v1/overview.json to /tmp/owut-overview.json (16073B at 0.245 Mbps)
...
```

Or for 23.05 and earler, use `auc`:
```bash
$ auc -c
auc/0.3.2-1
Server:    https://10.1.1.207:8000
Running:   23.05.5 r24106-10cc5fcd00 on mediatek/mt7622 (linksys,e8450-ubi)
Available: 23.05.5 r24106-10cc5fcd00
Requesting package lists...
 luci-app-adblock: git-24.224.28330-dc8b3a6 -> git-24.284.61672-4b84d8e
 adblock: 4.2.2-5 -> 4.2.2-6
 luci-mod-network: git-24.264.56960-63ba3cb -> git-24.281.58052-a6c2279
```

## Deployment notes

If you want your server to remain active after you log out of the server, you must enable "linger" in `loginctl`:
```bash
loginctl enable-linger
```
