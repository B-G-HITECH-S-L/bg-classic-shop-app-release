# bg-classic-shop-app-release
BiG Retail 正式包发布仓库

## 准备发布文件

在源码项目中准备好已签名的正式 APK，并确认包内版本与要发布的版本一致。
将 APK 放入本仓库的版本目录；发布说明可以提前填写，也可以由脚本生成：

```text
dist/
└── v0.0.1/
    ├── big-retail.apk
    ├── release-notes.md       # 可选，脚本自动补齐
    └── update.json            # 脚本从实际 APK 自动生成
```

- 版本号格式为 `v主版本.次版本.修订版本`，例如 `v0.0.1`；各部分不允许前导零。
- 目录中必须恰好有一个非空的 `.apk` 普通文件，文件名固定为 `big-retail.apk`，与客户端已有校验保持一致。
- `release-notes.md` 缺失、为空或只有空白时，脚本自动生成版本标题和安装包信息。
- `release-notes.md` 只作为 Release 正文；公开附件固定为 `big-retail.apk` 和自动生成的 `update.json`，其他本地文件不会上传。
- `/dist/` 已被 Git 忽略，APK、发布说明与更新文件都保留在本机。脚本和本文档纳入 Git 管理。
- APK 包名必须为 `com.byghitech.classicpos`，版本名必须与标签去掉 `v` 后一致，构建号须在 1 至 2100000000 之间；可调试 APK 会被拒绝。

APK 必须来自 PDA 源码仓库的 `scripts/build-release.sh` 成功快照，文件名已为 `big-retail.apk`。该构建入口校验正式非 Debug 签名、包名、版本和 ARM32/ARM64；符号、R8 映射、构建记录及 AAB 不得放入公开 Release。

本仓库发布脚本对实际上传快照重新检查 ZIP、双 ARM 库、包名、版本及不可调试，并用 `apksigner verify` 验签，要求证书 SHA-256 与 `config/release-cert.sha256` 一致。拒绝未签名、损坏、Debug 或其他证书；仅校验哈希不能证明签名。该文件已从现有正式 `classicpos` 证书提取，公开指纹不含私钥或密码；两仓库必须保持一致，不能为绕过检查而修改。`ANDROID_RELEASE_CERT_SHA256` 若提供，必须与已固定指纹一致。目标 PDA 覆盖安装仍需验收。生产地址、首发版本及构建号待确认，本文版本仅作格式示例。

### 自动生成更新附件

`update.json` 沿用客户端现有格式，示例如下：

```json
{
  "schemaVersion": 2,
  "applications": [
    {
      "id": "com.byghitech.classicpos",
      "platform": "android",
      "version": "0.1.22",
      "versionCode": 23,
      "packageFileName": "big-retail.apk",
      "packageUrl": "https://github.com/B-G-HITECH-S-L/bg-classic-shop-app-release/releases/download/v0.1.22/big-retail.apk",
      "sha256": "由实际 APK 计算的 64 位 SHA-256",
      "size": 67123379
    }
  ]
}
```

版本与构建号来自包内信息，大小与哈希来自实际上传的 APK 快照，不能通过标签推算构建号。下载地址固定到本次具体版本，不使用 `latest` APK 地址。脚本每次重新生成确定性的内容，复用草稿时也能逐字节校验；不需要手工编辑更新文件。

客户端直接访问：

```text
https://github.com/B-G-HITECH-S-L/bg-classic-shop-app-release/releases/latest/download/update.json
```

新版 BiG Retail检查更新不调用 GitHub REST API，也不读取 AIO 目录。AIO 应用管理和旧配置客户端仍使用 `bg-pos-aio-release/application/application-catalog.json`，因此每次正式发布都必须同步该文件；这不是仅在迁移期间执行的步骤。

### 每次正式发布同步 AIO 应用目录

正式 Release 的两个附件校验通过后，`release.sh` 自动执行 `scripts/sync-aio-catalog.py`，将同一份 `update.json` 的 `version`、`versionCode`、`packageUrl`、`sha256` 和 `size` 提交到 `B-G-HITECH-S-L/bg-pos-aio-release` 的 `main`，文件路径固定为 `application/application-catalog.json`。首次缺少 `com.byghitech.classicpos/android` 时新增 BiG Retail 条目；已有条目的应用名称、多语言名称、图标、其他配置及其他应用记录保持原值。

