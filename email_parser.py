# Credit for much of the code for reading the emails themselves goes to https://www.geeksforgeeks.org/how-to-read-emails-from-gmail-using-gmail-api-in-python/.
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dataclasses import dataclass
from typing import List, Tuple
from datetime import date, datetime
import pickle
import os.path
import base64
import re
from bs4 import BeautifulSoup
import argparse

import networkx as nx
import matplotlib.pyplot as plt

# Define the SCOPES. If modifying it, delete the token.pickle file.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# const strings used in labels networkx components
COUNT_ATTR = "weight"
TO_TYPE = "to"
CC_TYPE = "cc"
BCC_TYPE = "bcc"
KEYWORDS_ATTR = "keywords"

@dataclass
class Email:
  senders: Tuple[str]
  timestamp: datetime
  to: Tuple[str]
  cc: Tuple[str]
  bcc: Tuple[str]
  subject: str
  body: str


def parse_email_list(emails_str):
  emails = re.findall(r"[a-z0-9\.\-+_]+@[a-z0-9\.\-+_]+\.[a-z]+", emails_str)
  return tuple(emails)

def get_emails(nums_emails):
  emails = []

  # Variable creds will store the user access token.
  # If no valid token found, we will create one.
  creds = None

  # The file token.pickle contains the user access token.
  # Check if it exists
  if os.path.exists('token.pickle'):

    # Read the token from the file and store it in the variable creds
    with open('token.pickle', 'rb') as token:
      creds = pickle.load(token)

  # If credentials are not available or are invalid, ask the user to log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
      creds = flow.run_local_server(port=0)

    # Save the access token in token.pickle file for the next run
    with open('token.pickle', 'wb') as token:
      pickle.dump(creds, token)

  # Connect to the Gmail API
  service = build('gmail', 'v1', credentials=creds)

  # request a list of all the messages
  result = service.users().messages().list(maxResults=nums_emails, userId='me').execute()

  # We can also pass maxResults to get any number of emails. Like this:
  # result = service.users().messages().list(maxResults=200, userId='me').execute()
  messages = result.get('messages')

  # messages is a list of dictionaries where each dictionary contains a message id.

  # iterate through all the messages
  for msg in messages:
    # Get the message from its id
    txt = service.users().messages().get(userId='me', id=msg['id']).execute()

    try:
      payload = txt['payload']
      headers = payload['headers']

      cc = []
      bcc = []
      to = []

      # Pull out important values from the headers.
      for d in headers:
        if False:
          print(d.keys())
        if d['name'] == 'Subject':
          subject = d['value']
        if d['name'] == 'From':
          senders = parse_email_list(d['value'])
        if d['name'] == 'Date':
          timestamp = datetime.strptime(d['value'], '%a, %d %b %Y %H:%M:%S %z')
        if d['name'] == 'Cc':
          cc = parse_email_list(d['value'])
        if d['name'] == 'Bcc':
          bcc = parse_email_list(d['value'])
        if d['name'] == 'To':
          to = parse_email_list(d['value'])

      # The Body of the message is in Encrypted format. So, we have to decode it.
      # Get the data and decode it with base 64 decoder.
      data = payload.get('body').get("data", "")
      data = data.replace("-","+").replace("_","/")
      decoded_data = base64.b64decode(data)

      # Now, the data obtained is in lxml. So, we will parse
      # it with BeautifulSoup library
      soup = BeautifulSoup(decoded_data , "lxml")
      body = ""
      # body = soup.prettify()
      # body = soup.body()

      # Printing the subject, sender's email and message
      emails.append(Email(senders, timestamp, to, cc, bcc, subject, body))
      print(emails[-1])
      print('\n')

    except Exception as e:
      print("Error has occured...")
      print(e)

  return emails

# Extracts the most important keywords from the email body.
def extract_keywords(body, num_keywords=5):
  # Refer to https://www.analyticsvidhya.com/blog/2022/01/four-of-the-easiest-and-most-effective-methods-of-keyword-extraction-from-a-single-text-using-python/
  return []

# Creates a new edge if one doesn't exist yet.
# 
# Args:
#   g: networkx graph
#   u: source name
#   v: destination name
#   edge_type: the type of email sent, which is either TO_TYPE, CC_TYPE, or BCC_TYPE
def maybe_add_edge(g, u, v, edge_type):
  edge = g.get_edge_data(u, v, edge_type)
  if edge == None:
    g.add_edge(u, v, key=edge_type)
    g[u][v][edge_type][COUNT_ATTR] = 0
    g[u][v][edge_type][KEYWORDS_ATTR] = []


# Constructs a Networkx graph of email communications. 
# 
# Args:
#   emails: list of Email objects representing emails received.
#
# Returns:
#   graph: a directed graph with parallel edges, where each edge
#          represents are 'to', 'cc', or 'bcc' relationship in a sent email, 
#          originating from the sender and terminating at the receiver.
#          The weight on the graph is the number of such emails sent.
#          The attributes contain information on common keywords from the email.         
def construct_social_graph(emails):
  # Social graph
  g = nx.MultiDiGraph() 

  # Create nodes for each user in graph.
  users = set()
  for email in emails:
    users.update(email.senders, email.to, email.cc, email.bcc)
  for user in users:
    g.add_node(user)

  print(g)
  
  # Build edges in graph
  for email in emails:
    for sender in email.senders:
      # TODO(akrentsel): Just handling tos for now. Add other types.
      for to in email.to:
        edge = maybe_add_edge(g, sender, to, TO_TYPE)
        g[sender][to][TO_TYPE][COUNT_ATTR] = g[sender][to][TO_TYPE][COUNT_ATTR] + 1
      for cc in email.cc:
        edge = maybe_add_edge(g, sender, to, CC_TYPE)
        g[sender][to][CC_TYPE][COUNT_ATTR] = g[sender][to][CC_TYPE][COUNT_ATTR] + 1
      for bcc in email.bcc:
        edge = maybe_add_edge(g, sender, to, BCC_TYPE)
        g[sender][to][BCC_TYPE][COUNT_ATTR] = g[sender][to][BCC_TYPE][COUNT_ATTR] + 1
  
  print(g)
  
  draw_graph(g)

# Visualizes the communication graph as stored in G.
# See https://stackoverflow.com/a/67145811/4015623 for more details
def draw_graph(G, filename="output/output.png"):
  # Consider using Netgraph: https://github.com/paulbrodersen/netgraph
  # Maybe draw 3 separate graphs, one for each kind of edge?
  # TODO(akrentsel): Add type labels and better edge labels.
  # print(nx.get_edge_attributes(G, COUNT_ATTR))
  pos = nx.circular_layout(G)
  plt.figure()
  nx.draw(
    G, pos, edge_color='black', width=1, linewidths=1,
    node_size=500, node_color='pink', alpha=0.9,
    labels={node: node for node in G.nodes()}
  )
  nx.draw_networkx_edge_labels(
    G, pos,
    # edge_labels=nx.get_edge_attributes(G, COUNT_ATTR),  
    font_color='red'
  )
  plt.axis('off')
  plt.savefig(filename)

def main():
  parser = argparse.ArgumentParser(description='Process some integers.')
  parser.add_argument('--num_emails', help="the number of emails to pull", type=int, default=5)
  args = parser.parse_args()
  emails = get_emails(args.num_emails)
  construct_social_graph(emails)

if __name__ == "__main__":
    main()

