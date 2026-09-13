
from typing import Optional

from .postgres import PostgresDB


# ============================================================
# DATABASE INSTANCE
# ============================================================

db = PostgresDB(
    host="localhost",
    port=5432,
    database="accounting",
    user="postgres",
    password="1234",
)


# ============================================================
# ACCOUNT
# ============================================================

def get_account(account_id: str):
    """
    Get one account from the chart of accounts.

    Args:
        account_id: Account ID, e.g. ACC-1100.

    Returns:
        Account record or empty list if not found.
    """

    return db.query(
        """
        SELECT
            account_id,
            code,
            name,
            type,
            normal_balance,
            currency,
            active
        FROM public.chart_of_accounts
        WHERE account_id = %s
        """,
        (account_id,),
    )


def get_account_balance(account_id: str):
    """
    Calculate the current ledger balance of an account.

    Args:
        account_id: Account ID, e.g. ACC-1100.

    Returns:
        total_debit, total_credit and balance.
    """

    return db.query(
        """
        SELECT
            coa.account_id,
            coa.code,
            coa.name,
            coa.type,
            COALESCE(SUM(gl.debit), 0) AS total_debit,
            COALESCE(SUM(gl.credit), 0) AS total_credit,
            COALESCE(SUM(gl.debit - gl.credit), 0) AS balance
        FROM public.chart_of_accounts coa
        LEFT JOIN public.general_ledger gl
            ON coa.account_id = gl.account_id
        WHERE coa.account_id = %s
        GROUP BY
            coa.account_id,
            coa.code,
            coa.name,
            coa.type
        """,
        (account_id,),
    )


def get_chart_of_accounts():
    """
    Get the company's chart of accounts.

    Returns:
        List of active account records.
    """

    return db.query(
        """
        SELECT
            account_id,
            code,
            name,
            type,
            normal_balance,
            currency,
            active
        FROM public.chart_of_accounts
        WHERE active = TRUE
        ORDER BY code
        """
    )


# ============================================================
# VENDOR
# ============================================================

def get_vendor(vendor_id: str):
    """
    Get one vendor.

    Args:
        vendor_id: Vendor ID, e.g. VEN-0001.

    Returns:
        Vendor record.
    """

    return db.query(
        """
        SELECT
            vendor_id,
            name,
            category,
            currency,
            payment_terms,
            tax_id,
            status
        FROM public.vendors
        WHERE vendor_id = %s
        """,
        (vendor_id,),
    )


# ============================================================
# CUSTOMER
# ============================================================

def get_customer(customer_id: str):
    """
    Get one customer.

    Args:
        customer_id: Customer ID, e.g. CUS-0001.

    Returns:
        Customer record.
    """

    return db.query(
        """
        SELECT
            customer_id,
            name,
            payment_terms,
            credit_limit,
            currency,
            status
        FROM public.customers
        WHERE customer_id = %s
        """,
        (customer_id,),
    )


# ============================================================
# PURCHASE INVOICE
# ============================================================

def get_invoice(invoice_id: str):
    """
    Get one purchase invoice with vendor and PO information.

    Args:
        invoice_id: Invoice ID, e.g. INV-000001.

    Returns:
        Invoice details including vendor and purchase order.
    """

    return db.query(
        """
        SELECT
            i.invoice_id,
            i.invoice_number,
            i.vendor_id,
            v.name AS vendor_name,
            i.po_id,
            i.invoice_date,
            i.due_date,
            i.subtotal,
            i.tax,
            i.total,
            i.status
        FROM public.purchase_invoices i
        JOIN public.vendors v
            ON i.vendor_id = v.vendor_id
        WHERE i.invoice_id = %s
        """,
        (invoice_id,),
    )


def get_invoices(
    vendor_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
):
    """
    Search purchase invoices.

    Args:
        vendor_id: Optional vendor ID filter.
        status: Optional invoice status filter.
        limit: Maximum records to return. Default 20, maximum 100.

    Returns:
        List of matching invoices.
    """

    limit = min(max(limit, 1), 100)

    query = """
        SELECT
            i.invoice_id,
            i.invoice_number,
            i.vendor_id,
            v.name AS vendor_name,
            i.po_id,
            i.invoice_date,
            i.due_date,
            i.total,
            i.status
        FROM public.purchase_invoices i
        JOIN public.vendors v
            ON i.vendor_id = v.vendor_id
        WHERE 1 = 1
    """

    params = []

    if vendor_id:
        query += " AND i.vendor_id = %s"
        params.append(vendor_id)

    if status:
        query += " AND i.status = %s"
        params.append(status)

    query += """
        ORDER BY i.invoice_date DESC
        LIMIT %s
    """

    params.append(limit)

    return db.query(query, tuple(params))


