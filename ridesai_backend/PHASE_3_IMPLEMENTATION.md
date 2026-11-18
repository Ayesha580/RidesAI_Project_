# Rides AI WhatsApp AI Agent — Phase 3: Tool Calling & Database Order Execution

## 1. Executive Summary

Phase 3 upgrades the Rides AI WhatsApp Voice & Chat Agent from static conversational prompt-grounding to **strict OpenAI/Groq Tool Calling (Function Calling) with atomic Django ORM database execution**.

The AI Agent can now interact directly with tenant database tables in real time:
- Browsing and filtering live menu/catalog items with real-time stock levels.
- Executing atomic transactions that create production `Order`, `OrderItem`, and `OrderEvent` records.
- Deducting inventory and generating stock movement records.
- Querying real-time order status and order history for customer inquiries.
- **Fail-Closed Multi-Tenant Hardening**: Eliminating cross-tenant data leaks and mock fallback menus. If a destination `phone_number_id` is unmapped or unconfigured, the system fails closed immediately.

---

## 2. End-to-End Architectural Flow

```
                      +------------------------------------------+
                      |         WhatsApp Customer Client         |
                      +------------------------------------------+
                                    |              ^
                 Audio / Text Note  |              |  Audio / Text Reply
                                    v              |
                      +------------------------------------------+
                      |      Meta WhatsApp Cloud API v21.0       |
                      +------------------------------------------+
                                    |              ^
                 Webhook POST Event |              |  Outbound Message (POST)
                                    v              |
                      +------------------------------------------+
                      | Django: WhatsAppWebhookAPIView (views.py)|
                      +------------------------------------------+
                                    |
                    Extracts phone_number_id, sender_phone,
                    customer_name, text, media_id
                                    v
     +----------------------------------------------------------------------+
     |           whatsapp_agent.process_incoming_whatsapp_message           |
     +----------------------------------------------------------------------+
              |                                            ^
  (Audio?)    |                                            |
      +-------v-------+                                    |
      | audio_service |                                    |
      |   (STT: Groq) |                                    |
      +-------+-------+                                    |
              |                                            |
              v Transcribed text                           |
     +-----------------------------------------+           |
     | Multi-Tenant Resolver & Fail-Closed Guard |          |
     | - Checks phone_number_id mapping        |           |
     | - Fails closed if unmapped              |           |
     | - Injects server-verified Company       |           |
     +-----------------------------------------+           |
              |                                            |
              v Grounded Context                           |
     +-------------------------------------------------------------+
     |                 OpenAI Completion (Turn 1)                  |
     | - Model: gpt-4o-mini                                        |
     | - Tools: get_catalog_items, create_order, check_order_status|
     | - tool_choice: "auto"                                       |
     +-------------------------------------------------------------+
              |
              | tool_calls returned
              v
     +-------------------------------------------------------------+
     |             Server-Side Tool Execution Engine               |
     |  (Strictly enforces server-verified Company context)       |
     |                                                             |
     |  [get_catalog_items]  --> Query CatalogItem & Inventory     |
     |  [create_order]       --> transaction.atomic()              |
     |                           * Match CatalogItems              |
     |                           * Decrement Inventory             |
     |                           * Create Order (source="agent")   |
     |                           * Create OrderItem records        |
     |                           * Create OrderEvent audit log     |
     |  [check_order_status] --> Query Order by Phone / Reference  |
     +-------------------------------------------------------------+
              |
              v Tool execution output (JSON) appended as role="tool"
     +-------------------------------------------------------------+
     |                 OpenAI Completion (Turn 2)                  |
     | - Ingests tool outputs into conversation context            |
     | - Synthesizes natural confirmation (Order #, Total, ETA)   |
     +-------------------------------------------------------------+
              |
              v Final Text Reply
  (Voice Note?)|
      +-------v-------+
      | audio_service |
      |   (TTS: OGG)  |
      +-------+-------+
              |
              v Dispatched via WhatsAppService (Media/Text)
```

---

## 3. Tool Schemas (`AGENT_TOOLS`)

The tool schemas are registered via standard OpenAI JSON schema format in `ridesai_backend/operations/whatsapp_agent.py`:

### 3.1 `get_catalog_items`
```json
{
  "type": "function",
  "function": {
    "name": "get_catalog_items",
    "description": "Fetches real-time available menu/catalog items, stock availability, descriptions, and prices for the current business store.",
    "parameters": {
      "type": "object",
      "properties": {
        "search_query": {
          "type": "string",
          "description": "Optional keyword or category to search for specific items (e.g. 'burger', 'drink')."
        }
      },
      "required": []
    }
  }
}
```

### 3.2 `create_order`
```json
{
  "type": "function",
  "function": {
    "name": "create_order",
    "description": "Executes a confirmed order transaction in the store database. Call this ONLY when the customer has clearly confirmed they want to order and has provided their delivery address.",
    "parameters": {
      "type": "object",
      "properties": {
        "delivery_address": {
          "type": "string",
          "description": "The customer's complete delivery address or table/pickup location."
        },
        "items": {
          "type": "array",
          "description": "List of items and quantities being ordered.",
          "items": {
            "type": "object",
            "properties": {
              "item_name": {
                "type": "string",
                "description": "Name of the catalog item."
              },
              "quantity": {
                "type": "integer",
                "description": "Number of units to order (minimum 1)."
              },
              "special_instructions": {
                "type": "string",
                "description": "Optional preparation notes (e.g. 'no onions', 'extra spicy')."
              }
            },
            "required": ["item_name", "quantity"]
          }
        },
        "customer_name": {
          "type": "string",
          "description": "Name of the customer placing the order."
        },
        "notes": {
          "type": "string",
          "description": "General delivery instructions or notes for the kitchen/staff."
        }
      },
      "required": ["delivery_address", "items"]
    }
  }
}
```

