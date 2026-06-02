RSS_FEEDS = [
    # ── English Sources ──────────────────────────────────────────
    {
        "name": "CNBC",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "lang": "en",
        "category": "finance",
    },
    {
        "name": "Wall Street Journal",
        "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "lang": "en",
        "category": "markets",
    },
    {
        "name": "CoinTelegraph",
        "url": "https://cointelegraph.com/rss",
        "lang": "en",
        "category": "crypto",
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "lang": "en",
        "category": "tech",
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "lang": "en",
        "category": "tech",
    },

    {
        "name": "Hacker News",
        "url": "https://hnrss.org/frontpage",
        "lang": "en",
        "category": "tech",
    },


    # ── Chinese Sources ──────────────────────────────────────────
    {
        "name": "36氪",
        "url": "https://36kr.com/feed",
        "lang": "zh",
        "category": "cn-tech",
    },
    {
        "name": "IT之家",
        "url": "https://www.ithome.com/rss/",
        "lang": "zh",
        "category": "cn-tech",
    },
    {
        "name": "少数派",
        "url": "https://sspai.com/feed",
        "lang": "zh",
        "category": "cn-tech",
    },
    {
        "name": "钛媒体",
        "url": "https://www.tmtpost.com/rss.xml",
        "lang": "zh",
        "category": "cn-tech",
    },
    {
        "name": "爱范儿",
        "url": "https://www.ifanr.com/feed",
        "lang": "zh",
        "category": "cn-tech",
    },
    {
        "name": "虎嗅",
        "url": "https://rsshub.rssforever.com/huxiu/article",
        "lang": "zh",
        "category": "cn-finance",
    },
    {
        "name": "百度热搜",
        "url": "https://rsshub.rssforever.com/baidu/top/realtime",
        "lang": "zh",
        "category": "cn-general",
    },
    {
        "name": "财联社",
        "url": "https://rsshub.rssforever.com/cls/telegraph",
        "lang": "zh",
        "category": "cn-finance",
    },
    {
        "name": "澎湃新闻",
        "url": "https://rsshub.rssforever.com/thepaper/featured",
        "lang": "zh",
        "category": "cn-news",
    },
    {
        "name": "观察者网",
        "url": "https://rsshub.rssforever.com/guancha/headline",
        "lang": "zh",
        "category": "cn-news",
    },
    {
        "name": "格隆汇",
        "url": "https://rsshub.rssforever.com/gelonghui/live",
        "lang": "zh",
        "category": "cn-finance",
    },
    {
        "name": "华尔街见闻",
        "url": "https://rsshub.rssforever.com/wallstreetcn/live/global",
        "lang": "zh",
        "category": "cn-finance",
    },
    # ── Additional English Sources ───────────────────────────────
    {
        "name": "CNBC Tech",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
        "lang": "en",
        "category": "tech",
    },
    {
        "name": "WSJ Markets",
        "url": "https://feeds.a.dj.com/rss/RSSWSJD.xml",
        "lang": "en",
        "category": "markets",
    },
    {
        "name": "MarketWatch",
        "url": "https://feeds.marketwatch.com/marketwatch/topstories",
        "lang": "en",
        "category": "markets",
    },
    {
        "name": "Seeking Alpha",
        "url": "https://seekingalpha.com/market_currents.xml",
        "lang": "en",
        "category": "markets",
    },
    {
        "name": "Hacker News Best",
        "url": "https://hnrss.org/best",
        "lang": "en",
        "category": "tech",
    },
]

# Market keywords for classification
MARKET_KEYWORDS = {
    "A股": {
        "zh": ["A股", "沪深", "上证", "深证", "创业板", "科创板", "证监会", "央行", "降准", "降息", "LPR", "人民币", "中概股回归", "北向资金", "南向资金", "融资融券", "IPO", "注册制", "国资委", "国务院", "发改委", "财政部"],
        "en": ["A-share", "Shanghai", "Shenzhen", "ChiNext", "STAR Market", "CSRC", "PBOC", "RMB", "yuan", "onshore", "mainland China", "Chinese stocks"],
    },
    "港股": {
        "zh": ["港股", "恒生", "港交所", "南向", "北向", "H股", "红筹", "中资", "香港", "联系汇率"],
        "en": ["Hong Kong", "Hang Seng", "HKEX", "HSI", "HK stock", "HK market"],
    },
    "美股": {
        "zh": ["美股", "纳斯达克", "标普", "道琼斯", "美联储", "美债", "美元", "华尔街", "特斯拉", "苹果", "英伟达", "微软", "谷歌", "Meta", "亚马逊"],
        "en": ["Wall Street", "Nasdaq", "S&P 500", "Dow Jones", "Fed", "Federal Reserve", "Treasury", "US stock", "NYSE", "Apple", "Tesla", "Nvidia", "Microsoft", "Google", "Amazon", "Meta"],
    },
    "币圈": {
        "zh": ["比特币", "以太坊", "加密", "币圈", "区块链", "NFT", "DeFi", "Web3", "虚拟货币", "数字货币", "稳定币", "USDT", "交易所"],
        "en": ["Bitcoin", "BTC", "Ethereum", "ETH", "crypto", "blockchain", "NFT", "DeFi", "Web3", "stablecoin", "USDT", "Binance", "Coinbase", "altcoin", "token"],
    },
}

# Sentiment keywords
BULLISH_KEYWORDS = {
    "zh": ["利好", "上涨", "大涨", "暴涨", "突破", "新高", "反弹", "回暖", "利多", "看涨", "飙升", "强势", "增长", "超预期", "降息", "降准", "刺激", "提振", "支持", "扶持", "加码"],
    "en": ["rally", "surge", "soar", "bullish", "upgrade", "beat", "exceed", "growth", "record high", "breakout", "stimulus", "boost", "optimism", "recovery", "outperform", "gain"],
}

BEARISH_KEYWORDS = {
    "zh": ["利空", "下跌", "大跌", "暴跌", "崩盘", "新低", "回调", "跳水", "风险", "看跌", "衰退", "低迷", "萎缩", "不及预期", "加息", "收紧", "制裁", "关税", "贸易战", "退市", "暴雷", "违约", "恐慌"],
    "en": ["crash", "plunge", "tumble", "bearish", "downgrade", "miss", "decline", "recession", "sell-off", "selloff", "risk", "tariff", "sanctions", "default", "fear", "warning", "loss", "slump", "weak"],
}

# Source color mapping for UI
SOURCE_COLORS = {
    "CNBC": "#005594",
    "Wall Street Journal": "#000000",
    "CoinTelegraph": "#F7931A",
    "TechCrunch": "#0A9B0A",
    "The Verge": "#EA4C89",
    "Hacker News": "#FF6600",
    "Yahoo Finance": "#7B0099",
    "36氪": "#0088FF",
    "IT之家": "#D4213D",
    "少数派": "#D71A1B",
}
