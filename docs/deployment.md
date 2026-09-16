# 发布说明

当前公开测试版本为 `2.0.0-beta.1`。测试站必须保留全局 Beta 提示，不应将合成 fixture 测试描述为真实实验验证。发布后需要依次检查健康端点、实验目录、数据计算、OCR 人工确认和 PDF 报告下载。

## GitHub Pages

仓库中的 Pages 工作流只发布 `frontend/` 的 Next.js 静态导出。仓库设置中需要将 Pages 的 Source 设为 **GitHub Actions**。

实验计算和 Word/PDF 报告生成仍由 FastAPI 后端完成。后端应部署到独立的 HTTPS 地址，并在仓库的 Actions variable 中设置：

```text
NEXT_PUBLIC_API_URL=https://你的后端域名
```

如果不配置后端地址，Pages 上只能浏览静态页面和仓库内已有的静态资源，不能提交数据、计算或下载动态报告。

## Oracle Always Free（推荐的零月费方案）

项目提供 `deploy/oracle/` 的同源 Docker Compose 部署方案，适用于 Oracle Cloud Always Free VM：

- `backend` 运行 FastAPI、NumPy、SciPy、Matplotlib 和报告生成依赖；
- `frontend` 构建 Next.js 静态页面，由 Nginx 提供并反向代理 `/api/`；
- 两个容器均配置 `restart: unless-stopped`，后端不因空闲进入冷启动；
- 详细准备、VCN 放行和部署命令见 `deploy/oracle/README.md`。

该方案使用同源 API，前端生产构建时 `NEXT_PUBLIC_API_URL` 为空；本地开发仍使用 `.env.local` 指向 `http://localhost:8001`。

## Cloudflare Pages + Containers

本项目已经提供 Cloudflare Container Worker 配置：

- `backend/Dockerfile`：打包 FastAPI、NumPy、SciPy、Matplotlib 和报告生成依赖。
- `cloudflare/wrangler.jsonc`：声明 Container、Durable Object 绑定和镜像路径。
- `cloudflare/src/index.ts`：将 API 请求转发到容器的 8001 端口。

在仓库根目录安装 Wrangler 并部署后端：

```bash
npm install --prefix cloudflare
npm run --prefix cloudflare deploy
```

Cloudflare Containers 需要 Workers Paid 计划。部署前，如果使用自定义 Pages 域名，请把 `cloudflare/wrangler.jsonc` 中的 `image_vars.CORS_ORIGINS` 改为实际 Pages 源；默认值已配置为本项目的 GitHub Pages 地址。部署后，将 `https://<你的-worker>.workers.dev` 作为 Cloudflare Pages 的 `NEXT_PUBLIC_API_URL`。Cloudflare Pages 的构建根目录设为 `frontend`，构建命令为 `npm ci && npm run build`，输出目录为 `out`；Cloudflare Pages 上应将 `NEXT_PUBLIC_BASE_PATH` 留空。

部署后先检查 `https://<你的-worker>.workers.dev/health`，再从 Pages 页面验证 `/api/experiments`、数据处理和报告下载。

PhysKiller 2.0 的匿名分析和 OCR 反馈默认写入容器临时目录中的 SQLite。若需要在自托管后端保留统计，应通过环境变量 `PHYSICSLAB_TELEMETRY_DB` 指向持久卷；不要把该数据库提交到 Git。默认 OCR provider 是 RapidOCR，只有在镜像额外安装 PaddleOCR 后才设置 `PHYSICSLAB_OCR_PROVIDER=paddleocr`。

## 本地验证

```bash
cd frontend
npm ci
NEXT_PUBLIC_BASE_PATH=/physicslab npm run build
```

静态文件会输出到 `frontend/out/`。后端仍按根目录 README 中的 FastAPI 命令单独启动。
