# 社交媒体定时简报原型

这是一个可运行的 Python 原型，用来做这条链路：

1. 定时抓取你指定的来源
2. 去重入库
3. 按来源生成摘要或简介
4. 产出 Markdown 简报
5. 可选发到邮箱

当前项目重点是把主流程搭稳，并把平台差异隔离到适配器层。

如果你当前最关心的是 X，这个原型现在已经额外支持：

- 监控多个 X 账号
- 给账号打分类标签，比如 `AI 科技`、`宏观财经`、`Web3 币圈`
- 通过命令行指定抓取时间范围
- 把账号放进独立账号池文件，后续可持续追加
- API 失败时切到浏览器读取兜底
- 浏览器兜底会按“本机脚本 -> Chrome Headless dump-dom -> Remote Debugging”顺序尝试

## 已支持的接入方式

- `x`：官方 X API v2 用户时间线
- `weibo`：实验性微博公开页采集器
- `wechat`：
  - `material_api`：你自己的微信公众号素材接口
  - `feed`：外部 RSS、Atom 或自建中转 Feed
- `mock`：本地演示数据源，方便先验证整条流程

## 快速开始

### 1. 安装

```powershell
python -m pip install -e .
```

### 2. 准备配置

```powershell
Copy-Item config.example.toml config.toml
```

先用 `mock` 数据源跑通流程，再逐步打开真实来源。

### 3. 运行一次

```powershell
social-digest --config config.toml run-once
```

指定时间范围：

```powershell
social-digest --config config.toml run-once --start 2026-03-08T00:00:00+08:00 --end 2026-03-08T23:59:59+08:00
```

### 4. 只抓取不出简报

```powershell
social-digest --config config.toml fetch
```

### 5. 按历史数据生成简报

```powershell
social-digest --config config.toml digest
```

### 6. 守护运行

```powershell
social-digest --config config.toml daemon
```

## 推荐下一步

如果你准备把这个原型真正长期跑起来，下一步最值得补的是：

1. 增加 LLM 摘要器
2. 增加企业微信、Telegram 或飞书推送
3. 给微博和第三方公众号接入更稳定的中转层
4. 改成 Windows 任务计划或服务器守护进程部署

## X 账号池管理

默认账号池文件是 `sources/x_accounts.csv`。

追加一个账号：

```powershell
social-digest --config config.toml add-x-account --username elonmusk --category macro-finance
```

列出当前账号池：

```powershell
social-digest --config config.toml list-x-accounts
```

CSV 字段说明：

- `username`：X 用户名
- `category`：分类标签，建议用 `ai-tech`、`macro-finance`、`web3-crypto`
- `display_name`：可选显示名
- `enabled`：是否启用
- `notes`：备注

## X 浏览器兜底

如果 X API token 不可用，或你希望在失败时自动切到浏览器模式，可以保留：

```toml
strategy = "api_then_browser"
remote_debug_profile_dir = "secrets/x_chrome_profile"
remote_debug_port = 9222
```

浏览器兜底依赖 Playwright：

```powershell
python -m pip install -e .[browser]
python -m playwright install chromium
```

`remote_debug_profile_dir` 是 Chrome Remote Debugging 使用的持久化用户目录。你如果用这个目录手动登录过一次，后续程序可以复用登录态继续抓取。

## 失败来源说明

如果某个网页来源最终没有拿到正文，简报里会追加失败说明，并使用这条固定文案：

`已依次尝试 curl 移动端 UA、Headless dump-dom、Remote Debugging，仍未获取正文`

## 分类汇总

简报会优先按分类汇总，再从每类里挑出少量代表性更新，避免把多人时间线原样堆出来。当前默认支持的分类名只是建议值，你后面给我新的分类也可以直接继续加。
