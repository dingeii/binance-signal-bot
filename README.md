# Binance 24H 涨跌榜机器人

📊 自动推送币安 USDT 交易对涨跌榜到 Telegram。

## 功能

- 每小时自动推送涨跌榜（GitHub Actions 定时运行）
- Telegram 命令 `/run` 获取当前榜单
- 支持现货与合约，格式美观，适合手机查看

## 使用方法

### 1. 准备工作

- 创建 Telegram 机器人，获取 `TELEGRAM_BOT_TOKEN`
- 获取你要接收消息的 `TELEGRAM_CHAT_ID`

### 2. 添加 GitHub Secrets

在仓库中设置以下 Secret：

| Name                | 描述                       |
|---------------------|----------------------------|
| TELEGRAM_BOT_TOKEN  | Telegram 机器人 Token      |
| TELEGRAM_CHAT_ID    | 接收消息的 Telegram ID     |

### 3. 自动部署

仓库包含 `.github/workflows/main.yml`，每小时运行 `main.py` 推送涨跌榜。

### 4. 本地测试运行

```bash
pip install -r requirements.txt
python main.py
