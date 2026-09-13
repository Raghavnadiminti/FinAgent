# mcp_analytics_tools.py

from mcp.server.fastmcp import FastMCP

from DB.functions import (
    get_general_ledger,
    get_ar_aging,
    get_ap_aging,
)


mcp = FastMCP("AI Accountant Analytics")


# ============================================================
# HELPERS
# ============================================================

def money(value) -> float:
    """Safely convert a value to a rounded monetary amount."""
    return round(float(value or 0), 2)


def gl_amount(row: dict) -> float:
    """Return signed GL amount: debit positive, credit negative."""
    return money(row.get("debit")) - money(row.get("credit"))


# ============================================================
# 1. TRIAL BALANCE
# ============================================================

@mcp.tool()
def calculate_trial_balance(
    start_date: str,
    end_date: str,
):
    """
    Calculate the trial balance for an accounting period.

    The trial balance summarizes total debits and credits for
    each GL account and verifies whether total debits equal
    total credits.

    Args:
        start_date:
            Start date in YYYY-MM-DD format.

        end_date:
            End date in YYYY-MM-DD format.

    Returns:
        Compact trial balance containing:
        - total_debit
        - total_credit
        - difference
        - balanced
        - account_count
        - accounts

        Each account contains:
        - account_id
        - account_name
        - debit
        - credit
        - balance

    Use when:
        The agent needs to determine whether the ledger is
        balanced or obtain account-level trial balance figures.
    """

    rows = get_general_ledger(
        start_date=start_date,
        end_date=end_date,
        limit=5000,
    )

    accounts = {}

    for row in rows:

        account_id = row.get("account_id")

        if not account_id:
            continue

        if account_id not in accounts:
            accounts[account_id] = {
                "account_id": account_id,
                "account_name": row.get("account_name"),
                "debit": 0.0,
                "credit": 0.0,
            }

        accounts[account_id]["debit"] += money(
            row.get("debit")
        )

        accounts[account_id]["credit"] += money(
            row.get("credit")
        )

    total_debit = round(
        sum(a["debit"] for a in accounts.values()),
        2,
    )

    total_credit = round(
        sum(a["credit"] for a in accounts.values()),
        2,
    )

    difference = round(
        total_debit - total_credit,
        2,
    )

    account_results = []

    for account in accounts.values():

        account["debit"] = round(
            account["debit"],
            2,
        )

        account["credit"] = round(
            account["credit"],
            2,
        )

        account["balance"] = round(
            account["debit"] - account["credit"],
            2,
        )

        account_results.append(account)

    return {
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": difference,
        "balanced": abs(difference) <= 0.01,
        "account_count": len(account_results),
        "accounts": account_results,
    }


# ============================================================
# 2. PROFIT & LOSS
# ============================================================

@mcp.tool()
def generate_profit_loss(
    start_date: str,
    end_date: str,
):
    """
    Generate a Profit and Loss statement for an accounting period.

    Calculates revenue, expenses, and net profit/loss from
    general ledger transactions.

    Args:
        start_date:
            Start date in YYYY-MM-DD format.

        end_date:
            End date in YYYY-MM-DD format.

    Returns:
        {
            "revenue": number,
            "expenses": number,
            "net_profit": number,
            "net_margin": percentage,
            "revenue_accounts": [...],
            "expense_accounts": [...]
        }

    Use when:
        The user asks about profitability, revenue, expenses,
        or financial performance for a period.

    Important:
        Account classification should come from the chart of
        accounts/account_type returned by the database.
    """

    rows = get_general_ledger(
        start_date=start_date,
        end_date=end_date,
        limit=5000,
    )

    revenue_accounts = {}
    expense_accounts = {}

    for row in rows:

        account_type = (
            str(row.get("account_type") or "")
            .upper()
        )

        account_id = row.get("account_id")

        if not account_id:
            continue

        amount = gl_amount(row)

        account = {
            "account_id": account_id,
            "account_name": row.get("account_name"),
        }

        if account_type in {
            "REVENUE",
            "INCOME",
        }:

            if account_id not in revenue_accounts:
                revenue_accounts[account_id] = {
                    **account,
                    "amount": 0.0,
                }

            # Revenue normally has credit balance.
            revenue_accounts[account_id]["amount"] += -amount

        elif account_type in {
            "EXPENSE",
            "COST_OF_GOODS_SOLD",
            "COGS",
        }:

            if account_id not in expense_accounts:
                expense_accounts[account_id] = {
                    **account,
                    "amount": 0.0,
                }

            expense_accounts[account_id]["amount"] += amount

    revenue = round(
        sum(
            x["amount"]
            for x in revenue_accounts.values()
        ),
        2,
    )

    expenses = round(
        sum(
            x["amount"]
            for x in expense_accounts.values()
        ),
        2,
    )

    net_profit = round(
        revenue - expenses,
        2,
    )

    net_margin = (
        round((net_profit / revenue) * 100, 2)
        if revenue
        else 0.0
    )

    return {
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "revenue": revenue,
        "expenses": expenses,
        "net_profit": net_profit,
        "net_margin": net_margin,
        "revenue_accounts": list(
            revenue_accounts.values()
        ),
        "expense_accounts": list(
            expense_accounts.values()
        ),
    }


