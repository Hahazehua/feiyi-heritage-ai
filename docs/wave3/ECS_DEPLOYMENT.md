# ECS 部署指南 — HAHA｜飞颐礼遇

把本项目从 Streamlit Community Cloud 迁移到赛事发放的 ECS 服务器。
运行方式：Docker + Nginx 反向代理，直接用公网 IP 访问（`http://<你的服务器IP>/`）。

服务器有效期为发放日起两个月，到期后应用会随实例一起下线。**最终提交材料里请同时保留 Streamlit Cloud 地址作为备用入口。**

---

## 0. 先做这一步：改掉初始密码

初始 root 密码是通过邮件/聊天明文下发的，等于已经泄露。公网上的 SSH 端口每天会被扫描上千次，弱口令 + root 直登是最常见的失陷方式。**在做任何其他事之前先改密码。**

```bash
ssh root@<你的服务器IP>
# 输入初始密码后：
passwd            # 设置一个长随机密码
```

更好的做法是改用密钥登录（在**本地**机器上执行第一条命令）：

```bash
# 本地：生成并上传公钥
ssh-keygen -t ed25519 -C "haha-ecs"
ssh-copy-id root@<你的服务器IP>

# 服务器上：确认密钥能登录之后，再关闭密码登录
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

> 关闭密码登录前，务必先开一个新终端确认密钥登录成功，否则会把自己锁在门外。

---

## 1. 开放安全组端口

云厂商的**安全组**和服务器内部的防火墙是两层，两层都要放行，只开一层不通。

在控制台的安全组入方向规则中放行：

| 协议 | 端口 | 源地址 | 用途 |
|---|---|---|---|
| TCP | 22 | 建议限制为你的 IP | SSH |
| TCP | 80 | 0.0.0.0/0 | 网站访问 |

服务器内部的 `ufw` 由下一步的脚本自动配置。

---

## 2. 一键初始化服务器

以 root 登录服务器后执行：

```bash
curl -fsSL https://raw.githubusercontent.com/Hahazehua/feiyi-heritage-ai/main/deploy/bootstrap-ecs.sh -o bootstrap-ecs.sh
bash bootstrap-ecs.sh
```

脚本做四件事：更新系统包 → 安装 Docker Engine 与 compose 插件 → 配置 ufw（只放行 22/80）→ 把仓库克隆到 `/opt/haha` 并生成 `.env`。

> 如果仓库是私有的，先 `git clone` 到本地再用 `scp -r` 上传到 `/opt/haha`，然后直接跑脚本即可（脚本会跳过克隆步骤）。

---

## 3. 填写 .env

```bash
nano /opt/haha/.env
```

关键项：

```ini
DEEPSEEK_API_KEY=<你的真实 Key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
LLM_ENABLED=true

AGENT_REVIEW_MODE_ENABLED=false   # 评审期间需要 Trace 时改 true
AGENT_REVIEW_TOKEN=               # 建议同时设置一个随机 Token
ANALYTICS_ENABLED=false
ANALYTICS_STORE_RAW_CHAT=false    # 必须保持 false
APP_VERSION=0.1.0
```

`.env` 已在 `.gitignore` 与 `.dockerignore` 中，不会进镜像也不会进 Git；容器通过 `env_file` 在运行时读取。文件权限应为 `600`。

不配置 Key 时应用会退回本地确定性解析器，推荐与方案生成仍可运行——可以先不填 Key 跑通部署，再补 Key。

---

## 4. 部署

```bash
bash /opt/haha/deploy/deploy.sh
```

脚本会拉取最新代码、构建镜像、启动 `app` + `nginx` 两个容器，并轮询健康检查直到应用就绪。首次构建约 3–6 分钟（主要是下载依赖）。

完成后访问：

- 客户模式：`http://<你的服务器IP>/`
- 评审模式：`http://<你的服务器IP>/?review_mode=1`（需服务端 `AGENT_REVIEW_MODE_ENABLED=true`；若设了 Token 还要带 `&review_token=<TOKEN>`）

**以后每次更新代码，只需重新跑一遍 `deploy.sh`。**

---

## 5. 部署后自检

```bash
# 容器状态与健康
docker compose -f /opt/haha/deploy/docker-compose.yml ps

# 应用日志
docker compose -f /opt/haha/deploy/docker-compose.yml logs -f app

# 健康检查
curl -I http://localhost/_stcore/health

# 确认 8501 只监听回环，没有直接暴露到公网
ss -tlnp | grep 8501     # 应显示 127.0.0.1:8501
```

沿用 Wave 3 的验收清单：

- [ ] 无痕窗口打开普通 URL，不显示 Agent Trace
- [ ] 评审 URL 仅在双重门控满足时显示 Trace
- [ ] 无 Key 场景仍能推荐或明确返回无匹配
- [ ] 完成推荐 → 选品 → 方案生成 → JSON 下载全链路
- [ ] 1440×1000 与 390×844 无横向滚动
- [ ] 20 件正式商品可推荐，30 件参考商品不进入正式推荐
- [ ] 页面与日志无 Key、数据库地址、聊天原文或完整异常堆栈泄露

---

## 6. 常见问题

| 现象 | 排查方向 |
|---|---|
| 浏览器一直转圈打不开 | 九成是安全组没放行 80。先在服务器上 `curl -I http://localhost/`，本地通=安全组问题，本地也不通=看容器日志 |
| 页面能开但每分钟断线重连 | Nginx 少了 websocket 头。确认用的是 `deploy/nginx.conf`，`Upgrade`/`Connection` 两行都在 |
| `ModuleNotFoundError: heritagelink` | 构建日志里 `-e .` 没跑成功；确认 `pyproject.toml` 与 `src/` 都被 COPY 进镜像 |
| 图片 404 | `assets/` 未提交到 Git，或 CSV 里的文件名大小写与实际不符（Linux 区分大小写，Windows 不区分） |
| 构建时磁盘满 | `docker system prune -af` 清理旧镜像；`assets/` 约 46MB，镜像总体约 1.2GB |
| 改了 `.env` 但不生效 | `.env` 在容器启动时读取，需要 `docker compose ... up -d` 重启容器 |
| 需要重启 | `docker compose -f /opt/haha/deploy/docker-compose.yml restart` |

---

## 7. 关于 HTTPS

裸 IP 无法申请 Let's Encrypt 证书。如果之后拿到域名：

```bash
# 域名 A 记录指向服务器 IP 之后
apt-get install -y certbot
docker compose -f /opt/haha/deploy/docker-compose.yml stop nginx
certbot certonly --standalone -d your-domain.com
```

然后把证书目录挂进 nginx 容器，在 `deploy/nginx.conf` 中加 `listen 443 ssl;` 段并把 80 端口重定向到 443，同时在 compose 里放行 `443:443`、ufw 放行 443。

在此之前是纯 HTTP：**不要在这个站点上收集任何真实的密码或个人敏感信息**，演示与评审用途没问题。

---

## 文件清单

| 文件 | 作用 |
|---|---|
| `deploy/Dockerfile` | Python 3.11 镜像，非 root 用户运行，内置健康检查 |
| `deploy/docker-compose.yml` | app + nginx 两个服务，app 仅绑定 127.0.0.1 |
| `deploy/nginx.conf` | 反向代理，含 Streamlit websocket 所需配置 |
| `deploy/bootstrap-ecs.sh` | 服务器一次性初始化 |
| `deploy/deploy.sh` | 每次更新时重复执行的部署脚本 |
| `.dockerignore` | 把 `.env`、`.venv`、测试与文档排除出构建上下文 |
