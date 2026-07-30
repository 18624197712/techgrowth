# 安全模型

TechGrowth 是单用户服务，不开放注册。管理员密码使用 Argon2id，登录后强制 TOTP；Session 为服务端不透明令牌，写入 `HttpOnly`、`SameSite=Lax`、生产环境 `Secure` Cookie。所有状态变更接口校验 CSRF，登录按邮箱与 IP 限流，并记录安全审计事件。

## 信任边界

- Caddy 是唯一公网入口，只开放 80/443。
- PostgreSQL 位于 internal Docker 网络，不映射宿主机端口。
- 模型输出必须通过 Pydantic Schema；单次 Agent 和每日评测都有 token 上限。
- 技术来源与仓库内容均作为不可信数据包裹，提示词不得遵循其中的指令。
- 模型不能直接提高技能等级，只有满足 Rubric 的审阅证据能更新画像。
- 通知只发送状态文字和站点链接，不发送代码、API Key、恢复码或文件路径。

## 连接器

连接器使用一次性配对码注册 Ed25519 公钥。每个请求覆盖 HTTP 方法、路径、时间戳、随机 nonce 和请求体 SHA-256；服务端限制 5 分钟窗口并拒绝 nonce 重放。Bearer 设备令牌只保存在 Credential Manager。

服务器下发的文件路径仍在本地重新执行授权根、仓库边界、`.gitignore`、符号链接、密钥、二进制和大小检查。设备撤销立即使令牌失效。首版明确禁止自动执行仓库代码。

## 密钥与数据

`.env` 权限应为 `600`，不得提交到 Git。`TG_SECRET_KEY`、`TG_ENCRYPTION_KEY`、数据库密码、模型 Key、SMTP 密码和 VAPID 私钥分别生成，不复用。更换 `TG_ENCRYPTION_KEY` 前必须实现数据重加密；直接替换会使现有加密字段不可读。

上传文件使用加密临时存储。正常分析完成立即删除；Worker 每小时清理超过 24 小时的异常暂存。长期保留的仅为哈希、指标、引用位置和成长证据。

## 持续检查

CI 执行 Ruff、pytest、ESLint、Vitest、TypeScript、PostgreSQL 迁移、Gitleaks、Trivy、Python/Node 依赖审计和 Windows 打包。真实模型评测每天和手动运行，最多 50,000 token；Schema、引用和安全拒绝必须 100%，任务约束与 Rubric 覆盖至少 95%。

生产变更只允许受保护 `main` 分支，部署 Runner 使用专用 ECS 标签和 GitHub Environment 审批。发现泄露后立即撤销设备/Session、轮换受影响凭据、检查审计日志，并从泄露前备份验证数据完整性。

