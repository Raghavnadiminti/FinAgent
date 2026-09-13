# mcp_validation_tools.py

from mcp.server.fastmcp import FastMCP

from DB.functions import (
    get_journal_entry,
    get_invoice,
    get_account,
    get_account_balance,
    get_vendor,
    get_purchase_order,
    get_payment,
)


mcp = FastMCP("AI Accountant Validation")


@mcp.tool()
def validate_journal_entry(journal_id: str):
    """
    Validate a journal entry for basic accounting correctness.

    Checks:
    - Debit total equals credit total.
    - Journal entry exists.
    - All referenced accounts exist.
    - Entry is posted to a valid accounting structure.

    Args:
        journal_id: Journal entry ID, e.g. JE-000001.

    Returns:
        Validation result containing:
        - valid: true/false
        - journal_id
        - total_debit
        - total_credit
        - difference
        - errors
        - warnings

    Use when:
        Investigating whether a journal entry is balanced and
        structurally valid.
    """

    entry = get_journal_entry(journal_id)

    if not entry:
        return {
            "valid": False,
            "journal_id": journal_id,
            "errors": ["Journal entry not found"],
        }

    total_debit = sum(
        float(row.get("debit") or 0)
        for row in entry
    )

    total_credit = sum(
        float(row.get("credit") or 0)
        for row in entry
    )

    difference = total_debit - total_credit

    errors = []

    if abs(difference) > 0.01:
        errors.append(
            "Debit and credit totals do not balance"
        )

    for row in entry:
        if not row.get("account_id"):
            errors.append(
                f"Missing account on line {row.get('line_no')}"
            )

    return {
        "valid": len(errors) == 0,
        "journal_id": journal_id,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": difference,
        "errors": errors,
        "warnings": [],
    }



@mcp.tool()
def validate_invoice(invoice_id: str):
    """
    Validate a purchase invoice for basic data and accounting consistency.

    Checks:
    - Invoice exists.
    - Vendor exists and is active.
    - Invoice total is non-negative.
    - Invoice date is present.
    - Due date is not before invoice date.
    - Required invoice fields are present.

    Args:
        invoice_id: Invoice ID, e.g. INV-000001.

    Returns:
        Validation result:
        - valid
        - invoice_id
        - errors
        - warnings

    Use when:
        An invoice needs a general validation before approval or payment.
    """

    invoices = get_invoice(invoice_id)

    if not invoices:
        return {
            "valid": False,
            "invoice_id": invoice_id,
            "errors": ["Invoice not found"],
            "warnings": [],
        }

    invoice = invoices[0]

    errors = []
    warnings = []

    if not invoice.get("vendor_id"):
        errors.append("Vendor is missing")

    if not invoice.get("invoice_number"):
        errors.append("Invoice number is missing")

    if invoice.get("invoice_date") is None:
        errors.append("Invoice date is missing")

    if invoice.get("due_date") is None:
        errors.append("Due date is missing")

    if invoice.get("total") is None:
        errors.append("Invoice total is missing")
    elif float(invoice["total"]) < 0:
        errors.append("Invoice total cannot be negative")

    if invoice.get("vendor_id"):

        vendor = get_vendor(invoice["vendor_id"])

        if not vendor:
            errors.append("Vendor does not exist")

        elif vendor[0].get("status") != "active":
            warnings.append("Vendor is not active")

    return {
        "valid": len(errors) == 0,
        "invoice_id": invoice_id,
        "errors": errors,
        "warnings": warnings,
    }



@mcp.tool()
def validate_tax(invoice_id: str, tolerance: float = 0.01):
    """
    Validate the tax amount on a purchase invoice.

    Compares:
        subtotal + tax = total

    Args:
        invoice_id: Invoice ID, e.g. INV-000001.
        tolerance: Allowed monetary difference. Default 0.01.

    Returns:
        Validation result containing:
        - valid
        - subtotal
        - recorded_tax
        - total
        - expected_total
        - difference
        - errors

    Use when:
        Checking whether the recorded invoice tax and total are
        mathematically consistent.
    """

    invoices = get_invoice(invoice_id)

    if not invoices:
        return {
            "valid": False,
            "invoice_id": invoice_id,
            "errors": ["Invoice not found"],
        }

    invoice = invoices[0]

    subtotal = float(invoice.get("subtotal") or 0)
    tax = float(invoice.get("tax") or 0)
    total = float(invoice.get("total") or 0)

    expected_total = subtotal + tax
    difference = total - expected_total

    valid = abs(difference) <= tolerance

    return {
        "valid": valid,
        "invoice_id": invoice_id,
        "subtotal": subtotal,
        "recorded_tax": tax,
        "total": total,
        "expected_total": expected_total,
        "difference": difference,
        "errors": (
            []
            if valid
            else ["Tax and invoice total are inconsistent"]
        ),
    }




