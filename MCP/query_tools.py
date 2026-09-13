# mcp.py

from mcp_inst import mcp

from DB.functions import (
    get_account,
    get_account_balance,
    get_chart_of_accounts,
    get_vendor,
    get_customer,
    get_invoice,
    get_invoices,
    get_purchase_order,
    get_payment,
    get_bank_transactions,
    get_journal_entry,
    get_general_ledger,
    get_ar_aging,
    get_ap_aging,
)





@mcp.tool()
def account(account_id: str):
    """
    Retrieve one accounting account.

    Use when you need account metadata such as account name,
    type, code, currency, or normal balance.

    Args:
        account_id: Account ID such as ACC-1100.

    Returns:
        One account record.
    """

    return get_account(account_id)  

@mcp.tool()
def account_balance(account_id: str):
    """
    Calculate the current debit, credit and net balance
    of an accounting account.

    Args:
        account_id: Account ID such as ACC-1100.

    Returns:
        Account ID, account name, total debit, total credit,
        and balance.
    """

    return get_account_balance(account_id)


@mcp.tool()
def chart_of_accounts():
    """
    Retrieve the active chart of accounts.

    Use when account classification or account lookup is needed.

    Returns:
        List of active accounts with ID, code, name, type,
        normal balance and currency.
    """

    return get_chart_of_accounts() 


@mcp.tool()
def vendor(vendor_id: str):
    """
    Retrieve vendor information.

    Args:
        vendor_id: Vendor ID such as VEN-0001.

    Returns:
        Vendor profile including category, payment terms,
        tax ID, currency and status.
    """

    return get_vendor(vendor_id) 

@mcp.tool()
def customer(customer_id: str):
    """
    Retrieve customer information.

    Args:
        customer_id: Customer ID such as CUS-0001.

    Returns:
        Customer profile including payment terms,
        credit limit, currency and status.
    """

    return get_customer(customer_id)


@mcp.tool()
def invoice(invoice_id: str):
    """
    Retrieve one purchase invoice.

    Use for invoice validation or investigation.

    Args:
        invoice_id: Invoice ID such as INV-000001.

    Returns:
        Invoice amount, tax, dates, vendor, PO and status.
    """

    return get_invoice(invoice_id)


@mcp.tool()
def invoices(
    vendor_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
):
    """
    Search purchase invoices.

    Args:
        vendor_id: Optional vendor ID.
        status: Optional invoice status such as approved,
            pending, paid or overdue.
        limit: Maximum results. Default 20, maximum 100.

    Returns:
        Matching invoices with vendor, PO, amount, dates and status.
    """

    return get_invoices(
        vendor_id=vendor_id,
        status=status,
        limit=limit,
    )


@mcp.tool()
def purchase_order(po_id: str):
    """
    Retrieve one purchase order.

    Use to compare an invoice against its PO.

    Args:
        po_id: Purchase order ID such as PO-000001.

    Returns:
        PO amount, tax, vendor, date, currency and status.
    """

    return get_purchase_order(po_id)



@mcp.tool()
def payment(payment_id: str):
    """
    Retrieve one vendor payment.

    Use for payment verification and invoice reconciliation.

    Args:
        payment_id: Payment ID such as PAY-000001.

    Returns:
        Payment amount, invoice, vendor, date, method,
        reference and status.
    """

    return get_payment(payment_id)




@mcp.tool()
def bank_transactions(
    account_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
):
    """
    Retrieve bank transactions.

    Args:
        account_id: Optional bank account ID.
        start_date: Optional YYYY-MM-DD start date.
        end_date: Optional YYYY-MM-DD end date.
        limit: Maximum results. Default 50, maximum 200.

    Returns:
        Bank transaction ID, date, description, amount,
        currency and reference.
    """

    return get_bank_transactions(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )



@mcp.tool()
def journal_entry(journal_id: str):
    """
    Retrieve a journal entry and its debit/credit lines.

    Use to investigate accounting entries and verify
    whether debits equal credits.

    Args:
        journal_id: Journal ID such as JE-000001.

    Returns:
        Journal header plus account, debit and credit lines.
    """

    return get_journal_entry(journal_id)


@mcp.tool()
def general_ledger(
    account_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
):
    """
    Retrieve general ledger entries.

    Args:
        account_id: Optional account filter.
        start_date: Optional YYYY-MM-DD start date.
        end_date: Optional YYYY-MM-DD end date.
        limit: Maximum results. Default 100, maximum 500.

    Returns:
        Journal ID, account, date, debit and credit for each entry.
    """

    return get_general_ledger(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )


@mcp.tool()
def ar_aging():
    """
    Retrieve outstanding accounts receivable with aging buckets.

    Returns:
        Customer invoice, total, paid amount, outstanding amount,
        due date and aging bucket.
    """

    return get_ar_aging()


@mcp.tool()
def ap_aging():
    """
    Retrieve outstanding accounts payable with aging buckets.

    Returns:
        Vendor invoice, total, paid amount, outstanding amount,
        due date and aging bucket.
    """

    return get_ap_aging()


