# VideoGrab · 视频去水印批量下载（Web 应用）

> 全栈 Web 应用：粘贴视频链接 → 自动解析无水印直链 → 单条 / 批量 ZIP 下载。
> 支持抖音 / 快手 / 小红书 / B 站 / 微博 / YouTube 等平台（其余走 yt-dlp 兜底）。

## ✨ 功能

- 多平台解析：抖音 / 快手 / 小红书 / B 站 / 微博 / YouTube / 通用 (yt-dlp)
- 抖音走 iesdouyin 接口拿无水印源
- 批量 ZIP 打包下载
- 内置限流（每个 IP 解析 30/分钟、下载 60/分钟、批量 15/分钟）
- 可选 API Key 鉴权（环境变量 `API_KEY`）
- 自动 `/robots.txt` + `/tos` 使用条款
- 现代深色 UI，移动端可用
- Docker / Render / Fly.io / GitHub Actions 多种部署方式

## 📁 目录结构

```
video-downloader/
├── backend/                  FastAPI 后端
│   ├── main.py               API 入口（含限流、ToS、robots、中间件）
│   ├── requirements.txt
│   ├── .env.example          环境变量模板
│   └── parsers/              平台解析器（可插拔）
│       ├── base.py / registry.py
│       ├── douyin.py / kuaishou.py / xiaohongshu.py
│       ├── bilibili.py / weibo.py / generic.py
├── frontend/                 静态前端
│   ├── index.html / app.js / style.css
├── deploy/                   部署文件
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── nginx.conf
│   ├── render.yaml           Render.com 一键
│   └── fly.toml              Fly.io 一键
├── .github/workflows/        GitHub Actions 自动部署
└── README.md
```

## 🚀 本地运行（30 秒上手）

```bash
cd video-downloader/backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
# 打开 http://localhost:8000
```

## ☁️ 部署到网站（5 种方式，挑一个）

### 方式 1：Render.com（推荐 · 免费 · 5 分钟搞定）

1. 把仓库推到 GitHub
2. 登录 [render.com](https://render.com)，点 New + Blueprint
3. 选你的 GitHub 仓库，Render 自动识别 `deploy/render.yaml`
4. 点 Apply，自动构建 + 部署
5. 免费 plan 每月 750 小时，闲置 15 分钟后会休眠

### 方式 2：Fly.io（免费 tier · 全球节点）

```bash
# 安装 flyctl（Windows: scoop install flyctl）
fly auth signup
fly launch --copy-config   # 会自动用 deploy/fly.toml
fly deploy
```

### 方式 3：Railway.app（$5 免费额度）

1. 登录 [railway.app](https://railway.app)
2. New Project → Deploy from GitHub repo
3. 选你的仓库，自动识别 Dockerfile

### 方式 4：Docker（自己的 VPS / NAS）

```bash
cd video-downloader/deploy
docker compose up -d --build
# 应用跑在 8000，Nginx 反代跑在 8080
```

外网暴露（Nginx + Let's Encrypt）：
```nginx
server {
  listen 443 ssl http2;
  server_name your-domain.com;
  ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
  location / { proxy_pass http://127.0.0.1:8080; proxy_set_header Host $host; }
}
```

### 方式 5：ngrok（仅本地调试 / 分享）

```bash
ngrok http 8000
# 拿到一个 https://xxx.ngrok-free.dev URL
# 注意：免费 plan 限制 1GB/月，且 URL 每次启动会变
```

## 🔐 安全配置（生产建议）

`backend/.env`：
```env
API_KEY=your-strong-secret-here      # 启用鉴权
PUBLIC_BASE_URL=https://your-domain.com
ALLOW_ORIGINS=https://your-domain.com
LOG_LEVEL=WARNING
```

启用 API Key 后，前端调用需要加 `X-API-Key` 头或 `?api_key=` 参数。

## 🔌 API 文档

启动后访问 `http://your-host:8000/docs` 查看 OpenAPI。

主要接口：
- `POST /api/parse` — 单次最多 20 个链接，返回元信息 + 无水印直链
- `GET  /api/download?url=...` — 流式下载单条
- `POST /api/batch-download` — 打包 ZIP
- `GET  /api/platforms` — 支持的平台
- `GET  /robots.txt`、`GET /tos` — 站点规范

## ⚠️ 注意事项

- 抖音 / 小红书 IP 段敏感，建议海外节点或住宅 IP
- 部署后请立即在 `/tos` 页面挂上你的联系方式与举报邮箱
- 平台 ToS 经常变动，`yt-dlp` 升级即可：`pip install -U yt-dlp`
- 大量并发 / 滥用会触发上游风控，建议开启 API Key + 限流

## ⚖️ 免责声明

本项目仅供学习与个人备份。视频版权归原作者及平台所有。
下载内容的法律责任由使用者承担，运营者保留随时终止服务的权利。

## 🤝 二次开发

- 新增平台：在 `backend/parsers/` 加 `YourPlatform(BaseParser)`，到 `registry.py` 注册
- 改 UI：编辑 `frontend/` 三个文件
- 加鉴权：设置 `API_KEY` 环境变量即可
