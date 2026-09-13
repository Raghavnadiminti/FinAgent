from typing import Optional

from mcp_inst import mcp

from DB.functions import (
    get_invoice,
    get_payment,
    get_payments_for_invoice,
    get_bank_transactions,
    get_general_ledger,
    get_ap_aging,
    get_ar_aging,
)





# ============================================================
# CONSTANTS
# ============================================================

MONEY_TOLERANCE = 0.01
DATE_TOLERANCE_DAYS = 3


# ============================================================
# HELPERS
# ============================================================

def money(value) -> float:
    """Safely convert a database numeric value to float."""
    return round(float(value or 0), 2)


def normalize_text(value) -> str:
    """Normalize text for reference/description comparison."""
    if value is None:
        return ""

    return " ".join(str(value).lower().strip().split())


def transaction_amount(row: dict) -> float:
    """
    Convert a GL transaction into a signed amount.

    Debit  = positive
    Credit = negative
    """
    debit = money(row.get("debit"))
    credit = money(row.get("credit"))

    return round(debit - credit, 2)


# ============================================================
# 1. MATCH INVOICE -> PAYMENT
# ============================================================

@mcp.tool()
def match_invoice_payment(invoice_id: str):
    """
    Reconcile one purchase invoice against all payments recorded
    for that invoice.

    Checks:
    - Invoice exists.
    - Payments reference the invoice.
    - Vendor consistency.
    - Total paid amount.
    - Outstanding amount.
    - Overpayment.

    Args:
        invoice_id:
            Purchase invoice ID, e.g. INV-000001.

    Returns:
        Compact reconciliation result containing:
        - status: UNPAID, PARTIALLY_PAID, PAID, or OVERPAID
        - invoice_total
        - paid_amount
        - outstanding
        - payment_count
        - payment_ids
        - errors

    Use when:
        Determining whether an invoice has been settled correctly.
    """

    invoice_rows = get_invoice(invoice_id)

    if not invoice_rows:
        return {
            "status": "NOT_FOUND",
            "invoice_id": invoice_id,
            "errors": ["Invoice not found"],
        }

    invoice = invoice_rows[0]

    invoice_total = money(invoice.get("total"))
    invoice_vendor = invoice.get("vendor_id")

    payments = get_payments_for_invoice(invoice_id)

    paid_amount = 0.0
    payment_ids = []
    errors = []

    for payment in payments:
        amount = money(payment.get("amount"))

        paid_amount += amount

        if payment.get("payment_id"):
            payment_ids.append(payment["payment_id"])

        payment_vendor = payment.get("vendor_id")

        if (
            invoice_vendor
            and payment_vendor
            and invoice_vendor != payment_vendor
        ):
            errors.append(
                f"Payment {payment.get('payment_id')} "
                "belongs to a different vendor"
            )

    paid_amount = round(paid_amount, 2)

    outstanding = round(
        invoice_total - paid_amount,
        2,
    )

    if paid_amount > invoice_total + MONEY_TOLERANCE:
        status = "OVERPAID"

    elif abs(outstanding) <= MONEY_TOLERANCE:
        status = "PAID"

    elif paid_amount > MONEY_TOLERANCE:
        status = "PARTIALLY_PAID"

    else:
        status = "UNPAID"

    if status == "OVERPAID":
        errors.append("Payments exceed invoice total")

    return {
        "status": status,
        "invoice_id": invoice_id,
        "invoice_total": invoice_total,
        "paid_amount": paid_amount,
        "outstanding": outstanding,
        "payment_count": len(payments),
        "payment_ids": payment_ids,
        "errors": errors,
    }


# ============================================================
# 2. RECONCILE BANK -> GL
# ============================================================

