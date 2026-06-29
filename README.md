# 🍔 BiliBurgie

**B站直播弹幕 → 游戏指令中继器**

~~比利·伯吉，你也可以叫他———比伯（）~~

专为 [Burgie's Cozy Kitchen](https://heynaugames.com/burgie-commands) 直播模式设计。 观众在 B站直播间发弹幕，BiliBurgie 自动翻译成游戏指令，通过 IRC 发送给游戏客户端，实现弹幕互动玩法。

> 📺 详细使用教程请看 B站 [@黑猫厌胜](https://space.bilibili.com/14957556)

![Platform](https://img.shields.io/badge/platform-Windows-blue) ![Python](https://img.shields.io/badge/python-3.11%2B-green) ![License](https://img.shields.io/badge/license-MIT-orange)

<p align="center"><img src="logo.png" alt="BiliBurgie Logo" width="128"></p>

---

## ✨ 核心功能

### 🔗 实时弹幕监听
- 连接 B站直播间 WebSocket，实时接收弹幕和礼物消息
- 支持登录态（Cookie），显示完整用户名
- 未登录时游客模式也可使用

### 🧠 大模型智能解析
- 支持 OpenAI 兼容 API（DeepSeek / OpenAI / 自定义）
- 支持本地 Ollama 模型
- 自动将自然语言弹幕翻译为游戏指令
- 可编辑系统提示词

### ⚡ 内置硬匹配
- 中文关键词直接映射为游戏指令，无需调用 LLM
- 包含所有官方提供的指令（不知道是不是因为接口的原因还是啥，皮肤指令我一直测试不管用）

### 🎁 礼物权限控制
- 送礼后才能使用大模型（弹幕指令不受影响）
- 可设置最低礼物金额（金瓜子）
- 可指定允许的礼物名称（逗号分隔）
- 白名单有效期可配置

### 🖥 IRC 服务
- 内置 IRC 服务器，游戏客户端直接连接
- 默认监听 `127.0.0.1:6667`

### 🔒 隐私安全
- 配置文件加密存储（XOR + Base64），Cookie / API Key 不会明文泄露
- 所有配置完全本地加载，网络交互只限于弹幕获取与大模型调用
- 配置文件存储在用户目录（`%APPDATA%\BiliBurgie\config.dat`）
- 日志仅在内存中，手动导出才会写盘

---

## 🚀 快速开始

### 方式一：下载可执行文件（推荐）

从 [Releases](../../releases) 页面下载 `BiliBurgie.exe`，双击运行，无需安装 Python。

### 方式二：源码运行

```bash
# 克隆仓库
git clone https://github.com/Cat-Qin/BiliBurgie.git
cd BiliBurgie

# 创建虚拟环境（可选）
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

---

## ⚙️ 配置说明

### 1. 直播平台（🍔）
| 配置项 | 说明 |
|--------|------|
| 直播间 ID | B站直播间的数字 ID（URL 中的数字） |
| SESSDATA | 登录后从浏览器 Cookie 获取，填入可显示完整用户名 |
| bili_jct | CSRF Token，与 SESSDATA 配套 |
| buvid3 | 设备标识，可选 |

> **如何获取 Cookie：** 浏览器登录 B站 → F12 → Application → Cookies → bilibili.com → 复制 SESSDATA / bili_jct / buvid3

### 2. 大模型（🤖）
| 配置项 | 说明 |
|--------|------|
| 服务商 | `本地 (Ollama)` 或 `自定义 (OpenAI 兼容)` |
| 模型名称 | 从 API 获取列表后选择，或手动输入 |
| API 地址 | 如 `http://localhost:11434/api/generate`（Ollama）或 `https://api.deepseek.com` |
| API Key | 自定义 API 需要，本地 Ollama 不需要 |
| 超时 / 最大 Token / 温度 | 控制 LLM 响应行为 |

注：本地模型本人并未进行测试，不保证能够正常使用。小参数模型可能需要更长的超时时间。

点击 **🔄 刷新** 按钮可自动拉取可用模型列表。  
点击 **📝 编辑系统提示词** 可自定义 LLM 的指令翻译规则。

### 3. 权限（🔐）
| 配置项 | 说明 |
|--------|------|
| 启用礼物权限 | 开启后只有送礼观众能通过大模型发指令 |
| 白名单有效期 | 送礼后权限持续多久 |
| 最低礼物价格 | 金瓜子门槛（1000 金瓜子 = 1 元），0 表示不限制 |
| 允许的礼物名 | 只有列表中的礼物才计入（逗号分隔），留空表示全部允许 |

### 4. 指令指南（📖）
查看所有内置的中文硬匹配规则。观众用自然语言发弹幕即可触发对应游戏指令。

---

## 🎮 使用流程

1. 打开 Burgie's Cozy Kitchen 游戏，进入直播模式
2. 在 BiliBurgie 中填入直播间 ID
3. 配置大模型（可选）
4. 点击 **▶ 启动**
5. 游戏连接 `127.0.0.1:6667`
6. 观众在直播间发弹幕，指令自动送达游戏

**指令示例：**
| 观众发送 | 解析结果 |
|----------|----------|
| `!burgie 全熟 双重芝士 可乐` | LLM 解析 → `!Burgie + well done + extra cheese + cola` |
| `点单 半熟 芝士 番茄` | 硬匹配 → `!Burgie + medium + cheese + tomato` |
| `着火` | 硬匹配 → `!Fire` |
| `按铃` | 硬匹配 → `!Bell` |

---

## 📦 打包为 EXE

```bash
pip install pyinstaller
pyinstaller build.spec --clean --noconfirm
# 输出在 dist/BiliBurgie.exe
```

---

## 🛠 技术栈

| 组件 | 技术 |
|------|------|
| UI 框架 | PyQt5 |
| 异步引擎 | asyncio + aiohttp |
| B站弹幕 | blivedm |
| 配置存储 | PyYAML + XOR 加密 |
| 打包 | PyInstaller |

---

## 🤖 AI 生成声明

本项目由 AI 辅助开发，具体范围如下：

| 类型 | 说明 |
|------|------|
| **AI 生成** | 全部 Python 源代码、UI 布局、样式表、构建配置 |
| **AI 辅助** | 架构设计、Bug 排查与修复、技术选型建议 |
| **人工提供** | 项目需求与产品方向、UI 图标与配色风格指导、游戏指令规则与官方文档、测试与反馈 |

>顺带一提，ai真的太好用了（），现在只要有想法，知道想要的方向和产品具体功能，谁都能把自己的想法变为现实

>花了10块左右的token，用的是deepseek-v4-pro，耗时两天，大家可以参考一下

> 本项目遵循 MIT 开源协议，欢迎贡献代码或提出改进建议。

---

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)

---

## 🙏 致谢

- [blivedm](https://github.com/xfgryujk/blivedm) — B站 弹幕客户端库
- [Burgie's Cozy Kitchen](https://heynaugames.com/burgie-commands) — 游戏本体，请支持开发者
