[English](README.md) | 简体中文

# modal-comfyui

在 Modal 上运行 ComfyUI，支持自动扩缩容、GPU 快照和模型管理。

适合测试 wan2.2 或其他视频生成模型。

## 前置条件

- 一个 Modal 账号
- 已安装 Python
- 已安装 `uv`

## 安装

1. 克隆本仓库。
2. 安装 Modal 客户端：

   ```bash
   uv sync
   ```

3. 登录 Modal：

   ```bash
   modal setup
   ```

4. 创建 Hugging Face 和 CivitAI 使用的 Secret（可选，但推荐）：

   ```bash
   modal secret create huggingface-secret \
     HF_TOKEN=hf_[你的 Hugging Face Token] \
     CIVITAI_TOKEN=[你的 CivitAI Token，如需要]
   ```

5. 创建用于克隆私有工作流仓库的 GitHub Secret：

   ```bash
   modal secret create github-secret GITHUB_TOKEN=github_pat_[...]
   ```

   如果使用 Fine-grained PAT，需要给 `SurpassHR/ComfyUI-workflows`
   授予 **Contents: Read** 权限。该 Token 只会用于镜像构建时的克隆步骤，
   不会出现在运行中的 ComfyUI 容器里。

## 配置

### 模型

复制 `models.example.py` 为 `models.py`，然后编辑文件管理模型：

- Hugging Face 模型使用 `repo_id` 和 `filename`。
- 外部模型（例如 CivitAI）使用 `models_ext` 和直链 `url`。

模型会在构建 Modal 镜像时下载，并软链接到指定的 `model_dir`。
模型数据保存在 `hf-hub-cache` Volume 中，因此重新构建镜像时通常不会
重新下载未变化的文件。

`model_dir` 支持两种写法：

- **相对路径**（推荐用于标准 ComfyUI 目录）：相对于
  `/root/comfy/ComfyUI/models/`。例如 `"checkpoints"` 对应
  `/root/comfy/ComfyUI/models/checkpoints`。
- **绝对路径**：按原样使用。适用于 ComfyUI 模型目录之外的路径，例如某个
  自定义节点自己的模型目录。

可参考 `models.example.py`。

### 工作流

ComfyUI 的网页工作流目录是：

```text
/root/comfy/ComfyUI/user/default/workflows
```

本项目会克隆
`https://github.com/SurpassHR/ComfyUI-workflows.git`，并将仓库内容
**直接复制**到上面的工作流目录。ComfyUI 的 Workflow 侧边栏不会多出一层
仓库名目录。

该仓库是私有的，所以必须配置 `github-secret`，其中包含
`GITHUB_TOKEN`。构建时会通过临时 Git credential helper 拉取仓库，
移除 `.git`，并确认仓库中存在 JSON 工作流。

部署时可以通过 `WORKFLOW_REPO_REF` 使用 `master` 之外的分支或 Tag：

```bash
WORKFLOW_REPO_REF=my-branch modal deploy comfyui.py
```

工作流克隆层使用 `force_build=True`，因此每次 `modal deploy`
都会重新拉取指定 revision，但不会重建昂贵的 ComfyUI 镜像层。

只有仓库中的工作流会被持久保证。在 ComfyUI 网页中新建或修改的工作流保存在
容器镜像文件系统中，缩容或重新部署后会丢失，除非后续将用户目录迁移到
Modal Volume。

内置的 `reverse_proxy_fix` 自定义节点还会处理反向代理解码
`/userdata` 路径中 `%2F` 的问题。它会注册支持斜杠的 GET、
POST、DELETE 路由，使嵌套目录中的工作流能够正常加载和保存。

### 插件和自定义节点

复制 `plugins.example.py` 为 `plugins.py`，添加要通过
`comfy-cli` 安装的自定义节点 ID 或名称。

- **工作流依赖**：如果根目录存在 `workflow_api.json`，部署时会自动
  安装该工作流需要的自定义节点。

对于外部 Git 插件，只要仓库中存在 `requirements.txt`，就会自动安装。
也可以显式提供 `requirements` 列表，或使用
`"requirements": []` 跳过依赖安装。

自定义节点会在 Modal 镜像构建阶段克隆。`plugins.py` 会被复制进镜像，
因此修改插件配置会使对应镜像层失效，并在下次部署时重建。

