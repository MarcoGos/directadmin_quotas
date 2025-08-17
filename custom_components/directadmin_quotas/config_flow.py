"""Config flow for DirectAdmin quotas integration."""

from __future__ import annotations

import logging
from typing import Any
from aiohttp.client_exceptions import (
    ClientConnectorDNSError,
    ConnectionTimeoutError,
)

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_validation, device_registry as dr

from .const import (
    DOMAIN,
    CONF_HOSTNAME,
    CONF_PORT,
    CONF_DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_ACCOUNTS,
)
from .api import (
    QuotasAPI,
    DirectAdminAuthError,
    DomainNotFoundError,
    DirectAdminConnectionError,
)

_LOGGER = logging.getLogger(__name__)


class DirectAdminQuotasOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for DirectAdmin Quotas."""

    def __init__(self) -> None:
        """Initialize DirectAdmin Quotas options flow."""

    async def async_step_init(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the DirectAdmin Quotas options."""
        return await self.async_step_accounts()

    async def async_step_accounts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors: dict[str, str] | None = {}
        entry = self.config_entry

        if user_input is not None:
            new_accounts = user_input.get(CONF_ACCOUNTS, [])
            old_accounts = entry.data.get(CONF_ACCOUNTS, [])
            device_registry = dr.async_get(self.hass)
            if removed_accounts := set(old_accounts) - set(new_accounts):
                for account in removed_accounts:
                    device = device_registry.async_get_device(
                        identifiers={(DOMAIN, account)}
                    )
                    if device:
                        _LOGGER.debug("Removing device: %s", device)
                        device_registry.async_update_device(
                            device_id=device.id,
                            remove_config_entry_id=entry.entry_id,
                        )

            self.hass.config_entries.async_update_entry(
                entry,
                data=entry.data | user_input,  # type: ignore
            )
            await self.hass.config_entries.async_reload(entry.entry_id)  # type: ignore
            return self.async_abort(reason="changes_successful")

        hostname = entry.data.get(CONF_HOSTNAME, "")
        port = entry.data.get(CONF_PORT, 2222)
        domain = entry.data.get(CONF_DOMAIN, "")
        username = entry.data.get(CONF_USERNAME, "")
        password = entry.data.get(CONF_PASSWORD, "")
        api = QuotasAPI(
            hass=self.hass,
            hostname=hostname,
            port=port,
            domain=domain,
            username=username,
            password=password,
        )
        accounts = []
        quotas = await api.get_quotas()
        for account in sorted(quotas.keys()):
            accounts.append(account)

        data_schema = vol.Schema(
            {vol.Required(CONF_ACCOUNTS): config_validation.multi_select(accounts)}
        )

        return self.async_show_form(
            step_id="accounts",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=data_schema,
                suggested_values=entry.data | (user_input or {}),  # type: ignore
            ),
            errors=errors,
        )


class DirectAdminQuotasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DirectAdmin Quotas."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DOMAIN])
            self._abort_if_unique_id_configured()

            try:
                api = QuotasAPI(
                    hass=self.hass,
                    hostname=user_input[CONF_HOSTNAME],
                    port=user_input.get(CONF_PORT, 2222),
                    domain=user_input.get(CONF_DOMAIN, ""),
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                await api.test_connection()
                await api.test_domain()
            except (ClientConnectorDNSError, DirectAdminConnectionError):
                errors["base"] = "cannot_connect"
            except DirectAdminAuthError:
                errors["base"] = "invalid_auth"
            except DomainNotFoundError:
                errors["base"] = "domain_not_found"
            except ConnectionTimeoutError:
                errors["base"] = "timeout"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._config[CONF_HOSTNAME] = user_input[CONF_HOSTNAME]
                self._config[CONF_PORT] = user_input.get(CONF_PORT, 2222)
                self._config[CONF_DOMAIN] = user_input.get(CONF_DOMAIN, "")
                self._config[CONF_USERNAME] = user_input[CONF_USERNAME]
                self._config[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                return await self.async_step_accounts()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOSTNAME): str,
                vol.Optional(CONF_PORT, default=2222): int,
                vol.Optional(CONF_DOMAIN): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=data_schema,
                suggested_values=user_input or {},
            ),
            errors=errors,
        )

    async def async_step_accounts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the accounts step."""

        if user_input is not None:
            # Create all the devices and entities
            selected_accounts = user_input[CONF_ACCOUNTS]
            self._config[CONF_ACCOUNTS] = selected_accounts
            return self.async_create_entry(
                title=f"{self._config[CONF_DOMAIN]}", data=self._config
            )

        api = QuotasAPI(
            hass=self.hass,
            hostname=self._config[CONF_HOSTNAME],
            port=self._config.get(CONF_PORT, 2222),
            domain=self._config[CONF_DOMAIN],
            username=self._config[CONF_USERNAME],
            password=self._config[CONF_PASSWORD],
        )
        accounts = []
        quotas = await api.get_quotas()
        for account in sorted(quotas.keys()):
            accounts.append(account)

        data_schema = vol.Schema(
            {vol.Required(CONF_ACCOUNTS): config_validation.multi_select(accounts)}
        )

        return self.async_show_form(step_id="accounts", data_schema=data_schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        errors: dict[str, str] | None = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])  # type: ignore

        if user_input is not None:
            try:
                api = QuotasAPI(
                    hass=self.hass,
                    hostname=user_input[CONF_HOSTNAME],
                    port=user_input.get(CONF_PORT, 2222),
                    domain=user_input[CONF_DOMAIN],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
                await api.test_connection()
                await api.test_domain()
            except (ClientConnectorDNSError, DirectAdminConnectionError):
                errors["base"] = "cannot_connect"
            except DirectAdminAuthError:
                errors["base"] = "invalid_auth"
            except DomainNotFoundError:
                errors["base"] = "domain_not_found"
            except ConnectionTimeoutError:
                errors["base"] = "timeout"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,  # type: ignore
                    data=entry.data | user_input,  # type: ignore
                )
                await self.hass.config_entries.async_reload(entry.entry_id)  # type: ignore
                return self.async_abort(reason="reconfigure_successful")

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOSTNAME): str,
                vol.Optional(CONF_PORT, default=2222): int,
                vol.Optional(CONF_DOMAIN): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                data_schema=data_schema,
                suggested_values=entry.data | (user_input or {}),  # type: ignore
            ),
            description_placeholders={"name": entry.title},  # type: ignore
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> DirectAdminQuotasOptionsFlowHandler:
        """Options callback for DirectAdmin Quotas."""
        return DirectAdminQuotasOptionsFlowHandler()