### 3.3 `check_order_status`
```json
{
  "type": "function",
  "function": {
    "name": "check_order_status",
    "description": "Queries the real-time status and details of recent orders for the customer by order number or customer phone number.",
    "parameters": {
      "type": "object",
      "properties": {
        "order_number": {
          "type": "string",
          "description": "Optional order reference number (e.g., 'RA-261117-XXXX')."
        }
      },
      "required": []
    }
  }
}
```

---

## 4. Multi-Tenant Isolation & Security Hardening

### 4.1 Server-Enforced Company Invariant
- **Rule:** The LLM is never allowed to dictate the tenant. Even if an LLM prompt or tool parameter proposes an arbitrary `company_id`, the execution engine strictly ignores it and binds `company = context["company"]`, which is securely resolved from the destination `phone_number_id`.
- **Result:** Zero possibility of prompt injection or cross-tenant contamination.

### 4.2 Fail-Closed on Unmapped Phone Numbers
- **Previous Vulnerability:** Previous code fell back to `Company.objects.first()` if `phone_number_id` was unmapped.
- **Phase 3 Fix:** The fallback has been completely eliminated. If `get_config_by_phone_number_id(phone_number_id)` does not return a registered Company:
  - System logs a warning.
  - Returns `is_configured = False` and `company = None`.
  - Dispatches a polite static refusal message without invoking the LLM or touching any company database tables.

### 4.3 Elimination of Mock Defaults
- **Previous Vulnerability:** If a clean tenant company had 0 catalog items, previous code injected a mock burger menu ("Classic Beef Burger", "Crispy Chicken Burger").
- **Phase 3 Fix:** Mock defaults have been permanently removed. If a company has no catalog items, the context reflects an empty list, and the system prompt instructs the agent that the store catalog is currently being updated.

---

## 5. Database Schema & ORM Mapping

| Model | Role in AI Agent Workflow |
| :--- | :--- |
| `Company` | Multi-tenant tenant boundary; defines brand voice, address, contact, operating hours. |
| `CatalogItem` | Active items available for sale; queried by `execute_get_catalog_items`. |
| `Inventory` | Tracks stock count. Decremented inside `transaction.atomic()` during order placement. |
| `StockMovement` | Audit trail of inventory reductions (`movement_type="remove"`). |
| `Order` | Root order record. Auto-assigns `RA-{yymmdd}-{uuid8}` order number, `status="new"`, `source="agent"`. |
| `OrderItem` | Line item records linked to `CatalogItem` and `Order` with `quantity`, `unit_price`, and `line_total`. |
| `OrderEvent` | Immutable event log record (`event_type="agent_order_created"`) tracking agent lifecycle. |

---

## 6. Automated Test Suite & Verification Matrix

The test suite in `ridesai_backend/operations/tests.py` verifies all Phase 3 capabilities:

| Test Case | Description | Status |
| :--- | :--- | :--- |
| `test_execute_get_catalog_items_tenant_isolation` | Verifies Tenant A only sees Tenant A catalog items and search filters work. | **PASSED** |
| `test_execute_create_order_atomic_success` | Verifies atomic creation of `Order`, `OrderItem`, `OrderEvent` with exact line total math. | **PASSED** |
| `test_execute_create_order_multi_tenant_isolation` | Verifies ordering an item belonging to another tenant is rejected. | **PASSED** |
| `test_execute_create_order_inventory_tracking` | Verifies stock decrement and refusal when stock is depleted. | **PASSED** |
| `test_execute_check_order_status` | Verifies querying status by phone/order number with strict tenant isolation. | **PASSED** |
| `test_unmapped_phone_number_fails_closed` | Verifies unmapped `phone_number_id` fails closed with 0 orders created. | **PASSED** |
| `test_generate_agent_reply_executes_tool_call` | Verifies end-to-end OpenAI tool-calling loop and database creation. | **PASSED** |
| *Core Operations Tests (8 tests)* | Orders view isolation, rider delivery advancing, delivery zones, order lifecycle. | **PASSED** |

**Execution Result:**
```
Ran 15 tests in 20.365s
OK
System check identified no issues (0 silenced).
```

---

## 7. Environment & Operational Configuration

The following environment variables configure the dynamic WhatsApp Agent pipeline:

```bash
# OpenAI Configuration (Tool Calling, Reasoning, TTS)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Groq Configuration (Speech-to-Text Whisper)
GROQ_API_KEY=gsk_...
GROQ_MODEL=whisper-large-v3

# Meta WhatsApp Cloud API (Per-tenant or default fallback)
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=EAAG...
WHATSAPP_VERIFY_TOKEN=ridesai_webhook_verify_token
```
