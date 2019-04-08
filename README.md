## Automated workflow connecting Slack API and Google Sheets API

### Description

Script does the following:

1. Downloads message history from selected Slack channel ([Thank you Chandler for this solution!](https://gist.github.com/Chandler/fb7a070f52883849de35))
2. Uses Pandas to analyze the downloaded messages
3. Update a specified Google Spreadsheet updating each students progress
4. Use a Slack bot to send reminders to Slack users
5. Additionally send email reminders to Slack users

### Installation instructions

#### Configure Slack bot access

+ Install a Slack bot into your Slack workspace. [slack.com/apps] (https://api.slack.com/apps)
+ From the menu select "Add features and functionality", then select "Bots", add a name
+ From the menu select "OAuth & Permissions", scroll down to "Scopes". Add:
  - channels:history
  - channels:read
  - channels:write
+ Click "Install app in the workspace" (top of the "OAuth & Permissions" page) and click Authorize
+ Update config params:
  - Set "OAuth Access Token" to be the TOKEN parameter in settings
  - Set "Bot User OAuth Access Token" to be the SLACK_AUTH_TOKEN parameter in settings
  - Set the 'SLACK_CHANNEL_ID' param to be the id of your Slack channel
  - Set the 'SLACK_CHANNEL_NAME' param to be the name of your Slack channel
+ Invite the bot to your channel

#### Configure Google API access 
([littel outdated but valid instructions](https://gspread.readthedocs.io/en/latest/oauth2.html), except add Google Sheets API)

+ Open the [Google Developers Console and create a new project (or select the one you have.)](https://console.developers.google.com/project)
+ Under "Enable APIs and services", in the API enable "Google Sheets API".
+ Go to “Credentials” and choose “New Credentials > Service Account Key”.
+ Download the JSON files with credentials and put it in the app directory
+ Set the 'CREDENTIALS' in 'SPREADSHEET' section to be the name of this json credentials file
+ IMPORTANT: share your spreadsheet with the email from your credentils JSON file

#### Configure smtp access

To allow script to send email notifications, set the google username and password under the GMAIL_AUTH section
