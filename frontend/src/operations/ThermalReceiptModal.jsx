import React, { useState, useEffect, useRef } from "react";
import { dashboardApi } from "../api/operationsApi";

export default function ThermalReceiptModal({
  order,
  initialSlipType = "invoice",
  autoTriggerPrint = false,
  onClose,
}) {
  const [slipType, setSlipType] = useState(initialSlipType);
  const [loading, setLoading] = useState(true);
  const [printingLocal, setPrintingLocal] = useState(false);
  const [receiptData, setReceiptData] = useState(null);
  const [statusMsg, setStatusMsg] = useState(null);
  const printAreaRef = useRef(null);
  const autoPrintedRef = useRef(false);

  useEffect(() => {
    if (!order?.id) return;
    loadReceipt(slipType);
  }, [order?.id, slipType]);

  const loadReceipt = async (type) => {
    setLoading(true);
    setStatusMsg(null);
    try {
      const res = await dashboardApi.getOrderReceipt(order.id, type);
      setReceiptData(res.data);
    } catch (err) {
      console.error("Failed to load receipt data:", err);
      setStatusMsg({ type: "error", text: "Failed to load receipt data." });
    } finally {
      setLoading(false);
    }
  };

  const handleBrowserPrint = async () => {
    window.print();
    // Record browser print audit log
    try {
      const res = await dashboardApi.printOrderReceipt(order.id, {
        slip_type: slipType,
        mode: "browser",
      });
      if (res.data?.print_count !== undefined) {
        setReceiptData((prev) => (prev ? { ...prev, print_count: res.data.print_count } : prev));
      }
    } catch (err) {
      console.warn("Failed to log browser print audit:", err);
    }
  };

  // Auto-trigger browser print dialog when autoTriggerPrint is true and receipt finishes loading
  useEffect(() => {
    if (autoTriggerPrint && !loading && receiptData && !autoPrintedRef.current) {
      autoPrintedRef.current = true;
      const timer = setTimeout(() => {
        handleBrowserPrint();
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [autoTriggerPrint, loading, receiptData]);

  const handleDirectEscposPrint = async () => {
    setPrintingLocal(true);
    setStatusMsg(null);
    try {
      const res = await dashboardApi.printOrderReceipt(order.id, {
        slip_type: slipType,
        mode: "escpos_local",
      });
      const data = res.data;
      if (data.success) {
        setStatusMsg({
          type: "success",
          text: `Sent to printer "${data.printer}" (${data.bytes_sent} bytes).`,
        });
        if (data.print_count !== undefined) {
          setReceiptData((prev) => prev ? { ...prev, print_count: data.print_count } : prev);
        }
      } else {
        setStatusMsg({
          type: data.simulated ? "warning" : "error",
          text: data.error || "Failed to print via ESC/POS.",
        });
      }
    } catch (err) {
      console.error("Direct ESC/POS print error:", err);
      setStatusMsg({ type: "error", text: "Direct printing failed to dispatch." });
    } finally {
      setPrintingLocal(false);
    }
  };

  if (!order) return null;

  const r = receiptData?.receipt;
  const biz = r?.business || {};
  const ord = r?.order || {};
  const items = r?.items || [];
  const totals = r?.totals;
  const curr = r?.currency_symbol || biz?.currency_symbol || receiptData?.currency_symbol || "Rs.";

  return (
    <>
      <style>{`
        /* Screen Styles */
        .trm-backdrop {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(15, 23, 42, 0.7);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 9999;
          padding: 16px;
        }

        .trm-modal {
          background: #ffffff;
          border-radius: 16px;
          max-width: 600px;
          width: 100%;
          max-height: 92vh;
          display: flex;
          flex-direction: column;
          box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
          overflow: hidden;
          animation: trmFadeIn 0.2s ease-out;
        }

        @keyframes trmFadeIn {
          from { opacity: 0; transform: scale(0.97); }
          to { opacity: 1; transform: scale(1); }
        }

        .trm-header {
          padding: 18px 24px;
          border-bottom: 1px solid #e2e8f0;
          display: flex;
          align-items: center;
          justify-content: space-between;
          background: #f8fafc;
        }

        .trm-header-left {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .trm-title {
          font-size: 17px;
          font-weight: 700;
          color: #0f172a;
          margin: 0;
        }

        .trm-badge {
          display: inline-block;
          font-size: 11px;
          font-weight: 600;
          padding: 3px 8px;
          border-radius: 6px;
          background: #e2e8f0;
          color: #475569;
        }

        .trm-close-btn {
          border: none;
          background: transparent;
          font-size: 22px;
          color: #64748b;
          cursor: pointer;
          border-radius: 6px;
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.15s;
        }

        .trm-close-btn:hover {
          background: #e2e8f0;
          color: #0f172a;
        }

        .trm-tabs-bar {
          display: flex;
          background: #f1f5f9;
          padding: 4px;
          margin: 14px 24px 0 24px;
          border-radius: 10px;
          gap: 4px;
        }

        .trm-tab {
          flex: 1;
          padding: 8px 12px;
          border: none;
          background: transparent;
          font-size: 13.5px;
          font-weight: 600;
          color: #64748b;
          cursor: pointer;
          border-radius: 8px;
          transition: all 0.15s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }

        .trm-tab.active {
          background: #ffffff;
          color: #0f172a;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .trm-body {
          padding: 16px 24px;
          overflow-y: auto;
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          background: #f8fafc;
        }

        /* 80mm Thermal Receipt Simulation (Width 72mm-80mm ~ 302px) */
        .trm-paper {
          width: 310px;
          background: #ffffff;
          color: #111827;
          font-family: 'Courier New', Courier, monospace;
          font-size: 12px;
          line-height: 1.35;
          padding: 16px 14px;
          box-shadow: 0 4px 15px rgba(0,0,0,0.08);
          border: 1px solid #e2e8f0;
          border-radius: 4px;
          box-sizing: border-box;
          word-break: break-word;
        }

        .trm-paper-header {
          text-align: center;
          margin-bottom: 8px;
        }

        .trm-store-title {
          font-size: 16px;
          font-weight: 800;
          text-transform: uppercase;
          margin-bottom: 2px;
        }

        .trm-divider {
          border-top: 1px dashed #4b5563;
          margin: 8px 0;
        }

        .trm-divider-double {
          border-top: 2px double #111827;
          margin: 8px 0;
        }

        .trm-paper-title {
          text-align: center;
          font-weight: 800;
          font-size: 13px;
          margin: 4px 0;
        }

        .trm-row {
          display: flex;
          justify-content: space-between;
          margin-bottom: 2px;
        }

        .trm-items-table {
          width: 100%;
          border-collapse: collapse;
          margin: 4px 0;
        }

        .trm-items-table th {
          text-align: left;
          font-weight: 700;
          padding-bottom: 4px;
        }

        .trm-items-table td {
          padding: 2px 0;
          vertical-align: top;
        }

        .trm-kot-item {
          display: flex;
          align-items: baseline;
          gap: 6px;
          margin: 4px 0;
          font-size: 13.5px;
        }

        .trm-kot-qty {
          font-size: 16px;
          font-weight: 900;
          color: #0f172a;
          min-width: 32px;
        }

        .trm-kot-name {
          font-weight: 700;
          color: #1e293b;
        }

        /* High Visibility Instructions Box */
        .trm-notes-box {
          background: #fffbeb;
          border: 2px dashed #d97706;
          border-radius: 4px;
          padding: 8px 10px;
          margin: 10px 0;
          color: #92400e;
        }

        .trm-notes-title {
          font-weight: 800;
          font-size: 11px;
          text-transform: uppercase;
          margin-bottom: 4px;
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .trm-notes-text {
          font-weight: 700;
          font-size: 12px;
          line-height: 1.3;
        }

        .trm-total-row {
          font-size: 15px;
          font-weight: 800;
        }

        .trm-paper-footer {
          text-align: center;
          font-size: 11px;
          color: #6b7280;
          margin-top: 10px;
        }

        /* Footer & Actions */
        .trm-modal-footer {
          padding: 16px 24px;
          border-top: 1px solid #e2e8f0;
          background: #ffffff;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .trm-footer-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-size: 12px;
          color: #64748b;
        }

        .trm-actions {
          display: flex;
          gap: 10px;
          align-items: center;
        }

        .trm-btn-secondary {
          padding: 10px 16px;
          background: #f1f5f9;
          color: #334155;
          font-weight: 600;
          font-size: 13.5px;
          border-radius: 10px;
          border: 1px solid #cbd5e1;
          cursor: pointer;
          transition: background 0.15s;
        }

        .trm-btn-secondary:hover {
          background: #e2e8f0;
        }

        .trm-btn-primary {
          flex: 1;
          padding: 10px 18px;
          background: #4f46e5;
          color: #ffffff;
          font-weight: 600;
          font-size: 13.5px;
          border-radius: 10px;
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          transition: background 0.15s;
        }

        .trm-btn-primary:hover {
          background: #4338ca;
        }

        .trm-btn-speedx {
          padding: 10px 16px;
          background: #0f172a;
          color: #ffffff;
          font-weight: 600;
          font-size: 13.5px;
          border-radius: 10px;
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 6px;
          transition: background 0.15s;
        }

        .trm-btn-speedx:hover {
          background: #1e293b;
        }

        .trm-btn-speedx:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .trm-status-banner {
          font-size: 12.5px;
          padding: 8px 12px;
          border-radius: 8px;
          margin-top: 4px;
        }

        .trm-status-success {
          background: #ecfdf5;
          color: #065f46;
          border: 1px solid #a7f3d0;
        }

        .trm-status-warning {
          background: #fffbeb;
          color: #92400e;
          border: 1px solid #fde68a;
        }

        .trm-status-error {
          background: #fef2f2;
          color: #991b1b;
          border: 1px solid #fecaca;
        }

        /* 80mm Print Media Query (Strict Single Sheet Continuous Thermal Print) */
        @media print {
          @page {
            size: 80mm auto; /* 80mm width, auto height */
            margin: 0mm; /* Remove default browser margins */
          }
          html, body {
            margin: 0 !important;
            padding: 0 !important;
            height: max-content !important;
            min-height: max-content !important;
            overflow: visible !important;
            background: #ffffff !important;
          }
          body * {
            visibility: hidden !important;
          }
          .trm-backdrop, .trm-modal {
            position: static !important;
            background: transparent !important;
            padding: 0 !important;
            margin: 0 !important;
            width: auto !important;
            height: auto !important;
            min-height: 0 !important;
            max-height: none !important;
            overflow: visible !important;
            box-shadow: none !important;
            border: none !important;
          }
          #thermal-print-area, #thermal-print-area * {
            visibility: visible !important;
          }
          #thermal-print-area, .receipt-print-container {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 78mm !important;
            max-width: 80mm !important;
            margin: 0 !important;
            padding: 2mm 3mm !important;
            border: none !important;
            box-shadow: none !important;
            page-break-after: avoid !important;
            page-break-before: avoid !important;
            page-break-inside: avoid !important;
            break-inside: avoid !important;
          }
        }
      `}</style>

      <div className="trm-backdrop" onClick={onClose}>
        <div className="trm-modal" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div className="trm-header">
            <div className="trm-header-left">
              <span style={{ fontSize: 22 }}>🖨️</span>
              <div>
                <h3 className="trm-title">Thermal Receipt #{order.order_number}</h3>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 2 }}>
                  <span className="trm-badge">SpeedX SP-200U (80mm)</span>
                  {receiptData?.auto_print_kot && (
                    <span className="trm-badge" style={{ background: "#fef3c7", color: "#92400e" }}>
                      ⚡ Auto KOT
                    </span>
                  )}
                  {receiptData?.auto_print_invoice && (
                    <span className="trm-badge" style={{ background: "#ecfdf5", color: "#065f46" }}>
                      ⚡ Auto Invoice
                    </span>
                  )}
                  {autoTriggerPrint && (
                    <span className="trm-badge" style={{ background: "#dbeafe", color: "#1e40af" }}>
                      🖨️ Auto-Print Dialog
                    </span>
                  )}
                </div>
              </div>
            </div>
            <button className="trm-close-btn" onClick={onClose} title="Close">✕</button>
          </div>

          {/* Slip Type Switcher */}
          <div className="trm-tabs-bar">
            <button
              className={`trm-tab ${slipType === "invoice" ? "active" : ""}`}
              onClick={() => setSlipType("invoice")}
            >
              🧾 Customer Invoice
            </button>
            <button
              className={`trm-tab ${slipType === "kot" ? "active" : ""}`}
              onClick={() => setSlipType("kot")}
            >
              🍳 Kitchen Order Ticket (KOT)
            </button>
          </div>

          {/* Body with 80mm simulated paper */}
          <div className="trm-body">
            {loading ? (
              <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>
                <div>⏳ Generating 80mm slip preview...</div>
              </div>
            ) : (
              <div id="thermal-print-area" className="trm-paper receipt-print-container" ref={printAreaRef}>
                {/* INVOICE VIEW */}
                {slipType === "invoice" ? (
                  <>
                    <div className="trm-paper-header">
                      <div className="trm-store-title">{biz.name || "RIDES AI STORE"}</div>
                      <div style={{ fontSize: 10, color: "#64748b", margin: "2px 0 4px", fontWeight: 700 }}>
                        Owned by Rides Technologies
                      </div>
                      {biz.address && <div>{biz.address}</div>}
                      {biz.phone && <div>Tel: {biz.phone}</div>}
                      {biz.header && biz.header !== "Owned by Rides Technologies" && <div>{biz.header}</div>}
                    </div>

                    <div className="trm-divider" />
                    <div className="trm-paper-title">*** TAX INVOICE ***</div>
                    <div className="trm-divider" />

                    <div className="trm-row">
                      <span>Order: #{ord.order_number}</span>
                      <span>{ord.created_at}</span>
                    </div>
                    <div className="trm-row">
                      <span>Cust: {ord.customer_name}</span>
                      <span>{ord.customer_phone}</span>
                    </div>
                    {ord.delivery_address && (
                      <div style={{ marginTop: 2 }}>
                        <span>Address: {ord.delivery_address}</span>
                      </div>
                    )}
                    {(ord.assigned_rider_name || ord.assigned_rider?.name) && (
                      <div className="trm-row" style={{ marginTop: 2 }}>
                        <span>Rider:</span>
                        <span style={{ fontWeight: 700, color: "#2563eb" }}>
                          🛵 {ord.assigned_rider_name || ord.assigned_rider?.name}
                        </span>
                      </div>
                    )}

                    <div className="trm-divider" />

                    {/* Items table */}
                    <table className="trm-items-table">
                      <thead>
                        <tr>
                          <th style={{ width: "55%" }}>ITEM</th>
                          <th style={{ width: "15%", textAlign: "center" }}>QTY</th>
                          <th style={{ width: "30%", textAlign: "right" }}>TOTAL</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((it, idx) => (
                          <tr key={idx}>
                            <td>{it.name}</td>
                            <td style={{ textAlign: "center" }}>{it.quantity}</td>
                            <td style={{ textAlign: "right" }}>{curr} {it.line_total.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    <div className="trm-divider" />

                    {/* Totals */}
                    {totals && (
                      <>
                        <div className="trm-row">
                          <span>Subtotal:</span>
                          <span>{curr} {totals.subtotal.toFixed(2)}</span>
                        </div>
                        {totals.delivery_fee > 0 && (
                          <div className="trm-row">
                            <span>Delivery Fee:</span>
                            <span>{curr} {totals.delivery_fee.toFixed(2)}</span>
                          </div>
                        )}
                        <div className="trm-divider-double" />
                        <div className="trm-row trm-total-row">
                          <span>TOTAL:</span>
                          <span>{curr} {totals.total.toFixed(2)}</span>
                        </div>
                        <div className="trm-divider-double" />
                      </>
                    )}

                    {/* Special Instructions */}
                    {ord.has_notes && (
                      <div className="trm-notes-box">
                        <div className="trm-notes-title">⚠️ Special Instructions</div>
                        <div className="trm-notes-text">{ord.notes}</div>
                      </div>
                    )}

                    <div className="trm-paper-footer">
                      <div>{biz.footer || "Thank you for ordering!"}</div>
                      <div style={{ fontSize: 9.5, color: "#94a3b8", marginTop: 4, letterSpacing: "0.5px" }}>
                        Powered by Rides Technologies
                      </div>
                    </div>
                  </>
                ) : (
                  /* KOT VIEW */
                  <>
                    <div className="trm-paper-header">
                      <div className="trm-store-title">*** KOT ***</div>
                      <div style={{ fontSize: 10, color: "#64748b", margin: "2px 0 4px", fontWeight: 700 }}>
                        Owned by Rides Technologies
                      </div>
                      <div style={{ fontSize: 18, fontWeight: 900, marginTop: 4 }}>
                        ORDER #{ord.order_number}
                      </div>
                      <div style={{ fontSize: 11, marginTop: 2 }}>
                        {ord.created_at} | {ord.source?.toUpperCase()}
                      </div>
                      <div style={{ fontSize: 11, marginTop: 2 }}>
                        Customer: {ord.customer_name} ({ord.customer_phone})
                      </div>
                      {(ord.assigned_rider_name || ord.assigned_rider?.name) && (
                        <div style={{ fontSize: 11, marginTop: 3, fontWeight: 700, color: "#2563eb" }}>
                          Rider: 🛵 {ord.assigned_rider_name || ord.assigned_rider?.name}
                        </div>
                      )}
                    </div>

                    <div className="trm-divider-double" />

                    {/* KOT Items */}
                    <div style={{ margin: "6px 0" }}>
                      {items.map((it, idx) => (
                        <div key={idx} className="trm-kot-item">
                          <span className="trm-kot-qty">{it.quantity}x</span>
                          <span className="trm-kot-name">{it.name}</span>
                        </div>
                      ))}
                    </div>

                    <div className="trm-divider-double" />

                    {/* Special Instructions (Crucial for Kitchen) */}
                    {ord.has_notes ? (
                      <div className="trm-notes-box" style={{ background: "#fef3c7", borderColor: "#b45309" }}>
                        <div className="trm-notes-title" style={{ fontSize: 12, color: "#92400e" }}>
                          🚨 KITCHEN SPECIAL NOTES:
                        </div>
                        <div className="trm-notes-text" style={{ fontSize: 13, color: "#78350f" }}>
                          {ord.notes}
                        </div>
                      </div>
                    ) : (
                      <div style={{ textAlign: "center", color: "#6b7280", fontStyle: "italic", margin: "6px 0" }}>
                        No special kitchen instructions
                      </div>
                    )}

                    <div className="trm-divider" />
                    <div style={{ textAlign: "center", fontSize: 10, color: "#9ca3af" }}>
                      [END OF KOT TICKET]
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Modal Footer */}
          <div className="trm-modal-footer">
            <div className="trm-footer-top">
              <span>
                <strong>Audit:</strong> Printed {receiptData?.print_count ?? 0} time(s)
                {receiptData?.last_printed_at ? ` (Last: ${new Date(receiptData.last_printed_at).toLocaleTimeString()})` : ""}
              </span>
              <span>
                <strong>Target:</strong> {receiptData?.printer_name || "SpeedX SP-200U"}
              </span>
            </div>

            {statusMsg && (
              <div className={`trm-status-banner trm-status-${statusMsg.type}`}>
                {statusMsg.text}
              </div>
            )}

            <div className="trm-actions">
              <button className="trm-btn-secondary" onClick={onClose}>
                Close
              </button>
              <button className="trm-btn-primary" onClick={handleBrowserPrint}>
                🖨️ Browser 80mm Print
              </button>
              <button
                className="trm-btn-speedx"
                disabled={printingLocal}
                onClick={handleDirectEscposPrint}
                title="Send raw ESC/POS binary directly to local SpeedX SP-200U printer via Windows Spooler"
              >
                {printingLocal ? "Sending..." : "⚡ SpeedX Direct Print"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
