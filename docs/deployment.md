# 发布说明

## GitHub Pages

仓库中的 Pages 工作流只发布 `frontend/` 的 Next.js 静态导出。仓库设置中需要将 Pages 的 Source 设为 **GitHub Actions**。

实验计算和 Word/PDF 报告生成仍由 FastAPI 后端完成。后端应部署到独立的 HTTPS 地址，并在仓库的 Actions variable 中设置：

```text
NEXT_PUBLIC_API_URL=https://你的后端域名
```

如果不配置后端地址，Pages 上只能浏览静态页面和仓库内已有的静态资源，不能提交数据、计算或下载动态报告。

## Cloudflare Pages + Containers

本项目已经提供 Cloudflare Container Worker 配置：

- `backend/Dockerfile`：打包 FastAPI、NumPy、SciPy、Matplotlib 和报告生成依赖。
- `cloudflare/wrangler.jsonc`：声明 Container、Durable Object 绑定和镜像路径。
- `cloudflare/src/index.ts`：将 API 请求转发到容器的 8001 端口。

在仓库根目录安装 Wrangler 并部署后端：

```bash
npm install --prefix cloudflare
npx wrangler deploy --config cloudflare/wrangler.jsonc
```

Cloudflare Containers 需要 Workers Paid 计划。部署前，如果使用自定义 Pages 域名，请把 `cloudflare/wrangler.jsonc` 中的 `image_vars.CORS_ORIGINS` 改为实际 Pages 源；默认值已配置为本项目的 GitHub Pages 地址。部署后，将 `https://<你的-worker>.workers.dev` 作为 Cloudflare Pages 的 `NEXT_PUBLIC_API_URL`。Cloudflare Pages 的构建根目录设为 `frontend`，构建命令为 `npm ci && npm run build`，输出目录为 `out`；Cloudflare Pages 上应将 `NEXT_PUBLIC_BASE_PATH` 留空。

部署后先检查 `https://<你的-worker>.workers.dev/health`，再从 Pages 页面验证 `/api/experiments`、数据处理和报告下载。

## 本地验证

```bash
cd frontend
npm ci
NEXT_PUBLIC_BASE_PATH=/physicslab npm run build
```

静态文件会输出到 `frontend/out/`。后端仍按根目录 README 中的 FastAPI 命令单独启动。
