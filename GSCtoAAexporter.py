import datetime
import os
import requests
import sys
import re
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Open and load the configuration file
with open('config.json', 'r') as file:
    config = json.load(file)

if config.get("start_date") and config.get("end_date"):
    start = datetime.datetime.strptime(config["start_date"], "%Y-%m-%d")
    end = datetime.datetime.strptime(config["end_date"], "%Y-%m-%d")
    delta = (end - start).days
    date_list = [(start + datetime.timedelta(days=x)).strftime("%Y-%m-%d")
                 for x in range(delta + 1)]
    print("Using date range: {} to {}".format(
        config["start_date"], config["end_date"]))
else:
    base = datetime.datetime.today()
    date_list = [(base - datetime.timedelta(days=x)).strftime("%Y-%m-%d")
                 for x in range(config["lookback_days"])]
    print("Using lookback: {} days from today".format(config["lookback_days"]))

if config.get("clicks_event") or config.get("impressions_event") or config.get("position_event") or config.get("ctr_event"):
    if config.get("url_evar") and config.get("keyword_evar"):
        print("Both URL and Keyword eVar given. Importing Keywords per URL...")
        operating_mode = "URL and Keyword"
        query_dimensions = ['date', 'page', 'query']
        datasource_columns = ['Date']
    elif config.get("keyword_evar"):
        print("Only Keyword eVar given. Importing only Keywords...")
        operating_mode = "Keyword Only"
        query_dimensions = ['date', 'query']
        datasource_columns = ['Date']
    elif config.get("url_evar"):
        print("Only URL eVar given. Importing only URLs...")
        operating_mode = "URL Only"
        query_dimensions = ['date', 'page']
        datasource_columns = ['Date']
    else:
        print("No eVars given. Importing metrics only")
        operating_mode = "Metrics Only"
        query_dimensions = ['date']
        datasource_columns = ['Date']
    if config.get("type_evar"):
        datasource_columns.append('Evar '+config["type_evar"])
    if config.get("url_evar") and operating_mode in ("URL and Keyword", "URL Only"):
        datasource_columns.append('Evar '+config["url_evar"])
    if config.get("keyword_evar") and operating_mode in ("URL and Keyword", "Keyword Only"):
        datasource_columns.append('Evar '+config["keyword_evar"])
    if config.get("clicks_event"):
        datasource_columns.append("Event "+config["clicks_event"])
    if config.get("impressions_event"):
        datasource_columns.append("Event "+config["impressions_event"])
    if config.get("position_event"):
        datasource_columns.append("Event "+config["position_event"])
    if config.get("ctr_event"):
        datasource_columns.append("Event "+config["ctr_event"])
else:
    print("No events given. Aborting...")
    sys.exit()


GOOGLE_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GOOGLE_TOKEN_FILE = "google_token.json"
GOOGLE_CLIENT_SECRETS_FILE = "client_secret_amtrak.com.json"


