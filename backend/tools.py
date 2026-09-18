"""The tools the agents can call.

Every tool gets the logged-in user and checks the access model before it reads
anything. Results are kept small, because they go back into the conversation
the model sees.
"""

import pickle
from datetime import date, timedelta

from sklearn.metrics.pairwise import cosine_similarity

import access
from config import INDEX_PATH, TODAY
from db import query, query_one

_index = None


def _load_index():
    global _index
    if _index is None:
        with open(INDEX_PATH, "rb") as f:
            _index = pickle.load(f)
    return _index


def _cutoff(days):
    """The date N days before the dataset's 'today'."""
    return (date.fromisoformat(TODAY) - timedelta(days=days)).isoformat()


# --- Machine identity and documentation (every user) ------------------------


def list_machines(user):
    """All machines owned by the user's company."""
    machines = query(
        """SELECT m.machineId, m.serialNumber, mo.modelCode, m.plantLocation,
                  m.configurationProfile, m.deliveryDate
           FROM Machines m JOIN MachineModels mo ON m.modelId = mo.modelId
           WHERE m.companyId = ? ORDER BY m.machineId""",
        (user["companyId"],),
    )
    if not machines:
        return {"machines": [], "note": "This company does not own any machine."}
    return {"machines": machines}


def get_machine_details(user, machine):
    """Identity, as-built configuration and model specification of one machine."""
    row = access.get_machine(user, machine)
    if not row:
        return access.machine_not_found(machine)
    model = query_one("SELECT * FROM MachineModels WHERE modelId = ?", (row["modelId"],))
    return {
        "machineId": row["machineId"],
        "serialNumber": row["serialNumber"],
        "deliveryDate": row["deliveryDate"],
        "plantLocation": row["plantLocation"],
        # The as-built configuration wins over the model specification.
        "configurationProfile": row["configurationProfile"],
        "plcFamily": row["plcFamily"],
        "softwareVersion": row["softwareVersion"],
        "model": model,
    }


def search_manual(user, machine, question, results=3):
    """Search the use-and-maintenance manual of one specific machine."""
    row = access.get_machine(user, machine)
    if not row:
        return access.machine_not_found(machine)

    index = _load_index()
    positions = [
        i for i, c in enumerate(index["chunks"])
        if c["serialNumber"] == row["serialNumber"]
    ]
    scores = cosine_similarity(
        index["vectorizer"].transform([question]), index["matrix"][positions]
    )[0]
    best = sorted(range(len(positions)), key=lambda i: scores[i], reverse=True)[:results]

    passages = []
    for i in best:
        if scores[i] <= 0:
            continue
        chunk = index["chunks"][positions[i]]
        passages.append({"page": chunk["page"], "text": chunk["text"][:1500]})
    if not passages:
        return {"note": "Nothing found in this manual for that question."}
    return {"serialNumber": row["serialNumber"], "passages": passages}


# --- Operational data (full / technician) -----------------------------------


def get_telemetry_summary(user, machine, days=7):
    """Aggregated telemetry of one machine over the last N days."""
    if not access.can_access(user, "operational"):
        return access.denied("operational")
    row = access.get_machine(user, machine)
    if not row:
        return access.machine_not_found(machine)

    stats = query_one(
        """SELECT COUNT(*) AS hours, ROUND(AVG(uptimePercentage),1) AS avgUptimePercentage,
                  ROUND(AVG(temperatureC),1) AS avgTemperatureC, MAX(temperatureC) AS maxTemperatureC,
                  ROUND(SUM(energyKwh),1) AS totalEnergyKwh, SUM(alarmCount) AS alarms
           FROM TelemetrySnapshots WHERE machineId = ? AND timestamp >= ?""",
        (row["machineId"], _cutoff(days)),
    )
    running = query_one(
        """SELECT ROUND(AVG(productionRateBph)) AS avgProductionRateBph,
                  MAX(productionRateBph) AS maxProductionRateBph
           FROM TelemetrySnapshots WHERE machineId = ? AND timestamp >= ? AND productionRateBph > 0""",
        (row["machineId"], _cutoff(days)),
    )
    statuses = query(
        """SELECT operationalStatus, COUNT(*) AS hours FROM TelemetrySnapshots
           WHERE machineId = ? AND timestamp >= ? GROUP BY operationalStatus ORDER BY hours DESC""",
        (row["machineId"], _cutoff(days)),
    )
    return {
        "machineId": row["machineId"],
        "serialNumber": row["serialNumber"],
        "periodDays": days,
        "nominalConfiguration": row["configurationProfile"],
        "averages": {**stats, **running},
        "hoursPerStatus": statuses,
    }