外部 Git 插件使用浅克隆，单次最多 180 秒，最多尝试 3 次。这样可以避免一次
临时 GitHub 网络超时导致整个镜像构建失败。

#### 部署镜像中的包管理

本仓库的本地 CLI 环境使用 uv，由 pyproject.toml 和 uv.lock 管理。Modal 镜像
则使用不同的组合：ComfyUI 由 comfy-cli 安装，基础依赖使用 pip，自定义节点
依赖使用 uv。comfy-cli 会安装 uv 到 /usr/local/bin/uv，因此运行中的 ComfyUI
容器里有 uv。如果看不到 uv，请确认检查的是 Modal App 容器，而不是反向代理
服务器或其他环境。

自定义节点依赖会连同传递依赖一起安装。构建时会生成 constraints 文件，固定
torch、torchvision、torchaudio、CUDA/NVIDIA 库、numpy、OpenCV、triton 和
xformers 的版本。这样既能补齐 pyparsing、lazy-loader 等缺失依赖，又不会把
CUDA PyTorch 替换成 CPU 版本。

镜像会显式请求 CUDA 13.0，因为构建阶段没有 GPU，comfy-cli 默认会回退到
CUDA 12.6。`int8 convrot` 模型使用的 Comfy Kitchen 优化路径需要 CUDA 13.0。
只有目标 GPU 驱动过旧时才需要覆盖版本：

```bash
COMFY_CUDA_VERSION=12.6 modal deploy comfyui.py
```

#### ComfyUI-Manager

ComfyUI-Manager 已内置于受管理的 ComfyUI 安装中，并通过 --enable-manager
启用。不要将 ComfyUI-Manager 加入 plugins.py 或 comfy_plugins_ext；ComfyUI
会主动阻止 custom_nodes 中的重复 Manager。已安装的 Python 包仍会提供 Manager
界面和缓存服务。

### 缺失自定义节点时

打开 ComfyUI Manager，点击 **Used in Workflow**，查看当前工作流使用了哪些
自定义节点。

将这些节点加入 `plugins.py`，注意填写 ComfyUI Registry 中的节点 ID，
而不是显示名称。

## 使用

### 开发模式

使用以下命令启动开发环境：

```bash
modal serve comfyui.py
```

这会创建一个临时的 ephemeral App，其 Web Function URL 通常在区域前带有
`-dev`，例如：

```text
...--modal-comfyui-comfyui-ui-dev.us-east.modal.run
```

该进程必须保持运行，而且地址可能与生产 URL 不同。

### 生产部署

部署一个持久运行的 ComfyUI App：

```bash
modal deploy comfyui.py
```

请使用 `modal deploy` 输出的 Web Function URL。正式地址通常不带
`-dev`。只要 App 名称、环境、类名和 Web 方法名不变，后续部署会保持
同一个生产 URL，因此反向代理**不需要**每次部署都修改。

当前部署使用普通容器启动，不启用 Modal 的内存或 GPU 快照。快照曾导致
CUDA 13 的 ComfyUI Web 容器一直处于 pending 状态，无法创建可运行容器。
冷启动大约需要 60–90 秒；空闲 60 秒后容器会缩容到零。

### 访问已部署的容器

Modal **不会**为普通应用容器开放公网 SSH，ComfyUI 镜像中也没有运行 SSH
Server。不要尝试直接 SSH 到 `.modal.run` 地址。

容器正在运行时，可以在另一个终端使用已认证的 Modal CLI：

```bash
modal container list
modal shell <container-id>
```

执行单条非交互命令：

```bash
modal container exec <container-id> -- /bin/bash -lc '
  ls -la /root/comfy/ComfyUI
  find /root/comfy/ComfyUI/user/default/workflows -maxdepth 2 -type f | head
'
```

容器会在配置的空闲时间后缩容到零，因此请求唤醒 ComfyUI 之前，
`modal container list` 可能看不到容器。缩容后容器及其临时文件系统会
消失，需要持久化的数据应放入 Modal Volume。

也可以用 App 的镜像规格启动一个独立的 Shell：

```bash
modal shell comfyui.py::ComfyUI.ui
```

这**不保证**进入当前正在运行的同一个容器，也不保证能看到该容器的内存状态。

