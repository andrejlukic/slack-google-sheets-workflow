'''
Created on 6 Apr 2019

@author: test
'''
import pandas as pd
#from pandas.io.json import json_normalize
import json
from slacker import Slacker
#import argparse
import os
import sbot as sb
import datetime as dt
from dateutil import parser
from dateutil.relativedelta import relativedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
#import smtplib as mail
#from _multiprocessing import send
#import time
#import re
from slackclient import SlackClient
import configparser as cp

'''
['bot_id', 'client_msg_id', 'display_as_bot', 'edited', 'files',
       'inviter', 'latest_reply', 'parent_user_id', 'replies', 'reply_count',
       'reply_users', 'reply_users_count', 'subscribed', 'subtype', 'text',
       'thread_ts', 'ts', 'type', 'upload', 'user', 'username']
'''
CONFIG_FILE = 'nastavitve.ini'
LOG_FEEDBACK_WARNING = 'WARNFEED'
LOG_FEEDBACK_WARNING2 = 'WARNFEED2'
LOG_ATTACHMENT_WARNING = 'WARNASSI'

scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/spreadsheets',
         'https://www.googleapis.com/auth/drive']

def update_messages(config):
    slack = Slacker(config['SLACK_AUTH']['TOKEN'])    
    #testAuth = sb.doTestAuth(slack)    
    #userIdNameMap = sb.getUserMap(slack)
    channels = slack.channels.list().body['channels']  
    #print("\nFound channels: ")
    #for channel in channels:
    #    print(channel['name'])
    sb.mkdir(config['APP']['DATA_DIR'])
    info = 0
    for channel in channels:
        if(channel['name'].lower() != config['WORKFLOW']['SLACK_CHANNEL_NAME']):
            continue
        else:
            #print("Downlading {0}".format(channel['name']))
            fileName = "{parent}/{file}.json".format(parent = config['APP']['DATA_DIR'], file = channel['name'])
            messages = sb.getHistory(slack.channels, channel['id'])
            channelInfo = slack.channels.info(channel['id']).body['channel']
            with open(fileName, 'w') as outFile:
                #print("writing {0} records to {1}".format(len(messages), fileName))
                info += len(messages) 
                json.dump({'channel_info': channelInfo, 'messages': messages }, outFile, indent=4)
    return info

def load_messages(config, date_from):
    src = r'{0}/{1}.json'.format(config['APP']['DATA_DIR'], config['WORKFLOW']['SLACK_CHANNEL_NAME'])    
    with open(src) as data_file:    
        d = json.load(data_file)  
        #print(d['messages'])
        #df = json_normalize(d, 'messages')
        df = pd.DataFrame(d['messages'])
        df['text'] = df['text'].astype('str')
        # TODO
        df['date'] = df['ts'].apply(lambda x: dt.datetime.fromtimestamp(int(x.split('.')[0])))
        if(date_from):
        #print('Filtering on {0}'.format(date_from))
        #print(df['ts'].apply(lambda x: dt.datetime.fromtimestamp(int(x.split('.')[0]))))
            df = df[df['date'] >= date_from]
        #print(df['date'])
        #df['user'] = df['user'].astype('str')
        #df['parent_user_id'] = df['parent_user_id'].astype('str')
        #df = pd.read_json(d['messages'])
        #print(df.head())
        return df
    
def list_users_in_thread(df):
    return df[df['user'].notnull()]['user'].unique()

def list_users_who_posted_attachment(df):
    att = df[df['upload'].notnull()]
    users = att['user'].unique()
    return att, set(users)

# TODO: add condition, that the parent message has attachment.
def list_users_who_gave_feedback(df, l=1, n=1):
    replies = df[df['parent_user_id'].notnull()]
    # exclude reply to your own thread
    replies = replies[replies['parent_user_id'] != replies['user']]    
    #print(replies[['user','text', 'date']])
    if(l > 1):
        replies = replies[replies['text'].str.len() > l]
    replies = replies.groupby('user').agg({'client_msg_id': 'count'})  
    #print(replies)  
    if(n>1):
        replies = replies[replies['client_msg_id'] >= n]
    return set(replies.index)

def list_users_who_did_not_give_feedback(user_list, df, l=1, n=1):
    t = list_users_who_gave_feedback(df, l, n)
    uset = set(user_list.keys())
    return uset - t

def list_users_who_did_not_post_attachment(user_list, df):
    _,t = list_users_who_posted_attachment(df)
    uset = set(user_list.keys())
    return uset - t

def send_email(user, pwd, recipient, subject, body):
    import smtplib

    FROM = user
    TO = recipient if isinstance(recipient, list) else [recipient]
    SUBJECT = subject
    TEXT = body

    # Prepare actual message
    message = """From: %s\nTo: %s\nSubject: %s\n\n%s
    """ % (FROM, ", ".join(TO), SUBJECT, TEXT)
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(user, pwd)
        server.sendmail(FROM, TO, message)
        server.close()
        return 0
    except:
        return -1