同步工具重新确认源版本为 Latest 正式版，核对已发布 APK 和更新附件的大小及 SHA-256。通过 GitHub Contents API 携带原文件 blob SHA 创建提交，目录并发变更会报错，不覆盖他人的修改。相同信息重复执行不产生新提交；远程构建号更高、同构建号但信息冲突或重复条目均阻止更新。正式发布前会同时核验当前公开 Latest 的更新附件及 APK 校验信息，候选构建号必须严格更高；即使 AIO 目录落后或缺失，也不能放行同/低构建号。查询失败或附件异常会停止，不推断为首次发布；完整分页列表确无正式版才允许首次发布。上传后、设为 Latest 前再次检查 Latest 与目录，发布后再次核对。

`--draft` 不修改 AIO 目录，也不要求 AIO 写权限。正式发布和默认 `--dry-run` 预览会提前检查两个仓库的写权限。目录同步失败时，已发布的 Release 保留，但脚本返回失败，不报告发布全部完成；修复权限或并发冲突后单独重试：

```bash
# 只读预览已发布版本对应的目录更新
python3 scripts/sync-aio-catalog.py v0.1.23 --dry-run

# 读取并验证正式 Release 附件，再提交目录；不重建、不重发 APK
python3 scripts/sync-aio-catalog.py v0.1.23
```

独立同步命令只需要 Python 和已登录的 `gh`，不依赖本地 APK、Android SDK 或 AIO 仓库 checkout。若本地已有 AIO checkout，远程同步后可在工作区无冲突时执行 `git pull --ff-only` 获取提交。

旧开发客户端若严格要求 `app-prod-release.apk`，不能直接接受新附件名；需手动首次安装正确签名的新版。同步 AIO 目录不绕过旧客户端校验。

### 自动维护安装包信息

脚本基于本次实际上传的 APK 快照计算 SHA-256 和文件大小，并在发布说明中维护以下区块：

```markdown
<!-- release-package-info:start -->
## 安装包信息

- 文件名: big-retail.apk
- SHA-256: <本次 APK 的 64 位 SHA-256>
- Size: <本次 APK 的整数形式字节数>
<!-- release-package-info:end -->
```

`Size` 的单位固定为字节，例如 `43461008`，不换算为 KB / MB。
已有人工正文保留；首次追加自动区块，后续运行原位更新，避免重复追加或保留旧的校验数据。
自动区块的标记需要成对且唯一；标记损坏或重复时脚本报错，避免误删正文。

实际发布、保留草稿和续传时，在远程检查通过后、修改远程之前写回本地 `update.json` 与 `release-notes.md`，
发布说明作为 GitHub Release 正文，更新文件作为附件。若后续上传失败，本地文件仍保留。
`--dry-run` 只在终端展示拟生成的说明，不创建或修改版本目录中的说明文件或 `update.json`。

## 环境要求

- Bash 3.2 或以上（兼容 macOS 自带 Bash）。
- GitHub CLI `gh`、Python 3.8 或以上，以及系统工具 `git`、`unzip`、`shasum` 等。
- Android SDK Build Tools 的 `aapt` 和 `apksigner`。可通过 `AAPT_BIN` / `APKSIGNER_BIN` 指定可执行文件；否则从 PATH、`ANDROID_HOME`、`ANDROID_SDK_ROOT` 或 macOS/Linux 默认 SDK 目录查找。缺失时在访问 GitHub 前报错。
- GitHub.com 当前登录账号具备本发布仓库及 `B-G-HITECH-S-L/bg-pos-aio-release` 的写入权限；只准备草稿时仅需本仓库写权限。

macOS 安装并登录：

```bash
brew install gh
gh auth login --hostname github.com --git-protocol ssh --web --skip-ssh-key
gh auth status --active --hostname github.com
```

## 发布命令

在仓库根目录执行：

```bash
# 先预览：校验并展示计划、发布说明，不修改本地说明和远程
./scripts/release.sh v0.0.1 --dry-run

# 上传并发布为正式版，设为 Latest
./scripts/release.sh v0.0.1

# 只上传到草稿
./scripts/release.sh v0.0.1 --draft

# 预览或继续已有的同版本草稿
./scripts/release.sh v0.0.1 --resume --dry-run
./scripts/release.sh v0.0.1 --resume

# 继续草稿，但仍保留为草稿
./scripts/release.sh v0.0.1 --resume --draft
```