认证后的反向代理服务器是另一台独立机器，需要使用它自己的 SSH 配置登录，
不属于 Modal 容器。不要为了日常管理通过反向代理暴露 SSH Server；Modal CLI
访问由已认证的 Workspace 管理。

### 更新已部署应用

在本地修改 `models.py` 和/或 `plugins.py` 后重新部署：

```bash
uv sync
modal deploy comfyui.py
```

`models.py` 和 `plugins.py` 已被 gitignore，执行部署的机器上必须
存在这两个文件。

如果只想验证新模型、自定义节点或工作流，而不替换生产部署，可以先运行：

```bash
modal serve comfyui.py
```

#### 更新模型

1. 在 `models.py` 中添加、删除或修改模型条目。
2. 运行 `modal deploy comfyui.py`。
3. 等待模型下载和镜像构建完成。

修改 `models.py` 会改变镜像构建输入，因此下载层会重新构建。
`hf-hub-cache` Volume 中已经存在的文件会被复用。

只把文件直接上传到 Volume 并不足以让模型出现在 ComfyUI 的模型目录中，因为
镜像构建时还会创建软链接。修改模型配置后必须重新部署。

查看或清理持久缓存：

```bash
uv run modal volume ls hf-hub-cache
uv run modal volume rm -r hf-hub-cache <列表中的路径>
```

从 `models.py` 删除模型后，下次构建不会再创建对应软链接，但 Volume
中的缓存文件不会自动删除。如果不再需要该文件，需要手动删除对应路径。

如果远程文件内容变化，但 URL 和文件名不变，已有缓存仍会被复用。需要先删除
对应缓存，再部署：

```bash
uv run modal volume ls hf-hub-cache
uv run modal volume rm hf-hub-cache <缓存文件或目录>
MODAL_IGNORE_CACHE=1 modal deploy comfyui.py
```

Hugging Face 缓存目录通常类似
`models--organization--repository`；需要刷新某个仓库时，删除对应目录。

#### 更新自定义节点

修改 `plugins.py` 后重新部署：

```bash
modal deploy comfyui.py
```

通过 Git 安装的插件可以使用 `branch` 固定分支或 Tag。需要更多选项时，
可以直接在 `comfy_plugins_ext` 中写完整配置：

```python
comfy_plugins_ext = [
    {
        "url": "https://github.com/owner/custom-node.git",
        "branch": "main",
        "install": "install.py",  # 可选
    },
]
```

插件存在 `requirements.txt` 时会自动安装。可用
`"requirements": []` 跳过依赖安装，或显式指定要安装的文件列表。

如果 Git 仓库有了新提交，但 `plugins.py` 没有变化，Modal 可能会复用
缓存的克隆结果。此时可以绕过镜像缓存，获取最新上游版本：

```bash
MODAL_IGNORE_CACHE=1 modal deploy comfyui.py
```

`MODAL_IGNORE_CACHE=1` 会重新构建镜像，但不会替换共享的 Modal 镜像
缓存。也可以使用 `MODAL_FORCE_BUILD=1`，但它会覆盖被重建层的缓存，
可能导致其他镜像之后也被迫重建。

节点构建是非交互式的：可选 requirements 文件不存在时会跳过；如果文件存在但
安装失败，构建仍会失败，以便暴露问题。

#### 更新工作流

在本地修改工作流仓库并提交后，执行：

```bash
modal deploy comfyui.py
```

部署时会强制重建工作流克隆层，因此即使其他镜像层命中缓存，也会获取配置分支上
的最新提交。不需要修改反向代理或 URL。

如果轮换了 GitHub Token，需要先更新 Modal Secret，再重新部署，让工作流克隆层
重新完成认证：

```bash
modal secret create --force github-secret GITHUB_TOKEN=github_pat_[...]
modal deploy comfyui.py
```

### 保护 Web 端点

Web Functions 默认是公开的。本项目在 ComfyUI 端点上启用了 Modal Proxy Token：

```python
@modal.web_server(8000, startup_timeout=300, requires_proxy_auth=True)
def ui(self):
    ...
```

因此直接请求时必须携带 Modal Proxy Token。可以在 Modal Dashboard 的
**Settings → Proxy Tokens** 中创建，也可以使用较新的 Modal CLI：

```bash
modal workspace proxy-tokens create --name comfyui
```

Modal 接受两种认证方式：

```bash
curl \
  -H "Modal-Key: wk-..." \
  -H "Modal-Secret: ws-..." \
  https://your-app-url.modal.run
```