def sendAssignmentNotification(config, to):
    subject = config['REMINDERS']['ASS_EMAIL_SUBJ']
    body = config['REMINDERS']['ASS_EMAIL_BODY']
    send_email(config['GMAIL_AUTH']['GMAIL_U'],config['GMAIL_AUTH']['GMAIL_P'],to,subject,body)

def sendFeedbackNotification(config, to):
    subject = config['REMINDERS']['FEED_EMAIL_SUBJ']  
    body = config['REMINDERS']['FEED_EMAIL_BODY']
    send_email(config['GMAIL_AUTH']['GMAIL_U'],config['GMAIL_AUTH']['GMAIL_P'],to,subject,body)

def updatelog(to_log, n=None):
    if(n):
        fn = 'log-{}.dat'.format(n)
    else:
        fn = 'log.dat'

    if(to_log):
        with open(fn, 'a') as f:
            for dict in to_log:                    
                f.write('{0},{1},{2}\n'.format(dict['lid'], dict['uid'], dict['aid'], dict['val']))

def readLog(n=None):    
    
    if(n):
        fn = 'log-{}.dat'.format(n)
    else:
        fn = 'log.dat'
    
    if(not os.path.isfile(fn)):
        return None
    try:
        df = pd.read_csv(fn, header=None)
    except:
        # empty file
        return None
    return set(df.iloc[:, 0].unique()) 

def connectGS(config):
    credentials = ServiceAccountCredentials.from_json_keyfile_name(config['SPREADSHEET']['CREDENTIALS'], scope)
    gc = gspread.authorize(credentials)
    wks = gc.open(config['SPREADSHEET']['SPREADSHEET_NAME']).worksheet(config['SPREADSHEET']['SHEET_NAME'])
    return wks

def findUserRow(wks, name):
    cell = wks.find(name)
    if(cell):
        return cell.row
    return None

def findColumn(wks, cname):
    cell = wks.find(cname)
    if(cell):
        return cell.col
    return None

def updateStatusCol(config, wks, usern, update_text):
    row = findUserRow(wks, usern)
    col = findColumn(wks, config['SPREADSHEET']['STATUS_COLUMN'])
    if(row and col):        
        wks.update_cell(row, col, update_text)
        return 1
    else:
        return 0
# dela
def updateFeedbackCol(config, wks, usern, update_text):
    row = findUserRow(wks, usern)
    col = findColumn(wks, config['SPREADSHEET']['FEEDBACK_COLUMN'])
    if(row and col):        
        wks.update_cell(row, col, update_text)
        return 1
    else:
        return 0   
def botReminder(config, ufeed):
    slack_client = SlackClient(config['SLACK_AUTH']['SLACK_AUTH_TOKEN'])       
    if slack_client.rtm_connect(with_team_state=False):
        starterbot_id = slack_client.api_call("auth.test")["user_id"]
        print("Bot connected")
        # Read bot's user ID by calling Web API method `auth.test`
        #starterbot_id = slack_client.api_call("auth.test")["user_id"]
        s = ', '.join(['<@{0}>'.format(x.upper()) for x in ufeed])
        response = "{0} {1}".format(s, config['REMINDERS']['BOT_MSG'])
        # Sends the response back to the channel
        slack_client.api_call(
            "chat.postMessage",
            channel=config['WORKFLOW']['SLACK_CHANNEL_ID'],
            text=response
        )
        return 0
    else:
        print("Connection failed. Exception traceback printed above.")
        return -1
