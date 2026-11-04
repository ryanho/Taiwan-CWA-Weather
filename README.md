<h1 align="left">
  <img src="logo.jpeg" alt="" width="56" align="center" />
  &nbsp;Taiwan CWA Weather
</h1>

<p align="left">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=puyanlin&repository=Taiwan-CWA-Weather&category=integration"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store."/></a>
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="hacs_badge"/></a>
</p>

A Home Assistant custom integration for Taiwan Central Weather Administration (中央氣象署, CWA) weather data.  
台灣中央氣象署天氣資料的 Home Assistant 自訂整合。

---

## Why Taiwan CWA? / 為什麼選台灣中央氣象署？

Taiwan is an independent island nation sitting at the intersection of the Pacific Ocean, East China Sea, and South China Sea. Its dramatic terrain — from steep mountain ranges exceeding 3,000m to low-lying coastal plains — combined with seasonal monsoons and typhoon tracks creates one of the most meteorologically complex environments in the world within a relatively small land area. Taiwan's Central Weather Administration (CWA) maintains dedicated forecast infrastructure and observational networks specifically calibrated for these conditions.  
台灣是一個獨立的島國，位處太平洋、東海與南海交界，境內地形從逾3000公尺的高山到低地平原兼具，加上季風與颱風路徑的交互影響，使這片小小的國土擁有全球少見的複雜氣象環境。台灣中央氣象署（CWA）維運專屬預報模型與觀測網路，針對這些在地條件精準調校。

## Taiwan's Rain Probability — What Makes It Different / 台灣降雨機率的特別之處

**CWA's definition (and why it matters):**  
CWA defines "rain probability" as the probability that **precipitation ≥ 0.1mm will occur** at any point in a given area during a 12-hour forecast period. This is fundamentally different from what many international weather apps report.  

**CWA 的定義（為何重要）：**  
中央氣象署的「降雨機率」定義為：預報區域在特定 **12 小時時段內，出現 ≥0.1mm 降水的機率**。這與多數國際天氣 App 的計算方式有本質差異。

Key characteristics / 關鍵特性：
- Reported in **10% increments** (10%, 20% … 90%) — you will never see 37% / 以**十分進位**呈現（10%、20%…90%），不會出現 37% 這種數字
- Does **not** indicate duration, intensity, or spatial coverage of rain / **不代表**下雨時間長短、雨量大小或降雨範圍
- "30% chance of rain" = 30% probability that rain occurs at all, not "rain 30% of the time" / 「降雨機率 30%」= 有下雨這件事發生的機率為 30%，而非「30% 的時間會下雨」
- Daily and twice-daily forecasts use 12-hour probabilities; the hourly forecast uses CWA's 3-hour probabilities / 每天與一天兩次的預報使用 12 小時降雨機率，每小時預報使用 3 小時降雨機率

**Why different apps show different numbers / 為什麼不同 App 數字差很多：**
1. **Different models** — CWA uses proprietary statistical models + WRF; international apps use ECMWF, GFS, or Dark Sky nowcasting / 模型不同：CWA 用自家統計＋WRF；國際 App 用 ECMWF、GFS 等
2. **Different definitions** — some apps report "probability of rain in any given hour," others report "probability at a specific point" / 定義不同：有些算每小時任一點的機率，有些算特定地點的機率
3. **Nowcasting vs. probabilistic forecast** — radar extrapolation (0–2 hr) and probabilistic models are completely different techniques / 雷達外推（0–2 小時）與機率預報是完全不同的技術

> **For Taiwanese users, CWA's probability is the standard reference because it is calculated specifically for Taiwan's geography and aligns with how rain probability is communicated in local media and daily life.**  
> **對台灣用戶而言，CWA 的降雨機率是標準參考值，因為它針對台灣地理條件計算，也與本地媒體及日常生活慣用的表達方式一致。**

Reference: [CWA QPF documentation](https://www.cwa.gov.tw/V8/C/P/QPF.html) · [Meteorological verification metrics](https://nhess.copernicus.org/articles/22/23/2022/)

---

## Features / 功能

- A weather service for a Home Assistant zone (your home by default), like Open-Meteo / 為 Home Assistant 區域（預設為首頁）提供天氣服務，使用方式與 Open-Meteo 相同
- Current conditions from the nearest CWA observation station, updated every 10 minutes / 目前天氣取自最近的中央氣象署觀測站，每 10 分鐘更新
- Township-level forecasts: 7-day daily, twice-daily (day/night) and hourly / 鄉鎮層級預報：7 天每日、一天兩次（白天／夜晚）與每小時
- The nearest township and station are chosen automatically from the zone's coordinates / 依區域座標自動選擇最近的鄉鎮與測站
- English and Traditional Chinese, following Home Assistant's language / 依 Home Assistant 語言顯示英文或繁體中文

---

## Installation via HACS / 透過 HACS 安裝

### One-click / 一鍵安裝

Click the button below to open HACS and add this repository automatically.  
點擊下方按鈕，HA 會自動打開 HACS 安裝對話框。

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=puyanlin&repository=Taiwan-CWA-Weather&category=integration)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

