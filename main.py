import os
from flask import Flask, request, jsonify
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

app = Flask(__name__)

# Gmail API scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Email to impersonate when using service account
# UPDATE THIS to your email address
USER_EMAIL = os.environ.get('USER_EMAIL', 'test.user@example.com')

def get_gmail_service():
    """
    Authenticate and return Gmail API service object.
    Uses service account if USE_SERVICE_ACCOUNT env var is set,
    otherwise uses OAuth flow (for local development).
    """
    # Check if we should use service account
    use_service_account = os.environ.get('USE_SERVICE_ACCOUNT', '').lower() == 'true'
    
    if use_service_account:
        # Service Account authentication (for Cloud Run)
        try:
            credentials = service_account.Credentials.from_service_account_file(
                'service-account.json', 
                scopes=SCOPES,
                subject=USER_EMAIL  # Impersonate this user
            )
            return build('gmail', 'v1', credentials=credentials)
        except Exception as e:
            raise Exception(f"Service account authentication failed: {str(e)}")
    else:
        # OAuth flow authentication (for local development)
        creds = None

        # Token file stores the user's access and refresh tokens
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        # If there are no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return build('gmail', 'v1', credentials=creds)

@app.route('/')
def hello():
    """Hello World endpoint"""
    auth_method = "Service Account" if os.environ.get('USE_SERVICE_ACCOUNT', '').lower() == 'true' else "OAuth"
    return jsonify({
        "message": "Hello World from Cloud Run!",
        "auth_method": auth_method,
        "user_email": USER_EMAIL if os.environ.get('USE_SERVICE_ACCOUNT', '').lower() == 'true' else "OAuth user"
    })

@app.route('/gmail-test')
def gmail_test():
    """Test endpoint to list Gmail labels"""
    try:
        service = get_gmail_service()
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])

        return jsonify({
            "status": "success",
            "label_count": len(labels),
            "labels": [label['name'] for label in labels],
            "auth_method": "Service Account" if os.environ.get('USE_SERVICE_ACCOUNT', '').lower() == 'true' else "OAuth"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "hint": "Check that domain-wide delegation is properly configured if using service account."
        }), 500
    
@app.route('/gmail-messages')
def gmail_messages():
    """List recent messages (example of additional functionality)"""
    try:
        service = get_gmail_service()

        # Get the first 10 messages
        results = service.users().messages().list(
            userId='me', 
            maxResults=10
        ).execute()

        messages = results.get('messages', [])

        # Get details for each message
        message_details = []
        for msg in messages:
            message = service.users().messages().get(
                userId='me', 
                id=msg['id'],
                format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()

            headers = {h['name']: h['value'] for h in message['payload']['headers']}
            message_details.append({
                'id': message['id'],
                'snippet': message['snippet'],
                'from': headers.get('From', 'Unknown'),
                'subject': headers.get('Subject', 'No subject'),
                'date': headers.get('Date', 'Unknown')
            })

        return jsonify({
            "status": "success",
            "message_count": len(message_details),
            "messages": message_details,
            "auth_method": "Service Account" if os.environ.get('USE_SERVICE_ACCOUNT', '').lower() == 'true' else "OAuth"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "hint": "Check that domain-wide delegation is properly configured if using service account."
        }), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
