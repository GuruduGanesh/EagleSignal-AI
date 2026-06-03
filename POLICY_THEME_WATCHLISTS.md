# Policy and Technology Theme Watchlists

These lists are research baskets, not buy recommendations. They are kept outside
`config/watchlist.yml` so strict watchlist mode does not waste runs on symbols
you did not explicitly choose.

The machine-readable version is `config/policy_theme_watchlists.yml`.

## Trump and Administration Policy Basket

Use this basket to monitor market impact from:

- White House statements, executive orders, and fact sheets
- Federal Register presidential documents
- Tariffs and export controls
- CHIPS Act / domestic manufacturing actions
- Defense, space, and shipbuilding procurement
- Nuclear, grid, and AI data-center power policy
- DOJ/FTC antitrust and regulatory actions
- Immigration/border/security contracting
- Sanctions and geopolitical policy

### Direct Trump Business

| Ticker | Company | Why it belongs |
|---|---|---|
| DJT | Trump Media & Technology Group | Direct public Trump-affiliated media/technology company; very headline-sensitive |

### Policy-Adjacent Public Stocks

| Ticker | Company | Theme |
|---|---|---|
| PLTR | Palantir Technologies | Defense AI and government software |
| BAH | Booz Allen Hamilton | Federal IT, defense consulting |
| LMT | Lockheed Martin | Defense procurement |
| RTX | RTX | Defense/aerospace |
| NOC | Northrop Grumman | Defense/space |
| GD | General Dynamics | Defense/shipbuilding |
| GE | GE Aerospace | Aerospace/defense engines |
| OKLO | Oklo | Nuclear power for AI/data centers |
| SMR | NuScale Power | Small modular nuclear reactors |
| CEG | Constellation Energy | Nuclear/power/data centers |
| VST | Vistra | Power/data centers |
| TSLA | Tesla | EV, energy, robotics, SpaceX adjacency |
| RKLB | Rocket Lab | Space launch/defense |
| LUNR | Intuitive Machines | Lunar/government space contracts |
| ASTS | AST SpaceMobile | Space communications |
| INTC | Intel | Domestic chips/CHIPS policy |
| AAPL | Apple | AI devices, supply chain, China/tariff exposure |
| MU | Micron Technology | Domestic memory/chips |
| NVDA | NVIDIA | AI GPUs/export controls |
| AMD | Advanced Micro Devices | AI GPUs/export controls |
| AVGO | Broadcom | AI networking/chips |
| MRVL | Marvell Technology | AI networking/custom silicon |
| QBTS | D-Wave Quantum | Quantum/AI compute, high-beta event risk |
| ORCL | Oracle | AI cloud/government |
| MSFT | Microsoft | AI cloud/government |
| AMZN | Amazon | Cloud/data centers/government |
| GOOGL | Alphabet | AI/cloud/policy |
| META | Meta Platforms | AI/data-center policy |
| DELL | Dell Technologies | AI servers |
| HPE | Hewlett Packard Enterprise | AI servers/networking |

Private companies such as Groq, SpaceX, Anduril, OpenAI, Anthropic, Vantage
Data Centers, and Hadrian can be used as context only unless a public proxy
exists. Groq has no public ticker/options chain, so it should inform AI
inference-chip context but must not create an active trade row.

## Additional Active AI Context Names

These requested public symbols are now active scoring targets in
`config/watchlist.yml`: AAPL, MRVL, and QBTS. Intel, Google/Alphabet, Microsoft,
Amazon, Meta, and Apple are represented by INTC, GOOGL, MSFT, AMZN, META, and
AAPL.

## Top 15 AI / GPU Compute / Storage / Chips / Robots / Space

| Rank | Ticker | Company | Main themes |
|---:|---|---|---|
| 1 | NVDA | NVIDIA | AI, GPU compute, chips |
| 2 | AMD | Advanced Micro Devices | AI, GPU compute, chips |
| 3 | AVGO | Broadcom | AI networking, chips |
| 4 | TSM | Taiwan Semiconductor Manufacturing | Semiconductor foundry |
| 5 | ASML | ASML Holding | Lithography, chip equipment |
| 6 | AMAT | Applied Materials | Chip equipment |
| 7 | LRCX | Lam Research | Chip equipment |
| 8 | MU | Micron Technology | Memory, AI storage |
| 9 | SMCI | Super Micro Computer | AI servers, GPU compute |
| 10 | DELL | Dell Technologies | AI servers, storage |
| 11 | HPE | Hewlett Packard Enterprise | AI servers, networking |
| 12 | WDC | Western Digital | Storage |
| 13 | TSLA | Tesla | Robotics, autonomous compute |
| 14 | ISRG | Intuitive Surgical | Robotics, medical automation |
| 15 | RKLB | Rocket Lab | Space, defense space |

## How To Use

1. Keep these lists as research baskets by default.
2. Copy only the symbols you want to score into `config/watchlist.yml`.
3. Let government/news/social feeds act as context for watched symbols.
4. Do not create predictions for every company mentioned in policy news.
5. Review `News & Evidence`, `Trends & Impact`, and `Manual Trades` tabs before trusting a signal.
