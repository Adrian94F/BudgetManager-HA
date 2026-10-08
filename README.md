# Budget Manager for Home Assistant

A custom integration that brings a [Budget Manager](https://github.com/Adrian94F/BudgetManagerSrv)
server into Home Assistant: this month's balance, the daily allowance, what
was spent today and per category, plus actions to add expenses and incomes.

> Work in progress. Needs a server with the `/api/summary/` endpoint.

## Installation

**HACS:**

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Adrian94F&repository=BudgetManager-HA&category=integration)

or add this repository as a custom repository (category *Integration*) by hand.
Then download *Budget Manager* and restart Home Assistant.

**Manually:** copy `custom_components/budgetmanager` to the `custom_components`
folder of your Home Assistant configuration and restart.

Then add the integration:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=budgetmanager)

or go to *Settings → Devices & services → Add integration → Budget Manager*,
and enter the server URL, username and password. The password is used once to
sign in; only a refresh token is stored. If Home Assistant stays offline for
longer than the token lives (7 days), it asks you to sign in again.

## Entities

All figures are for the month going on today and match the Summary page.

| Entity | Description |
|---|---|
| `sensor.*_balance` | Incomes minus expenses; the figure after planned savings is in attributes |
| `sensor.*_daily_allowance` | What may still be spent per day |
| `sensor.*_spent_today` | Daily expenses dated today |
| `sensor.*_daily_allowance_used` | Today's spending as % of the allowance |
| `sensor.*_days_left` | Days to the end of the month, today included |
| `sensor.*_incomes`, `*_expenses`, `*_recurring_expenses`, `*_daily_expenses` | Month totals |
| `sensor.*_last_expense` | The latest expense; category, comment and date in attributes |
| `sensor.*_average_monthly_balance` | Mean balance of all months; per-month history in attributes |
| `sensor.*_spent_on_<category>` | One per expense category |
| `binary_sensor.*_over_budget` | The balance is below zero |
| `binary_sensor.*_daily_allowance_exceeded` | Today's spending is above the allowance |
| `binary_sensor.*_server` | Whether the last poll reached the server |
| `number.*_planned_savings` | Planned savings, editable |

The server is polled every 5 minutes and right after any change made from
Home Assistant. To poll more or less often, open *Settings → Devices &
services → Budget Manager → Configure* and set the interval in hours, minutes
and seconds (at least 10 seconds). It takes effect at once, without a restart.

## Actions

```yaml
action: budgetmanager.add_expense
data:
  value: 42.50
  category: Food      # name or id
  comment: Lunch      # optional
  date: "2026-10-07"  # optional, defaults to today
  is_monthly: false   # optional
```

```yaml
action: budgetmanager.add_income
data:
  value: 5000
  is_salary: true
```

The date must fall within the month going on.

## Example automation

```yaml
alias: Daily spending report
triggers:
  - trigger: time
    at: "20:00:00"
actions:
  - action: notify.mobile_app_phone
    data:
      message: >
        Spent {{ states('sensor.budget_manager_alice_spent_today') }} of
        {{ states('sensor.budget_manager_alice_daily_allowance') }} today
        ({{ states('sensor.budget_manager_alice_daily_allowance_used') }}%).
```

A sample dashboard is in [examples/dashboard.yaml](examples/dashboard.yaml).

## Releasing

```bash
./release.sh patch   # or minor, major, or an explicit X.Y.Z
```

On Windows run it from Git Bash; in PowerShell, `bash` is usually WSL's,
whose git lacks your identity and GitHub credentials:

```powershell
& "C:\Program Files\Git\bin\bash.exe" release.sh patch
```

The script bumps `version` in `manifest.json`, commits, tags `vX.Y.Z` and
pushes; the *Release* workflow then publishes the GitHub release, which HACS
offers as an update. Run `./release.sh 0.1.0` for the first release: it tags
the current version without bumping it.

## License

[Apache License 2.0](LICENSE)