# ============================================================
# PURCHASE ORDER
# ============================================================

def get_purchase_order(po_id: str):
    """
    Get one purchase order.

    Args:
        po_id: Purchase order ID, e.g. PO-000001.

    Returns:
        Purchase order details including vendor.
    """

    return db.query(
        """
        SELECT
            po.po_id,
            po.vendor_id,
            v.name AS vendor_name,
            po.date,
            po.currency,
            po.subtotal,
            po.tax,
            po.total,
            po.status
        FROM public.purchase_orders po
        JOIN public.vendors v
            ON po.vendor_id = v.vendor_id
        WHERE po.po_id = %s
        """,
        (po_id,),
    )


# ============================================================
# PAYMENT
# ============================================================

def get_payment(payment_id: str):
    """
    Get one AP payment.

    Args:
        payment_id: Payment ID, e.g. PAY-000001.

    Returns:
        Payment details including invoice and vendor.
    """

    return db.query(
        """
        SELECT
            p.payment_id,
            p.invoice_id,
            p.vendor_id,
            v.name AS vendor_name,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.reference,
            p.status
        FROM public.payments p
        JOIN public.vendors v
            ON p.vendor_id = v.vendor_id
        WHERE p.payment_id = %s
        """,
        (payment_id,),
    )


# ============================================================
# BANK TRANSACTIONS
# ============================================================

def get_bank_transactions(
    account_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50,
):
    """
    Get bank transactions with optional filters.

    Args:
        account_id: Optional bank/GL account ID.
        start_date: Optional start date, YYYY-MM-DD.
        end_date: Optional end date, YYYY-MM-DD.
        limit: Maximum records, default 50, maximum 200.

    Returns:
        List of bank transactions.
    """

    limit = min(max(limit, 1), 200)

    query = """
        SELECT
            bank_txn_id,
            account_id,
            date,
            description,
            amount,
            currency,
            reference
        FROM public.bank_transactions
        WHERE 1 = 1
    """

    params = []

    if account_id:
        query += " AND account_id = %s"
        params.append(account_id)

    if start_date:
        query += " AND date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND date <= %s"
        params.append(end_date)

    query += """
        ORDER BY date DESC
        LIMIT %s
    """

    params.append(limit)

    return db.query(query, tuple(params))


# ============================================================
# JOURNAL ENTRY
# ============================================================

def get_journal_entry(journal_id: str):
    """
    Get a journal entry and all of its ledger lines.

    Args:
        journal_id: Journal ID, e.g. JE-000001.

    Returns:
        Journal header and debit/credit lines.
    """

    return db.query(
        """
        SELECT
            je.journal_id,
            je.date,
            je.description,
            je.source,
            je.status,
            gl.line_no,
            gl.account_id,
            coa.code,
            coa.name AS account_name,
            gl.debit,
            gl.credit
        FROM public.journal_entries je
        JOIN public.general_ledger gl
            ON je.journal_id = gl.journal_id
        JOIN public.chart_of_accounts coa
            ON gl.account_id = coa.account_id
        WHERE je.journal_id = %s
        ORDER BY gl.line_no
        """,
        (journal_id,),
    )


# ============================================================
# GENERAL LEDGER
# ============================================================

def get_general_ledger(
    account_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
):
    """
    Get general ledger entries.

    Args:
        account_id: Optional account filter.
        start_date: Optional start date, YYYY-MM-DD.
        end_date: Optional end date, YYYY-MM-DD.
        limit: Maximum records, default 100, maximum 500.

    Returns:
        List of ledger entries.
    """

    limit = min(max(limit, 1), 500)

    query = """
        SELECT
            gl.journal_id,
            gl.line_no,
            gl.account_id,
            coa.code,
            coa.name AS account_name,
            gl.date,
            gl.debit,
            gl.credit
        FROM public.general_ledger gl
        JOIN public.chart_of_accounts coa
            ON gl.account_id = coa.account_id
        WHERE 1 = 1
    """

    params = []

    if account_id:
        query += " AND gl.account_id = %s"
        params.append(account_id)

    if start_date:
        query += " AND gl.date >= %s"
        params.append(start_date)

    if end_date:
        query += " AND gl.date <= %s"
        params.append(end_date)

    query += """
        ORDER BY gl.date DESC, gl.journal_id, gl.line_no
        LIMIT %s
    """

    params.append(limit)

    return db.query(query, tuple(params))


