"""
Thermal Receipt & KOT Formatter Module.
Standardizes Order and Company models into structured payloads for 80mm printing.
"""

from decimal import Decimal


def build_receipt_payload(order, company=None, slip_type="invoice"):
    """
    Builds a JSON-serializable dictionary for rendering receipts in the browser
    or constructing ESC/POS raw byte streams.
    
    :param order: operations.models.Order instance
    :param company: companies.models.Company instance (defaults to order.company)
    :param slip_type: "invoice" | "kot"
    """
    comp = company or getattr(order, "company", None)
    
    currency_symbol = getattr(comp, "currency_symbol", "Rs.") or "Rs."

    # Format business info
    business_info = {
        "name": getattr(comp, "name", "Rides AI Store") if comp else "Rides AI Store",
        "branding": "Owned by Rides Technologies",
        "phone": getattr(comp, "phone", "") or getattr(comp, "agent_support_phone", "") or "",
        "address": getattr(comp, "address", "") or "",
        "header": getattr(comp, "receipt_header", "") or "Owned by Rides Technologies",
        "footer": getattr(comp, "receipt_footer", "") or "Thank you for your order! Powered by Rides Technologies",
        "printer_name": getattr(comp, "printer_name", "SpeedX SP-200U") if comp else "SpeedX SP-200U",
        "currency_symbol": currency_symbol,
        "auto_print_kot": getattr(comp, "auto_print_kot", False) if comp else False,
        "auto_print_invoice": getattr(comp, "auto_print_invoice", False) if comp else False,
    }
    
    # Format order info
    notes_str = (order.notes or "").strip()
    rider = getattr(order, "assigned_rider", None)
    if not rider and hasattr(order, "delivery") and order.delivery:
        rider = order.delivery.rider
    rider_name = (rider.get_full_name() or rider.username) if rider else None
    rider_phone = (getattr(rider, "phone", "") or "") if rider else ""

    order_info = {
        "id": order.id,
        "order_number": order.order_number,
        "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else "",
        "source": order.source,
        "status": order.status,
        "customer_name": order.customer_name or "Walk-in Customer",
        "customer_phone": order.customer_phone or "N/A",
        "delivery_address": order.delivery_address or "",
        "notes": notes_str,
        "has_notes": bool(notes_str),
        "assigned_rider_name": rider_name,
        "assigned_rider_phone": rider_phone,
    }
    
    # Format items
    items_list = []
    for item in order.items.all():
        qty = float(item.quantity) if isinstance(item.quantity, Decimal) else float(item.quantity or 0)
        unit_price = float(item.unit_price) if isinstance(item.unit_price, Decimal) else float(item.unit_price or 0)
        line_total = float(item.line_total) if isinstance(item.line_total, Decimal) else float(item.line_total or 0)
        items_list.append({
            "name": item.item_name,
            "quantity": qty,
            "unit_price": unit_price,
            "line_total": line_total,
        })
        
    subtotal = float(order.subtotal or 0) if isinstance(order.subtotal, Decimal) else float(order.subtotal or 0)
    delivery_fee = float(order.delivery_fee or 0) if isinstance(order.delivery_fee, Decimal) else float(order.delivery_fee or 0)
    total = float(order.total or 0) if isinstance(order.total, Decimal) else float(order.total or 0)
    
    totals_info = {
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total": total,
    }
    
    return {
        "slip_type": slip_type,
        "slip_title": "TAX INVOICE / RECEIPT" if slip_type == "invoice" else "KITCHEN ORDER TICKET (KOT)",
        "currency_symbol": currency_symbol,
        "business": business_info,
        "order": order_info,
        "items": items_list,
        "totals": totals_info if slip_type == "invoice" else None,
    }
