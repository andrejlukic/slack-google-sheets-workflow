'''
Created on 6 Apr 2019

@author: Andrej Lukic, based on Chandler Abraham's script https://gist.github.com/Chandler/fb7a070f52883849de35
'''
# MIT License

# Copyright (c) 2016 Chandler Abraham

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

from slacker import Slacker
import json
import argparse
import os

def getHistory(pageableObject, channelId, pageSize = 100):
  messages = []
  lastTimestamp = None

  while(True):
    response = pageableObject.history(
      channel = channelId,
      latest  = lastTimestamp,
      oldest  = 0,
      count   = pageSize
    ).body

    messages.extend(response['messages'])

    if (response['has_more'] == True):
      lastTimestamp = messages[-1]['ts'] # -1 means last element in a list
    else:
      break
  return messages

def mkdir(directory):
  if not os.path.exists(directory):
    os.makedirs(directory)

# fetch and write history for all public channels
def getChannels(slack, dryRun):
  channels = slack.channels.list().body['channels']
  
  print("\nfound channels: ")
  for channel in channels:
    print(channel['name'])
  
  if not dryRun:
    parentDir = "channels"
    mkdir(parentDir)
    for channel in channels:
      print("getting history for channel {0}".format(channel['name']))
      fileName = "{parent}/{file}.json".format(parent = parentDir, file = channel['name'])
      messages = getHistory(slack.channels, channel['id'])
      channelInfo = slack.channels.info(channel['id']).body['channel']
      with open(fileName, 'w') as outFile:
        print("writing {0} records to {1}".format(len(messages), fileName))
        json.dump({'channel_info': channelInfo, 'messages': messages }, outFile, indent=4)

# fetch and write history for all direct message conversations
# also known as IMs in the slack API.
def getDirectMessages(slack, ownerId, userIdNameMap, dryRun):
  dms = slack.im.list().body['ims']
  
  print("\nfound direct messages (1:1) with the following users:")
  for dm in dms:
    print(userIdNameMap.get(dm['user'], dm['user'] + " (name unknown)"))
  
  if not dryRun:
    parentDir = "direct_messages"
    mkdir(parentDir)
    for dm in dms:
      name = userIdNameMap.get(dm['user'], dm['user'] + " (name unknown)")
      print("getting history for direct messages with {0}".format(name))
      fileName = "{parent}/{file}.json".format(parent = parentDir, file = name)
      messages = getHistory(slack.im, dm['id'])
      channelInfo = {'members': [dm['user'], ownerId]}
      with open(fileName, 'w') as outFile:
        print("writing {0} records to {1}".format(len(messages), fileName))
        json.dump({'channel_info': channelInfo, 'messages': messages}, outFile, indent=4)

# fetch and write history for all private channels
# also known as groups in the slack API.
def getPrivateChannels(slack, dryRun):
  groups = slack.groups.list().body['groups']
  
  print("\nfound private channels:")
  for group in groups:
    print("{0}: ({1} members)".format(group['name'], len(group['members'])))
  
  if not dryRun:
    parentDir = "private_channels"
    mkdir(parentDir)

    for group in groups:
      messages = []
      print("getting history for private channel {0} with id {1}".format(group['name'], group['id']))
      fileName = "{parent}/{file}.json".format(parent = parentDir, file = group['name'])
      messages = getHistory(slack.groups, group['id'])
      channelInfo = slack.groups.info(group['id']).body['group']
      with open(fileName, 'w') as outFile:
        print("writing {0} records to {1}".format(len(messages), fileName))
        json.dump({'channel_info': channelInfo, 'messages': messages}, outFile, indent=4)

# fetch all users for the channel and return a map userId -> userName
def getUserMap(slack):
  #get all users in the slack organization
  users = slack.users.list().body['members']
  userIdNameMap = {}
  for user in users:
    userIdNameMap[user['id']] = user['name']
  print("found {0} users ".format(len(users)))
  return userIdNameMap

# get basic info about the slack channel to ensure the authentication token works
def doTestAuth(slack):
  testAuth = slack.auth.test().body
  teamName = testAuth['team']
  currentUser = testAuth['user']
  print("Successfully authenticated for team {0} and user {1} ".format(teamName, currentUser))
  return testAuth

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='download slack history')

  parser.add_argument('--token', help="an api token for a slack user")

  parser.add_argument(
    '--dryRun',
    action='store_true',
    default=False,
    help="if dryRun is true, don't fetch/write history only get channel names")

  parser.add_argument(
    '--skipPrivateChannels',
    action='store_true',
    default=False,
    help="skip fetching history for private channels")

  parser.add_argument(
    '--skipChannels',
    action='store_true',
    default=False,
    help="skip fetching history for channels")

  parser.add_argument(
    '--skipDirectMessages',
    action='store_true',
    default=False,
    help="skip fetching history for directMessages")

  args = parser.parse_args()

  slack = Slacker(args.token)

  testAuth = doTestAuth(slack)

  userIdNameMap = getUserMap(slack)

  dryRun = args.dryRun

  if not dryRun:
    with open('metadata.json', 'w') as outFile:
      print("writing metadata")
      metadata = {
        'auth_info': testAuth,
        'users': userIdNameMap
      }
      json.dump(metadata, outFile, indent=4)

  if not args.skipChannels:
    getChannels(slack, dryRun)

  if not args.skipPrivateChannels:
    getPrivateChannels(slack, dryRun)

  if not args.skipDirectMessages:
    getDirectMessages(slack, testAuth['user_id'], userIdNameMap, dryRun)