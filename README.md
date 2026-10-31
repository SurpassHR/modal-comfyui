[English](README.md) | [简体中文](README.zh-CN.md)

# modal-comfyui

Run ComfyUI on Modal with auto-scaling, GPU snapshots, and easy model management.

Good for testing wan2.2 or other video generation models.

## Prerequisites

- A Modal account
- Python installed
- `uv` installed

## Installation

1. Clone this repository.
2. Install the Modal client:
   ```bash
   uv sync
   ```
3. Set up your modal account (if not done already):
   ```bash
   modal setup
   ```
4. Set up your modal secret (optional; recommended)
   ```bash
   modal secret create huggingface-secret \
     HF_TOKEN=hf_[your HF access token] \
     CIVITAI_TOKEN=[your CivitAI token, if needed]
   ```
5. Create the GitHub secret used to clone the private workflow repository:
   ```bash
   modal secret create github-secret GITHUB_TOKEN=github_pat_[...]
   ```

   For a fine-grained PAT, grant **Contents: Read** access to
   `SurpassHR/ComfyUI-workflows`. The token is attached only to the image-build
   clone step; it is not present in the running ComfyUI container.

## Configuration

### Models

Copy `models.example.py` to `models.py` and edit it to manage your models. You can specify:
- Hugging Face models(`models`) using `repo_id` and `filename`.
- External models(`models_ext`, e.g. civitai) using a direct `url`.

Models are downloaded to volumes and symlinked to the specified `model_dir`.
The downloads happen while the Modal image is being built. Model payloads are
kept in the `hf-hub-cache` Volume, so rebuilding the image does not normally
download unchanged files again.

