# 发布说明

## GitHub Pages

仓库中的 Pages 工作流只发布 `frontend/` 的 Next.js 静态导出。仓库设置中需要将 Pages 的 Source 设为 **GitHub Actions**。

实验计算和 Word/PDF 报告生成仍由 FastAPI 后端完成。后端应部署到独立的 HTTPS 地址，并在仓库的 Actions variable 中设置：

```text
NEXT_PUBLIC_API_URL=https://你的后端域名
```

如果不配置后端地址，Pages 上只能浏览静态页面和仓库内已有的静态资源，不能提交数据、计算或下载动态报告。

## 本地验证

```bash
cd frontend
npm ci
NEXT_PUBLIC_BASE_PATH=/physicslab npm run build
```

静态文件会输出到 `frontend/out/`。后端仍按根目录 README 中的 FastAPI 命令单独启动。