def get_authenticated_google_service():
    creds = None
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(
            GOOGLE_TOKEN_FILE, GOOGLE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CLIENT_SECRETS_FILE, GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=8085)
        with open(GOOGLE_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build("webmasters", "v3", credentials=creds)


search_console = get_authenticated_google_service()

ADOBE_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
ADOBE_DISCOVERY_URL = "https://analytics.adobe.io/discovery/me"


def get_adobe_access_token(config):
    response = requests.post(
        ADOBE_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": config["apiKey"],
            "client_secret": config["client_secret"],
            "scope": config["scopes"]
        }
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_first_global_company_id(config, access_token):
    response = requests.get(
        ADOBE_DISCOVERY_URL,
        headers={
            "Authorization": "Bearer {}".format(access_token),
            "x-api-key": config["apiKey"]
        }
    )
    response.raise_for_status()
    return response.json().get("imsOrgs")[0].get("companies")[0].get("globalCompanyId")


access_token = get_adobe_access_token(config)
global_company_id = get_first_global_company_id(config, access_token)

dataSources = requests.post(
    "https://api.omniture.com/admin/1.4/rest/?method=DataSources.Get",
    headers={
        "Authorization": "Bearer {}".format(access_token),
        "x-api-key": config["apiKey"],
        "x-proxy-global-company-id": global_company_id
    },
    json={'reportSuiteID': config["report_suite_id"]}
)
dataSources.raise_for_status()
dataSources = dataSources.json()

dataSourceID = None
for dataSource in dataSources:
    if dataSource["name"] == config["data_source_name"]:
        dataSourceID = dataSource["id"]
        print("Found Data Source ID: " + str(dataSourceID))
        break

if dataSourceID:
    jobs = requests.post(
        "https://api.omniture.com/admin/1.4/rest/?method=DataSources.GetJobs",
        headers={
            "Authorization": "Bearer {}".format(access_token),
            "x-api-key": config["apiKey"],
            "x-proxy-global-company-id": global_company_id
        },
        json={'reportSuiteID': config["report_suite_id"],
              'dataSourceID': dataSourceID}
    ).json()
    for job in jobs:
        jobname = job["fileName"]
        if config["job_prefix"].lower() in jobname:
            matchstring = '^'+re.escape(config["job_prefix"].lower())+"_"+operating_mode.lower(
            )+'_([0-9]{4}-[0-9]{2}-[0-9]{2})_'+config["report_suite_id"]+'_'+dataSourceID+r'_[0-9]*\.tab$'
            p = re.compile(matchstring)
            regex_match = p.match(job["fileName"])
            if regex_match and job["status"] != "failed":
                jobdate = regex_match.group(1)
                if jobdate in date_list:
                    date_list.remove(jobdate)
else:
    print("Data Source not found. Please check your configured Data Source name.")
    sys.exit()

print("Number of days to fetch: "+str(len(date_list)))
i = 1
for query_date in date_list:
    print("Fetching Google Search Console Data for " +
          query_date+". Query "+str(i)+"/"+str(len(date_list)))
    max_rows_per_day = config.get("max_rows_per_day", 50000)
    gsc_rows = []
    start_row = 0
    while True:
        request = {
            'startDate': query_date,
            'endDate': query_date,
            'dimensions': query_dimensions,
            'rowLimit': 10000,
            'startRow': start_row
        }
        result = search_console.searchanalytics().query(
            siteUrl=config["google_property"], body=request).execute()
        batch = result.get("rows", [])
        gsc_rows.extend(batch)
        print("  Fetched {} rows (total: {})".format(len(batch), len(gsc_rows)))
        if len(batch) < 10000 or len(gsc_rows) >= max_rows_per_day:
            break
        start_row += len(batch)
    if len(gsc_rows) >= max_rows_per_day:
        gsc_rows = gsc_rows[:max_rows_per_day]
        print("  Capped at {} rows (max_rows_per_day)".format(max_rows_per_day))
    result_rows = []
    if gsc_rows:
        print("Received "+str(len(gsc_rows)) +
              " rows of data. Uploading to Adobe...")
        for row in gsc_rows:
            row_to_append = []
            row_to_append.append(
                row["keys"][0][5:7]+"/"+row["keys"][0][8:10]+"/"+row["keys"][0][0:4]+"/00/00/00")
            if config.get("type_evar"):
                row_to_append.append("Import Type: "+operating_mode)

            if operating_mode != "Metrics Only":
                row_to_append.append(row["keys"][1])
            if operating_mode == "URL and Keyword":
                row_to_append.append(row["keys"][2])

            if config.get("clicks_event"):
                row_to_append.append(str(row["clicks"]))
            if config.get("impressions_event"):
                row_to_append.append(str(row["impressions"]))
            if config.get("position_event"):
                row_to_append.append(str(row["position"]))
            if config.get("ctr_event"):
                row_to_append.append(str(row["ctr"]))
            result_rows.append(row_to_append)

    if len(result_rows) > 0:
        jobresponse = requests.post(
            "https://api.omniture.com/admin/1.4/rest/?method=DataSources.UploadData",
            headers={
                "Authorization": "Bearer {}".format(access_token),
                "x-api-key": config["apiKey"],
                "x-proxy-global-company-id": global_company_id
            },
            json={
                "columns": datasource_columns,
                'reportSuiteID': config["report_suite_id"],
                'dataSourceID': dataSourceID,
                "finished": True,
                "jobName": config["job_prefix"]+"_"+operating_mode+"_"+query_date,
                "rows": result_rows
            }
        )
    else:
        print("No Data for "+query_date)
    i += 1
