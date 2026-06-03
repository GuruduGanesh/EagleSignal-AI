# MARKET_FACTOR_CHECKLIST.md

## AI Prediction And Recommendation Factor Checklist

This is the required checklist for EagleSignal AI prediction and recommendation logic. It preserves the full analysis context so the system does not score a short-term equity, option, ETF, or index idea from only one narrow angle.

Scope rules:

- Analyze only explicit watchlist symbols as prediction candidates.
- Use related companies, sectors, indexes, government events, and global markets only as context unless they are also in the watchlist.
- Use public, legal, source-linked data only.
- Use real live, delayed, or historically downloaded data. Do not fabricate market data.
- Use `config/analysis_source_registry.yml` to decide source priority. Dashboards can monitor; official primary or licensed sources should verify important signals.
- Every final verdict must include bullish evidence, bearish evidence, confidence, risk, source links, and invalidation.

## Product Mapping

| Factor group | Main question | Current project mapping | Status |
|---|---|---|---|
| Company fundamentals | Is the business improving or weakening? | SEC/company facts, fundamentals score | Partial |
| Valuation | Is the stock too expensive or cheap for growth? | Fundamentals score, future ratio work | Partial |
| Macroeconomic | Is the broad market regime helping or hurting? | FRED/keyless macro, Treasury, BLS, VIX, dollar, oil | Partial-good |
| Government and policy | Are official actions changing expectations? | White House RSS, Federal Register, Treasury, BLS, FDA recalls, DOJ/FTC, GDELT policy | Partial-good |
| Geopolitical | Are global shocks changing risk appetite or supply chains? | GDELT/global context, future geopolitical engine | Partial |
| Sector and industry | Is the whole theme moving? | Watchlist tags, theme watchlists, sector/context evidence | Partial |
| Sentiment and psychology | Is crowd behavior changing short-term direction? | News sentiment, StockTwits/Reddit/Bluesky/Mastodon/X-token path | Partial |
| Technical analysis | What does price/volume structure say? | Technical indicators, patterns, Event Radar | Partial-good |
| Options market | What are options traders pricing? | yfinance options, CBOE fallback, Options Edge | Partial |
| Liquidity and structure | Can the idea be traded safely? | Market snapshot, options OI/volume, risk manager | Partial |
| Institutional flows | Are large funds/crowded trades involved? | 13F/Form 4 future work, ETF proxy future work | Missing-partial |
| Bonds, yields, credit | Are rates or credit stress affecting equities? | Treasury/yield proxies, VIX, macro regime | Partial |
| Currency | Is USD or FX exposure affecting earnings? | Dollar index proxy | Partial |
| Commodities | Are input costs or inflation-sensitive assets moving? | Oil proxy, future gold/copper/agriculture feeds | Partial |
| Global correlation | Are overseas markets confirming U.S. risk-on/risk-off? | Global markets and rolling correlations | Partial-good |
| News and events | What sudden catalyst changed expectations? | Multi-source news, SEC, government, Event Radar | Partial-good |
| Earnings calls | What did management say about the future? | Future transcript/calendar connector | Missing |
| Seasonal/calendar | Is timing increasing volatility or flows? | Options expiry DTE, future market calendar | Partial |
| Volatility and risk | Is market stress high? | VIX, expected move, risk manager | Partial-good |
| Alternative data | Is non-traditional demand data confirming the thesis? | Future Google Trends/job postings/app/web/credit-card sources | Missing |
| AI and technology | Is AI/cloud/GPU/storage/data-center demand affecting the thesis? | Watchlist tags, news/theme watchlists | Partial |
| Index factors | Is index weighting or ETF flow moving the name? | SPY/QQQ context, global/index snapshot | Partial |
| Black swan risk | Is an extreme unexpected event dominating normal signals? | News/government risk, future crisis detector | Partial |

## Source Verification Stack

Minimum daily stack:

```text
TradingView + Investing.com + Finviz + Reuters + SEC EDGAR + BLS/BEA/FRED + Cboe
```

How to use it:

- TradingView, Investing.com, Finviz, and Koyfin are excellent monitoring/research dashboards, but high-confidence recommendations should verify market-moving facts from official primary or licensed sources.
- SEC EDGAR is the primary source for filings, company facts, 8-Ks, 10-Qs, 10-Ks, S-1s, and Form 4 insider filings.
- BLS, BEA, Census, FRED, Treasury, Federal Reserve, EIA, OFAC, Federal Register, Congress.gov, and White House sources are the preferred official sources for macro/government/policy factors.
- Cboe is the preferred source for VIX, put/call, and market-wide options statistics where available.
- Reuters, Bloomberg, CNBC, MarketWatch, WSJ/Barron's, The Fly, Benzinga Pro, Briefing.com, and Seeking Alpha can support news flow, but paid/paywalled sources require licensed access and opinion/rumor items must be confirmed.
- X/Twitter, Substack, Reddit, StockTwits, Bluesky, Mastodon, and forums are sentiment/context only unless the item links back to a reliable primary source.

## 1. Company Fundamentals

| Parameter | Impact | Required treatment |
|---|---|---|
| Revenue growth | Higher revenue usually supports higher stock price. | Pull latest filings, earnings releases, and growth trend. |
| Profit / net income | Strong profits increase investor confidence. | Track profitability and margin direction. |
| EPS - Earnings Per Share | One of the most watched valuation metrics. | Compare actual EPS, expected EPS, and surprise. |
| Profit margins | Shows pricing power and operating efficiency. | Track gross, operating, and net margin. |
| Free cash flow | Important for long-term company strength. | Add FCF and FCF yield where filings allow. |
| Debt level | High debt increases risk, especially when rates rise. | Include leverage and interest coverage risk. |
| Cash reserves | More cash gives safety and flexibility. | Add cash runway and balance-sheet cushion. |
| Guidance | Management forecast can dominate short-term movement. | Ingest guidance from earnings releases/transcripts. |
| Earnings surprise | Beats/misses can move stocks sharply. | Compare reported numbers vs consensus when available. |
| Dividend | Stable or rising dividends can attract investors. | Track dividend stability and ex-dividend dates. |
| Share buybacks | Buybacks reduce share count and can increase EPS. | Detect buyback authorizations and execution. |
| Insider buying/selling | Can affect confidence. | Parse Form 4 trends; treat contextually, not as certainty. |
| Management quality | CEO/CFO decisions affect value. | Track leadership changes, guidance reliability, major strategic decisions. |
| Corporate governance | Weak governance creates risk. | Flag accounting issues, board disputes, restatements, investigations. |

## 2. Valuation Factors

| Parameter | Impact | Required treatment |
|---|---|---|
| P/E ratio | Measures price compared to earnings. | Compute trailing and sector-relative valuation. |
| Forward P/E | Based on expected future earnings. | Add licensed estimates when available. |
| PEG ratio | Compares valuation with growth. | Use only when growth estimate is reliable. |
| Price-to-sales | Useful for growth companies. | Compare to own history and peers. |
| Price-to-book | Useful for banks and asset-heavy companies. | Apply only where meaningful. |
| EV/EBITDA | Common for company comparisons. | Add enterprise-value calculations. |
| Market cap | Large, mid, and small caps behave differently. | Include size/liquidity regime. |
| Intrinsic value | If price is above fair value, downside risk rises. | Future DCF/scenario model, never a single certainty. |
| Analyst target price | Can influence market expectations. | Add licensed analyst revisions/targets if available. |

## 3. Macroeconomic Factors

| Parameter | Impact | Required treatment |
|---|---|---|
| Interest rates | Higher rates usually pressure stocks. | Track 2Y, 10Y, and 30Y yields. |
| Federal Reserve policy | Decisions and speeches move markets. | Add Fed calendar, statements, minutes, speeches. |
| Inflation | High inflation hurts margins and valuation multiples. | Track CPI, PPI, PCE, commodities, wage inflation. |
| CPI data | Major inflation report. | Add release calendar and surprise-vs-consensus. |
| PPI data | Shows producer cost pressure. | Add BLS PPI connector. |
| GDP growth | Strong GDP supports earnings. | Add BEA GDP connector. |
| Recession risk | Raises selling pressure. | Combine yield curve, credit, unemployment, breadth. |
| Unemployment rate | Affects economy and Fed decisions. | Already tracked partially via BLS/FRED. |
| Jobless claims | Shows labor market strength/weakness. | Add DOL claims feed. |
| Consumer spending | Important for retail, tech, travel, housing. | Add BEA/card-spend licensed sources if available. |
| Wage growth | Can raise inflation and company costs. | Add BLS wage series. |
| Manufacturing data | Impacts industrial/cyclical stocks. | Add ISM/PMI source where licensed. |
| Services data | Important because services dominate the U.S. economy. | Add ISM services source where licensed. |