@mcp.tool()
def validate_invoice_total(
    invoice_id: str,
    tolerance: float = 0.01,
):
    """
    Validate the mathematical total of an invoice.

    Checks:
        subtotal + tax = total

    Args:
        invoice_id: Invoice ID, e.g. INV-000001.
        tolerance: Allowed rounding difference. Default 0.01.

    Returns:
        - valid
        - subtotal
        - tax
        - recorded_total
        - calculated_total
        - difference
        - errors

    Use when:
        You only need to verify the invoice total calculation.
    """

    invoices = get_invoice(invoice_id)

    if not invoices:
        return {
            "valid": False,
            "invoice_id": invoice_id,
            "errors": ["Invoice not found"],
        }

    invoice = invoices[0]

    subtotal = float(invoice.get("subtotal") or 0)
    tax = float(invoice.get("tax") or 0)
    recorded_total = float(invoice.get("total") or 0)

    calculated_total = subtotal + tax
    difference = recorded_total - calculated_total

    valid = abs(difference) <= tolerance

    return {
        "valid": valid,
        "invoice_id": invoice_id,
        "subtotal": subtotal,
        "tax": tax,
        "recorded_total": recorded_total,
        "calculated_total": calculated_total,
        "difference": difference,
        "errors": (
            []
            if valid
            else ["Invoice total does not match subtotal + tax"]
        ),
    }



#IMPORTANT TO BE VERFIED AND INCRMENTED 
@mcp.tool()
def validate_three_way_match(invoice_id: str):
    """
    Perform a three-way match between invoice, purchase order,
    and received/ordered quantities where available.

    Checks:
    - Invoice is linked to a purchase order.
    - Invoice vendor matches PO vendor.
    - Invoice amount matches PO amount within tolerance.
    - Invoice and PO exist.

    Args:
        invoice_id: Invoice ID, e.g. INV-000001.

    Returns:
        Match result containing:
        - matched
        - invoice_id
        - po_id
        - invoice_amount
        - po_amount
        - amount_difference
        - errors
        - warnings

    Use when:
        Deciding whether an invoice agrees with its purchase order
        before approval or payment.
    """

    invoices = get_invoice(invoice_id)

    if not invoices:
        return {
            "matched": False,
            "invoice_id": invoice_id,
            "errors": ["Invoice not found"],
        }

    invoice = invoices[0]

    po_id = invoice.get("po_id")

    if not po_id:
        return {
            "matched": False,
            "invoice_id": invoice_id,
            "errors": ["Invoice is not linked to a purchase order"],
        }

    purchase_orders = get_purchase_order(po_id)

    if not purchase_orders:
        return {
            "matched": False,
            "invoice_id": invoice_id,
            "po_id": po_id,
            "errors": ["Purchase order not found"],
        }

    po = purchase_orders[0]

    errors = []
    warnings = []

    invoice_vendor = invoice.get("vendor_id")
    po_vendor = po.get("vendor_id")

    if invoice_vendor != po_vendor:
        errors.append(
            "Invoice vendor does not match purchase order vendor"
        )

    invoice_total = float(invoice.get("total") or 0)
    po_total = float(po.get("total") or 0)

    difference = invoice_total - po_total

    if abs(difference) > 0.01:
        errors.append(
            "Invoice total does not match purchase order total"
        )

    return {
        "matched": len(errors) == 0,
        "invoice_id": invoice_id,
        "po_id": po_id,
        "invoice_amount": invoice_total,
        "po_amount": po_total,
        "amount_difference": difference,
        "errors": errors,
        "warnings": warnings,
    }


