"""Entry point for the viewer."""
from datetime import datetime, timedelta
from json import dumps, loads
from typing import Any, Dict, Optional

from flask import Flask, escape, redirect, render_template, request
from monzo.authentication import Authentication
from monzo.endpoints.account import Account
from monzo.endpoints.transaction import Transaction
from monzo.exceptions import MonzoAuthenticationError, MonzoPermissionsError, MonzoServerError

from monzo_viewer.misc import FileSystem

app = Flask(__name__, template_folder='templates')

REDIRECT_URL = 'http://127.0.0.1:5000/setup/callback'
MONZO_HANDLER = FileSystem(file='monzo.json')


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
        context['ERROR_MESSAGE'] = 'Ensure you enter both a Client ID and a Client Secret'
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
            return redirect(location='/')
        except MonzoAuthenticationError:
            context['error'] = 'Monzo authentication error'
        except MonzoServerError:
            context['error'] = 'Monzo server error'
    else:
        context['error'] = 'Missing parameters'
    return render_template('error.html', **context)


@app.route('/', methods=['GET', 'POST'])
def index():
    """Handle displaying accounts."""
    auth = auth_setup()
    if not MONZO_HANDLER.is_configured:
        redirect('/setup/')
    if request.method == 'POST' and escape(request.form['account']):
        return redirect(f"/accounts/{escape(request.form['account'])}/")
    context = {'accounts': Account.fetch(auth=auth)}
    return render_template('index.html', **context)


@app.route('/accounts/<account>/')
def transactions_for_account(account: str):
    """Handle displaying transactions for an account."""
    auth = auth_setup()
    thirty_days_ago = datetime.now() - timedelta(days=30)
    context = {
        'transactions': Transaction.fetch(
            auth=auth,
            account_id=account,
            since=thirty_days_ago,
            expand=['merchant'],
        )
    }

    return render_template('transactions.html', **context)


@app.route('/raw_request/', methods=['GET', 'POST'])
def raw_request():
    """Handle the raw_request url."""
    context = {}
    auth = auth_setup()

    if request.method == 'GET':
        return render_template('raw_request.html', **context)

    if 'submit' in request.form:
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
    return render_template('raw_request.html', **context)


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
        records = {'error': 'Permissions error'}
    return records