## 4. Government And Policy Factors

This includes Trump/admin policy clues when they are public, legal, and source-linked.

| Parameter | Impact | Required treatment |
|---|---|---|
| Tax policy | Corporate tax changes affect profits. | Track White House, Congress, Treasury, IRS, CBO/JCT. |
| Government spending | Benefits defense, infrastructure, healthcare, energy. | Add USAspending, SAM.gov, DOD awards. |
| Regulations | Can help or hurt sectors. | Track Federal Register and agency actions. |
| Antitrust action | Major risk for large tech. | DOJ/FTC connector already partial. |
| SEC rules | Affects disclosure, trading, crypto, ETFs. | Add SEC rulemaking feed. |
| Tariffs | Impact import/export companies. | Track White House, USTR, Commerce/BIS. |
| Trade policy | Affects global companies. | Add export controls, sanctions, trade agreements. |
| Subsidies | Benefit EV, chips, clean energy, defense. | Track CHIPS, IRA, DOE/DOD grants and contracts. |
| Budget deficit | Can affect yields and confidence. | Treasury FiscalData already partial. |
| Government shutdown risk | Creates uncertainty. | Track Congress/OMB news. |
| Election results | Shift sector expectations. | Use official sources and sector mapping. |

## 5. Geopolitical Factors

| Parameter | Impact | Required treatment |
|---|---|---|
| War or military conflict | Raises uncertainty; can lift defense/oil. | Map affected sectors and defense/energy tickers. |
| Sanctions | Hurt companies exposed to affected countries. | Add OFAC/State/Commerce feeds. |
| U.S.-China tensions | Impacts chips, tech, manufacturing. | Important for NVDA, AMD, TSM, ASML, AMAT, LRCX. |
| Middle East tensions | Often affect oil prices. | Link to WTI, VIX, defense, airlines, shipping. |
| Russia/Ukraine developments | Affect energy, defense, agriculture. | Track official and reputable global sources. |
| Taiwan risk | Major semiconductor supply-chain risk. | Link to TSM, NVDA, AMD, ASML, AMAT, LRCX. |
| Global trade disruptions | Affect shipping, manufacturing, inflation. | Track ports, shipping, logistics, commodity impact. |
| Currency instability | Affects multinationals. | Link to dollar index and foreign revenue exposure. |

## 6. Sector And Industry Trends

| Parameter | Impact | Required treatment |
|---|---|---|
| Sector rotation | Money moves between sectors. | Add sector ETF relative-strength engine. |
| Industry growth | Growing industries receive higher valuations. | Track AI, chips, storage, robotics, space, nuclear power themes. |
| Competitive pressure | New competitors can hurt margins. | Add peer/supply-chain graph. |
| Pricing power | Supports profits. | Track margins, commentary, price actions. |
| Supply-chain strength | Shortages/delays hurt revenue. | Track supplier/customer evidence. |
| Commodity dependency | Input cost changes affect margins. | Link relevant commodities to sector. |
| Technology disruption | Creates or destroys leaders. | Track AI/cloud/GPU/robotics breakthroughs. |
| Regulatory pressure by sector | Healthcare, banking, energy, and big tech are sensitive. | Government-impact mapper must attach only relevant events. |

## 7. Market Sentiment And Psychology

