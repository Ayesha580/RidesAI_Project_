"""
ESC/POS Byte Stream Generator for 80mm Thermal Printers (e.g. SpeedX SP-200U).
Standard 80mm printer column width: 48 characters (Font A).
"""

import textwrap
from .receipt_formatter import build_receipt_payload

# ESC/POS Constants
ESC = b"\x1b"
GS = b"\x1d"

CMD_INIT = ESC + b"@"
ALIGN_LEFT = ESC + b"a\x00"
ALIGN_CENTER = ESC + b"a\x01"
ALIGN_RIGHT = ESC + b"a\x02"

TXT_NORMAL = ESC + b"!\x00"
TXT_BOLD = ESC + b"!\x08"
TXT_2HEIGHT = ESC + b"!\x10"
TXT_2WIDTH = ESC + b"!\x20"
TXT_2BOTH = ESC + b"!\x30"

CUT_PAPER = GS + b"V\x42\x00"
LINE_FEED = b"\n"

WIDTH_80MM = 48


def _encode_text(text: str) -> bytes:
    """Encode unicode text safely for ESC/POS printing."""
    return text.encode("ascii", errors="replace")


def _two_columns(left: str, right: str, width: int = WIDTH_80MM) -> str:
    """Align left text and right text to fit within width characters."""
    total_len = len(left) + len(right)
    if total_len >= width:
        # If too long, truncate left or wrap
        available_left = max(10, width - len(right) - 1)
        left = left[:available_left]
    spaces = " " * max(1, width - len(left) - len(right))
    return f"{left}{spaces}{right}"


def _three_columns(item: str, qty: str, total: str, width: int = WIDTH_80MM) -> list[str]:
    """
    Format 3 columns for 80mm line items:
    Item (28 chars), Qty (6 chars), Total (14 chars)
    """
    qty_str = qty.center(6)
    total_str = total.rjust(14)
    item_width = width - len(qty_str) - len(total_str) # 28 chars

    item_lines = textwrap.wrap(item, width=item_width) or [""]
    results = []
    first_line = f"{item_lines[0].ljust(item_width)}{qty_str}{total_str}"
    results.append(first_line)
    for subsequent in item_lines[1:]:
        results.append(subsequent.ljust(item_width))
    return results


def build_invoice_escpos(order, company=None) -> bytes:
    """
    Constructs ESC/POS binary stream for Customer Invoice on 80mm paper.
    """
    payload = build_receipt_payload(order, company=company, slip_type="invoice")
    biz = payload["business"]
    ord_info = payload["order"]
    items = payload["items"]
    totals = payload["totals"]
    currency_symbol = payload.get("currency_symbol") or biz.get("currency_symbol") or "Rs."

    buf = bytearray()
    buf.extend(CMD_INIT)

    # 1. Store Header
    buf.extend(ALIGN_CENTER)
    buf.extend(TXT_2BOTH)
    buf.extend(_encode_text(biz["name"].upper()) + LINE_FEED)
    buf.extend(TXT_NORMAL)
    if biz["address"]:
        for line in textwrap.wrap(biz["address"], width=WIDTH_80MM):
            buf.extend(_encode_text(line) + LINE_FEED)
    if biz["phone"]:
        buf.extend(_encode_text(f"Phone: {biz['phone']}") + LINE_FEED)
    if biz["header"]:
        buf.extend(_encode_text(biz["header"]) + LINE_FEED)

    buf.extend(_encode_text("-" * WIDTH_80MM) + LINE_FEED)

    # 2. Invoice Title & Order Meta
    buf.extend(TXT_BOLD)
    buf.extend(_encode_text("*** CUSTOMER INVOICE ***") + LINE_FEED)
    buf.extend(TXT_NORMAL)

    buf.extend(ALIGN_LEFT)
    buf.extend(_encode_text(_two_columns(f"Order: #{ord_info['order_number']}", f"Date: {ord_info['created_at']}")) + LINE_FEED)
    buf.extend(_encode_text(_two_columns(f"Cust: {ord_info['customer_name']}", f"Tel: {ord_info['customer_phone']}")) + LINE_FEED)
    if ord_info["delivery_address"]:
        addr_lines = textwrap.wrap(f"Delivery: {ord_info['delivery_address']}", width=WIDTH_80MM)
        for line in addr_lines:
            buf.extend(_encode_text(line) + LINE_FEED)

    buf.extend(_encode_text("-" * WIDTH_80MM) + LINE_FEED)

    # 3. Item Table Header
    buf.extend(TXT_BOLD)
    header_line = f"{'ITEM'.ljust(28)}{'QTY'.center(6)}{'TOTAL'.rjust(14)}"
    buf.extend(_encode_text(header_line) + LINE_FEED)
    buf.extend(TXT_NORMAL)
    buf.extend(_encode_text("-" * WIDTH_80MM) + LINE_FEED)

    # 4. Item List
    for item in items:
        qty_display = f"{item['quantity']:g}"
        total_display = f"{currency_symbol} {item['line_total']:.2f}"
        for formatted_line in _three_columns(item["name"], qty_display, total_display):
            buf.extend(_encode_text(formatted_line) + LINE_FEED)

    buf.extend(_encode_text("-" * WIDTH_80MM) + LINE_FEED)

    # 5. Financial Summary
    buf.extend(_encode_text(_two_columns("Subtotal:", f"{currency_symbol} {totals['subtotal']:.2f}")) + LINE_FEED)
    if totals["delivery_fee"] > 0:
        buf.extend(_encode_text(_two_columns("Delivery Fee:", f"{currency_symbol} {totals['delivery_fee']:.2f}")) + LINE_FEED)

    buf.extend(_encode_text("=" * WIDTH_80MM) + LINE_FEED)
    buf.extend(TXT_2HEIGHT)
    buf.extend(TXT_BOLD)
    buf.extend(_encode_text(_two_columns("TOTAL AMOUNT:", f"{currency_symbol} {totals['total']:.2f}")) + LINE_FEED)
    buf.extend(TXT_NORMAL)
    buf.extend(_encode_text("=" * WIDTH_80MM) + LINE_FEED)

    # 6. Special Instructions (if any)
    if ord_info["has_notes"]:
        buf.extend(TXT_BOLD)
        buf.extend(_encode_text("SPECIAL INSTRUCTIONS:") + LINE_FEED)
        buf.extend(TXT_NORMAL)
        for note_line in textwrap.wrap(ord_info["notes"], width=WIDTH_80MM):
            buf.extend(_encode_text(f"  * {note_line}") + LINE_FEED)
        buf.extend(_encode_text("-" * WIDTH_80MM) + LINE_FEED)

    # 7. Footer
    buf.extend(ALIGN_CENTER)
    if biz["footer"]:
        for foot_line in textwrap.wrap(biz["footer"], width=WIDTH_80MM):
            buf.extend(_encode_text(foot_line) + LINE_FEED)

    # Feed & Cut
    buf.extend(LINE_FEED * 4)
    buf.extend(CUT_PAPER)

    return bytes(buf)