# ============================================================
# 3. BALANCE SHEET
# ============================================================

@mcp.tool()
def generate_balance_sheet(
    as_of_date: str,
):
    """
    Generate a Balance Sheet as of a specified date.

    Summarizes:
    - Assets
    - Liabilities
    - Equity

    Also verifies:

        Assets = Liabilities + Equity

    Args:
        as_of_date:
            Balance sheet date in YYYY-MM-DD format.

    Returns:
        {
            "assets": number,
            "liabilities": number,
            "equity": number,
            "total_liabilities_and_equity": number,
            "difference": number,
            "balanced": true/false
        }

    Use when:
        The user asks for current financial position,
        assets, liabilities, equity, or a balance sheet.
    """

    rows = get_general_ledger(
        start_date="1900-01-01",
        end_date=as_of_date,
        limit=10000,
    )

    accounts = {}

    for row in rows:

        account_id = row.get("account_id")

        if not account_id:
            continue

        if account_id not in accounts:
            accounts[account_id] = {
                "account_id": account_id,
                "account_name": row.get("account_name"),
                "account_type": row.get("account_type"),
                "balance": 0.0,
            }

        accounts[account_id]["balance"] += gl_amount(row)

    assets = 0.0
    liabilities = 0.0
    equity = 0.0

    asset_accounts = []
    liability_accounts = []
    equity_accounts = []

    for account in accounts.values():

        account_type = (
            str(account.get("account_type") or "")
            .upper()
        )

        balance = round(
            account["balance"],
            2,
        )

        result = {
            "account_id": account["account_id"],
            "account_name": account["account_name"],
            "balance": abs(balance),
        }

        if account_type == "ASSET":

            assets += balance
            asset_accounts.append(result)

        elif account_type == "LIABILITY":

            liabilities += -balance
            liability_accounts.append(result)

        elif account_type == "EQUITY":

            equity += -balance
            equity_accounts.append(result)

    assets = round(assets, 2)
    liabilities = round(liabilities, 2)
    equity = round(equity, 2)

    total_liabilities_and_equity = round(
        liabilities + equity,
        2,
    )

    difference = round(
        assets - total_liabilities_and_equity,
        2,
    )

    return {
        "as_of_date": as_of_date,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_liabilities_and_equity":
            total_liabilities_and_equity,
        "difference": difference,
        "balanced": abs(difference) <= 0.01,
        "asset_accounts": asset_accounts,
        "liability_accounts": liability_accounts,
        "equity_accounts": equity_accounts,
    }


# ============================================================
# 4. CASH FLOW
# ============================================================

@mcp.tool()
def calculate_cash_flow(
    start_date: str,
    end_date: str,
):
    """
    Calculate cash inflows and outflows for an accounting period.

    Uses GL transactions associated with cash/bank accounts.

    Args:
        start_date:
            Start date in YYYY-MM-DD format.

        end_date:
            End date in YYYY-MM-DD format.

    Returns:
        {
            "cash_inflow": number,
            "cash_outflow": number,
            "net_cash_flow": number,
            "transaction_count": number
        }

    Use when:
        The user asks about cash movement, cash inflows,
        cash outflows, or net cash flow.

    Important:
        A full indirect-method cash-flow statement requires
        additional account classification and opening/closing
        balances. This tool calculates cash movement from the
        configured cash/bank accounts.
    """

    rows = get_general_ledger(
        start_date=start_date,
        end_date=end_date,
        limit=5000,
    )

    cash_inflow = 0.0
    cash_outflow = 0.0
    transaction_count = 0

    for row in rows:

        account_type = (
            str(row.get("account_type") or "")
            .upper()
        )

        if account_type not in {
            "CASH",
            "BANK",
        }:
            continue

        debit = money(row.get("debit"))
        credit = money(row.get("credit"))

        cash_inflow += debit
        cash_outflow += credit

        transaction_count += 1

    cash_inflow = round(
        cash_inflow,
        2,
    )

    cash_outflow = round(
        cash_outflow,
        2,
    )

    net_cash_flow = round(
        cash_inflow - cash_outflow,
        2,
    )

    return {
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "cash_inflow": cash_inflow,
        "cash_outflow": cash_outflow,
        "net_cash_flow": net_cash_flow,
        "transaction_count": transaction_count,
    }


