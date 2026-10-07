"""Constants for the Budget Manager integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "budgetmanager"

CONF_REFRESH_TOKEN: Final = "refresh_token"

# The server throttles a user at 120 requests a minute and a poll makes two;
# budget figures change only when someone adds an entry, so a few minutes is
# plenty. The user can change it in the integration's options.
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=5)
MIN_SCAN_INTERVAL: Final = timedelta(seconds=10)

SERVICE_ADD_EXPENSE: Final = "add_expense"
SERVICE_ADD_INCOME: Final = "add_income"

ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_VALUE: Final = "value"
ATTR_CATEGORY: Final = "category"
ATTR_COMMENT: Final = "comment"
ATTR_DATE: Final = "date"
ATTR_IS_MONTHLY: Final = "is_monthly"
ATTR_IS_SALARY: Final = "is_salary"