def build_kot_escpos(order, company=None) -> bytes:
    """
    Constructs ESC/POS binary stream for Kitchen Order Ticket (KOT) on 80mm paper.
    Optimized for kitchen visibility: Large Order #, clear item quantities, highlighted special notes.
    """
    payload = build_receipt_payload(order, company=company, slip_type="kot")
    ord_info = payload["order"]
    items = payload["items"]

    buf = bytearray()
    buf.extend(CMD_INIT)

    # 1. KOT Big Header
    buf.extend(ALIGN_CENTER)
    buf.extend(TXT_2BOTH)
    buf.extend(_encode_text("*** KOT - KITCHEN TICKET ***") + LINE_FEED)
    buf.extend(_encode_text(f"ORDER #{ord_info['order_number']}") + LINE_FEED)
    buf.extend(TXT_NORMAL)

    buf.extend(_encode_text(_two_columns(f"Time: {ord_info['created_at']}", f"Source: {ord_info['source'].upper()}")) + LINE_FEED)
    buf.extend(_encode_text(_two_columns(f"Customer: {ord_info['customer_name']}", f"Tel: {ord_info['customer_phone']}")) + LINE_FEED)
    buf.extend(_encode_text("=" * WIDTH_80MM) + LINE_FEED)

    # 2. Items List (Big QTY + Item Name)
    buf.extend(ALIGN_LEFT)
    buf.extend(TXT_BOLD)
    buf.extend(_encode_text(f"{'QTY'.ljust(8)}{'ITEM DESCRIPTION'.ljust(40)}") + LINE_FEED)
    buf.extend(TXT_NORMAL)
    buf.extend(_encode_text("-" * WIDTH_80MM) + LINE_FEED)

    for item in items:
        qty_display = f"{item['quantity']:g}x".ljust(8)
        item_lines = textwrap.wrap(item["name"], width=40) or [""]
        buf.extend(TXT_2HEIGHT)
        buf.extend(TXT_BOLD)
        buf.extend(_encode_text(f"{qty_display}{item_lines[0]}") + LINE_FEED)
        buf.extend(TXT_NORMAL)
        for subsequent in item_lines[1:]:
            buf.extend(_encode_text(f"{' ' * 8}{subsequent}") + LINE_FEED)

    buf.extend(_encode_text("=" * WIDTH_80MM) + LINE_FEED)

    # 3. Special Instructions / Kitchen Notes (Critical for Kitchen!)
    if ord_info["has_notes"]:
        buf.extend(TXT_2BOTH)
        buf.extend(_encode_text("! ATTENTION KITCHEN !") + LINE_FEED)
        buf.extend(TXT_NORMAL)
        buf.extend(TXT_BOLD)
        buf.extend(_encode_text("SPECIAL PREPARATION INSTRUCTIONS:") + LINE_FEED)
        buf.extend(TXT_NORMAL)
        for line in textwrap.wrap(ord_info["notes"], width=WIDTH_80MM):
            buf.extend(_encode_text(f">> {line}") + LINE_FEED)
        buf.extend(_encode_text("=" * WIDTH_80MM) + LINE_FEED)
    else:
        buf.extend(_encode_text("No special preparation instructions.") + LINE_FEED)

    # Feed & Cut
    buf.extend(LINE_FEED * 4)
    buf.extend(CUT_PAPER)

    return bytes(buf)