或使用单个 Bearer Token：

```bash
curl -H "Authorization: Bearer wk-....ws-..." \
  https://your-app-url.modal.run
```

未认证请求会在 Modal 边缘直接返回 `401`，不会启动 GPU 容器。不要把
Proxy Token 提交到仓库，也不要暴露给浏览器 JavaScript。

Modal 的 WebSocket 边缘不支持 `permessage-deflate` 扩展。内置的
`reverse_proxy_fix` 节点会禁用 aiohttp WebSocket 压缩。否则连接可能显示为
`101` 已升级，随后立即以 `1000` 关闭，导致前端反复重连且收不到进度更新。

#### 使用 Nginx 反向代理提供浏览器访问

普通浏览器导航无法自动附加 Modal 所需的 Header，因此需要使用一个经过认证的
HTTPS 反向代理来注入 Header，并保留 WebSocket Upgrade。

将 Modal Token 放在仅 root 可读的 include 文件中：

```nginx
# /etc/nginx/snippets/modal-comfyui-auth.conf
proxy_set_header Modal-Key "wk-...";
proxy_set_header Modal-Secret "ws-...";
```

```bash
sudo chown root:root /etc/nginx/snippets/modal-comfyui-auth.conf
sudo chmod 600 /etc/nginx/snippets/modal-comfyui-auth.conf
```

反向代理自身也必须要求认证。不要公开一个会给匿名访问者自动注入 Modal Token
的 Nginx location。Basic Auth 必须通过 HTTPS 提供；也可以使用 OIDC、
Cloudflare Access 或其他认证网关替代。

```bash
sudo htpasswd -Bc /etc/nginx/comfyui.htpasswd comfy
sudo chown root:www-data /etc/nginx/comfyui.htpasswd
sudo chmod 640 /etc/nginx/comfyui.htpasswd
```

示例配置（替换 `comfy.example.com` 和上游 URL）：

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

        # 不要把浏览器的 Basic Auth Header 转发给 Modal。
        proxy_set_header Authorization "";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
    }
}
```

`proxy_ssl_verify_depth 5` 用于避免较旧的 Nginx/OpenSSL 在验证
Modal 证书链时出现 `certificate chain too long`。

修改 Nginx 配置后执行：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

DNS 和 TLS 正常后，预期检查结果：

```bash
# 代理认证生效
curl -I https://comfy.example.com
# HTTP/2 401

# 通过代理登录后访问 ComfyUI
curl -u comfy -I https://comfy.example.com
# HTTP/2 200

# 原始 Modal 地址仍应被阻止
curl -I https://your-app-url.modal.run
# HTTP/2 401
```

如果 Nginx 所在主机已经有公网 HTTP/HTTPS 访问，则不需要 FRP。如果使用 FRP，
应将 Dashboard 仅监听本机，启用认证和 TLS，并且只把 FRP 当作传输层，不要
把它当作认证层。

还建议在 **Settings → Environments → Block unauthenticated URLs** 中禁止
未认证 URL，并设置 Modal 预算上限，作为额外的纵深防御。

#### 从 `modal serve` 切换到 `modal deploy`

从 `-dev` 地址切换到生产地址时，需要一次性更新反向代理。修改 Nginx 中
以下三个上游值：

```nginx
proxy_pass https://PRODUCTION_URL.modal.run;
proxy_ssl_name PRODUCTION_URL.modal.run;
proxy_set_header Host PRODUCTION_URL.modal.run;
```

然后执行：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

只要以下内容不变，日常重新部署**不需要**修改反向代理：

- Modal App 名称
- Modal 环境
- 类和 Web 方法名
- Proxy Token

如果 `modal deploy` 实际输出的 URL 发生变化，才需要更新代理。如果轮换
Proxy Token，只需要更新 root 权限的 include 文件并重载 Nginx，不需要重新部署
App。

## 功能

- **自动扩缩容**：空闲时缩容到零，减少费用。
- **CUDA 13 加速**：为 `int8 convrot` 模型启用优化的 Comfy Kitchen 内核。
- **模型缓存**：使用 Modal Volume 在多次运行之间缓存模型。
- **自定义节点管理**：集成 `comfy-cli`，方便安装插件。

## 贡献

欢迎贡献，也欢迎性能优化建议。
