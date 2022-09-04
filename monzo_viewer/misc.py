"""Miscellaneous functions and classes."""

from json import dumps, loads
from typing import Dict, Union

from monzo.handlers.storage import Storage


class FileSystem(Storage):
    """Class that will store credentials on the file system."""

    __slots__ = [
        '_access_token',
        '_client_id',
        '_client_secret',
        '_expiry',
        '_file',
        '_refresh_token',
        '_fetched',
    ]

    def __init__(self, file: str):
        """
        Initialize FileSystem.

        Args:
            file: THe full path (including filename) to the storage file
        """
        self._file = file

        self._access_token: str = ''
        self._client_id: str = ''
        self._client_secret: str = ''
        self._expiry: int = 0
        self._refresh_token: str = ''
        self._fetched: bool = False

    def set_client_details(self, client_id: str, client_secret: str):
        """
        Store a given client id and secret and clear all other details.

        Args:
            client_id: Client ID
            client_secret: Client secret
        """
        self._access_token = ''
        self._client_id = client_id
        self._client_secret = client_secret
        self._expiry = 0
        self._refresh_token = ''
        self._fetched = False

        content = {
            'access_token': self._access_token,
            'client_id': self._client_id,
            'client_secret': self._client_secret,
            'expiry': self._expiry,
            'refresh_token': self._refresh_token
        }
        with open(self._file, 'w') as handler:
            handler.write(dumps(content))

    def store(
        self,
        access_token: str,
        client_id: str,
        client_secret: str,
        expiry: int,
        refresh_token: str = ''
    ) -> None:
        """
        Store the Monzo credentials.

        Args:
            access_token: New access token
            client_id: Monzo client ID
            client_secret: Monzo client secret
            expiry: Access token expiry as a unix timestamp
            refresh_token: Refresh token that can be used to renew an access token
        """
        self._fetched = True
        self._access_token = access_token
        self._client_id = client_id
        self._client_secret = client_secret
        self._expiry = expiry
        self._refresh_token = refresh_token

        content = {
            'access_token': access_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'expiry': expiry,
            'refresh_token': refresh_token
        }
        with open(self._file, 'w') as handler:
            handler.write(dumps(content))

    def fetch(self) -> Dict[str, Union[int, str]]:
        """
        Fetch the Monzo credentials previously stored.

        Returns:
            Dictionary containing access token, expiry and refresh token
        """
        try:
            with open(self._file, 'r') as handler:
                content = loads(handler.read())
                self._fetched = True
        except FileNotFoundError:
            content = {}

        for item, value in content.items():
            self.__setattr__(f'_{item}', value)
        return content

    @property
    def is_configured(self) -> bool:
        """
        Identify if Monzo has been configured.

        Returns:
             True if configured otherwise False
        """
        if not self._fetched:
            self.fetch()
        if not self._fetched:
            return False
        keys = [
            'client_id',
            'client_secret',
            'access_token',
            'expiry',
        ]
        print(all(self.__getattribute__(key) for key in keys))
        return all(self.__getattribute__(key) for key in keys)

    @property
    def access_token(self) -> str:
        """
        Property for access token.

        Returns:
             access token
        """
        if not self._fetched:
            self.fetch()
        return self._access_token or ''

    @property
    def client_id(self) -> str:
        """
        Property for client id.

        Returns:
            client id
        """
        if not self._fetched:
            self.fetch()
        return self._client_id or ''

    @client_id.setter
    def client_id(self, client_id: str):
        """
        Setter for client id.

        Args:
            client_id: Monzo client id
        """
        self._client_id = client_id

    @property
    def client_secret(self) -> str:
        """
        Property for client secret.

        Returns:
            client secret
        """
        if not self._fetched:
            self.fetch()
        return self._client_secret or ''

    @client_secret.setter
    def client_secret(self, client_secret: str):
        """
        Setter for client secret.

        Args:
            client_secret: Monzo client secret
        """
        self._client_secret = client_secret

    @property
    def expiry(self) -> int:
        """
        Property for expiry.

        Returns:
            expiry
        """
        if not self._fetched:
            self.fetch()
        return self._expiry or 0

    @property
    def refresh_token(self) -> str:
        """
        Property for refresh token.

        Returns:
            refresh token
        """
        if not self._fetched:
            self.fetch()
        return self._refresh_token or ''