脚本根据自身位置定位仓库，从其他工作目录通过脚本的完整路径执行也可以。
它固定操作 `B-G-HITECH-S-L/bg-classic-shop-app-release`，并检查 `origin`，避免发布到其他仓库。
每次执行会在 `dist/` 下建立临时快照，退出时清理，确保上传内容与本次校验内容一致。实际发布使用 `dist/.release-publish.lock` 串行处理同一 checkout 的操作；只读预览不加锁。异常中断后须确认无发布进程才清理锁。不同机器或 checkout 须统一排队；GitHub 的发布及跨仓库目录写入并非原子事务，本机锁不能提供全局互斥。

新版本以运行时远程 `main` 的提交作为目标，先创建草稿，上传并校验 APK 和 `update.json` 后再正式发布。
若同名标签已经存在，只有它指向该提交时才允许创建 Release；脚本不会移动标签。
续传已有草稿时保留其目标和标签，标题与正文使用本次版本号及更新包信息后的发布说明。
正式发布还会提交同步 AIO 应用目录，全部成功后输出 Release 地址、两个附件的下载地址及 APK SHA-256。

## 重复执行与失败恢复

| 情况 | 处理方式 |
| --- | --- |
| 版本不存在 | 创建草稿、上传校验，再按参数发布或保留草稿 |
| 已有同版本草稿 | 必须显式添加 `--resume`，预览同样如此 |
| 草稿没有附件 | 上传 APK 和生成的 `update.json`，全部校验后发布 |
| 草稿只有 APK 或 `update.json`，内容与本地一致 | 复用已校验附件，仅补传缺失附件 |
| 草稿两个附件均与本地一致 | 全部复用，不重复上传 |
| 草稿任一附件内容或下载地址不同、上传未完成，或存在重复 / 额外附件 | 停止，需人工核对，不自动覆盖或删除 |
| 同版本已正式发布 | 发布命令停止；若只需补同步目录，使用独立同步命令 |
| Release 已发布但目录同步失败 | 返回失败，保留 Release；修复后独立重试目录同步，避免重复发包 |
| 登录、权限或远程查询失败 | 报错，不把失败当成版本不存在 |
| 上传、更新说明或发布请求失败 | 报告失败阶段，保留已完成的远程操作，提示恢复方式 |

两个附件均先检查名称、上传状态、字节大小和版本下载地址；仅在草稿阶段允许 GitHub 返回本仓库的 `untagged-<十六进制>` 临时附件地址，正式发布后必须是本次版本的固定地址；内容校验优先使用 GitHub 返回的 SHA-256，没有此值时下载到临时目录计算。APK 或更新文件缺失、损坏均保留草稿，不发布半成品。
发布请求可能已经成功但响应丢失；重试前先检查 GitHub。若已经正式发布，脚本会停止；若仍为草稿，
使用 `--resume` 继续。上传失败也可能留下未完成的附件，需先在草稿页核对并处理，再重试。

脚本退出码为 `0` 表示完成（或预览通过）；非 `0` 表示校验或操作失败。

## 本地验证

```bash
/bin/bash -n scripts/release.sh
python3 -B -m unittest discover -s tests -v
```

生命周期测试使用临时版本目录、结构测试 APK 和模拟的 `gh` / `git` / SDK，覆盖 Latest 和 AIO 落后时的防回退、发布前二次核对、固定签名及草稿恢复，不会访问真实 GitHub Release。另有真实 Android SDK/JDK 测试，用一次性证书验证合法、未签名、Debug、其他证书和篡改 APK；未安装对应 SDK/JDK 时该组明确跳过，不能作为真实 SDK 验证通过。
测试文件都位于被忽略的 `dist/` 下，并在测试结束后清理。

参考：[GitHub CLI](https://cli.github.com/manual/gh_release_create)、
[Release 附件及文件名规则](https://docs.github.com/en/rest/releases/assets)、
[Latest 附件链接规则](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases)、
[目录提交与 blob SHA](https://docs.github.com/en/rest/repos/contents#create-or-update-file-contents)。

### 新版 SDK 证书输出兼容

支持 apksigner 的 `Signer #1` 与 `Signer (minSdkVersion=…, maxSdkVersion=…)` 证书输出。同一证书可按多个 SDK 区间重复出现；多个编号签名者、不同证书、未知应用签名摘要格式或异常签名者计数均拒绝，仍必须匹配固定的正式证书指纹。解析兼容不会放行签名轮换，也不会把 Source Stamp 当作应用签名证书。