def get_recent_telemetry(user, machine, hours=12):
    """The most recent hourly telemetry snapshots of one machine."""
    if not access.can_access(user, "operational"):
        return access.denied("operational")
    row = access.get_machine(user, machine)
    if not row:
        return access.machine_not_found(machine)

    snapshots = query(
        """SELECT timestamp, operationalStatus, productionRateBph, uptimePercentage,
                  alarmCount, temperatureC, healthNote
           FROM TelemetrySnapshots WHERE machineId = ?
           ORDER BY timestamp DESC LIMIT ?""",
        (row["machineId"], min(hours, 24)),
    )
    return {"machineId": row["machineId"], "snapshots": snapshots}


def get_alarms(user, machine, days=30, severity=None, status=None):
    """Alarm events raised by one machine, most recent first."""
    if not access.can_access(user, "operational"):
        return access.denied("operational")
    row = access.get_machine(user, machine)
    if not row:
        return access.machine_not_found(machine)

    sql = """SELECT alarmId, timestamp, alarmCode, severity, alarmStatus FROM Alarms
             WHERE machineId = ? AND timestamp >= ?"""
    params = [row["machineId"], _cutoff(days)]
    if severity:
        sql += " AND severity = ?"
        params.append(severity)
    if status:
        sql += " AND alarmStatus = ?"
        params.append(status)
    sql += " ORDER BY timestamp DESC LIMIT 25"
    return {"machineId": row["machineId"], "alarms": query(sql, params)}


def get_alarm_statistics(user, machine, days=30):
    """How many times each alarm code was raised: useful for repeated alarms."""
    if not access.can_access(user, "operational"):
        return access.denied("operational")
    row = access.get_machine(user, machine)
    if not row:
        return access.machine_not_found(machine)

    counts = query(
        """SELECT alarmCode, severity, COUNT(*) AS occurrences,
                  SUM(CASE WHEN alarmStatus != 'Resolved' THEN 1 ELSE 0 END) AS stillOpen,
                  MAX(timestamp) AS lastSeen
           FROM Alarms WHERE machineId = ? AND timestamp >= ?
           GROUP BY alarmCode, severity ORDER BY occurrences DESC LIMIT 15""",
        (row["machineId"], _cutoff(days)),
    )
    return {"machineId": row["machineId"], "periodDays": days, "alarmCodes": counts}


def get_maintenance_tickets(user, machine=None, status=None):
    """Maintenance and service tickets, for one machine or for the whole fleet."""
    if not access.can_access(user, "operational"):
        return access.denied("operational")

    sql = """SELECT t.ticketId, t.machineId, t.alarmId, a.alarmCode, t.ticketType,
                    t.ticketStatus, t.priority, t.createdDate, t.ownerRole
             FROM MaintenanceTickets t
             JOIN Machines m ON t.machineId = m.machineId
             LEFT JOIN Alarms a ON t.alarmId = a.alarmId
             WHERE m.companyId = ?"""
    params = [user["companyId"]]
    if machine:
        row = access.get_machine(user, machine)
        if not row:
            return access.machine_not_found(machine)
        sql += " AND t.machineId = ?"
        params.append(row["machineId"])
    if status:
        sql += " AND t.ticketStatus = ?"
        params.append(status)
    sql += " ORDER BY t.createdDate DESC LIMIT 25"
    return {"tickets": query(sql, params)}


