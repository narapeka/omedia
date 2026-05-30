# OMEDIA

OMEDIA 用 LLM 读懂混乱命名，用 TMDB 校验真实条目，再用置信度和暂存库把风险挡在媒体库外。无论是手动整理、临时批量，还是高置信监控目录，它都能把电影和剧集识别、分类、复核并发布到合适的位置，让媒体库保持准确、干净、可追踪。

## 文档

- [中文指南](frontend/src/content/user-guide.zh-CN.md)
- [English Guide](frontend/src/content/user-guide.en.md)

安装后也可以在 OMEDIA 界面的 Help 页面查看完整用户指南。

## 主要能力

- 双重识别：LLM 负责理解复杂命名和分集线索，TMDB 负责精确匹配与元数据校验，并显示识别置信度。
- 媒体库防污染：不确定或低置信度内容不会直接进入最终媒体库，可先在暂存库复核，或进入 `.unknown` 等待人工处理。
- 灵活分类规则：可按媒体类型、年份、地区、TMDB 类型、相对路径等条件，把整理结果和入库路径分流到不同目录。
- 本地目录整理：将来源目录、暂存库、最终媒体库分离，适配手动来源、临时批量来源和监控来源。
- 审核后入库：文件先进入暂存库，可复核、退回、重命名、删除，再手动或定时发布到媒体库。
- 自动化：支持监控目录自动整理，也支持按计划定时入库。
- 可追踪：记录整理、入库、跳过、失败和退回历史。
- 维护：支持配置备份/恢复、TMDB 缓存清理和历史清理。

## 快速开始

### Windows

1. 从 GitHub Releases 下载 `omedia-setup-vX.Y.Z.exe`。
2. 运行安装包。安装后会自动注册并启动 `omedia` Windows 服务。
3. 打开浏览器访问 `http://127.0.0.1:7108`。

Windows 版本默认把运行数据保存在 `%ProgramData%\omedia\data`。

### Docker Run

```powershell
docker run -p 7108:7108 -v ${PWD}\data:/data docker.io/narapeka/omedia:vX.Y.Z
```

`/data` 用于保存 OMEDIA 配置、SQLite 数据库和日志。媒体目录需要按实际路径额外挂载。

### Docker Compose

```yaml
services:
  omedia:
    image: docker.io/narapeka/omedia:vX.Y.Z
    container_name: omedia
    ports:
      - "7108:7108"
    volumes:
      - ./data:/data
      - "D:/Media:/media"
    restart: unless-stopped
```

## 第一次使用

1. 打开 **OMEDIA 界面**：`http://127.0.0.1:7108`。
2. 在 **设置** 中配置 **TMDB** 和 **LLM 提供商**。
3. 创建 **暂存库**，设置 **暂存库路径** 和 **最终媒体库路径**。
4. 创建 **来源**，设置 **来源路径**、**媒体类型** 和 **目标暂存库**。
5. 在 **整理** 中执行 **扫描**、**识别**、**审核**，并把文件整理到 **暂存库**。
6. 在 **入库** 中把 **暂存库** 内容发布到 **最终媒体库**。
7. 可选：在 **服务** 中启用 **监控自动整理** 和 **定时入库**。

## 进阶使用

### CLI 用法

不同安装方式的运行入口不同：

- **Windows 安装版**：在安装目录中运行 `omedia.exe`，或把安装目录加入 `PATH` 后直接运行 `omedia`。
- **源码仓库**：clone 仓库后，在仓库根目录使用脚本运行 CLI：

```powershell
.\scripts\cli.ps1 --help
```

查看已经配置的 **来源**：

```powershell
omedia origin --list
omedia origin --origin manual-movies
```

查看已经配置的 **暂存库**：

```powershell
omedia depot --list
omedia depot --depot movies-stage
```

整理一个已配置的 **手动来源**：

```powershell
omedia organize --origin manual-movies
```

整理一个 **临时来源**，不需要先把它保存为长期来源：

```powershell
omedia organize --source "D:\drop" --depot movies-stage --type movie --bucket first-char
```

将一个 **暂存库** 发布到最终媒体库：

```powershell
omedia transfer --depot movies-stage
```

### API 接口

适合把 OMEDIA 接入自己的脚本、自动化工具或本地运维面板。

```text
http://127.0.0.1:7108/docs
http://127.0.0.1:7108/redoc
http://127.0.0.1:7108/openapi.json
```

其中 `/docs` 是 Swagger UI，`/redoc` 是 ReDoc，`/openapi.json` 是 OpenAPI JSON 描述。

常用入口：

- `GET /api/settings/health`：查看配置和运行状态。
- `GET /api/origins`：查看来源。
- `GET /api/depots`：查看暂存库。
- `POST /api/organize/sessions`：创建整理会话。
- `POST /api/transfer/jobs`：创建入库任务。
- `GET /api/activity/events`：查看活动历史。

## 许可

OMEDIA is licensed under the GNU General Public License v3.0.