| Parameter | Impact | Required treatment |
|---|---|---|
| Fear and greed | Drives short-term buying/selling. | Add sentiment and volatility regime. |
| Investor confidence | High confidence lifts markets. | Combine breadth, VIX, news tone, flows. |
| Panic selling | Causes sharp declines. | Detect breakdowns, volume spikes, negative news clusters. |
| FOMO buying | Pushes price quickly higher. | Event Radar breakout/exhaustion helps detect. |
| Retail investor activity | Moves meme and small-cap stocks. | StockTwits/Reddit/Bluesky/Mastodon/X when legal. |
| Social media sentiment | Can affect momentum. | Use source-linked public/legal data; cap influence. |
| News headlines | Cause immediate reactions. | Multi-source news merge and evidence polarity. |
| Rumors | Can create temporary moves. | Classify as rumor unless confirmed by official/reliable sources. |
| Market narratives | AI, rate cuts, recession, soft landing, etc. | Track narrative tags and trend direction. |

## 8. Technical Analysis Factors

| Parameter | Impact | Required treatment |
|---|---|---|
| Support level | Area where buyers may enter. | Add support/resistance engine. |
| Resistance level | Area where sellers may appear. | Add breakout/breakdown detection. |
| Moving averages | 50D and 200D are heavily watched. | Already partial in technicals and Event Radar. |
| RSI | Shows overbought/oversold. | Expose in confidence trace. |
| MACD | Momentum indicator. | Expose in confidence trace. |
| Volume | Confirms strength/weakness. | Event Radar and market snapshot use volume. |
| Breakout | Price moving above resistance. | Event Radar breakout score. |
| Breakdown | Price falling below support. | Add bearish breakdown score. |
| Trend lines | Shows direction. | Future technical enhancement. |
| Gap up / gap down | Often caused by news/earnings. | Add premarket/open gap detector. |
| VWAP | Important for intraday traders. | Add intraday provider and VWAP engine. |
| Relative strength | Shows stock vs market. | Add sector/index relative-strength score. |

## 9. Options Market Impact

| Parameter | Impact | Required treatment |
|---|---|---|
| Implied volatility | Higher IV means higher expected movement. | Options Edge shows IV, IV/RV, and data-dependent IV rank/percentile. |
| Options volume | Shows trader interest. | Collected where provider supports it. |
| Open interest | Shows where large positions exist. | Options Edge shows OI. |
| Put/call ratio | Measures bearish vs bullish positioning. | Options Edge shows P/C. |
| Gamma exposure | Dealer hedging can amplify moves. | Add licensed/options vendor source for market-wide gamma exposure. |
| Delta hedging | Market makers hedge by trading shares. | Approximate contract Greeks exist; add dealer exposure model. |
| Max pain | Context only, low confidence. | Add only as optional low-weight feature. |
| Expiration date | Weekly/monthly expiry can raise volatility. | Options Edge scores DTE/expiry. |
| Unusual options activity | May signal institutional positioning. | Chain-derived unusual activity and OI-change are implemented; add paid institutional flow vendor for stronger confirmation. |
| Short-dated options | Can cause fast intraday moves. | Add 0DTE/weekly risk warnings. |

## 10. Liquidity And Market Structure

| Parameter | Impact | Required treatment |
|---|---|---|
| Trading volume | Low volume can cause sharp moves. | Market snapshot and risk manager. |
| Bid-ask spread | Wider spread raises trading cost. | Add spread filter for options/contracts. |
| Institutional ownership | Big funds can stabilize or move stocks. | Add 13F/ownership source. |
| ETF ownership | ETF flows can move related stocks. | Add ETF holdings/flows. |
| Index inclusion | Joining an index can lift demand. | Add index event calendar. |
| Index removal | Can cause forced selling. | Add index event calendar. |
| Passive fund flows | Index funds buy/sell automatically. | Add ETF/index flow proxies. |
| Dark pool activity | Off-exchange activity can affect liquidity. | Add legal vendor only if available. |
| Market maker activity | Affects short-term liquidity. | Add options market-structure model. |
| Circuit breakers | Stop trading during extreme volatility. | Add halt/circuit-breaker alerts. |

## 11. Institutional And Fund Flows

