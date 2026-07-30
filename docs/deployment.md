# TechGrowth 阿里云 ECS 部署

## 前置条件

- 中国大陆阿里云 ECS，建议至少 2 vCPU、4 GB RAM、40 GB 云盘，Ubuntu 22.04/24.04。
- 已备案域名，例如 `growth.example.com`，A/AAAA 记录指向 ECS 公网地址。
- Docker Engine 与 Compose v2，服务器能拉取 GHCR、Docker Hub 镜像。
- 阿里云安全组仅向公网开放 TCP 80/443；SSH 22 只允许固定管理 IP。不要开放 5432、8000 或 Caddy 管理端口。

## 首次部署

1. 把仓库放到 ECS 的专用目录，例如 `/opt/techgrowth`，然后进入该目录。
2. 执行 `cp .env.example .env`，填写域名、ACME 邮箱、GHCR 镜像和所有密钥。`POSTGRES_PASSWORD` 使用 URL-safe 随机字符，因为它也用于数据库连接 URL。
3. 使用 `openssl rand -hex 32` 分别生成 `TG_SECRET_KEY`、`TG_ENCRYPTION_KEY` 和数据库密码。`TG_ENCRYPTION_KEY` 丢失后无法解密 TOTP、模型凭据和通知目标，必须纳入服务器密钥备份。
4. 设置 `TG_ICP_NUMBER`，例如 `京ICP备12345678号-1`。备案号会显示在页面底部。
5. 创建运行目录并限制备份权限：

```bash
mkdir -p logs/caddy backups
chmod 700 backups
chmod +x infra/scripts/*.sh
```

6. 登录 GHCR，执行迁移并启动：

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
docker compose pull
docker compose run --rm api alembic upgrade head
docker compose up -d
docker compose run --rm api techgrowth create-admin --email you@example.com
```

7. 访问 `https://APP_DOMAIN`。首次登录必须绑定 TOTP，并立即离线保存恢复码。

Caddy 会自动申请和续签 HTTPS 证书。Compose 只映射 Caddy 的 80/443；API、Web、Worker、PostgreSQL 均无公网端口。

## 模型与通知

登录后在“设置”填写 OpenAI 兼容 Base URL、聊天模型、Embedding 模型和 API Key。API Key 在数据库中加密保存。

SMTP 使用 `.env` 中的 `TG_SMTP_*`。Web Push 需要一对 VAPID 密钥，私钥放入 `TG_VAPID_PRIVATE_KEY`，浏览器公钥放入 `TG_VAPID_PUBLIC_KEY`，`TG_VAPID_SUBJECT` 使用管理员邮箱。通知正文只包含任务、审阅或周复盘状态，不包含代码和敏感数据。

## 备份、恢复与演练

每天运行备份：

```cron
15 3 * * * cd /opt/techgrowth && ./infra/scripts/backup.sh >> logs/backup.log 2>&1
```

脚本保留 7 个日备份、4 个周备份和 6 个月备份。恢复会重建目标数据库，必须显式确认：

```bash
./infra/scripts/restore.sh /opt/techgrowth/backups/daily/techgrowth-YYYY.dump --confirm
```

每月自动恢复到临时数据库并检查表结构，结束后删除临时数据库：

```cron
0 4 2 * * cd /opt/techgrowth && ./infra/scripts/verify-backup.sh >> logs/restore-check.log 2>&1
```

同时在阿里云配置系统盘/数据盘每日自动快照，保留 7 天。数据库备份用于逻辑恢复，云盘快照用于实例级故障恢复，两者不能互相替代。

## 发布与回滚

GitHub Actions 在托管 Runner 完成测试和镜像构建，以完整 Git SHA 推送 GHCR。带 `techgrowth-production` 标签的 ECS 自托管 Runner 只执行受保护 `main` 分支的 deploy job，GitHub `production` Environment 应配置审批和分支限制。

手动发布同样使用 SHA：

```bash
./infra/scripts/deploy.sh 0123456789abcdef0123456789abcdef01234567
```

脚本先备份，再拉取 SHA 镜像、执行向后兼容迁移并检查容器内和公网 HTTPS 健康状态。失败时恢复 `.env` 中上一镜像标签并重新启动旧镜像。数据库迁移必须保持至少一个版本向后兼容。

## 生产验收

逐项检查 HTTPS、登录/TOTP、今日任务、审阅、通知、连接器同步、`docker compose restart`、ECS 重启、备份恢复和失败发布回滚。Caddy、API 与数据库日志均应设置监控告警；绝不在工单或日志中粘贴 `.env`、恢复码和上传代码。