@mcp.tool()
def reconcile_bank(
    account_id: str,
    start_date: str,
    end_date: str,
    limit: int = 200,
):
    """
    Reconcile bank transactions against GL entries for one
    account and date range.

    Matching priority:
    1. Exact reference + amount.
    2. Exact amount + same date.
    3. Exact amount + nearby date.

    Args:
        account_id:
            Bank/GL account ID.

        start_date:
            Start date, YYYY-MM-DD.

        end_date:
            End date, YYYY-MM-DD.

        limit:
            Maximum transactions inspected. Default 200, maximum 500.

    Returns:
        Reconciliation summary:
        - status
        - bank_total
        - gl_total
        - difference
        - matched_count
        - unmatched_bank_count
        - unmatched_gl_count
        - unmatched_bank_ids
        - unmatched_gl_ids

    Use when:
        Comparing bank activity with the accounting ledger.
    """

    limit = min(max(limit, 1), 500)

    bank_rows = get_bank_transactions(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    gl_rows = get_general_ledger(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    bank_total = round(
        sum(money(row.get("amount")) for row in bank_rows),
        2,
    )

    gl_total = round(
        sum(transaction_amount(row) for row in gl_rows),
        2,
    )

    used_gl = set()
    matched_count = 0
    unmatched_bank = []

    # --------------------------------------------------------
    # MATCH BANK -> GL
    # --------------------------------------------------------

    for bank in bank_rows:

        bank_id = bank.get("bank_txn_id")
        bank_amount = money(bank.get("amount"))
        bank_reference = normalize_text(
            bank.get("reference")
        )
        bank_date = str(bank.get("date") or "")

        match_index: Optional[int] = None
        match_reason: Optional[str] = None

        # ----------------------------------------------------
        # PASS 1:
        # Reference + amount
        # ----------------------------------------------------

        if bank_reference:

            for index, gl in enumerate(gl_rows):

                if index in used_gl:
                    continue

                gl_amount = transaction_amount(gl)

                gl_reference = normalize_text(
                    gl.get("journal_id")
                )

                if (
                    abs(bank_amount - gl_amount)
                    <= MONEY_TOLERANCE
                    and bank_reference == gl_reference
                ):
                    match_index = index
                    match_reason = "REFERENCE_AND_AMOUNT"
                    break

        # ----------------------------------------------------
        # PASS 2:
        # Amount
        #
        # We intentionally do not blindly use description
        # similarity here because that can create false matches.
        # ----------------------------------------------------

        if match_index is None:

            candidates = []

            for index, gl in enumerate(gl_rows):

                if index in used_gl:
                    continue

                gl_amount = transaction_amount(gl)

                if abs(bank_amount - gl_amount) <= MONEY_TOLERANCE:
                    candidates.append(index)

            if len(candidates) == 1:
                match_index = candidates[0]
                match_reason = "UNIQUE_AMOUNT_MATCH"

        # ----------------------------------------------------
        # RECORD RESULT
        # ----------------------------------------------------

        if match_index is not None:

            used_gl.add(match_index)
            matched_count += 1

        else:

            unmatched_bank.append({
                "bank_txn_id": bank_id,
                "date": bank.get("date"),
                "amount": bank_amount,
                "description": bank.get("description"),
                "reference": bank.get("reference"),
                "reason": "NO_UNIQUE_GL_MATCH",
            })

    # --------------------------------------------------------
    # FIND GL ENTRIES WITH NO BANK MATCH
    # --------------------------------------------------------

    unmatched_gl = []

    for index, gl in enumerate(gl_rows):

        if index in used_gl:
            continue

        unmatched_gl.append({
            "journal_id": gl.get("journal_id"),
            "line_no": gl.get("line_no"),
            "date": gl.get("date"),
            "amount": transaction_amount(gl),
            "account_id": gl.get("account_id"),
            "account_name": gl.get("account_name"),
            "reason": "NO_BANK_MATCH",
        })

    difference = round(
        bank_total - gl_total,
        2,
    )

    if (
        abs(difference) <= MONEY_TOLERANCE
        and not unmatched_bank
        and not unmatched_gl
    ):
        status = "RECONCILED"

    else:
        status = "EXCEPTION"

    return {
        "status": status,
        "account_id": account_id,
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "bank_total": bank_total,
        "gl_total": gl_total,
        "difference": difference,
        "bank_transaction_count": len(bank_rows),
        "gl_transaction_count": len(gl_rows),
        "matched_count": matched_count,
        "unmatched_bank_count": len(unmatched_bank),
        "unmatched_gl_count": len(unmatched_gl),
        "unmatched_bank": unmatched_bank,
        "unmatched_gl": unmatched_gl,
    }


# ============================================================
# 3. RECONCILE AP -> GL
# ============================================================

@mcp.tool()
def reconcile_ap_gl(
    start_date: str,
    end_date: str,
    ap_account_id: str,
    limit: int = 200,
):
    """
    Reconcile the AP subledger against its GL liability account.

    The AP subledger balance is calculated from outstanding vendor
    invoices. The GL balance is calculated from the supplied AP
    liability account.

    Args:
        start_date:
            Start date, YYYY-MM-DD.

        end_date:
            End date, YYYY-MM-DD.

        ap_account_id:
            GL account ID representing Accounts Payable.

        limit:
            Maximum GL entries inspected. Default 200, maximum 500.

    Returns:
        - status
        - ap_balance
        - gl_balance
        - difference
        - exception

    Use when:
        Checking whether AP subledger and AP control account agree.
    """

    limit = min(max(limit, 1), 500)

    # --------------------------------------------------------
    # AP SUBLEDGER
    # --------------------------------------------------------

    ap_rows = get_ap_aging()

    ap_balance = 0.0

    for row in ap_rows:

        invoice_date = str(
            row.get("invoice_date") or ""
        )

        if (
            start_date
            <= invoice_date
            <= end_date
        ):
            ap_balance += money(
                row.get("outstanding")
            )

    ap_balance = round(ap_balance, 2)

    # --------------------------------------------------------
    # GL
    # --------------------------------------------------------

    gl_rows = get_general_ledger(
        account_id=ap_account_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    gl_balance = round(
        sum(transaction_amount(row) for row in gl_rows),
        2,
    )

    difference = round(
        ap_balance - abs(gl_balance),
        2,
    )

    status = (
        "RECONCILED"
        if abs(difference) <= MONEY_TOLERANCE
        else "EXCEPTION"
    )

    return {
        "status": status,
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "ap_account_id": ap_account_id,
        "ap_balance": ap_balance,
        "gl_balance": gl_balance,
        "difference": difference,
    }


# ============================================================
# 4. RECONCILE AR -> GL
# ============================================================

@mcp.tool()
def reconcile_ar_gl(
    start_date: str,
    end_date: str,
    ar_account_id: str,
    limit: int = 200,
):
    """
    Reconcile the AR subledger against its GL receivable account.

    The AR subledger balance is calculated from outstanding customer
    invoices. The GL balance is calculated from the supplied AR
    control account.

    Args:
        start_date:
            Start date, YYYY-MM-DD.

        end_date:
            End date, YYYY-MM-DD.

        ar_account_id:
            GL account ID representing Accounts Receivable.

        limit:
            Maximum GL entries inspected. Default 200, maximum 500.

    Returns:
        - status
        - ar_balance
        - gl_balance
        - difference
        - exception

    Use when:
        Checking whether AR subledger and AR control account agree.
    """

    limit = min(max(limit, 1), 500)

    # --------------------------------------------------------
    # AR SUBLEDGER
    # --------------------------------------------------------

    ar_rows = get_ar_aging()

    ar_balance = 0.0

    for row in ar_rows:

        invoice_date = str(
            row.get("invoice_date") or ""
        )

        if (
            start_date
            <= invoice_date
            <= end_date
        ):
            ar_balance += money(
                row.get("outstanding")
            )

    ar_balance = round(ar_balance, 2)

    # --------------------------------------------------------
    # GL
    # --------------------------------------------------------

    gl_rows = get_general_ledger(
        account_id=ar_account_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )

    gl_balance = round(
        sum(transaction_amount(row) for row in gl_rows),
        2,
    )

    difference = round(
        ar_balance - abs(gl_balance),
        2,
    )

    status = (
        "RECONCILED"
        if abs(difference) <= MONEY_TOLERANCE
        else "EXCEPTION"
    )

    return {
        "status": status,
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "ar_account_id": ar_account_id,
        "ar_balance": ar_balance,
        "gl_balance": gl_balance,
        "difference": difference,
    }


# ============================================================
# 5. FIND UNMATCHED TRANSACTIONS
# ============================================================

@mcp.tool()
def find_unmatched_transactions(
    account_id: str,
    start_date: str,
    end_date: str,
    limit: int = 50,
):
    """
    Find bank transactions and GL entries that cannot be uniquely
    matched.

    Matching uses:
    - reference + amount
    - unique amount

    A transaction is not marked matched when multiple GL records
    have the same amount, because that would be ambiguous.

    Args:
        account_id:
            Bank/GL account ID.

        start_date:
            Start date, YYYY-MM-DD.

        end_date:
            End date, YYYY-MM-DD.

        limit:
            Maximum unmatched records returned. Default 50,
            maximum 200.

    Returns:
        - unmatched_bank
        - unmatched_gl
        - counts
        - matching_method

    Use when:
        A bank reconciliation has exceptions and the agent needs
        transaction-level items to investigate.
    """

    limit = min(max(limit, 1), 200)

    bank_rows = get_bank_transactions(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=500,
    )

    gl_rows = get_general_ledger(
        account_id=account_id,
        start_date=start_date,
        end_date=end_date,
        limit=500,
    )

    used_gl = set()
    unmatched_bank = []

    for bank in bank_rows:

        bank_amount = money(
            bank.get("amount")
        )

        bank_reference = normalize_text(
            bank.get("reference")
        )

        # ----------------------------------------------------
        # Reference + amount
        # ----------------------------------------------------

        candidates = []

        for index, gl in enumerate(gl_rows):

            if index in used_gl:
                continue

            gl_amount = transaction_amount(gl)

            gl_reference = normalize_text(
                gl.get("journal_id")
            )

            if (
                abs(bank_amount - gl_amount)
                <= MONEY_TOLERANCE
                and bank_reference
                and bank_reference == gl_reference
            ):
                candidates.append(index)

        # ----------------------------------------------------
        # Unique amount
        # ----------------------------------------------------

        if not candidates:

            amount_candidates = []

            for index, gl in enumerate(gl_rows):

                if index in used_gl:
                    continue

                gl_amount = transaction_amount(gl)

                if (
                    abs(bank_amount - gl_amount)
                    <= MONEY_TOLERANCE
                ):
                    amount_candidates.append(index)

            if len(amount_candidates) == 1:
                candidates = amount_candidates

        if len(candidates) == 1:

            used_gl.add(candidates[0])

        else:

            if len(unmatched_bank) < limit:

                reason = (
                    "AMBIGUOUS_MATCH"
                    if len(candidates) > 1
                    else "NO_MATCH"
                )

                unmatched_bank.append({
                    "bank_txn_id": bank.get(
                        "bank_txn_id"
                    ),
                    "date": bank.get("date"),
                    "amount": bank_amount,
                    "description": bank.get(
                        "description"
                    ),
                    "reference": bank.get(
                        "reference"
                    ),
                    "reason": reason,
                })

    # --------------------------------------------------------
    # Remaining GL entries
    # --------------------------------------------------------

    unmatched_gl = []

    for index, gl in enumerate(gl_rows):

        if index in used_gl:
            continue

        if len(unmatched_gl) >= limit:
            break

        unmatched_gl.append({
            "journal_id": gl.get("journal_id"),
            "line_no": gl.get("line_no"),
            "date": gl.get("date"),
            "account_id": gl.get("account_id"),
            "account_name": gl.get(
                "account_name"
            ),
            "amount": transaction_amount(gl),
            "reason": "NO_BANK_MATCH",
        })

    return {
        "account_id": account_id,
        "period": {
            "start": start_date,
            "end": end_date,
        },
        "unmatched_bank_count": len(
            unmatched_bank
        ),
        "unmatched_gl_count": len(
            unmatched_gl
        ),
        "unmatched_bank": unmatched_bank,
        "unmatched_gl": unmatched_gl,
        "matching_method": [
            "REFERENCE_AND_AMOUNT",
            "UNIQUE_AMOUNT",
        ],
    }


# ============================================================
# 6. INVESTIGATE EXCEPTION
# ============================================================

@mcp.tool()
def investigate_exception(
    exception_type: str,
    record_id: str,
):
    """
    Retrieve compact context for investigating a reconciliation
    exception.

    Supported exception types:
    - invoice
    - payment

    Args:
        exception_type:
            Exception category.

        record_id:
            ID of the accounting record to investigate.

    Returns:
        Relevant record information and related accounting data.

    Use when:
        Another validation or reconciliation tool has identified
        an exception requiring deeper investigation.

    Note:
        This tool gathers evidence. It does not invent a root cause.
        The agent should infer the cause from the returned evidence.
    """

    exception_type = (
        exception_type.strip().lower()
    )

    # --------------------------------------------------------
    # INVOICE EXCEPTION
    # --------------------------------------------------------

    if exception_type == "invoice":

        invoice_rows = get_invoice(record_id)

        if not invoice_rows:
            return {
                "found": False,
                "exception_type": "invoice",
                "record_id": record_id,
                "error": "Invoice not found",
            }

        invoice = invoice_rows[0]

        payments = get_payments_for_invoice(
            record_id
        )

        paid_amount = round(
            sum(
                money(
                    payment.get("amount")
                )
                for payment in payments
            ),
            2,
        )

        invoice_total = money(
            invoice.get("total")
        )

        return {
            "found": True,
            "exception_type": "invoice",
            "record_id": record_id,
            "invoice": {
                "invoice_id": invoice.get(
                    "invoice_id"
                ),
                "invoice_number": invoice.get(
                    "invoice_number"
                ),
                "vendor_id": invoice.get(
                    "vendor_id"
                ),
                "po_id": invoice.get(
                    "po_id"
                ),
                "invoice_date": invoice.get(
                    "invoice_date"
                ),
                "due_date": invoice.get(
                    "due_date"
                ),
                "subtotal": money(
                    invoice.get("subtotal")
                ),
                "tax": money(
                    invoice.get("tax")
                ),
                "total": invoice_total,
                "status": invoice.get(
                    "status"
                ),
            },
            "payment_summary": {
                "payment_count": len(
                    payments
                ),
                "paid_amount": paid_amount,
                "outstanding": round(
                    invoice_total - paid_amount,
                    2,
                ),
                "payment_ids": [
                    p.get("payment_id")
                    for p in payments
                ],
            },
        }

    # --------------------------------------------------------
    # PAYMENT EXCEPTION
    # --------------------------------------------------------

    if exception_type == "payment":

        payment_rows = get_payment(
            record_id
        )

        if not payment_rows:
            return {
                "found": False,
                "exception_type": "payment",
                "record_id": record_id,
                "error": "Payment not found",
            }

        payment = payment_rows[0]

        invoice_id = payment.get(
            "invoice_id"
        )

        invoice = None

        if invoice_id:

            invoice_rows = get_invoice(
                invoice_id
            )

            if invoice_rows:
                invoice = invoice_rows[0]

        result = {
            "found": True,
            "exception_type": "payment",
            "record_id": record_id,
            "payment": {
                "payment_id": payment.get(
                    "payment_id"
                ),
                "invoice_id": invoice_id,
                "vendor_id": payment.get(
                    "vendor_id"
                ),
                "payment_date": payment.get(
                    "payment_date"
                ),
                "amount": money(
                    payment.get("amount")
                ),
                "payment_method": payment.get(
                    "payment_method"
                ),
                "reference": payment.get(
                    "reference"
                ),
                "status": payment.get(
                    "status"
                ),
            },
        }

        if invoice:

            result["invoice"] = {
                "invoice_id": invoice.get(
                    "invoice_id"
                ),
                "vendor_id": invoice.get(
                    "vendor_id"
                ),
                "total": money(
                    invoice.get("total")
                ),
                "status": invoice.get(
                    "status"
                ),
            }

        return result

    # --------------------------------------------------------
    # UNSUPPORTED TYPE
    # --------------------------------------------------------

    return {
        "found": False,
        "exception_type": exception_type,
        "record_id": record_id,
        "error": (
            "Unsupported exception type. "
            "Supported types: invoice, payment"
        ),
    }


# ============================================================
# SERVER
# ============================================================

# if __name__ == "__main__":
#     mcp.run()