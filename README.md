# Binance Telegram Bot

自动获取币安现货和合约USDT交易对24小时涨跌榜，并通过Telegram机器人推送。

## 功能

- 抓取币安活跃交易对涨跌数据（现货与合约）
- 生成涨幅榜和跌幅榜，包含涨跌百分比和最新价格
- 每小时自动推送至Telegram
- 支持手动触发推送

## 使用

### 环境变量配置

请在GitHub仓库的Settings → Secrets 中添加：

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 本地运行

```bash
pip install -r requirements.txt
python main.py