def run():
    print('Starting script')
    config = cp.ConfigParser()
    config.read(CONFIG_FILE)

    disable_all_reminders = config['REMINDERS']['DISABLE_ALL'] != 'False'
    
    if(disable_all_reminders):
        print('Reminders disabled')
    
    user_list = {}
    for u,uemail in config['STUDENTS'].items():
        user_list.update({u.upper():uemail})

    print('Participants: {0}'.format(user_list.keys()))
    
    start = parser.parse(config['WORKFLOW']['ASSIGNMENT_START_DATE'])
    end = start + relativedelta(days=5)
    end2 = start + relativedelta(days=6)
    end3 = start + relativedelta(days=7)
    print('End assigment {0} End feedback {1} End spreadsheet updates {2}'.format(end,end2, end3))
    diff = end - dt.datetime.now()
    diff2 = end2 - dt.datetime.now()
    diff3 = end3 - dt.datetime.now()
    print(diff2)
    days_left = diff.days
    hours_left = diff.seconds // 3600
    days_left2 = diff2.days
    hours_left2 = diff2.seconds // 3600
    days_left3 = diff3.days
    hours_left3 = diff3.seconds // 3600

    if(days_left3 < 0):
        print('Assignment and feedback due date ended on {0} and {1}. Hand-in closed on {2} Exiting ...'.format(end,end2,end3))
        return -1
    
    print('Check assignment {0} - {1}, {2} days and {3} hours to go'.format(start,end, days_left, hours_left))
    # 1. Download new messages
    print("Downlading {0} history ...".format(config['WORKFLOW']['SLACK_CHANNEL_NAME']))
    info = update_messages(config)
    print("... downloaded {0} messages".format(info))
    # 1. Load message history        
    df = load_messages(config, start)
    # 2. Check attachments
    ua = list_users_who_did_not_post_attachment(user_list, df)
    print('Attachments still pending for: {0}'.format(','.join(ua)))
    #print(ua)
    # 3. Check feedbacks
    # List users who did not yet give 3 feedbacks:
    uf = list_users_who_did_not_give_feedback(user_list, df, int(config['WORKFLOW']['MIN_REPLY_LENGTH']), int(config['WORKFLOW']['MIN_FEEDBACK_COUNT']))
    # List users who gave more than 0 feedbacks:
    uf2 = list_users_who_did_not_give_feedback(user_list, df, int(config['WORKFLOW']['MIN_REPLY_LENGTH']), 1) 
    print('Feedbacks still pending for: {0}'.format(','.join(uf)))
    # 4. send assignemnt notifications
    send_assign_notif = days_left == 0 and hours_left < 5
    if(not disable_all_reminders and send_assign_notif):
        st = readLog('not')
        if(not ua):
            print('All users gave in their assignments.')
        else:
            log_list = []
            for u in ua:                
                skip = checkLog(config, st, str(u), LOG_ATTACHMENT_WARNING)
                if(not skip):
                    print('Sending email reminder to {0}({1}) for forgotten assignment.'.format(u, user_list[u]))
                    sendAssignmentNotification(config, user_list[u])
                    log_list.append({'lid': makeLogId(config, u, LOG_ATTACHMENT_WARNING),
                                   'uid': u,
                                   'aid': LOG_ATTACHMENT_WARNING,
                                   'val': 'assignment warning'})
            updatelog(log_list, 'not')

    # 5. send feedback notifications
    send_feedback_notif = days_left2 == 0 and hours_left2 <= 2
    if(not disable_all_reminders and send_feedback_notif):
        st = readLog('not')
        if(not uf):
            print('All users have written their feedbacks.')
        else:
            log_list = []
            remind_set = set()
            for u in uf:                
                skip = checkLog(config, st, str(u), LOG_FEEDBACK_WARNING)
                if(not skip):
                    remind_set.add(u)
                    log_list.append({'lid': makeLogId(config, u, LOG_FEEDBACK_WARNING),
                                    'uid': u,
                                    'aid': LOG_FEEDBACK_WARNING,
                                    'val': 'feedback warning'})
            updatelog(log_list, 'not')
            if(remind_set):
                botReminder(config, remind_set)
            
            if(config['REMINDERS']['SEND_FEEDBACK_WARN_EMAIL'] == 'True'):
                log_list = []
                for u in uf:                
                    skip = checkLog(config, st, str(u), LOG_FEEDBACK_WARNING2)
                    if(not skip):
                        print('Sending email reminder to {0}({1}) for forgotten feedbacks.'.format(u, user_list[u]))
                        sendFeedbackNotification(config, user_list[u])
                        log_list.append({'lid': makeLogId(config, u, LOG_FEEDBACK_WARNING2),
                                       'uid': u,
                                       'aid': LOG_FEEDBACK_WARNING2,
                                       'val': 'feedback warning email'})
                updatelog(log_list, 'not')
            
    else:
        print('Feedback reminders not yet due or everybody written theirs.')
    
    # 6. update spreadsheets for assignments / tolerate 12h
    # days_left >= 0 and hours_left >= -12 
    update_excel = days_left >= -1
    if(update_excel):
        wks = connectGS(config)
        #msg = 'D' if(hours_left>=0) else 'D*'
        msg = 'D' if(days_left>=0) else 'D*'
        u = set(user_list.keys())
        good = u - ua
        if(good):
            print('Assignments accomplished for: {0}'.format(','.join(good)))
            for good_user in good:
                updateStatusCol(config, wks, good_user, msg)
    else:
        print('Updating Status column has been already closed (skipping)')
    
    # 7. update spreadsheets for feedbacks / tolerate 12h 
    # update_excel = days_left2 >= 0 and hours_left2 >= -12
    update_excel = days_left2 >= -1
    if(update_excel):
        wks = connectGS(config)
        #msg = 'D' if(hours_left>=0) else 'D*'
        msg = 'D' if(days_left2>=0) else 'D*'
        u = set(user_list.keys())
        good = u - uf
        better_than_nothing = u - uf2 - good
        print('Users who gave more than zero feedbacks: {0}'.format(better_than_nothing))
        if(good):
            print('Feedback accomplished for: {0}'.format(','.join(good)))
            for good_user in good:            
                updateFeedbackCol(config, wks, good_user, msg)
        if(better_than_nothing):
            print('More than zero feedbacks accomplished for: {0}'.format(','.join(better_than_nothing)))
            for good_user in better_than_nothing:            
                updateFeedbackCol(config, wks, good_user, 'P')
    else:
        print('Updating Feedback column has been already closed (skipping)')
    return 0

def makeLogId(config, userid, actionid):
    return str(parser.parse(config['WORKFLOW']['ASSIGNMENT_START_DATE'])) + '->'+ str(actionid) + '->' + str(userid)

def checkLog(config, st, userid, actionid):
    if(not st):
        return False
    lid = makeLogId(config, userid, actionid)
    return lid in st
    

run()   
    