| Parameter | Impact | Required treatment |
|---|---|---|
| Hedge fund positioning | Can create crowded trades. | Add 13F and licensed positioning data if available. |
| Mutual fund flows | Inflows support; outflows pressure. | Add fund-flow source. |
| Pension fund rebalancing | Can cause month/quarter-end moves. | Calendar model. |
| ETF inflows/outflows | Strongly affect sectors and indexes. | Add ETF flow provider. |
| 13F filings | Reveal holdings with delay. | Add parser and lag warning. |
| Analyst upgrades/downgrades | Can trigger fund buying/selling. | Add licensed analyst feed. |
| Short interest | Can lead to short squeeze. | Add Nasdaq/FINRA/market-data source. |
| Margin debt | High leverage increases crash risk. | Add FINRA margin debt macro feature. |
| Forced liquidation | Selling due to margin calls. | Detect via price/volume/liquidity stress proxy. |

## 12. Bonds, Yields, And Credit Markets

| Parameter | Impact | Required treatment |
|---|---|---|
| 10-year Treasury yield | Higher yield usually pressures growth stocks. | Keyless macro tracks proxy/FRED where available. |
| 2-year Treasury yield | Reflects Fed expectations. | Add direct 2Y feed or proxy. |
| Yield curve | Inversion can signal recession risk. | Compute 10Y-2Y and 10Y-3M. |
| Credit spreads | Wider spreads show rising default risk. | Add FRED/ICE BofA credit spreads. |
| Corporate bond market | Weakness can hurt stocks. | Add credit ETF/proxy. |
| Mortgage rates | Affect housing and consumer spending. | Add FRED mortgage series. |
| Dollar liquidity | Tight liquidity pressures risk assets. | Add Fed balance sheet/liquidity proxies. |

## 13. Currency Impact

| Parameter | Impact | Required treatment |
|---|---|---|
| U.S. dollar strength | Can hurt U.S. exporters. | Dollar index proxy exists in keyless macro. |
| Foreign exchange rates | Affect international revenue. | Add company revenue exposure mapping. |
| Emerging market currencies | Can affect global risk sentiment. | Add EM FX proxy. |
| Currency hedging | Impacts earnings for global companies. | Future filing/transcript extraction. |

## 14. Commodity Prices

| Parameter | Impact | Required treatment |
|---|---|---|
| Oil prices | Affects energy, airlines, transport, inflation. | WTI proxy exists in keyless macro. |
| Natural gas | Affects utilities, chemicals, energy. | Add gas feed. |
| Gold | Safe-haven and inflation signal. | Add gold proxy. |
| Copper | Economic growth indicator. | Add copper proxy. |
| Steel/aluminum | Important for industrials and autos. | Add metals feeds. |
| Lithium | Important for EV and batteries. | Add lithium source where available. |
| Wheat/corn/soybeans | Affects food inflation and agriculture. | Add agriculture futures/proxies. |

## 15. Global Market Correlation

| Parameter | Impact | Required treatment |
|---|---|---|
| European markets | Can influence U.S. premarket. | Global markets snapshot exists. |
| Asian markets | Affect overnight sentiment. | Global markets snapshot exists. |
| China economy | Impacts commodities, tech, luxury, industrials. | Add China macro/ETF proxies. |
| Japan rates/currency | Can affect global liquidity. | Add BOJ/yield/JPY context. |
| Emerging markets | Risk-on/risk-off signal. | Add EM ETF/index proxies. |
| Global central banks | ECB/BOJ/PBOC affect liquidity. | Add central-bank calendar/news. |
| Global recession risk | Pressures multinational earnings. | Combine global breadth, PMIs, credit, commodities. |

## 16. News And Event-Driven Factors

