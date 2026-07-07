# VideoGrab · 视频去水印批量下载（Web 应用）

> 一个可直接部署到网站的全栈应用：粘贴视频链接 → 自动解析无水印直链 → 单条 / 批量 ZIP 下载。
> 支持抖音、快手、小红书、B 站、微博、YouTube 等主流平台（其余平台走 yt-dlp 兜底）。

## ✨ 功能特性
- 🪄 多平台解析：抖音 / 快手 / 小红书 / B 站 / 微博 / YouTube / 通用 (yt-dlp)
- 🚫 去水印：抖音走 iesdouyin 接口拿到无水印源
- 📦 批量下载：一键打包 ZIP，前端直接保存
- 🎨 现代 UI：深色玻璃拟态、响应式、移动端可用
- 🐳 一键部署：自带 Dockerfile + docker-compose + Nginx 反代模板
- 🔌 OpenAPI 文档：内置 /docs，可二次集成

## 📁 项目结构
```
video-downloader/
├── backend/                  # FastAPI 后端
│   ├── main.py               # API 入口
│   ├── requirements.txt      # Python 依赖
│   └── parsers/              # 各平台解析器
│       ├── base.py           # 统一接口 + 数据结构
│       ├── registry.py       # 解析器注册中心
│       ├── douyin.py         # 抖音（无水印）
│       ├── kuaishou.py       # 快手
│       ├── xiaohongshu.py    # 小红书
│       ├── bilibili.py       # B 站
│       ├── weibo.py          # 微博
│       └── generic.py        # yt-dlp 兜底
├── frontend/                 # 静态前端
│   ├── index.html            # 主页
│   ├── app.js                # 交互逻辑
│   └── style.css             # 样式
└── deploy/                   # 部署文件
    ├── Dockerfile
    ├── docker-compose.yml
    └── nginx.conf
```

## 🚀 快速开始

### 方式一：Docker Compose（推荐）
```bash
cd video-downloader/deploy
docker compose up -d --build
# 访问 http://localhost:8000（直连）或 http://localhost:8080（经 Nginx）
```

### 方式二：直接运行
```bash
cd video-downloader/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
# 访问 http://localhost:8000
```

## 🔌 API 文档

启动后访问 http://localhost:8000/docs 查看完整 OpenAPI 文档。

### POST /api/parse
解析一个或多个链接，返回视频元信息 + 无水印直链。
```bash
curl -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d "{\"urls\":[\"https://v.douyin.com/xxxxx/\"]}"
```

### GET /api/download?url=...
根据原始链接解析并流式下载单个视频。
```bash
curl -L -o video.mp4 "http://localhost:8000/api/download?url=https%3A%2F%2Fv.douyin.com%2Fxxxxx%2F"
```

### POST /api/batch-download
把多条视频打包为 ZIP 返回。
```bash
curl -X POST http://localhost:8000/api/batch-download \
  -H "Content-Type: application/json" \
  -d "{\"items\":[{\"url\":\"...\",\"title\":\"a\"},{\"url\":\"...\",\"title\":\"b\"}]}" \
  -o videos.zip
```

## 🌐 公网部署建议
- 用 Nginx / Caddy 反向代理，开启 HTTPS（Let's Encrypt）
- 抖音 / 小红书等平台对 IP 段敏感，建议使用住宅 IP 的 VPS，或搭配 IP 轮换代理
- 如遇 403 / 风控，更新 yt-dlp 到最新版：pip install -U yt-dlp

## ⚖️ 免责声明
本项目仅用于学习与个人备份，请勿用于商业用途或侵犯他人版权。
所有视频版权归原作者及平台所有，下载内容的责任由使用者承担。

## 🤝 二次开发
- 新增平台：在 backend/parsers/ 添加 YourPlatform(BaseParser)，再到 registry.py 注册即可
- 修改 UI：编辑 frontend/index.html / app.js / style.css
- 鉴权 / 限流：可在 main.py 增加中间件或 API Key