# ============================================================
# AR AGING
# ============================================================

def get_ar_aging():
    """
    Get outstanding accounts receivable grouped by aging bucket.

    Returns:
        Outstanding customer invoices with:
        Current, 1-30, 31-60, 61-90 and 90+ day buckets.
    """

    return db.query(
        """
        SELECT
            i.ar_invoice_id,
            i.customer_id,
            c.name AS customer_name,
            i.invoice_date,
            i.due_date,
            i.total,
            COALESCE(SUM(r.amount), 0) AS paid_amount,
            i.total - COALESCE(SUM(r.amount), 0) AS outstanding,

            CASE
                WHEN CURRENT_DATE <= i.due_date
                    THEN 'Current'

                WHEN CURRENT_DATE - i.due_date <= 30
                    THEN '1-30 Days'

                WHEN CURRENT_DATE - i.due_date <= 60
                    THEN '31-60 Days'

                WHEN CURRENT_DATE - i.due_date <= 90
                    THEN '61-90 Days'

                ELSE '90+ Days'
            END AS aging_bucket

        FROM public.ar_invoices i

        JOIN public.customers c
            ON i.customer_id = c.customer_id

        LEFT JOIN public.ar_receipts r
            ON i.ar_invoice_id = r.ar_invoice_id

        GROUP BY
            i.ar_invoice_id,
            i.customer_id,
            c.name,
            i.invoice_date,
            i.due_date,
            i.total

        HAVING
            i.total - COALESCE(SUM(r.amount), 0) > 0

        ORDER BY i.due_date
        """
    )


# ============================================================
# AP AGING
# ============================================================

def get_ap_aging():
    """
    Get outstanding accounts payable grouped by aging bucket.

    Returns:
        Outstanding vendor invoices with:
        Current, 1-30, 31-60, 61-90 and 90+ day buckets.
    """

    return db.query(
        """
        SELECT
            i.invoice_id,
            i.vendor_id,
            v.name AS vendor_name,
            i.invoice_number,
            i.invoice_date,
            i.due_date,
            i.total,
            COALESCE(SUM(p.amount), 0) AS paid_amount,
            i.total - COALESCE(SUM(p.amount), 0) AS outstanding,

            CASE
                WHEN CURRENT_DATE <= i.due_date
                    THEN 'Current'

                WHEN CURRENT_DATE - i.due_date <= 30
                    THEN '1-30 Days'

                WHEN CURRENT_DATE - i.due_date <= 60
                    THEN '31-60 Days'

                WHEN CURRENT_DATE - i.due_date <= 90
                    THEN '61-90 Days'

                ELSE '90+ Days'
            END AS aging_bucket

        FROM public.purchase_invoices i

        JOIN public.vendors v
            ON i.vendor_id = v.vendor_id

        LEFT JOIN public.payments p
            ON i.invoice_id = p.invoice_id

        GROUP BY
            i.invoice_id,
            i.vendor_id,
            v.name,
            i.invoice_number,
            i.invoice_date,
            i.due_date,
            i.total

        HAVING
            i.total - COALESCE(SUM(p.amount), 0) > 0

        ORDER BY i.due_date
        """
    )


# ============================================================
# ACCOUNTING PERIOD
# ============================================================

def get_accounting_period(date: str):
    """
    Find the accounting period containing a given date.

    Args:
        date: Date to search for, YYYY-MM-DD.

    Returns:
        Matching accounting period.
    """

    return db.query(
        """
        SELECT
            period_id,
            start_date,
            end_date,
            status
        FROM public.accounting_periods
        WHERE start_date <= %s
          AND end_date >= %s
        LIMIT 1
        """,
        (date, date),
    )


# ============================================================
# PAYMENTS FOR INVOICE
# ============================================================

def get_payments_for_invoice(invoice_id: str):
    """
    Get all payments associated with an invoice.

    Args:
        invoice_id: Invoice ID.

    Returns:
        List of payments for the invoice.
    """

    return db.query(
        """
        SELECT
            payment_id,
            invoice_id,
            vendor_id,
            payment_date,
            amount,
            payment_method,
            reference,
            status
        FROM public.payments
        WHERE invoice_id = %s
        ORDER BY payment_date
        """,
        (invoice_id,),
    )

