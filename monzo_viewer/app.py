"""Entry point for the viewer."""
from datetime import datetime, timedelta
from json import dumps, loads
from typing import Any, Dict, List, Optional

from flask import Flask, escape, redirect, render_template, request
from monzo.authentication import Authentication
from monzo.endpoints.account import Account
from monzo.endpoints.feed_item import FeedItem
from monzo.endpoints.transaction import Transaction
from monzo.exceptions import MonzoAuthenticationError, MonzoHTTPError, MonzoPermissionsError, MonzoServerError

from monzo_viewer.misc import FileSystem

app = Flask(__name__, template_folder='templates')

REDIRECT_URL = 'http://127.0.0.1:5000/setup/callback'
MONZO_HANDLER = FileSystem(file='monzo.json')

LINKS = [
    {
        'name': 'Accounts',
        'url': '/accounts',
    },
    {
        'name': 'Feed Item',
        'url': '/feed_item',
    },
    {
        'name': 'Raw Request',
        'url': '/raw_request',
    },
]


def auth_setup(client_id: str = None, client_secret: str = None):
    """
    Create and set up the Auth object.

    Args:
        client_id: Monzo Client ID, if not specified it will use the value from the handler.
        client_secret: Monzo Client Secret, if not specified it will use the value from the handler.

    Returns:
        Auth object with handler specified
    """
    if not client_id:
        client_id = MONZO_HANDLER.client_id
    if not client_secret:
        client_secret = MONZO_HANDLER.client_secret
    auth = Authentication(
        access_token=MONZO_HANDLER.access_token,
        access_token_expiry=MONZO_HANDLER.expiry,
        client_id=client_id,
        client_secret=client_secret,
        redirect_url=REDIRECT_URL,
        refresh_token=MONZO_HANDLER.refresh_token,
    )
    auth.register_callback_handler(MONZO_HANDLER)
    return auth


@app.route('/')
def index():
    """Handle displaying index page."""
    if not MONZO_HANDLER.is_configured:
        return redirect('/setup/')
    context = {
        'links': LINKS,
    }
    return render_template('index.html', **context)


@app.route('/accounts')
def accounts():
    """Handle displaying accounts."""
    if not MONZO_HANDLER.is_configured:
        return redirect('/setup/')
    auth = auth_setup()
    try:
        account_list = fetch_accounts(auth=auth, all_accounts=True)
    except MonzoPermissionsError:
        context = {
            'error': 'The request resulted in a permissions error.'
        }
        return render_template('error.html', **context)
    context = {
        'accounts': account_list,
    }
    return render_template('accounts.html', **context)


@app.route('/feed_item', methods=['GET', 'POST'])
def feed_iten():
    """Post an item on the feed."""
    auth = auth_setup()
    context = {
        'accounts': fetch_accounts(auth=auth, all_accounts=False)
    }
    if request.method == 'GET':
        return render_template('feed_item_form.html', **context)
    optional_parameters = (
        'body',
        'title_color',
        'body_color',
        'background_color',
        'image_url',
    )
    parameters = {
        'title': escape(request.form['title'])
    }
    feed_item_url: Optional[str] = None
    for optional_parameter in optional_parameters:
        if optional_parameter in request.form:
            parameters[optional_parameter] = escape(request.form[optional_parameter])
    account = escape(request.form['account'])
    if 'feed_item_url' in request.form:
        feed_item_url = escape(request.form['feed_item_url'])
    auth = auth_setup()
    try:
        FeedItem.create(
            auth=auth,
            account_id=account,
            feed_type='basic',
            params=parameters,
            url=feed_item_url,
        )
        template_name = 'message.html'
        context['message'] = 'Feed item posted successfully.'
    except MonzoHTTPError:
        context['message'] = 'The Monzo API did not understand the request.'
        template_name = 'error.html'
    except MonzoPermissionsError:
        context['message'] = 'The request resulted in a permissions error.'
        template_name = 'error.html'
    return render_template(template_name, **context)


@app.route('/transactions', methods=['post'])
def transactions_for_account():
    """Handle displaying transactions for an account."""
    if 'account' in request.form and escape(request.form['account']):
        account = escape(request.form['account'])
        if account == 'Please Select':
            context = {
                'message': 'No account specified.'
            }
            return render_template('error.html', **context)
    else:
        context = {
            'message': 'No account specified.'
        }
        return render_template('error.html', **context)
    auth = auth_setup()
    thirty_days_ago = datetime.now() - timedelta(days=30)
    try:
        context = {
            'transactions': Transaction.fetch(
                auth=auth,
                account_id=account,
                since=thirty_days_ago,
                expand=['merchant'],
            )
        }
        return render_template('transactions.html', **context)
    except MonzoPermissionsError:
        error = (
            'The API returned a permissions issue. Either the token has expired or the account cannot return '
            + 'transactions.'
        )
        context = {
            'message': error,
        }
        return render_template('error.html', **context)