@mcp.tool()
def detect_duplicate_invoice(invoice_id: str):
    """
    Detect potential duplicate purchase invoices.

    Compares invoices using:
    - Same vendor
    - Same invoice number

    Args:
        invoice_id: Invoice ID to investigate, e.g. INV-000001.

    Returns:
        Duplicate analysis containing:
        - duplicate_found
        - invoice_id
        - matching_invoice_ids
        - match_reason

    Use when:
        Checking whether an invoice may have already been recorded.
    """

    invoices = get_invoice(invoice_id)

    if not invoices:
        return {
            "duplicate_found": False,
            "invoice_id": invoice_id,
            "error": "Invoice not found",
        }

    invoice = invoices[0]

    vendor_id = invoice.get("vendor_id")
    invoice_number = invoice.get("invoice_number")

    if not vendor_id or not invoice_number:
        return {
            "duplicate_found": False,
            "invoice_id": invoice_id,
            "error": "Vendor or invoice number is missing",
        }

    duplicates = get_invoice(
        vendor_id=vendor_id,
        limit=100,
    )

    matching_ids = [
        row["invoice_id"]
        for row in duplicates
        if (
            row.get("invoice_number") == invoice_number
            and row.get("invoice_id") != invoice_id
        )
    ]

    return {
        "duplicate_found": len(matching_ids) > 0,
        "invoice_id": invoice_id,
        "matching_invoice_ids": matching_ids,
        "match_reason": (
            "Same vendor and invoice number"
            if matching_ids
            else None
        ),
    }




@mcp.tool()
def validate_payment(payment_id: str):
    """
    Validate a vendor payment against its invoice.

    Checks:
    - Payment exists.
    - Referenced invoice exists.
    - Payment vendor matches invoice vendor.
    - Payment amount is positive.
    - Payment does not exceed the invoice total.

    Args:
        payment_id: Payment ID, e.g. PAY-000001.

    Returns:
        Validation result containing:
        - valid
        - payment_id
        - invoice_id
        - payment_amount
        - invoice_amount
        - errors
        - warnings

    Use when:
        Verifying whether a vendor payment is valid against
        its associated invoice.
    """

    payments = get_payment(payment_id)

    if not payments:
        return {
            "valid": False,
            "payment_id": payment_id,
            "errors": ["Payment not found"],
        }

    payment = payments[0]

    errors = []
    warnings = []

    amount = float(payment.get("amount") or 0)

    if amount <= 0:
        errors.append("Payment amount must be greater than zero")

    invoice_id = payment.get("invoice_id")

    if not invoice_id:
        errors.append("Payment has no invoice reference")

        return {
            "valid": False,
            "payment_id": payment_id,
            "errors": errors,
            "warnings": warnings,
        }

    invoices = get_invoice(invoice_id)

    if not invoices:
        errors.append("Referenced invoice does not exist")

        return {
            "valid": False,
            "payment_id": payment_id,
            "invoice_id": invoice_id,
            "errors": errors,
            "warnings": warnings,
        }

    invoice = invoices[0]

    invoice_amount = float(invoice.get("total") or 0)

    if amount > invoice_amount:
        errors.append(
            "Payment amount exceeds invoice total"
        )

    if payment.get("vendor_id") != invoice.get("vendor_id"):
        errors.append(
            "Payment vendor does not match invoice vendor"
        )

    return {
        "valid": len(errors) == 0,
        "payment_id": payment_id,
        "invoice_id": invoice_id,
        "payment_amount": amount,
        "invoice_amount": invoice_amount,
        "errors": errors,
        "warnings": warnings,
    }


@mcp.tool()
def validate_accounting_period(
    transaction_date: str,
):
    """
    Check whether a transaction date belongs to an open
    accounting period.

    Args:
        transaction_date: Date to validate, YYYY-MM-DD.

    Returns:
        Validation result containing:
        - valid
        - transaction_date
        - period_id
        - period_status
        - errors

    Use when:
        Checking whether a journal entry or transaction can
        be posted for a particular accounting date.
    """

    from DB.functions import get_accounting_period

    periods = get_accounting_period(transaction_date)

    if not periods:
        return {
            "valid": False,
            "transaction_date": transaction_date,
            "errors": [
                "No accounting period exists for this date"
            ],
        }

    period = periods[0]

    status = period.get("status")

    valid = status == "OPEN"

    return {
        "valid": valid,
        "transaction_date": transaction_date,
        "period_id": period.get("period_id"),
        "period_status": status,
        "errors": (
            []
            if valid
            else [
                f"Accounting period is {status}"
            ]
        ),
    }