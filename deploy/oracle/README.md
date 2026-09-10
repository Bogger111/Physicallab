# Oracle Always Free 部署

该方案把前端静态导出和 FastAPI 后端放在同一台 Oracle Always Free VM 上：

- `frontend`：Nginx 提供 Next.js 静态文件，并反向代理 `/api/`
- `backend`：FastAPI + NumPy/SciPy/Matplotlib/Word/PDF 依赖
- 两个服务都配置 `restart: unless-stopped`
- 浏览器使用同源 API，不需要把后端地址写进前端

## 云主机首次准备

在 Oracle VM（Ubuntu 22.04/24.04）执行：

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
newgrp docker
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw --force enable
```

Oracle 控制台的 VCN Security List 还要放行 TCP `80`（来源 `0.0.0.0/0`）。

## 部署

```bash
git clone <你的 GitHub 仓库地址> physicslab
cd physicslab/deploy/oracle
chmod +x deploy.sh
./deploy.sh
```

然后访问：

```text
http://<Oracle 公网 IP>/
http://<Oracle 公网 IP>/health
```

## HTTPS（推荐）

仅用公网 IP 是 HTTP。要让 GitHub Pages 通过 HTTPS 调用后端，需要一个域名：

1. 把域名 A 记录指向 Oracle 公网 IP；
2. 将 `nginx.conf` 的 Nginx 改为 Caddy，或在 Nginx 前配置 Let's Encrypt；
3. 把 GitHub Actions variable `NEXT_PUBLIC_API_URL` 改为后端 HTTPS 域名，并重新发布前端。

如果前后端都部署在此 VM 上，则不需要配置 `NEXT_PUBLIC_API_URL`，访问同一个域名即可。
