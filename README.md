# google_search_console_to_adobe_analytics
Small script to import Google Search performance data to Adobe Analytics via the 1.4 DataSources API.

For usage instructions see https://www.fullstackanalyst.io/blog/adobe-analytics/importing-organic-google-search-data-to-adobe-analytics-with-a-single-script/?r=g

Configuration has moved to a dedicated config file since initial release, thank you @chip902!

Initially created by Frederik Werner (https://www.frederikwerner.de/?r=g)

## Setup

### Prerequisites

- Python 3.8+
- A Google Cloud project with the Search Console API enabled and OAuth 2.0 credentials (`client_secrets.json`)
- An Adobe Developer Console project with OAuth Server-to-Server credentials

### Installation

```bash
pip install -r requirements.txt
```

### Google Authentication

1. Create OAuth 2.0 credentials in the [Google Cloud Console](https://console.cloud.google.com/apis/credentials) (Desktop application type).
2. Download the credentials JSON and save it as `client_secrets.json` in the project root.
3. On first run, a browser window will open for you to authorize access to Search Console. The resulting token is saved to `google_token.json` for subsequent runs.

> **Note:** If upgrading from the previous `oauth2client`-based version, you will need to re-authenticate on first run. The old `oauth2.json` token file is no longer used.

### Adobe Authentication

This script uses Adobe's **OAuth Server-to-Server** credentials (replacing the deprecated JWT/Service Account v1 flow).

1. In the [Adobe Developer Console](https://developer.adobe.com/console), create a project with OAuth Server-to-Server credentials and add the Adobe Analytics API.
2. Copy the **Client ID**, **Client Secret**, and **Scopes** into `config.json`.

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
    "type_evar": "197",
    "url_evar": "198",
    "keyword_evar": "199",
    "ctr_event": "997",
    "clicks_event": "998",
    "impressions_event": "999",
    "position_event": "1000"
}
```

| Field | Description |
|-------|-------------|
| `apiKey` | Adobe OAuth Client ID |
| `client_secret` | Adobe OAuth Client Secret |
| `orgId` | Adobe Organization ID |
| `scopes` | Adobe OAuth scopes (comma-separated) |
| `google_property` | Google Search Console property URL |
| `data_source_name` | Name of the Adobe Analytics Data Source |
| `report_suite_id` | Adobe Analytics Report Suite ID |
| `job_prefix` | Prefix for upload job names (used for deduplication) |
| `lookback_days` | Number of days to look back for data |
| `type_evar` / `url_evar` / `keyword_evar` | eVar numbers for import type, URL, and keyword |
| `clicks_event` / `impressions_event` / `position_event` / `ctr_event` | Event numbers for metrics |

## Usage

```bash
python GSCtoAAexporter.py
```

The script will fetch Search Console data for each day in the lookback window (skipping dates already uploaded) and upload it to Adobe Analytics via the DataSources API.
