"""DirectAdmin Quotas API"""

import logging
import re
from aiohttp import BasicAuth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)


class QuotasAPI:
    """Class to interact with the DirectAdmin Quotas API."""

    _quotas = {}
    _hostname: str
    _port: int = 2222  # Default port for DirectAdmin
    _domain: str
    _username: str
    _password: str

    def __init__(
        self,
        hass: HomeAssistant,
        hostname: str,
        port: int,
        domain: str,
        username: str,
        password: str,
    ):
        self._hass = hass
        self._hostname = hostname
        self._port = port
        self._domain = domain
        self._username = username
        self._password = password
        self._session = async_get_clientsession(self._hass)
        if self._hostname:
            self.__check_hostname()

    async def get_quotas(self):
        """Get the quotas for all mailboxes."""
        await self.update_quotas()
        return self._quotas
    
    async def get_domains(self):
        """Get the list of domains."""
        json_data = await self.send_request("CMD_API_SHOW_DOMAINS")
        if json_data:
            return json_data
        return []

    async def update_quotas(self):
        """Update the quotas for all mailboxes."""
        self._quotas = {}
        json_data = await self.send_request(
            "CMD_API_POP", {"action": "list", "domain": self._domain, "type": "quota"}
        )
        quotas = {}
        for account, value in json_data.items():
            account = f"{account}@{self._domain}"
            quotas[account] = {}
            for info in value.split("&"):
                key, value = info.split("=")
                value = int(value)
                quotas[account][key] = int(value)

            quota = quotas[account].get("quota", 0)
            usage = quotas[account].get("usage", 0)

            percentage_usage = round(usage / quota * 100, 1) if quota else None
            free = float(quota) - float(usage) if quota else None
            percentage_free = 100 - percentage_usage if percentage_usage else None

            quotas[account]["percentage_usage"] = percentage_usage
            quotas[account]["free"] = free
            quotas[account]["percentage_free"] = percentage_free

        self._quotas = quotas

    async def test_connection(self):
        """Test the connection to the DirectAdmin server."""
        try:
            await self.send_request("CMD_API_LOGIN_TEST")
        except Exception as e:
            _LOGGER.error("Failed to connect to DirectAdmin: %s", e)
            raise DirectAdminConnectionError(
                "Authentication failed or connection error."
            ) from e
        
    def __check_hostname(self):
        pattern = re.compile(r"^[a-zA-Z0-9.-]+$")  # Simple regex to validate hostname
        if not pattern.match(self._hostname):
            raise InvalidHostnameException("Invalid hostname format")


    async def test_domain(self):
        """Test if the given domain is valid."""
        valid_domains = await self.send_request("CMD_API_SHOW_DOMAINS")
        if not valid_domains:
            raise DirectAdminAuthError("Authentication failed or no domains found.")
        if self._domain not in valid_domains:
            raise DomainNotFoundError(
                f"Domain {self._domain} is not valid or does not exist."
            )

    async def send_request(self, function: str, payload: dict | None = None) -> dict:
        response = await self._session.post(
            f"https://{self._hostname}:{self._port}/{function}",
            auth=BasicAuth(self._username, self._password),
            data=payload,
            params={"json": "yes"},
        )
        if response.status != 200:
            _LOGGER.error(
                "Server responded with a non-200 http code while trying to run function %s on %s. Response content : %s",
                function,
                self._hostname,
                response.content,
            )
            return {}
        return await response.json()


class DirectAdminConnectionError(Exception):
    """Exception raised for connection errors with DirectAdmin."""


class DirectAdminAuthError(Exception):
    """Exception raised for authentication errors with DirectAdmin."""


class DomainNotFoundError(Exception):
    """Exception raised when the specified domain is not found."""

class InvalidHostnameException(Exception):
    """Exception raised for invalid hostname format."""