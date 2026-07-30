# Windows 连接器

## 安装与配对

GitHub Actions 的 Windows Runner 生成 `TechGrowthConnector.exe` 和 `SHA256SUMS.txt`。首版未进行代码签名，发布流程只提示新版本，不静默下载或安装。运行前先校验 SHA-256。

1. 在 Web 的“项目与仓库”创建 10 分钟有效的一次性配对码。
2. 启动托盘程序，选择“配对设备”，填写公网 HTTPS 地址、配对码和设备名称。
3. 选择“添加授权目录”。连接器只访问明确授权的根目录。
4. 选择“立即同步”，Web 中会出现仓库元数据。

设备私钥与令牌存放在当前 Windows 用户的 Credential Manager；`%APPDATA%\TechGrowth\Connector\connector.json` 只保存服务器地址、授权目录和本地仓库映射。连接器没有监听端口，服务器不能主动浏览电脑。

## 同步边界

连接器发现 Git 仓库并同步分支、Commit、语言统计等元数据。只有服务器下发按需文件任务时才上传单个授权文件；不会批量上传整个仓库，也不会执行构建、安装、测试或任何仓库代码。

扫描器遵守 `.gitignore`，并拒绝：

- 授权根目录外路径、路径穿越和任何符号链接路径；
- `.git`、`node_modules`、`.venv`、`vendor`、`dist`、`build`、`target` 等目录；
- `.env*`、私钥、证书、Credential 文件、二进制文件和超过 1 MiB 的文件。

分块上传的偏移写入本地 SQLite 队列。断网后使用相同幂等键和偏移继续；服务端校验完整文件 SHA-256 和大小。分析文件在服务端加密暂存，成功后应由分析流程立即删除，异常文件最迟 24 小时清理。

## 撤销与卸载

在 Web 删除设备后，后续签名请求返回未授权，托盘程序会清除本地配对凭据并要求重新配对。卸载前取消“开机启动”，退出托盘，删除便携版程序；如需清除本地状态，再删除 `%APPDATA%\TechGrowth\Connector` 和 Credential Manager 中的 `TechGrowth Connector` 条目。