# ============================================================
# 5. VARIANCE ANALYSIS
# ============================================================

@mcp.tool()
def calculate_variance(
    account_id: str,
    current_start_date: str,
    current_end_date: str,
    comparison_start_date: str,
    comparison_end_date: str,
):
    """
    Calculate the variance of one GL account between two periods.

    Args:
        account_id:
            GL account to analyze.

        current_start_date:
            Start of current period, YYYY-MM-DD.

        current_end_date:
            End of current period, YYYY-MM-DD.

        comparison_start_date:
            Start of comparison period, YYYY-MM-DD.

        comparison_end_date:
            End of comparison period, YYYY-MM-DD.

    Returns:
        {
            "current_amount": number,
            "comparison_amount": number,
            "absolute_variance": number,
            "percentage_variance": number
        }

    Use when:
        The user asks why an account increased/decreased,
        or wants period-over-period financial variance.
    """

    current_rows = get_general_ledger(
        account_id=account_id,
        start_date=current_start_date,
        end_date=current_end_date,
        limit=5000,
    )

    comparison_rows = get_general_ledger(
        account_id=account_id,
        start_date=comparison_start_date,
        end_date=comparison_end_date,
        limit=5000,
    )

    current_amount = round(
        sum(
            gl_amount(row)
            for row in current_rows
        ),
        2,
    )

    comparison_amount = round(
        sum(
            gl_amount(row)
            for row in comparison_rows
        ),
        2,
    )

    absolute_variance = round(
        current_amount - comparison_amount,
        2,
    )

    if abs(comparison_amount) > 0.01:

        percentage_variance = round(
            (
                absolute_variance
                / abs(comparison_amount)
            ) * 100,
            2,
        )

    else:

        percentage_variance = None

    return {
        "account_id": account_id,
        "current_period": {
            "start": current_start_date,
            "end": current_end_date,
        },
        "comparison_period": {
            "start": comparison_start_date,
            "end": comparison_end_date,
        },
        "current_amount": current_amount,
        "comparison_amount": comparison_amount,
        "absolute_variance": absolute_variance,
        "percentage_variance": percentage_variance,
    }


# ============================================================
# 6. AGING
# ============================================================

@mcp.tool()
def calculate_aging(
    aging_type: str,
    as_of_date: str,
):
    """
    Calculate outstanding AR or AP aging as of a date.

    Args:
        aging_type:
            Either:
            - "AR" for Accounts Receivable
            - "AP" for Accounts Payable

        as_of_date:
            Aging date in YYYY-MM-DD format.

    Returns:
        Aging buckets:
        - current
        - 1_30
        - 31_60
        - 61_90
        - over_90
        - total_outstanding

    Use when:
        The user asks who owes money, who needs to be paid,
        overdue invoices, receivables aging, or payables aging.
    """

    aging_type = aging_type.strip().upper()

    if aging_type not in {"AR", "AP"}:
        return {
            "success": False,
            "error": "aging_type must be 'AR' or 'AP'",
        }

    if aging_type == "AR":

        rows = get_ar_aging(
            as_of_date=as_of_date
        )

    else:

        rows = get_ap_aging(
            as_of_date=as_of_date
        )

    buckets = {
        "current": 0.0,
        "1_30": 0.0,
        "31_60": 0.0,
        "61_90": 0.0,
        "over_90": 0.0,
    }

    records = []

    for row in rows:

        outstanding = money(
            row.get("outstanding")
        )

        if outstanding <= 0:
            continue

        days_overdue = int(
            row.get("days_overdue") or 0
        )

        if days_overdue <= 0:
            bucket = "current"

        elif days_overdue <= 30:
            bucket = "1_30"

        elif days_overdue <= 60:
            bucket = "31_60"

        elif days_overdue <= 90:
            bucket = "61_90"

        else:
            bucket = "over_90"

        buckets[bucket] += outstanding

        records.append({
            "record_id": (
                row.get("invoice_id")
                or row.get("document_id")
            ),
            "party_id": (
                row.get("customer_id")
                or row.get("vendor_id")
            ),
            "outstanding": outstanding,
            "days_overdue": days_overdue,
            "bucket": bucket,
        })

    for bucket in buckets:
        buckets[bucket] = round(
            buckets[bucket],
            2,
        )

    total_outstanding = round(
        sum(buckets.values()),
        2,
    )

    return {
        "type": aging_type,
        "as_of_date": as_of_date,
        "current": buckets["current"],
        "1_30": buckets["1_30"],
        "31_60": buckets["31_60"],
        "61_90": buckets["61_90"],
        "over_90": buckets["over_90"],
        "total_outstanding": total_outstanding,
        "record_count": len(records),
        "records": records,
    }


# ============================================================
# SERVER
# ============================================================

if __name__ == "__main__":
    mcp.run()