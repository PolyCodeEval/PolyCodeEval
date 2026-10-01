# PolyCodeEval Docker

`docker/` 位于仓库根目录，和 `datasets/` 平级。它是整个数据集的共享 Docker 运行层。所有评测在统一镜像 `polycodeeval/unified:all` 中执行，该镜像包含全部语言环境，与项目数据完全分离。

## 目录结构

```text
PolyCodeEval/
├── datasets/
│   └── {language}/{project_id}/
│       ├── src/
│       ├── tests/
│       ├── docs/
│       ├── tasks/
│       └── config.json
└── docker/
    ├── runner_lib.py
    ├── build_images.py
    ├── scripts/
    │   └── run_batch.py
    ├── images/
    │   └── unified.Dockerfile
    └── README.md
```

## 各文件作用

- `runner_lib.py`：共享工具函数，负责发现项目、读取配置、拼装 Docker 命令、管理缓存挂载
- `build_images.py`：构建统一镜像 `polycodeeval/unified:all`
- `scripts/run_batch.py`：**容器内**批量运行器，读取 manifest 顺序执行各项目测试
- `images/unified.Dockerfile`：全语言统一镜像（Python 3.11、GCC 12、Go 1.23、Java 8/11/17、Node 14/18/20/22）

## 运行方式

项目配置仍然是唯一事实源：

- `install_command`：描述依赖怎么装
- `test_command`：描述测试怎么跑
- `docker_image`：保留用于**版本推导**（如 Java JDK 版本、Node.js 版本），实际运行时统一使用 `polycodeeval/unified:all`

## 常用命令

构建统一镜像：

```bash
python docker/build_images.py
```

L0 blackbox 评测（batch 模式，所有项目在单个容器内执行）：

```bash
python scripts/run_l0_eval.py --all --solver oracle --mode blackbox --batch
```

L0 普通模式（每个 task 单独容器，并行 workers）：

```bash
python scripts/run_l0_eval.py --all --solver oracle --mode blackbox --workers 4
```

L1/L2/L3 评测（默认同时运行白盒+黑盒测试）：

```bash
python scripts/run_l1_eval.py --language python --solver oracle
python scripts/run_l2_eval.py --language go --solver oracle
python scripts/run_l3_eval.py --language java --solver oracle

# 只运行白盒测试（复现旧行为）
python scripts/run_l3_eval.py --language python --solver oracle --tests whitebox

# 只运行黑盒测试
python scripts/run_l3_eval.py --language go --solver oracle --tests blackbox
```

## 数据集同步

`datasets/` 目录不纳入 git，通过 DockerHub 镜像分发。使用 `docker/sync_datasets.py` 进行同步。

### 拉取数据集（新机器 / 首次使用）

```bash
# 拉取全部语言
python docker/sync_datasets.py pull --all

# 只拉取需要的语言
python docker/sync_datasets.py pull --language go
python docker/sync_datasets.py pull --language python
```

拉取后 `datasets/{language}/` 和 `docs/` 会自动写入本地。

### 推送数据集（数据有更新时）

```bash
docker login   # 需要 err404notfound 账号权限

# 推送全部语言（默认使用 http://127.0.0.1:7897 代理）
python docker/sync_datasets.py push --all

# 指定代理地址
python docker/sync_datasets.py push --all --proxy http://127.0.0.1:1087

# 不需要代理（网络可直连 DockerHub）
python docker/sync_datasets.py push --all --no-proxy

# 推送单语言
python docker/sync_datasets.py push --language javascript
```

推送使用 `docker buildx` 构建 linux/amd64 + linux/arm64 多架构镜像。由于 buildx 的 buildkit 不继承 Docker Desktop 的代理设置，脚本会自动设置 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量（默认 `http://127.0.0.1:7897`）。如果你的代理端口不同，用 `--proxy` 指定；如果网络可直连，用 `--no-proxy` 跳过。

### 可用镜像

| 镜像 | 内容 |
|:---|:---|
| `err404notfound/polycodeeval-datasets-python:latest` | Python 数据集 + docs |
| `err404notfound/polycodeeval-datasets-go:latest` | Go 数据集 + docs |
| `err404notfound/polycodeeval-datasets-java:latest` | Java 数据集 + docs |
| `err404notfound/polycodeeval-datasets-cpp:latest` | C++ 数据集 + docs |
| `err404notfound/polycodeeval-datasets-javascript:latest` | JavaScript/TypeScript 数据集 + docs（不含 node_modules） |

### 镜像构建细节

每个语言对应一个 `docker/datasets/Dockerfile.{language}`，使用 `FROM scratch` 最小化镜像层。构建时 build context 为仓库根目录，`.dockerignore` 排除 `node_modules`、`__pycache__` 等构建产物。

JS 项目的 `node_modules` 不打入镜像，评测时通过 `install_command`（如 `cd src && npm install`）在容器内重新安装。