| Parameter | Impact | Required treatment |
|---|---|---|
| Earnings reports | Biggest scheduled stock catalyst. | Add earnings calendar and actual-vs-estimate. |
| Product launches | Important for tech, pharma, consumer. | Add company IR and press releases. |
| Mergers and acquisitions | Target stock usually rises. | Add M&A news classifier. |
| Lawsuits | Legal risk can reduce valuation. | Add legal/regulatory news classifier. |
| FDA approval/rejection | Huge for biotech/pharma. | Add FDA approvals/CRLs, not only recalls. |
| Cybersecurity breaches | Can damage trust and create costs. | Add cyber incident classifier. |
| Executive resignations | Creates uncertainty. | Parse 8-K and company releases. |
| Accounting issues | Very negative for stock confidence. | Parse filings/restatements/auditor changes. |
| Bankruptcy risk | Can crash stock price. | Add distress signals and filings. |
| Credit rating downgrade | Increases borrowing cost. | Add rating agency/credit source if licensed. |
| New contracts | Can increase revenue expectations. | Add SAM.gov/DOD/USAspending/company PR. |
| Customer wins/losses | Important for SaaS, defense, suppliers. | Add customer/supplier relationship graph. |

## 17. Earnings Call Details

| Parameter | Impact | Required treatment |
|---|---|---|
| Revenue beat/miss | Direct impact. | Add consensus source. |
| EPS beat/miss | Direct impact. | Add consensus source. |
| Forward guidance | Often more important than past results. | Extract guidance changes. |
| Margin guidance | Shows future profitability. | Extract margin language. |
| Demand commentary | Shows business strength. | Extract demand tone. |
| Inventory levels | Important for retail, semis, autos. | Track inventory and management comments. |
| Capex plans | Shows investment or cost pressure. | Critical for AI/data-center supply chain. |
| AI spending / cloud spending | Very important for tech stocks. | Track hyperscaler capex and supplier impact. |
| Customer growth | Important for SaaS/subscription companies. | Extract customer metrics. |
| Churn rate | High churn hurts valuation. | Extract from filings/transcripts. |

## 18. Seasonal And Calendar Effects

| Parameter | Impact | Required treatment |
|---|---|---|
| January effect | Small caps sometimes perform well early year. | Add seasonal calendar context. |
| Earnings season | Higher volatility. | Add earnings window flag. |
| Options expiration week | Can increase market movement. | Options Edge uses DTE; add OpEx risk. |
| Month-end rebalancing | Fund flows can move indexes. | Calendar model. |
| Quarter-end window dressing | Funds adjust holdings. | Calendar model. |
| Tax-loss harvesting | Weak stocks may sell near year-end. | Calendar model. |
| Holiday trading | Lower liquidity can increase volatility. | Market calendar/liquidity warning. |
| Sell in May narrative | Seasonal sentiment factor. | Low-weight context only. |

## 19. Risk And Volatility Indicators

| Parameter | Impact | Required treatment |
|---|---|---|
| VIX | Measures expected S&P 500 volatility. | Keyless macro tracks VIX. |
| VVIX | Volatility of volatility. | Add source. |
| MOVE index | Bond market volatility. | Add source if available. |
| Fear/greed indicators | Sentiment signal. | Add computed internal proxy. |
| Market breadth | Shows how many stocks participate. | Add breadth source/proxy. |
| Advance/decline line | Measures internal market strength. | Add breadth source. |
| New highs/new lows | Shows trend health. | Add breadth source. |
| Put/call ratio | Sentiment and hedging indicator. | Options Edge partial at ticker level; add index level. |

## 20. Alternative Data

Alternative data is useful only when legal, source-compliant, and labeled clearly.

| Parameter | Impact | Required treatment |
|---|---|---|
| Web traffic | Indicates customer interest. | Add licensed/public compliant source. |
| App downloads | Important for consumer tech. | Add legal source. |
| Credit card spending data | Shows real-time sales trends. | Licensed source only. |
| Satellite data | Oil, retail parking, shipping. | Licensed source only. |
| Job postings | Shows expansion or slowdown. | Add company job-posting trend where allowed. |
| Google Trends | Measures public interest. | Add public trend source if terms allow. |
| Social media mentions | Sentiment and momentum signal. | Current public/legal sentiment stack, capped. |
| Supply-chain data | Shows production/demand strength. | Add supplier/customer graph and import/shipping data. |
| Shipping/import data | Useful for retail/manufacturing. | Add public/customs/shipping sources where allowed. |
| Insider transactions | Shows management confidence/caution. | Parse Form 4 trends. |

## 21. AI And Technology-Specific Factors

