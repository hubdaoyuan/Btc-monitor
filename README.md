# BTC价格监控系统

🚀 自动获取BTC价格、技术分析数据，并通过微信推送通知

## 功能特性

- 📊 **实时价格**：获取BTC/USDT最新价格和24小时涨跌
- 📈 **K线数据**：自动获取日线数据并生成K线图
- 🎯 **技术分析**：
  - 支撑位/阻力位计算
  - RSI指标
  - 布林带
  - 趋势判断
- 😊 **市场情绪**：恐惧贪婪指数分析
- 📱 **微信推送**：通过Server酱推送至微信

## 快速开始

### 1. 本地运行

```bash
# 克隆项目
git clone <your-repo-url>
cd btc-monitor

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的Server酱SendKey

# 运行
bash run_btc_monitor.sh
```

### 2. GitHub Actions自动运行

项目已配置GitHub Actions，每天北京时间09:00自动运行并推送报告。

需要配置的Secrets：
- `SERVERCHAN_SENDKEY`: 你的Server酱SendKey

## 配置说明

### 获取Server酱SendKey

1. 访问 [https://sct.ftqq.com/](https://sct.ftqq.com/)
2. 使用GitHub账号登录
3. 微信扫码绑定
4. 复制SendKey

### 环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `SERVERCHAN_SENDKEY` | Server酱SendKey | 是 |

## 报告内容

每日推送包含：
- BTC当前价格和24h涨跌
- OHLC数据（开盘/最高/最低/收盘）
- 支撑位和阻力位
- RSI指标和布林带
- 市场情绪（恐惧贪婪指数）

## 技术架构

- **数据源**: Binance API（免费，无需API Key）
- **推送服务**: Server酱（免费版）
- **自动化**: GitHub Actions

## 项目结构

```
btc-monitor/
├── .github/workflows/
│   └── btc-monitor.yml    # GitHub Actions配置
├── btc_monitor.py         # 主监控脚本
├── run_btc_monitor.sh     # 本地运行脚本
├── .env.example           # 环境变量示例
└── README.md              # 项目说明
```

## 许可证

MIT License