# --- Commercial data (full / commercial) ------------------------------------


def list_quotes(user):
    """Quotations issued to the user's company, with their current revision."""
    if not access.can_access(user, "commercial"):
        return access.denied("commercial")

    quotes = query(
        """SELECT quoteId, createdAt, validUntil, currency, description
           FROM Quotes WHERE companyId = ? ORDER BY createdAt DESC""",
        (user["companyId"],),
    )
    for quote in quotes:
        # Status comes from the revision with the highest number.
        current = query_one(
            """SELECT revisionNumber, revisionStatus FROM QuoteRevisions
               WHERE quoteId = ? ORDER BY revisionNumber DESC LIMIT 1""",
            (quote["quoteId"],),
        )
        quote["currentRevision"] = current
        order = query_one("SELECT orderId FROM Orders WHERE quoteId = ?", (quote["quoteId"],))
        quote["orderId"] = order["orderId"] if order else None
    return {"quotes": quotes}


def get_quote_details(user, quote_id):
    """Full revision history of one quotation, with the lines of each revision."""
    if not access.can_access(user, "commercial"):
        return access.denied("commercial")

    quote = query_one(
        "SELECT * FROM Quotes WHERE quoteId = ? AND companyId = ?",
        (quote_id.strip(), user["companyId"]),
    )
    if not quote:
        return {"error": f"No quotation '{quote_id}' belongs to this user's company."}

    revisions = query(
        "SELECT * FROM QuoteRevisions WHERE quoteId = ? ORDER BY revisionNumber",
        (quote["quoteId"],),
    )
    for revision in revisions:
        # Line prices are already net of the revision discount.
        lines = query(
            """SELECT quoteLineId, machineId, price, description FROM QuoteLines
               WHERE quoteRevisionId = ?""",
            (revision["quoteRevisionId"],),
        )
        revision["lines"] = lines
        revision["total"] = round(sum(l["price"] for l in lines), 2)
    return {"quote": quote, "revisions": revisions}


def list_orders(user):
    """Orders placed by the user's company."""
    if not access.can_access(user, "commercial"):
        return access.denied("commercial")
    return {
        "orders": query(
            """SELECT orderId, quoteId, orderStatus, orderDate, expectedDeliveryDate,
                      shipmentStatus, currency, notes
               FROM Orders WHERE companyId = ? ORDER BY orderDate DESC""",
            (user["companyId"],),
        )
    }


def get_order_details(user, order_id):
    """One order with its fulfilment lines and the content of the approved revision."""
    if not access.can_access(user, "commercial"):
        return access.denied("commercial")

    order = query_one(
        "SELECT * FROM Orders WHERE orderId = ? AND companyId = ?",
        (order_id.strip(), user["companyId"]),
    )
    if not order:
        return {"error": f"No order '{order_id}' belongs to this user's company."}

    # OrderLines only track fulfilment: the content comes from the approved revision.
    approved = query_one(
        """SELECT * FROM QuoteRevisions WHERE quoteId = ? AND revisionStatus = 'Approved'
           ORDER BY revisionNumber DESC LIMIT 1""",
        (order["quoteId"],),
    )
    content = []
    if approved:
        content = query(
            "SELECT machineId, price, description FROM QuoteLines WHERE quoteRevisionId = ?",
            (approved["quoteRevisionId"],),
        )
    return {
        "order": order,
        "fulfillment": query(
            "SELECT orderLineId, fulfillmentStatus FROM OrderLines WHERE orderId = ?",
            (order["orderId"],),
        ),
        "approvedRevision": approved["quoteRevisionId"] if approved else None,
        "orderedItems": content,
        "total": round(sum(l["price"] for l in content), 2) if content else None,
    }