`model_dir` accepts two styles:
- **Relative path** (recommended for standard ComfyUI folders): resolved under `/root/comfy/ComfyUI/models/`. e.g. `"checkpoints"` → `/root/comfy/ComfyUI/models/checkpoints`.
- **Absolute path**: used as-is. Use this when the target lives outside `ComfyUI/models/` (e.g. a custom node's own model directory).

See `models.example.py` for reference.

### Workflows

ComfyUI stores browser workflows under:

```text
/root/comfy/ComfyUI/user/default/workflows
```

The project clones `https://github.com/SurpassHR/ComfyUI-workflows.git` and
copies the repository contents **directly** into the workflow directory above.
There is no extra repository-name folder in ComfyUI's Workflow sidebar.

Because this repository is private, cloning requires the Modal Secret named
`github-secret` with a `GITHUB_TOKEN` key. The clone step calls Git with a
temporary credential helper, removes `.git` from the result, and verifies that
the checkout contains JSON workflows.

Set `WORKFLOW_REPO_REF` at deploy time to use a branch or tag other than
`master`:

```bash
WORKFLOW_REPO_REF=my-branch modal deploy comfyui.py
```

The workflow clone layer uses `force_build=True`, so each `modal deploy` checks
out the latest requested revision without rebuilding the expensive ComfyUI
image layers.

The ComfyUI user directory is persisted in the `comfyui-user` Volume mounted at
`/root/comfy/ComfyUI/user`. On first start, defaults are copied from an image
snapshot at `/opt/modal-comfyui-user-defaults`; existing files in the Volume
are never overwritten. Workflows, Manager settings, and other files created or
edited in the browser therefore survive scale-down and redeployment.

Because seeding does not overwrite existing files, a changed upstream workflow
with the same filename will keep the version already stored in the Volume.
Delete or rename that Volume file if the new repository version should replace
it. The `input` and `output` directories are still ephemeral.

The bundled `reverse_proxy_fix` custom node also handles reverse proxies that
decode `%2F` in `/userdata` paths. It registers slash-tolerant GET, POST, and
DELETE routes so nested workflow files can both load and save correctly.

### Plugins and Custom Nodes

Copy `plugins.example.py` to `plugins.py` and edit it to add custom node IDs or titles to be installed via `comfy-cli`.
- **Workflow Dependencies**: If you have a `workflow_api.json` in the root directory, the setup will automatically install the necessary custom nodes for that workflow.

For external Git plugins, a `requirements.txt` is installed automatically when it exists. You can provide an explicit `requirements` list, or use `"requirements": []` to skip dependency installation.

Custom nodes are cloned while the Modal image is being built. The `plugins.py`
file is copied into the image, so changing the plugin configuration invalidates
that image layer and causes a rebuild on the next deployment.

External Git plugins use shallow clones with a 180-second timeout and three
attempts, which avoids failing the entire image build on a transient GitHub
connection timeout.

#### Package management in the deployed image

The repository's local CLI environment is managed by uv through pyproject.toml
and uv.lock. The Modal image is different: ComfyUI is installed with comfy-cli,
base packages use pip, and custom-node requirements use uv. comfy-cli installs
uv at /usr/local/bin/uv, so uv is available in the running ComfyUI container.
If uv is missing, check that you are inspecting the Modal app container rather
than the reverse-proxy host or another environment.

Custom-node requirements are installed together with their transitive
dependencies. A generated constraints file pins torch, torchvision, torchaudio,
CUDA/NVIDIA libraries, numpy, OpenCV, triton, and xformers. This resolves missing
packages such as pyparsing or lazy-loader without replacing the CUDA PyTorch
build with a CPU-only version.

The image requests CUDA 13.0 explicitly because ComfyUI is installed while the
builder has no GPU and otherwise falls back to CUDA 12.6. CUDA 13.0 is required
for the optimized Comfy Kitchen paths used by `int8 convrot` models. Override
the version only when the target GPU driver is too old:

```bash
COMFY_CUDA_VERSION=12.6 modal deploy comfyui.py
```

#### ComfyUI-Manager

ComfyUI-Manager is built into the managed ComfyUI installation and is enabled
with --enable-manager. Do not add ComfyUI-Manager to plugins.py or
comfy_plugins_ext: ComfyUI deliberately blocks the custom_nodes copy to avoid
loading a duplicate Manager. The deployment launches the legacy Manager UI
explicitly with --enable-manager-legacy-ui so the Manager entry is visible in
the frontend toolbar; the installed Python package provides the backend and
cache service.

### In case of Insufficient Custom Node

Open ComfyUI manager on comfyui and click "Used in Workflow" to see which custom nodes are used in the workflow.

Add these custom nodes to `plugins.py`(be careful of node id).

## Usage

### Serve (development)

Run the following command to start ComfyUI in development mode:

```bash
modal serve comfyui.py
```

This provides a temporary, ephemeral app whose Web Function URL normally ends
with `-dev` before the region (for example,
`...--modal-comfyui-comfyui-ui-dev.us-east.modal.run`). The process must remain
running, and the URL can differ from the production URL.

### Deploy (production)

To deploy ComfyUI as a persistent app:

```bash
modal deploy comfyui.py
```

The app requests an ordered GPU fallback list by default: `L4` → `A10G` →
`T4`. Modal tries each type in order when starting a container, so a shortage
of one GPU type does not block the deployment. Override the list with a
comma-separated `MODAL_GPU`:

```bash
MODAL_GPU=L4,A10G modal deploy comfyui.py
```

`T4` is the last fallback because it has only 16 GB of memory; the MOSS
workflow can run out of memory on it. Remove `T4` with
`MODAL_GPU=L4,A10G` if that happens.

Compute placement is global by default (no `region` pin), which gives the
largest resource pool. To restrict it, set comma-separated `MODAL_REGIONS`:

```bash
MODAL_REGIONS=us,eu,ap modal deploy comfyui.py
MODAL_REGIONS=ap-northeast modal deploy comfyui.py
```

Prefer broad regions when possible: they cover a larger resource pool and
cost 1.15x the base rate; narrow regions cost 1.75x. Region selection changes
compute placement only; the public Web URL and reverse proxy remain unchanged.

Use the Web Function URL printed by `modal deploy`; it normally has no `-dev`
suffix. Once the app name, environment, class name, and web method name remain
unchanged, later `modal deploy` runs keep the same production URL. A reverse
proxy therefore does **not** need to change for every deployment.

The current deployment uses normal container startup rather than Modal memory or
GPU snapshots. Snapshots were disabled because they could leave the CUDA 13
ComfyUI web container pending without creating a runnable container. A cold
start can take roughly 60-90 seconds; after the 60-second idle window the
container scales back to zero.

### Accessing the deployed container

Modal does **not** expose public SSH for application containers, and the
ComfyUI image does not run an SSH server. Do not try to SSH to the
`.modal.run` hostname.

While a container is running, use the authenticated Modal CLI from another
terminal:

```bash
modal container list
modal shell <container-id>
```

For a single non-interactive command:

```bash
modal container exec <container-id> -- /bin/bash -lc '
  ls -la /root/comfy/ComfyUI
  find /root/comfy/ComfyUI/user/default/workflows -maxdepth 2 -type f | head
'
```

Containers scale to zero after the configured idle window, so no container may
be listed until ComfyUI is woken by a request. The container and its temporary
filesystem disappear on scale-down; use a Modal Volume for data that must
persist.

You can also start a separate shell using the app's image specification:

```bash
modal shell comfyui.py::ComfyUI.ui
```

This does not guarantee access to the same running container or its in-memory
state.

The authenticated reverse-proxy host is a separate machine and is accessed via
its own SSH configuration. It is not part of the Modal container. Do not expose
an SSH server through the reverse proxy just for routine administration; Modal
CLI access is scoped to the authenticated Workspace.

### Updating a deployed app

Edit `models.py` and/or `plugins.py` locally, then redeploy:

```bash
uv sync
modal deploy comfyui.py
```

`models.py` and `plugins.py` are gitignored, so make sure they exist on the
machine performing the deployment.

Use `modal serve comfyui.py` first when you want to validate a new model,
custom node, or workflow without replacing the production deployment.

#### Updating models

1. Add, remove, or change an entry in `models.py`.
2. Run `modal deploy comfyui.py`.
3. Wait for the model download/build step to complete.

Changing `models.py` changes the image build inputs, so the download layer is
rebuilt. Files already present in the `hf-hub-cache` Volume are reused.

Adding a file directly to the Volume is not sufficient for a model to appear in
ComfyUI's model directory: the image also contains symlinks created by the build.
Redeploy after changing `models.py`.

Inspect or clean the persistent cache with:

```bash
uv run modal volume ls hf-hub-cache
uv run modal volume rm -r hf-hub-cache <path-from-the-listing>
```

Removing an entry from `models.py` removes its symlink from the next image, but
does not automatically delete the cached payload from the Volume. Delete the
Volume path explicitly if the storage is no longer needed.

If a remote file is replaced in place while keeping the same URL and filename,
the existing cached copy is reused. Delete that cache entry before deploying:

```bash
uv run modal volume ls hf-hub-cache
uv run modal volume rm hf-hub-cache <cached-file-or-directory>
MODAL_IGNORE_CACHE=1 modal deploy comfyui.py
```

Hugging Face downloads use hub cache directories named like
`models--organization--repository`; remove the relevant directory when you need
to refresh that repository.

#### Updating custom nodes

Edit `plugins.py`, then redeploy:

```bash
modal deploy comfyui.py
```

For a plugin installed from Git, you can pin a branch or tag with `branch`. Use a
direct entry in `comfy_plugins_ext` when you need extra options:

```python
comfy_plugins_ext = [
    {
        "url": "https://github.com/owner/custom-node.git",
        "branch": "main",
        "install": "install.py",  # optional
    },
]
```

The plugin's `requirements.txt` is installed automatically when present. Use
`"requirements": []` to skip that step, or provide an explicit list of files.

If the Git repository itself has new commits but `plugins.py` has not changed,
Modal may reuse the cached clone. Build without the image cache to fetch the
current upstream revision:

```bash
MODAL_IGNORE_CACHE=1 modal deploy comfyui.py
```

`MODAL_IGNORE_CACHE=1` performs a fresh image build without replacing the shared
Modal image cache. `MODAL_FORCE_BUILD=1` is also available, but it overwrites the
cache for the rebuilt layers and can force other images to rebuild later.

The node build is deliberately non-interactive: missing optional requirement
files are skipped, while an existing requirement file that fails to install
still fails the build so the problem is visible.

#### Updating workflows

Change the workflow repository locally as needed, then deploy:

```bash
modal deploy comfyui.py
```

The clone layer is force-rebuilt on deployment, so new commits on the configured
`master` branch are picked up even when the rest of the image is cached. No
reverse-proxy or URL change is needed.

If the GitHub token is rotated, update the Modal Secret and redeploy so the
workflow clone layer can authenticate:

```bash
modal secret create --force github-secret GITHUB_TOKEN=github_pat_[...]
modal deploy comfyui.py
```

### Securing the web endpoint

Web Functions are public by default. This project enables Modal Proxy Tokens on
the ComfyUI endpoint:

```python
@modal.web_server(8000, startup_timeout=300, requires_proxy_auth=True)
def ui(self):
    ...
```

Direct requests must therefore include a Modal proxy token. Create a token in
the Modal Dashboard under **Settings → Proxy Tokens**, or with a current Modal
CLI:

```bash
modal workspace proxy-tokens create --name comfyui
```

Modal accepts either:

```bash
curl \
  -H "Modal-Key: wk-..." \
  -H "Modal-Secret: ws-..." \
  https://your-app-url.modal.run
```

or a single bearer token:

```bash
curl -H "Authorization: Bearer wk-....ws-..." \
  https://your-app-url.modal.run
```

Unauthenticated requests are rejected at Modal's edge with `401`, before a GPU
container is started. Never commit proxy tokens or expose them to browser
JavaScript.

The Modal WebSocket edge does not support the `permessage-deflate` extension.
The bundled `reverse_proxy_fix` node therefore disables aiohttp WebSocket
compression. Without this, the connection can appear to upgrade with `101` and
then immediately close with code `1000`, causing the frontend to reconnect and
never receive progress updates.

#### Nginx reverse proxy for browser access

Because normal browser navigation cannot attach Modal's headers, run an
authenticated HTTPS reverse proxy that injects them. It must also preserve
WebSocket upgrades. Keep the Modal token in a root-owned include file:

```nginx
# /etc/nginx/snippets/modal-comfyui-auth.conf
proxy_set_header Modal-Key "wk-...";
proxy_set_header Modal-Secret "ws-...";
```

```bash
sudo chown root:root /etc/nginx/snippets/modal-comfyui-auth.conf
sudo chmod 600 /etc/nginx/snippets/modal-comfyui-auth.conf
```

The proxy itself must also require authentication. Do not publish an Nginx
location that injects the Modal token for anonymous callers. Basic Auth must be
served over HTTPS; OIDC, Cloudflare Access, or another authenticated gateway can
be used instead.

```bash
sudo htpasswd -Bc /etc/nginx/comfyui.htpasswd comfy
sudo chown root:www-data /etc/nginx/comfyui.htpasswd
sudo chmod 640 /etc/nginx/comfyui.htpasswd
```

Example configuration (replace `comfy.example.com` and the upstream URL):

```nginx
map $http_upgrade $comfyui_connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 443 ssl http2;
    server_name comfy.example.com;

    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    auth_basic           "ComfyUI";
    auth_basic_user_file /etc/nginx/comfyui.htpasswd;

    client_max_body_size 4g;
    proxy_connect_timeout 75s;
    proxy_read_timeout  3600s;
    proxy_send_timeout  3600s;
    proxy_buffering off;
    proxy_request_buffering off;

    location / {
        proxy_pass https://your-app-url.modal.run;
        proxy_http_version 1.1;

        proxy_ssl_server_name on;
        proxy_ssl_name your-app-url.modal.run;
        proxy_ssl_verify on;
        proxy_ssl_verify_depth 5;
        proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;

        proxy_set_header Host your-app-url.modal.run;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $comfyui_connection_upgrade;
        include snippets/modal-comfyui-auth.conf;

        # Do not forward the browser's Basic Auth credentials to Modal.
        proxy_set_header Authorization "";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
    }
}
```

`proxy_ssl_verify_depth 5` avoids `certificate chain too long` errors from older
Nginx/OpenSSL builds when verifying Modal's certificate chain.

After changing an Nginx configuration:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Expected checks after DNS and TLS are working:

```bash
# Proxy authentication is active
curl -I https://comfy.example.com
# HTTP/2 401

# Proxy login reaches ComfyUI
curl -u comfy -I https://comfy.example.com
# HTTP/2 200

# Direct access to the Modal URL must remain blocked
curl -I https://your-app-url.modal.run
# HTTP/2 401
```

FRP is not required when Nginx runs on a host that already has public HTTP/HTTPS
access. If FRP is used, keep its dashboard private, enable authentication and
TLS, and treat it only as a transport layer rather than the authentication layer.

It is also recommended to block unauthenticated Web Functions workspace-wide
under **Settings → Environments → Block unauthenticated URLs** and to set Modal
budget limits as defense in depth.

#### Switching from `modal serve` to `modal deploy`

This requires a one-time reverse-proxy update when moving from the `-dev` URL to
the production URL. Change exactly these three upstream values in the Nginx
configuration:

```nginx
proxy_pass https://PRODUCTION_URL.modal.run;
proxy_ssl_name PRODUCTION_URL.modal.run;
proxy_set_header Host PRODUCTION_URL.modal.run;
```

Then run `sudo nginx -t && sudo systemctl reload nginx`.

The reverse proxy does **not** need adjustment for routine redeployments while
all of the following remain unchanged:

- Modal app name
- Modal environment
- class and web method names
- proxy token

Update the proxy if the URL actually printed by `modal deploy` changes. If a
proxy token is rotated, update the root-owned include file and reload Nginx;
redeploying the app is not required.

## Features

- **Auto-scaling**: Scales down to zero when not in use to save costs.
- **CUDA 13 acceleration**: Optimized Comfy Kitchen kernels for `int8 convrot` models.
- **Model Caching**: Uses Modal Volumes to cache models across runs.
- **Custom Node Management**: Integrated with `comfy-cli` for easy plugin installation.

## Contributing

Please feel free to contribute to make this project better.
Performance improvements/optimizations are very welcome.