### Manual HACS / 手動 HACS

1. Open HACS → Integrations / 開啟 HACS → 整合
2. Click the three-dot menu → Custom Repositories / 點選右上角三點選單 → 自訂存放庫
3. Enter URL: `https://github.com/puyanlin/Taiwan-CWA-Weather` / 輸入上方網址
4. Category: Integration / 類別選「整合」
5. Click Add, then find and download "Taiwan CWA Weather" / 點新增，找到後下載
6. Restart Home Assistant / 重啟 Home Assistant

### Manual / 手動安裝

Copy `custom_components/taiwan_cwa/` to your HA `config/custom_components/` folder, then restart.  
將 `custom_components/taiwan_cwa/` 複製到 HA 的 `config/custom_components/` 後重啟。

---

## Configuration / 設定

After installation, go to **Settings → Devices & services → Add integration** and search for **Taiwan CWA Weather**.  
安裝後前往 **設定 → 裝置與服務 → 新增整合**，搜尋 **Taiwan CWA Weather**。

You will need: / 需要填入：
- **CWA API key** — get it free at [opendata.cwa.gov.tw](https://opendata.cwa.gov.tw/) / 免費申請
- **Zone / 區域** — defaults to Home; add the integration again for other zones / 預設為首頁，其他區域可重複新增

Setup finds the nearest of Taiwan's 368 forecast townships and picks up to three observation stations: the nearest ones, skipping expressway stations (`CA…`) when another station is within 10 km, and — for the home zone — stations more than 300 m higher or lower than your configured elevation. The extra stations are used when the first one is not reporting.  
設定時會從全台 368 個預報鄉鎮中找出最近者，並挑選最多三個觀測站：依距離排序；10 公里內有其他測站時略過國道測站（`CA…`）；首頁區域另會略過與 HA 設定海拔相差超過 300 公尺的測站。第一個測站沒有資料時會改用後面的備援測站。

**Options / 選項:** choose a station manually from the ten nearest, or pick the township and stations again. If the zone moves, this happens automatically on the next reload.  
可從最近的十個測站中手動指定，或重新選擇鄉鎮與測站。區域位置變更後，下次重新載入時也會自動重新選擇。

### Upgrading from 1.x / 從 1.x 升級

2.0 follows a zone instead of a list of cities, so 1.x settings cannot be reused. After updating, delete Taiwan CWA Weather under Settings → Devices & services and add it again. Entity IDs change.  
2.0 改為依區域提供天氣，無法沿用 1.x 的縣市設定。更新後請到「設定 → 裝置與服務」刪除 Taiwan CWA Weather 再重新新增，entity ID 也會改變。

---

## Entities / 實體

Entity IDs are based on the zone: `zone.home` → `weather.taiwan_cwa_home`, `sensor.taiwan_cwa_home_*`.  
Entity ID 依區域命名：`zone.home` → `weather.taiwan_cwa_home`、`sensor.taiwan_cwa_home_*`。

### Weather / 天氣實體

| Value / 項目 | Source / 來源 |
|---|---|
| Temperature, humidity, pressure, wind, gusts / 氣溫、濕度、氣壓、風、陣風 | Observation station / 觀測測站 |
| Apparent temperature, dew point / 體感溫度、露點 | Hourly forecast / 每小時預報 |
| UV index / 紫外線指數 | 12-hour forecast (daytime) / 12 小時預報（白天） |
| Condition / 天氣狀況 | Station sky cover, or the forecast when rain or thunderstorms are forecast for the current 3 hours (stations rarely report rain) / 測站雲量；若目前 3 小時預報有雨或雷雨則改用預報（測站鮮少回報降雨） |

Forecasts / 預報:
- **Daily / 每天** — 7 days; a day's day and night periods combined / 7 天，合併當天白天與夜晚時段
- **Twice daily / 一天兩次** — 14 day/night periods / 14 個白天／夜晚時段
- **Hourly / 每小時** — about 3 days; hourly at first, then every 3 hours / 約 3 天，前段每小時、之後每 3 小時

If the station is unreachable, temperature, humidity and wind fall back to the hourly forecast. The more-info dialog's attribution names the station and township in use.  
測站無法取得資料時，氣溫、濕度與風會改用每小時預報。詳細資訊視窗底部的資料來源會顯示目前使用的測站與鄉鎮。

### Sensors / 感應器

| Entity ID | Default | Description | 說明 |
|---|:-:|---|---|
| `sensor.taiwan_cwa_home_temperature` | ✅ | Temperature | 氣溫 |
| `sensor.taiwan_cwa_home_humidity` | ✅ | Humidity | 濕度 |
| `sensor.taiwan_cwa_home_precipitation` | ✅ | Precipitation since midnight | 今日累積雨量 |
| `sensor.taiwan_cwa_home_station` | ✅ | Observation station (diagnostic) | 觀測測站（診斷） |
| `sensor.taiwan_cwa_home_pressure` | | Pressure | 氣壓 |
| `sensor.taiwan_cwa_home_wind_speed` | | Wind speed | 風速 |
| `sensor.taiwan_cwa_home_wind_direction` | | Wind direction (°; unknown when calm or variable) | 風向（度；靜風或風向不定時為未知） |
| `sensor.taiwan_cwa_home_today_high` | | Today's high | 今日最高溫 |
| `sensor.taiwan_cwa_home_today_low` | | Today's low | 今日最低溫 |
| `sensor.taiwan_cwa_home_apparent_temperature` | | Apparent temperature (forecast) | 體感溫度（預報） |
| `sensor.taiwan_cwa_home_uv_index` | | UV index (forecast) | 紫外線指數（預報） |
| `sensor.taiwan_cwa_home_rain_probability` | | Rain probability, current 3 hours | 降雨機率（目前 3 小時） |
| `sensor.taiwan_cwa_home_weather_code` | | Weather, as a CWA weather code | 天氣現象（中央氣象署天氣代碼） |

Sensors without ✅ are disabled by default; enable them from the entity settings.  
未標示 ✅ 的感應器預設停用，可於實體設定中啟用。

The station sensor shows the station name, with its ID, altitude, distance, observation time, whether it is a fallback, and the forecast township as attributes.  
觀測測站感應器顯示測站名稱，屬性包含測站代碼、海拔、距離、觀測時間、是否為備援測站，以及預報鄉鎮。

### Languages / 語言

Entity names follow Home Assistant's system language: Traditional Chinese (`zh-Hant`), otherwise English. Weather conditions and the weather code sensor's states follow each user's own language. Station and township names are Chinese only, as CWA publishes them.  
實體名稱依 Home Assistant 系統語言顯示：繁體中文（`zh-Hant`）顯示中文，其他語言顯示英文。天氣狀況與天氣現象感應器的狀態依各使用者的介面語言顯示。測站與鄉鎮名稱由中央氣象署提供，僅有中文。

---

## Coverage / 涵蓋範圍

All of Taiwan including Penghu, Kinmen and Matsu: 22 cities and counties, 368 townships. Locations more than 50 km from any township (for example Pratas Island) are not supported.  
台灣本島與澎湖、金門、馬祖：22 縣市、368 個鄉鎮。距離任何鄉鎮超過 50 公里的地點（例如東沙島）不支援。

---

## Notes / 注意事項

- CWA's SSL certificate is missing the Subject Key Identifier extension, which Python 3.13's strict verification rejects. This integration keeps full TLS verification (signature chain, host name, expiry and trust anchor) and only relaxes that one pedantic RFC extension check, so the API key is never sent over an unverified connection.  
  CWA 官方 API 的 SSL 憑證缺少 Subject Key Identifier，會被 Python 3.13 的嚴格驗證擋下。本整合仍完整驗證 TLS（簽章鏈、主機名稱、效期與信任根），僅放寬這一項 RFC 擴充欄位的嚴格檢查，因此 API 金鑰不會透過未驗證的連線傳送。
- Data sources: O-A0001-001 (automatic weather station observations) and the F-D0047 township forecasts (3-day and 1-week), fetched together through F-D0047-093. About seven requests are made per hour.  
  資料來源：O-A0001-001（自動氣象站觀測資料）與 F-D0047 鄉鎮預報（未來 3 天與 1 週），透過 F-D0047-093 一次取得。每小時約發出 7 次請求。
- Weather codes follow CWA's [weather description code table](https://www.cwa.gov.tw/V8/assets/pdf/Weather_Icon.pdf).  
  天氣代碼依中央氣象署[預報產品天氣描述代碼表](https://www.cwa.gov.tw/V8/assets/pdf/Weather_Icon.pdf)。

---

## Support / 支持

If this integration is useful for your Home Assistant setup, consider buying me a coffee — it keeps the updates coming.  
如果這個整合對你的 Home Assistant 有幫助，歡迎請我喝杯咖啡，讓更新持續下去。

<p align="center">
  <a href="https://paypal.me/puyanlin">
    <img src="https://img.shields.io/badge/PayPal-Donate-00457C?style=for-the-badge&logo=paypal&logoColor=white" alt="Donate via PayPal"/>
  </a>
</p>
