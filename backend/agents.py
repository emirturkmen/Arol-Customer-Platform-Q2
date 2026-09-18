"""The three agents and the tools each of them may use.

One agent per data domain of the dataset:
  - manuals      : machine data and the manuals (RAG)
  - diagnostics  : telemetry, alarms, maintenance, troubleshooting
  - commercial   : quotations and orders
"""

import tools

TOOL_SCHEMAS = {
    "list_machines": {
        "description": "List the machines owned by the user's company.",
        "properties": {},
        "required": [],
    },
    "get_machine_details": {
        "description": "Identity, as-built configuration and model specification of one machine.",
        "properties": {
            "machine": {"type": "string", "description": "machineId (MCH-0004) or serial number (17478)"}
        },
        "required": ["machine"],
    },
    "search_manual": {
        "description": "Search the use-and-maintenance manual of one machine and return the "
                       "most relevant pages. Use it for procedures, safety instructions, "
                       "technical data, maintenance intervals and alarm remedies.",
        "properties": {
            "machine": {"type": "string", "description": "machineId or serial number"},
            "question": {"type": "string", "description": "What to look for, in plain words"},
        },
        "required": ["machine", "question"],
    },
    "get_telemetry_summary": {
        "description": "Aggregated telemetry of one machine (uptime, production rate, "
                       "temperature, energy, hours per status) over the last N days.",
        "properties": {
            "machine": {"type": "string", "description": "machineId or serial number"},
            "days": {"type": "integer", "description": "Length of the window, default 7"},
        },
        "required": ["machine"],
    },
    "get_recent_telemetry": {
        "description": "The most recent hourly telemetry snapshots of one machine.",
        "properties": {
            "machine": {"type": "string", "description": "machineId or serial number"},
            "hours": {"type": "integer", "description": "How many hours, at most 24"},
        },
        "required": ["machine"],
    },
    "get_alarms": {
        "description": "Alarm events raised by one machine, most recent first.",
        "properties": {
            "machine": {"type": "string", "description": "machineId or serial number"},
            "days": {"type": "integer", "description": "Length of the window, default 30"},
            "severity": {"type": "string", "description": "Critical, High, Medium or Low"},
            "status": {"type": "string", "description": "Open, Acknowledged or Resolved"},
        },
        "required": ["machine"],
    },
    "get_alarm_statistics": {
        "description": "How many times each alarm code was raised on one machine. "
                       "Use it to find repeated or recurring alarms.",
        "properties": {
            "machine": {"type": "string", "description": "machineId or serial number"},
            "days": {"type": "integer", "description": "Length of the window, default 30"},
        },
        "required": ["machine"],
    },
    "get_maintenance_tickets": {
        "description": "Maintenance and service tickets of one machine, or of the whole fleet "
                       "when no machine is given.",
        "properties": {
            "machine": {"type": "string", "description": "machineId or serial number, optional"},
            "status": {"type": "string", "description": "Open, In progress, Waiting for parts, Resolved or Closed"},
        },
        "required": [],
    },
    "list_quotes": {
        "description": "Quotations issued to the user's company, with their current revision "
                       "status and the order they became, if any.",
        "properties": {},
        "required": [],
    },
    "get_quote_details": {
        "description": "Full revision history of one quotation, with the lines and total of "
                       "each revision. Use it to compare revisions.",
        "properties": {"quote_id": {"type": "string", "description": "e.g. QTE-2025-0001"}},
        "required": ["quote_id"],
    },
    "list_orders": {
        "description": "Orders placed by the user's company.",
        "properties": {},
        "required": [],
    },
    "get_order_details": {
        "description": "One order with its fulfilment lines and the items of the approved "
                       "quote revision it came from.",
        "properties": {"order_id": {"type": "string", "description": "e.g. ORD-2025-0001"}},
        "required": ["order_id"],
    },
}

AGENTS = {
    "manuals": {
        "domain": "identity",
        "handles": "which machines the company owns, machine identity and as-built "
                   "configuration (model, serial number, heads, nominal rate, voltage), and "
                   "anything written in the use and maintenance manual: operating procedures, "
                   "safety instructions, technical data, spare parts, maintenance intervals.",
        "tools": ["list_machines", "get_machine_details", "search_manual"],
        "instructions": (
            "You are the Manuals agent. Answer only from the machine manual and the machine "
            "record. Always call search_manual before answering a documentation question, and "
            "cite the manual pages you used, for example (manual page 42). If the manual does "
            "not cover the question, say so instead of guessing."
        ),
    },
    "diagnostics": {
        "domain": "operational",
        "handles": "machine health, telemetry, production rate, uptime, temperature, alarms, "
                   "maintenance tickets and troubleshooting of a problem on the machine.",
        "tools": [
            "get_machine_details", "get_telemetry_summary", "get_recent_telemetry",
            "get_alarms", "get_alarm_statistics", "get_maintenance_tickets", "search_manual",
        ],
        "instructions": (
            "You are the Diagnostics agent. Look at the data before concluding anything. "
            "Judge telemetry against the machine's own configurationProfile (nominal rate, "
            "voltage, heads), never against another machine. An alarm code has the form "
            "ALnnn_MNEMONIC: to explain it or to give a remedy, call search_manual with the "
            "mnemonic written in plain words, and cite the manual pages you used. Report "
            "concrete numbers, dates and alarm codes."
        ),
    },
    "commercial": {
        "domain": "commercial",
        "handles": "quotations, quote revisions, prices, discounts, orders, delivery and "
                   "shipment status, and how much something cost.",
        "tools": ["list_machines", "list_quotes", "get_quote_details", "list_orders", "get_order_details"],
        "instructions": (
            "You are the Commercial agent. The status of a quotation is the status of its "
            "highest revision; earlier revisions are superseded. Quote line prices are already "
            "net of the revision discount, so never apply the discount again. Order lines only "
            "track fulfilment: the content of an order comes from its approved revision. Always "
            "give amounts with the currency."
        ),
    },
}

# Name -> function, used by the agent loop. Each schema above has a function with
# the same name in tools.py, so we build the map from the schema names.
IMPLEMENTATIONS = {name: getattr(tools, name) for name in TOOL_SCHEMAS}


def tool_definitions(agent_name):
    """The tool schemas of one agent, in the format the model expects."""
    definitions = []
    for name in AGENTS[agent_name]["tools"]:
        schema = TOOL_SCHEMAS[name]
        definitions.append({
            "type": "function",
            "function": {
                "name": name,
                "description": schema["description"],
                "parameters": {
                    "type": "object",
                    "properties": schema["properties"],
                    "required": schema["required"],
                },
            },
        })
    return definitions
