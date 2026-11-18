"""
Printer Service for Direct ESC/POS Spooling.
Sends raw byte streams to local/network thermal printers (e.g. SpeedX SP-200U)
using the Windows Print Spooler (win32print), with graceful fallbacks.
"""

import logging

logger = logging.getLogger(__name__)


def dispatch_to_local_printer(raw_bytes: bytes, printer_name: str = "") -> dict:
    """
    Sends raw ESC/POS bytes to the specified local printer.
    
    :param raw_bytes: Raw ESC/POS byte sequence.
    :param printer_name: Windows printer name (e.g. "SpeedX SP-200U"). If empty, uses default printer.
    :return: dict with status, printer name, and any error/warning messages.
    """
    try:
        import win32print
    except ImportError:
        logger.warning("pywin32 (win32print) is not installed. Direct local printing skipped.")
        return {
            "success": False,
            "error": "pywin32 library is not installed in this environment. Direct local print spooling is unavailable.",
            "printer": printer_name,
            "simulated": True,
        }

    target_printer = (printer_name or "").strip()
    try:
        if not target_printer:
            target_printer = win32print.GetDefaultPrinter()

        h_printer = win32print.OpenPrinter(target_printer)
        try:
            h_job = win32print.StartDocPrinter(h_printer, 1, ("RidesAI Receipt Print", None, "RAW"))
            try:
                win32print.StartPagePrinter(h_printer)
                win32print.WritePrinter(h_printer, raw_bytes)
                win32print.EndPagePrinter(h_printer)
            finally:
                win32print.EndDocPrinter(h_printer)
        finally:
            win32print.ClosePrinter(h_printer)

        logger.info(f"Successfully dispatched {len(raw_bytes)} bytes to printer '{target_printer}'.")
        return {
            "success": True,
            "printer": target_printer,
            "bytes_sent": len(raw_bytes),
        }
    except Exception as exc:
        err_msg = f"Failed to send print job to '{target_printer}': {str(exc)}"
        logger.error(err_msg)
        return {
            "success": False,
            "error": err_msg,
            "printer": target_printer,
        }


def trigger_auto_print_for_order(order, printed_by=None) -> list:
    """
    Non-blocking auto-print service for orders.
    Triggered when an order is created or confirmed if the tenant has enabled
    auto_print_kot or auto_print_invoice.
    
    Catches all exceptions gracefully and records OrderPrintLog so order creation/confirmation
    is NEVER blocked or disrupted.
    """
    from operations.models import OrderPrintLog
    from .escpos_builder import build_kot_escpos, build_invoice_escpos

    company = getattr(order, "company", None)
    if not company:
        return []

    logs_created = []

    # 1. Check KOT auto-print
    if getattr(company, "auto_print_kot", False):
        try:
            raw_kot = build_kot_escpos(order, company=company)
            result_kot = dispatch_to_local_printer(raw_kot, company.printer_name)
            log_status = OrderPrintLog.STATUS_SUCCESS if result_kot.get("success") else OrderPrintLog.STATUS_FAILED
            log_entry = OrderPrintLog.objects.create(
                company=company,
                order=order,
                slip_type=OrderPrintLog.SLIP_KOT,
                print_mode=OrderPrintLog.MODE_ESCPOS_LOCAL,
                status=log_status,
                error_message=result_kot.get("error", "") or "",
                printed_by=printed_by if hasattr(printed_by, "id") else None,
            )
            logs_created.append(log_entry)
        except Exception as exc:
            logger.error(f"[Auto-Print KOT Error] Order #{order.order_number}: {exc}", exc_info=True)
            try:
                log_entry = OrderPrintLog.objects.create(
                    company=company,
                    order=order,
                    slip_type=OrderPrintLog.SLIP_KOT,
                    print_mode=OrderPrintLog.MODE_ESCPOS_LOCAL,
                    status=OrderPrintLog.STATUS_FAILED,
                    error_message=str(exc),
                    printed_by=printed_by if hasattr(printed_by, "id") else None,
                )
                logs_created.append(log_entry)
            except Exception:
                pass

    # 2. Check Invoice auto-print
    if getattr(company, "auto_print_invoice", False):
        try:
            raw_invoice = build_invoice_escpos(order, company=company)
            result_inv = dispatch_to_local_printer(raw_invoice, company.printer_name)
            log_status = OrderPrintLog.STATUS_SUCCESS if result_inv.get("success") else OrderPrintLog.STATUS_FAILED
            log_entry = OrderPrintLog.objects.create(
                company=company,
                order=order,
                slip_type=OrderPrintLog.SLIP_INVOICE,
                print_mode=OrderPrintLog.MODE_ESCPOS_LOCAL,
                status=log_status,
                error_message=result_inv.get("error", "") or "",
                printed_by=printed_by if hasattr(printed_by, "id") else None,
            )
            logs_created.append(log_entry)
        except Exception as exc:
            logger.error(f"[Auto-Print Invoice Error] Order #{order.order_number}: {exc}", exc_info=True)
            try:
                log_entry = OrderPrintLog.objects.create(
                    company=company,
                    order=order,
                    slip_type=OrderPrintLog.SLIP_INVOICE,
                    print_mode=OrderPrintLog.MODE_ESCPOS_LOCAL,
                    status=OrderPrintLog.STATUS_FAILED,
                    error_message=str(exc),
                    printed_by=printed_by if hasattr(printed_by, "id") else None,
                )
                logs_created.append(log_entry)
            except Exception:
                pass

    return logs_created