| Parameter | Impact | Required treatment |
|---|---|---|
| AI adoption | Can increase growth expectations. | Track AI narrative and customer wins. |
| Cloud revenue | Key for MSFT, AMZN, GOOGL, ORCL. | Extract cloud growth and guidance. |
| GPU demand | Important for NVIDIA, AMD, semiconductor supply chain. | Track hyperscaler capex, export controls, supply chain. |
| Data-center spending | Impacts chips, utilities, real estate. | Track capex, power, nuclear/utilities, server/storage names. |
| Cybersecurity demand | Impacts security companies. | Future basket/source. |
| Automation trends | Can boost software companies. | Track robotics and automation news. |
| AI regulation | Can affect big tech and startups. | Government/policy mapper. |
| Energy demand from AI | Impacts utilities and infrastructure. | Track OKLO, SMR, CEG, VST and grid/power policy. |

## 22. Index-Level Factors

| Parameter | Impact | Required treatment |
|---|---|---|
| Mega-cap concentration | Few big stocks can move entire index. | Add index concentration view. |
| Index weighting | Mega caps heavily affect indexes. | Add holdings/weights source. |
| Sector weights | Tech-heavy indexes react differently. | Add sector exposure. |
| ETF flows | SPY, QQQ, IWM flows impact indexes. | Add ETF flow source. |
| Futures market | Premarket direction signal. | Add futures or ETF premarket proxy. |
| Rebalancing | Index changes affect buying/selling. | Add rebalance calendar. |
| Market breadth | Healthy rally needs many stocks participating. | Add breadth metrics. |

## 23. Black Swan And Unexpected Events

| Parameter | Impact | Required treatment |
|---|---|---|
| Pandemic | Can crash or transform markets. | Crisis classifier and official source monitoring. |
| Terror attack | Causes sudden risk-off moves. | Official/reputable breaking-news monitoring. |
| Banking crisis | Hits financials and credit. | Credit spreads, bank news, Fed/Treasury/FDIC feeds. |
| Flash crash | Technical/liquidity-driven crash. | Intraday market-structure alerts. |
| Natural disasters | Affect insurance, energy, supply chains. | FEMA/NOAA/news source mapping. |
| Major cyberattack | Can hit affected companies and sectors. | Cyber incident classifier. |
| Political crisis | Raises uncertainty. | White House/Congress/Federal Register/news mapping. |
| Sovereign debt crisis | Affects global markets. | Global credit/FX/rates monitoring. |

## Required Output Mapping

Every scored ticker should eventually expose these checklist outputs:

| Output field | Meaning |
|---|---|
| `factor_coverage` | Which of the 23 factor groups were available for this ticker today. |
| `missing_factor_groups` | Important factor groups that could not be checked. |
| `bullish_factor_groups` | Factor groups supporting upside/call thesis. |
| `bearish_factor_groups` | Factor groups supporting downside/put thesis. |
| `blocked_factor_groups` | Factor groups that block or reduce confidence because source data is stale, missing, or unreliable. |
| `factor_confidence_adjustment` | Confidence increase/decrease caused by coverage, freshness, agreement, or conflict. |
| `trace_links` | Source links proving why each important factor affected the verdict. |

## Immediate Engineering Gap List

1. Add a factor-coverage auditor that maps every `PredictionResult` to the 23 groups above.
2. Add source freshness gates so stale or missing critical factors lower confidence automatically.
3. Add earnings calendar, earnings-call transcript, guidance, and analyst-revision connectors.
4. Expand options market structure with paid gamma exposure, institutional unusual-flow/OI-change vendors, and full every-strike historical option-chain storage. Approximate Greeks, IV Rank, skew, term structure, chain-derived unusual activity, and snapshot OI-change are already implemented.
5. Add Fed, BEA, PPI, JOLTS, jobless claims, EIA, OFAC, Commerce/BIS, DOD/SAM.gov/USAspending, Congress.gov connectors.
6. Add sector ETF relative strength, market breadth, ETF flows, short interest, and 13F/institutional ownership.
7. Add intraday VWAP, gap, opening range, spread/liquidity, and halt/circuit-breaker logic.
8. Add outcome tracking by factor group so the system learns which factors helped or hurt short-term options predictions.
