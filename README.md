# google_search_console_to_adobe_analytics

Import natural search keywords and organic search performance data from Google Search Console into Adobe Analytics using the 1.4 DataSources API.

Since Google encrypts search queries, Adobe Analytics cannot natively capture organic keyword data. This script bridges that gap by pulling keyword-level performance data from the Google Search Console API and uploading it to Adobe Analytics via Data Sources, making it available for reporting alongside your other Analytics dimensions.

For background, see the original article: [Importing Organic Google Search Data to Adobe Analytics with a Single Script](https://www.fullstackanalyst.io/blog/adobe-analytics/importing-organic-google-search-data-to-adobe-analytics-with-a-single-script/)

Initially created by Frederik Werner (https://www.frederikwerner.de/?r=g). Configuration moved to a dedicated config file since initial release, thank you @chip902!

## What It Does

The script fetches the following from Google Search Console for each day in a configurable date range:

- **Search queries (keywords)** — the natural search terms users typed
- **Landing page URLs** — the pages that ranked for those terms
- **Clicks, impressions, CTR, and average position** — performance metrics per keyword/URL

It then uploads this data to Adobe Analytics via the Data Sources API, mapping keywords and URLs to eVars and metrics to events. The script tracks previously uploaded jobs to avoid duplicate imports.

### Operating Modes

The script automatically selects an import mode based on which eVars you configure:

| Mode | Dimensions Imported | Required Config |
|------|---------------------|-----------------|
| **URL and Keyword** | Keywords per URL (most granular) | `url_evar` + `keyword_evar` |
| **Keyword Only** | Search queries only | `keyword_evar` only |
| **URL Only** | Landing pages only | `url_evar` only |
| **Metrics Only** | Aggregate clicks/impressions/position/CTR | No eVars (events only) |

Each mode also imports whichever metric events you configure (clicks, impressions, position, CTR). The `type_evar` is optional — if set, each row is labeled with the operating mode (e.g., "Import Type: URL and Keyword").

## Setup

### Prerequisites

- Python 3.8+
- A Google Cloud project with the Search Console API enabled and OAuth 2.0 credentials (`client_secrets.json`)
- An Adobe Developer Console project with OAuth Server-to-Server credentials
- A Data Source already created in Adobe Analytics (the script looks it up by name)

### Installation

```bash
pip install -r requirements.txt
```

### Google Authentication

1. Enable the **Google Search Console API** for your project (APIs & Services > Library > search for "Google Search Console API" > Enable).
2. Configure the **OAuth consent screen** (APIs & Services > OAuth consent screen):
   - Choose **Internal** (if using Google Workspace) or **External**.
   - Fill in the required fields (app name, support email).
   - Add the scope `https://www.googleapis.com/auth/webmasters.readonly`.
   - If your app is in **Testing** status, you must add yourself as a test user under **Test users** — otherwise you'll get an `Error 403: access_denied` when trying to sign in. Alternatively, click **Publish App** to remove this restriction.
3. Create OAuth 2.0 credentials in the [Credentials page](https://console.cloud.google.com/apis/credentials):
   - Click **Create Credentials > OAuth client ID**
   - Application type: **Desktop app** (not "Web application" — Desktop credentials automatically allow localhost redirects, avoiding `Error 400: redirect_uri_mismatch`)
   - Give it a name (e.g., "GSC Exporter")
4. Download the credentials JSON and save it as `client_secrets.json` in the project root.
5. On first run, a browser window will open for you to authorize access to Search Console. The resulting token is saved to `google_token.json` for subsequent runs.

> **Note:** If upgrading from the previous `oauth2client`-based version, you will need to re-authenticate on first run. The old `oauth2.json` token file is no longer used.

### Adobe Authentication

This script uses Adobe's **OAuth Server-to-Server** credentials (replacing the deprecated JWT/Service Account v1 flow).

1. In the [Adobe Developer Console](https://developer.adobe.com/console), create a project with OAuth Server-to-Server credentials and add the Adobe Analytics API.
2. Copy the **Client ID**, **Client Secret**, and **Scopes** into `config.json`.

### Adobe Analytics Setup

Before running the script, set up the following in Adobe Analytics:

#### 1. Create a Data Source

1. Go to **Admin > Data Sources** in your report suite.
2. Create a new Data Source and note the name — it must match `data_source_name` in your config.

#### 2. Configure eVars

Go to **Admin > Report Suites > Edit Settings > Conversion > Conversion Variables** and allocate eVars:

| eVar | Purpose | Settings |
|------|---------|----------|
| **URL eVar** | Landing page URL from GSC. Use an existing Full URL eVar if you have one — GSC URLs won't have query strings, so they'll match your organic visits. | Allocation: Most Recent, Expiration: Hit |
| **Keyword eVar** | Natural search keyword/query | Allocation: Most Recent, Expiration: Hit |
| **Type eVar** (optional) | Labels rows with the import mode (e.g., "Import Type: URL and Keyword") | Allocation: Most Recent, Expiration: Hit |

#### 3. Configure Events

Go to **Admin > Report Suites > Edit Settings > Conversion > Success Events** and create four events:

| Event | Purpose | Type | Polarity |
|-------|---------|------|----------|
| **GSC Clicks** | Click-throughs from search results | **Numeric** | Up is Good |
| **GSC Impressions** | Times a result appeared in search | **Numeric** | Up is Good |
| **GSC Avg Position** | Average ranking position | **Numeric** | Down is Good |
| **GSC CTR** | Click-through rate (decimal, e.g., 0.053 = 5.3%) | **Numeric** | Up is Good |

All four events must be **Numeric**, not Counter. The script passes specific values (e.g., 45 clicks, 1200 impressions) — a Counter event would just record "1" per row regardless of the actual value. Position polarity is "Down is Good" because a lower number means a higher ranking.

### Configuration

Copy `config.json` and fill in your values:

```json
{
    "apiKey": "YOUR_CLIENT_ID",
    "client_secret": "YOUR_CLIENT_SECRET",
    "orgId": "YOUR_ORG_ID@AdobeOrg",
    "scopes": "openid,AdobeID,read_organizations,additional_info.projectedProductContext",
    "google_property": "https://www.website.com/",
    "data_source_name": "Google Search Console Import",
    "report_suite_id": "orgreportsuiteid",
    "job_prefix": "GSC-Import",
    "lookback_days": 100,
    "url_evar": "8",
    "keyword_evar": "29",
    "clicks_event": "998",
    "impressions_event": "999",
    "position_event": "1000",
    "ctr_event": "997"
}
```

#### Date Range

You can control which dates the script fetches using one of two approaches:

- **Lookback days** (default): Set `lookback_days` to fetch the last N days from today.
- **Explicit date range**: Set `start_date` and `end_date` (format: `YYYY-MM-DD`) to fetch a specific range. This is useful for testing with a single day or backfilling a specific period.

```json
"start_date": "2025-01-15",
"end_date": "2025-01-15"
```

If both `start_date`/`end_date` and `lookback_days` are present, the explicit date range takes priority.

#### Config Reference

| Field | Description |
|-------|-------------|
| `apiKey` | Adobe OAuth Client ID |
| `client_secret` | Adobe OAuth Client Secret |
| `orgId` | Adobe Organization ID |
| `scopes` | Adobe OAuth scopes (comma-separated) |
| `google_property` | Google Search Console property URL |
| `data_source_name` | Name of the Data Source in Adobe Analytics (must match exactly) |
| `report_suite_id` | Adobe Analytics Report Suite ID |
| `job_prefix` | Prefix for upload job names (used for deduplication) |
| `lookback_days` | Number of days to look back from today |
| `start_date` | Start of explicit date range (`YYYY-MM-DD`), used instead of `lookback_days` |
| `end_date` | End of explicit date range (`YYYY-MM-DD`), used instead of `lookback_days` |
| `max_rows_per_day` | Maximum rows to fetch per day from GSC (optional, default: 50,000). Acts as a guardrail to prevent runaway queries. |
| `dry_run` | Set to `true` to fetch GSC data and preview it without uploading to Adobe (optional, default: `false`) |
| `type_evar` | eVar number to label the import type (optional) |
| `url_evar` | eVar number for landing page URLs (optional — omit to skip URL import) |
| `keyword_evar` | eVar number for natural search keywords (optional — omit to skip keyword import) |
| `clicks_event` | Event number for clicks (Numeric) |
| `impressions_event` | Event number for impressions (Numeric) |
| `position_event` | Event number for average position (Numeric) |
| `ctr_event` | Event number for click-through rate (Numeric) |

## Usage

```bash
python GSCtoAAexporter.py
```

The script will:

1. Authenticate with Google Search Console and Adobe Analytics
2. Look up your Data Source by name and retrieve existing jobs
3. Skip dates that have already been successfully uploaded
4. For each remaining date, query GSC for up to 10,000 rows of keyword/URL performance data
5. Upload each day's data to Adobe Analytics via the DataSources.UploadData API

### Dry Run Mode

To preview the data without uploading to Adobe, add `"dry_run": true` to your config. The script will still authenticate and fetch GSC data, but instead of uploading it will print the column headers, total row count, and the first 5 rows so you can verify the data shape:

```
--- DRY RUN (not uploading) ---
Columns: ['Date', 'Evar 8', 'Evar 29', 'Event 35', 'Event 36', 'Event 37', 'Event 38']
Total rows: 39379
Sample rows (first 5):
  ['01/01/2025/00/00/00', 'https://www.amtrak.com/home', 'amtrak tickets', '45', '1200', '3.2', '0.0375']
  ...
--- END DRY RUN ---
```

Set `"dry_run": false` or remove it when you're ready to upload for real.

### Testing with a Single Day

To test before doing a full import, set `start_date` and `end_date` to the same date:

```json
"start_date": "2025-01-20",
"end_date": "2025-01-20"
```

Combine with `"dry_run": true` to preview data for a single day without uploading.

## Limitations

- **90 days per run**: Adobe Data Sources can only process 90 days of historical data per day. The script automatically truncates date ranges exceeding 90 days and warns you. Run the script on consecutive days to backfill larger ranges.
- **10,000 rows per API call**: The GSC API returns up to 10,000 rows per request. The script automatically paginates to fetch all available data, capped at `max_rows_per_day` (default: 50,000) to prevent runaway queries.
- **10,000 rows per upload**: The Adobe DataSources API accepts up to 10,000 rows per call. The script automatically batches larger uploads into multiple jobs (named `_part1`, `_part2`, etc.).
- **1.4 API only**: The script uses the Adobe Analytics 1.4 DataSources API (there is no 2.0 equivalent for aggregate data import).
