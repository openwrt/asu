# Package Selection API

## Overview

The Package Selection API provides a standalone endpoint for determining which packages will be installed on a device, without actually building an image. This allows for:

1. **Preview Mode**: See what packages will be installed before requesting a build
2. **Validation**: Verify package selections are valid for a specific device
3. **Service Separation**: Run package determination as a separate microservice

## Endpoint

```
POST /api/v1/packages
```

## Request Format

The request body uses the same format as the build API (`BuildRequest` model):

```json
{
  "version": "23.05.2",
  "target": "ath79/generic",
  "profile": "tplink_tl-wdr4300-v1",
  "packages": ["vim", "tmux", "luci"],
  "diff_packages": false,
  "distro": "openwrt"
}
```

### Required Fields

- `version`: OpenWrt version (e.g., "23.05.2", "SNAPSHOT")
- `target`: Target architecture (e.g., "ath79/generic", "x86/64")
- `profile`: Device profile (e.g., "tplink_tl-wdr4300-v1")

### Optional Fields

- `packages`: List of packages to install (default: `[]`)
- `packages_versions`: Dictionary mapping package names to specific versions
- `diff_packages`: If `true`, removes default packages not in the list (default: `false`)
- `distro`: Distribution name (default: `"openwrt"`)
- `defaults`: Custom shell script for first boot (if server allows)
- `rootfs_size_mb`: Custom rootfs partition size
- `repositories`: Additional repositories for user packages
- `repository_keys`: Verification keys for additional repositories

## Response Format

```json
{
  "status": 200,
  "detail": "Package selection completed",
  "packages": ["vim", "tmux", "luci"],
  "default_packages": ["base-files", "busybox", "..."],
  "profile_packages": ["kmod-ath9k", "..."],
  "requested_packages": ["vim", "tmux", "luci"],
  "diff_packages": false,
  "profile": "tplink_tl-wdr4300-v1",
  "version": "23.05.2",
  "target": "ath79/generic"
}
```

### Response Fields

- `status`: HTTP status code (200 for success)
- `detail`: Status message
- `packages`: Final package list that would be used for building
- `default_packages`: Default packages for the target
- `profile_packages`: Profile-specific packages for the device
- `requested_packages`: Packages requested by the client
- `diff_packages`: Whether diff_packages mode was used
- `profile`: Device profile identifier
- `version`: OpenWrt version
- `target`: Target architecture

## Examples

### Basic Package Selection

Request:
```bash
curl -X POST http://localhost:8000/api/v1/packages \
  -H "Content-Type: application/json" \
  -d '{
    "version": "23.05.2",
    "target": "ath79/generic",
    "profile": "tplink_tl-wdr4300-v1",
    "packages": ["vim", "tmux"]
  }'
```

Response:
```json
{
  "status": 200,
  "detail": "Package selection completed",
  "packages": ["vim", "tmux"],
  "default_packages": ["base-files", "busybox", ...],
  "profile_packages": ["kmod-ath9k", ...],
  "requested_packages": ["vim", "tmux"],
  "diff_packages": false,
  "profile": "tplink_tl-wdr4300-v1",
  "version": "23.05.2",
  "target": "ath79/generic"
}
```

### Package Selection with Diff Packages

When `diff_packages` is `true`, the endpoint calculates which default packages should be removed and which should be added:

Request:
```bash
curl -X POST http://localhost:8000/api/v1/packages \
  -H "Content-Type: application/json" \
  -d '{
    "version": "23.05.2",
    "target": "ath79/generic",
    "profile": "tplink_tl-wdr4300-v1",
    "packages": ["vim", "tmux"],
    "diff_packages": true
  }'
```

The response will include packages to remove (prefixed with `-`) and packages to add.

### Version-Specific Package Changes

The endpoint automatically applies version-specific package changes. For example, on version 24.10+, requesting `auc` will automatically be replaced with `owut`.

## Error Responses

### Invalid Version
```json
{
  "status": 400,
  "detail": "Unsupported branch: 99.99.99"
}
```

### Invalid Target
```json
{
  "status": 400,
  "detail": "Unsupported target: invalid/target"
}
```

### Invalid Profile
```json
{
  "status": 400,
  "detail": "Unsupported profile: nonexistent-device"
}
```

## Use Cases

### 1. Preview Package Selection

Before building an image, query the package endpoint to see exactly what packages will be installed:

```python
import requests

response = requests.post("http://localhost:8000/api/v1/packages", json={
    "version": "23.05.2",
    "target": "ath79/generic",
    "profile": "tplink_tl-wdr4300-v1",
    "packages": ["vim", "tmux", "luci"]
})

package_info = response.json()
print(f"Final packages: {package_info['packages']}")
print(f"Default packages: {package_info['default_packages']}")
```

### 2. Validate Package Selections

Check if a package selection is valid before submitting a build request:

```python
response = requests.post("http://localhost:8000/api/v1/packages", json={
    "version": "23.05.2",
    "target": "ath79/generic",
    "profile": "tplink_tl-wdr4300-v1",
    "packages": ["my-custom-package"]
})

if response.status_code == 200:
    print("Package selection is valid!")
    # Proceed with build request
else:
    print(f"Invalid selection: {response.json()['detail']}")
```

### 3. Separate Package Service

Run the package selection service independently from the build service:

```python
# Package Selection Service
def get_package_selection(device_config):
    response = requests.post("http://package-service:8000/api/v1/packages", 
                           json=device_config)
    return response.json()

# Build Service
def request_build(device_config):
    # First, get package selection
    packages = get_package_selection(device_config)
    
    # Then, request build with validated packages
    response = requests.post("http://build-service:8000/api/v1/build",
                           json=device_config)
    return response.json()
```

## Integration with Build API

The package selection endpoint uses the same request model as the build API (`BuildRequest`), ensuring consistency. You can:

1. Call `/api/v1/packages` to preview and validate
2. Call `/api/v1/build` with the same request to build the image

Both endpoints share the same validation logic, so a request that succeeds on `/api/v1/packages` will also be valid for `/api/v1/build` (assuming sufficient resources).

## Compatibility

The package selection endpoint:
- ✅ Maintains full API compatibility with existing endpoints
- ✅ Uses the same request model as the build API
- ✅ Applies the same validation and package changes
- ✅ Can be run as a separate microservice
- ✅ Does not affect the build API behavior

## Implementation Details

The package selection logic:

1. **Validates the request**: Checks version, target, and profile validity
2. **Fetches device metadata**: Retrieves default and profile packages from upstream
3. **Applies package changes**: Automatically applies version/target/profile-specific adjustments
4. **Calculates diff packages**: If requested, determines packages to add/remove
5. **Returns results**: Provides comprehensive information about the package selection

This is the same logic used by the build API, ensuring consistency between preview and actual builds.