@app.route('/raw_request', methods=['GET', 'POST'])
def raw_request():
    """Handle the raw_request url."""
    context = {}
    auth = auth_setup()

    if request.method == 'GET':
        return render_template('raw_request.html', **context)
    else:
        authenticated = bool(request.form.get('authenticated', True))
        request_type = request.form.get('authenticated', ['get'])
        headers = loads(request.form['headers']) if 'headers' in request.form else {}
        monzo_parameters = {}
        if 'parameters' in request.form and request.form['parameters']:
            monzo_parameters = loads(request.form['parameters'])
        records = get_raw_request(
            auth=auth,
            path=request.form.get('path', ['/']),
            authenticated=authenticated,
            request_type=request_type,
            headers=headers,
            parameters=monzo_parameters
        )
        context['records'] = dumps(records, indent=4, sort_keys=True)
        return render_template('raw_request_result.html', **context)


@app.route('/setup/', methods=['GET', 'POST'])
def setup():
    """Handle the initial Monzo setup."""
    context = {
        'REDIRECT_URL': REDIRECT_URL
    }
    if request.method == 'GET':
        return render_template('setup.html', **context)
    context['CLIENT_ID_VALUE'] = escape(request.form['client_id'])
    context['CLIENT_SECRET_VALUE'] = escape(request.form['client_secret'])
    if not len(context['CLIENT_ID_VALUE']) or not len(context['CLIENT_SECRET_VALUE']):
        context['message'] = 'Ensure you enter both a Client ID and a Client Secret.'
        return render_template('setup.html', **context)
    else:
        MONZO_HANDLER.set_client_details(
            client_id=context['CLIENT_ID_VALUE'],
            client_secret=context['CLIENT_SECRET_VALUE'],
        )
        auth = auth_setup(client_id=MONZO_HANDLER.client_id, client_secret=MONZO_HANDLER.client_secret)
        return redirect(auth.authentication_url)


@app.route('/setup/callback/')
def setup_callback():
    """Handle the callback requests from Monzo."""
    context = {}
    if all(["code" in request.args, "state" in request.args]):
        code = request.args["code"]
        state = request.args["state"]
        auth = Authentication(
            client_id=MONZO_HANDLER.client_id,
            client_secret=MONZO_HANDLER.client_secret,
            redirect_url=REDIRECT_URL,
        )
        auth.register_callback_handler(handler=MONZO_HANDLER)
        try:
            auth.authenticate(authorization_token=code, state_token=state)
            return render_template('success.html')
        except MonzoAuthenticationError:
            context['message'] = 'Monzo authentication error.'
        except MonzoServerError:
            context['message'] = 'Monzo server error.'
    else:
        context['message'] = 'Missing parameters.'
    return render_template('error.html', **context)


def fetch_accounts(auth, all_accounts: bool = False) -> List[Account]:
    """
    Fetch accounts from Monzo.

    Args:
        auth: The authentication object
        all_accounts: Returns all if True otherwise only those that will show transactions.
    Returns:
        List of transactions
    """
    account_list = Account.fetch(auth=auth)
    selected_accounts = []
    if not all_accounts:
        for account in account_list:
            if account.account_type() not in ('Loan (Flex)', 'Loan'):
                selected_accounts.append(account)
    else:
        selected_accounts = account_list
    return selected_accounts


def get_raw_request(
        auth: Authentication,
        path: str,
        authenticated: bool = True,
        request_type: str = 'get',
        headers: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
):
    """
    Perform a raw request.

    Args
        auth: Monzo Authentication object
        path: API path for request
        authenticated: True if call should be authenticated
        request_type: HTTP method to use (DELETE, GET, POST, PUT)
        headers: Dictionary of headers for the request
        parameters: Dictionary of parameters for the request

    Returns:
        List of Account objects
    """
    try:
        res = auth.make_request(
            path=path,
            authenticated=authenticated,
            method=request_type,
            data=parameters,
            headers=headers,
        )
        records = res['data']
    except MonzoPermissionsError:
        records = {
            'message': 'The request resulted in a permissions error.'
        }
    except MonzoHTTPError:
        records = {
            'message': 'The request appears invalid.'
        }
    return records
